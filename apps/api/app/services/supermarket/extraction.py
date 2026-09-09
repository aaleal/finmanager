"""Extraction — turning bytes into positioned words.

**Parse positions, not flat text.** The merchant differences are *positional*:
Continente puts the IVA token first, Lidl puts it last, Piquete puts quantity
first. A parser built on string-splitting ``pdftotext -layout`` output breaks the
moment the extractor's spacing changes, so every parser here works from word
boxes clustered into lines by their ``top`` coordinate.

Both stages sit behind a Protocol with a **local implementation that works
offline and unsubscribed** (Decision #13). A remote engine may be registered
alongside and selected per stage from ``Setting``; without a credential the stage
silently stays local rather than failing.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_LINE_TOLERANCE = 3.0


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    confidence: float | None = None


@dataclass(slots=True)
class Line:
    """Words sharing a baseline, left to right."""

    top: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @property
    def x0(self) -> float:
        return min((w.x0 for w in self.words), default=0.0)

    @property
    def x1(self) -> float:
        return max((w.x1 for w in self.words), default=0.0)

    def right_of(self, x: float) -> list[Word]:
        return [w for w in self.words if w.x0 >= x]

    def as_golden(self) -> dict[str, Any]:
        return {
            "top": round(self.top, 2),
            "words": [
                {"text": w.text, "x0": round(w.x0, 2), "x1": round(w.x1, 2)} for w in self.words
            ],
        }


@dataclass(slots=True)
class Page:
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)


@dataclass(slots=True)
class Extraction:
    """What every parser consumes, regardless of how the bytes arrived."""

    document_kind: str  # PDF_DIGITAL | IMAGE_SCAN
    engine: str
    pages: list[Page] = field(default_factory=list)
    #: 0-1 estimate of how much of the text can be trusted, fed to the confidence
    #: engine as the ``ocr_text`` signal.
    text_confidence: Decimal = Decimal("1.000")
    #: Raw provider payload, stored on the receipt and never selected in lists.
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def lines(self) -> list[Line]:
        return [line for page in self.pages for line in page.lines]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


def cluster_words(words: list[Word], tolerance: float = _LINE_TOLERANCE) -> list[Line]:
    """Group words into lines by vertical proximity, then sort each left to right."""
    lines: list[Line] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        for line in reversed(lines):
            if abs(line.top - word.top) <= tolerance:
                line.words.append(word)
                break
        else:
            lines.append(Line(top=word.top, words=[word]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


# --- Provider seams ----------------------------------------------------------


class ExtractionProvider(Protocol):
    """Digital PDFs."""

    name: str

    def extract(self, data: bytes) -> Extraction: ...


class OcrProvider(Protocol):
    """Photographs and scans."""

    name: str

    def extract(self, data: bytes) -> Extraction: ...


class PdfplumberExtraction:
    """Local engine for digital PDFs. Ships enabled, needs no network."""

    name = "pdfplumber"

    def extract(self, data: bytes) -> Extraction:
        import pdfplumber

        pages: list[Page] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                words = [
                    Word(
                        text=str(w["text"]),
                        x0=float(w["x0"]),
                        x1=float(w["x1"]),
                        top=float(w["top"]),
                        bottom=float(w["bottom"]),
                    )
                    for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)
                ]
                pages.append(
                    Page(
                        width=float(page.width),
                        height=float(page.height),
                        lines=cluster_words(words),
                    )
                )

        extraction = Extraction(document_kind="PDF_DIGITAL", engine=self.name, pages=pages)
        # A digital PDF carries real glyphs, so the only text risk is an empty page.
        extraction.text_confidence = Decimal("0.980") if extraction.lines else Decimal("0.000")
        return extraction


class TesseractOcr:
    """Local engine for photographs. Ships enabled, needs no network.

    Thermal *talões* are curved, skewed and often partly obscured, so this is a
    genuinely harder problem than a digital PDF and is reported separately: the
    per-word confidences tesseract returns become the ``ocr_text`` signal, and a
    poor photograph correctly lands in review instead of pretending.
    """

    name = "pytesseract"

    def extract(self, data: bytes) -> Extraction:
        import pytesseract
        from PIL import Image, ImageOps

        image = Image.open(io.BytesIO(data))
        prepared = ImageOps.autocontrast(ImageOps.grayscale(image))
        if prepared.width < 1400:  # thermal receipts photograph small; upscale before OCR
            scale = 1400 / prepared.width
            prepared = prepared.resize(
                (int(prepared.width * scale), int(prepared.height * scale)),
                Image.Resampling.LANCZOS,
            )

        data_dict = pytesseract.image_to_data(
            prepared,
            lang="por",
            config="--oem 1 --psm 6",
            output_type=pytesseract.Output.DICT,
        )

        words: list[Word] = []
        confidences: list[float] = []
        grouped: dict[tuple[int, int, int, int], list[Word]] = {}
        for index, text in enumerate(data_dict["text"]):
            token = str(text).strip()
            if not token:
                continue
            conf = float(data_dict["conf"][index])
            if conf >= 0:
                confidences.append(conf)
            word = Word(
                text=token,
                x0=float(data_dict["left"][index]),
                x1=float(data_dict["left"][index]) + float(data_dict["width"][index]),
                top=float(data_dict["top"][index]),
                bottom=float(data_dict["top"][index]) + float(data_dict["height"][index]),
                confidence=conf,
            )
            words.append(word)
            # Tesseract's own line grouping, not a `top` tolerance: a photographed
            # receipt is skewed, so the value at the right edge sits lower than
            # the description at the left and geometric clustering tears them apart.
            key = (
                int(data_dict["page_num"][index]),
                int(data_dict["block_num"][index]),
                int(data_dict["par_num"][index]),
                int(data_dict["line_num"][index]),
            )
            grouped.setdefault(key, []).append(word)

        lines = [
            Line(top=min(w.top for w in members), words=sorted(members, key=lambda w: w.x0))
            for members in grouped.values()
        ]
        lines.sort(key=lambda line: line.top)

        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        page = Page(width=float(prepared.width), height=float(prepared.height), lines=lines)
        return Extraction(
            document_kind="IMAGE_SCAN",
            engine=self.name,
            pages=[page],
            text_confidence=Decimal(str(round(mean_conf / 100, 3))),
            raw_payload={"mean_word_confidence": round(mean_conf, 2), "word_count": len(words)},
        )


class PdfPageOcr:
    """A PDF whose pages carry no text layer — render, then OCR."""

    name = "pdfplumber+pytesseract"

    def extract(self, data: bytes) -> Extraction:
        import pdfplumber

        ocr = TesseractOcr()
        pages: list[Page] = []
        confidences: list[Decimal] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                buffer = io.BytesIO()
                page.to_image(resolution=200).original.save(buffer, format="PNG")
                rendered = ocr.extract(buffer.getvalue())
                pages.extend(rendered.pages)
                confidences.append(rendered.text_confidence)

        mean = (
            sum(confidences, Decimal(0)) / Decimal(len(confidences)) if confidences else Decimal(0)
        )
        return Extraction(
            document_kind="IMAGE_SCAN",
            engine=self.name,
            pages=pages,
            text_confidence=mean.quantize(Decimal("0.001")),
        )


def extract(data: bytes, mime_type: str) -> Extraction:
    """Route bytes to the right local engine, falling back to OCR when needed."""
    if mime_type == "application/pdf":
        extraction = PdfplumberExtraction().extract(data)
        if extraction.lines:
            return extraction
        logger.info("PDF has no text layer; falling back to page OCR")
        return PdfPageOcr().extract(data)
    return TesseractOcr().extract(data)
