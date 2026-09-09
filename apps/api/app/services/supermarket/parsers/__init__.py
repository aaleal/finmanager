"""The parser registry.

``MerchantParserProfile.parser_key`` names one of these classes. Detection runs
**before** extraction-to-fields: identify the merchant from the document, choose
the highest-priority matching active profile, then parse with it. A document that
matches no profile falls through to ``generic_v1`` — never to an error.
"""

from __future__ import annotations

from app.services.supermarket.parsers.base import ParsedItem, ParsedReceipt, ReceiptParser
from app.services.supermarket.parsers.continente import ContinenteParser
from app.services.supermarket.parsers.generic import GenericParser
from app.services.supermarket.parsers.lidl import LidlParser
from app.services.supermarket.parsers.pingodoce import PingoDoceParser
from app.services.supermarket.parsers.piquete import PiqueteParser

GENERIC_PARSER_KEY = GenericParser.key

_REGISTRY: dict[str, type[ReceiptParser]] = {
    ContinenteParser.key: ContinenteParser,
    PingoDoceParser.key: PingoDoceParser,
    LidlParser.key: LidlParser,
    PiqueteParser.key: PiqueteParser,
    GenericParser.key: GenericParser,
}


def available() -> list[dict[str, str]]:
    return [{"parser_key": key, "display_name": cls.display_name} for key, cls in _REGISTRY.items()]


def get(parser_key: str) -> ReceiptParser:
    """Resolve a parser, falling back to the generic one for an unknown key."""
    return _REGISTRY.get(parser_key, GenericParser)()


__all__ = [
    "GENERIC_PARSER_KEY",
    "ContinenteParser",
    "GenericParser",
    "LidlParser",
    "ParsedItem",
    "ParsedReceipt",
    "PingoDoceParser",
    "PiqueteParser",
    "ReceiptParser",
    "available",
    "get",
]
