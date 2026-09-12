"""Protects: the Module 1 HTTP surface itself.

Every other M1 test drives the services directly, which is where the domain rules
live — but it also means a router that serialises a response wrongly passes them
all. This walks the whole surface through the real app: authenticated, CSRF-
checked, and asserting a usable status code on each route.
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from app.seed import INVOICES_DIR
from app.services.reference_data import ensure_all
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

FIXTURES = INVOICES_DIR

SETUP = {
    "household_name": "Casa de Teste",
    "display_name": "Ana",
    "email": "ana@exemplo.pt",
    "password": "finmanager-demo-1",
}


@pytest.fixture
def client(api_client: TestClient, db: Session) -> TestClient:
    # `/api/setup` is rate-limited per client IP and every test here calls it, so
    # the shared Redis counter has to be cleared or the suite throttles itself.
    from app.core.redis_client import get_redis

    with contextlib.suppress(Exception):
        redis = get_redis()
        for key in redis.scan_iter("ratelimit:*"):  # type: ignore[union-attr]
            redis.delete(key)

    response = api_client.post("/api/setup", json=SETUP)
    assert response.status_code == 201
    api_client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    ensure_all(db)
    return api_client


@pytest.fixture
def entity_id(client: TestClient) -> str:
    return str(client.get("/api/entities").json()[0]["id"])


@pytest.fixture
def receipt_id(client: TestClient, entity_id: str) -> str:
    with (FIXTURES / "continente-20260724.pdf").open("rb") as handle:
        response = client.post(
            "/api/supermarket",
            params={"entity_id": entity_id},
            headers={"Idempotency-Key": uuid.uuid4().hex},
            files=[("files", ("continente-20260724.pdf", handle, "application/pdf"))],
        )
    assert response.status_code == 201
    return str(response.json()["items"][0]["receipt_id"])


def test_upload_parses_and_serialises_a_full_receipt(client: TestClient, receipt_id: str) -> None:
    body = client.get(f"/api/supermarket/{receipt_id}").json()
    assert body["total_eur"] == "36.56"
    assert len(body["items"]) == 15
    assert body["derived"]["is_reconciled"] is True
    # An `<iframe>` cannot send a CSRF header, so the signature *is* the authorisation.
    assert body["document_url"] and "signature=" in body["document_url"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/supermarket",
        "/api/supermarket/queue",
        "/api/supermarket/status",
        "/api/supermarket-items",
        "/api/supermarket-items/summary",
        "/api/parser-profiles",
        "/api/parser-profiles/parsers",
        "/api/master-products",
        "/api/master-products/merge-candidates",
        "/api/categories/tree",
        "/api/categories/search?q=fruta",
        "/api/categories/export.xlsx",
        "/api/supermarket/analytics/shrinkflation",
        "/api/supermarket/analytics/category-spend",
        "/api/supermarket/analytics/loyalty",
        "/api/supermarket/analytics/loyalty/receipts",
    ],
)
def test_every_read_endpoint_answers(client: TestClient, receipt_id: str, path: str) -> None:
    assert client.get(path).status_code == 200


def test_the_price_history_endpoint_serialises_its_slotted_dataclasses(
    client: TestClient, receipt_id: str
) -> None:
    """`PricePoint` and `ShrinkflationSignal` use `slots=True` and have no `__dict__`."""
    client.post(f"/api/supermarket/{receipt_id}/confirm")
    product_id = client.post(
        "/api/master-products", json={"canonical_name": "Produto de Teste"}
    ).json()["id"]

    body = client.get(f"/api/master-products/{product_id}/price-history").json()
    assert body["canonical_name"] == "Produto de Teste"
    assert body["points"] == []
    assert body["shrinkflation"] == []

    csv_response = client.get(f"/api/master-products/{product_id}/price-history.csv")
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")


def test_the_ledger_link_endpoint_explains_itself(client: TestClient, receipt_id: str) -> None:
    body = client.get(f"/api/supermarket/{receipt_id}/link").json()
    assert body["ledger_available"] is False
    assert body["message"]
    assert body["link_id"] is None


def test_a_line_can_be_reassigned_to_another_product(client: TestClient, receipt_id: str) -> None:
    """The correction the whole review flow hangs on: it once had no route at all."""
    item_id = client.get(f"/api/supermarket/{receipt_id}").json()["items"][0]["id"]
    product_id = client.post(
        "/api/master-products", json={"canonical_name": "Polpa de Tomate", "brand": "Guloso"}
    ).json()["id"]

    response = client.patch(
        f"/api/supermarket-items/{item_id}/product", json={"master_product_id": product_id}
    )
    assert response.status_code == 200
    assert response.json()["master_product_id"] == product_id
    assert response.json()["display_name"] == "Polpa de Tomate"


def test_a_pack_format_is_added_idempotently_through_the_api(client: TestClient) -> None:
    """Appending a format never has to send the ones already there."""
    product_id = client.post(
        "/api/master-products", json={"canonical_name": "Arroz Carolino"}
    ).json()["id"]
    path = f"/api/master-products/{product_id}/pack-variants"

    assert client.post(path, json={"weight_kg": "0.5"}).status_code == 200
    body = client.post(path, json={"weight_kg": "0.5"}).json()

    assert body["pack_variants"] == [
        {"label": "500 g", "weight_kg": "0.500", "barcode": None},
    ]


def test_an_fs_article_can_be_appended_through_the_api(client: TestClient, receipt_id: str) -> None:
    before = client.get(f"/api/supermarket/{receipt_id}").json()
    response = client.post(
        f"/api/supermarket/{receipt_id}/items",
        json={"description_raw": "Bolo oferecido", "unit_price_pvp_eur": "7.50"},
    )
    assert response.status_code == 201
    after = response.json()

    assert after["total_eur"] == before["total_eur"]
    assert after["derived"]["computed_total_eur"] == before["derived"]["computed_total_eur"]
    assert after["derived"]["printed_item_count"] == before["derived"]["printed_item_count"]
    assert after["derived"]["fs_value_eur"] == "7.50"


def test_an_fs_article_without_a_value_is_refused_by_the_contract(
    client: TestClient, receipt_id: str
) -> None:
    response = client.post(
        f"/api/supermarket/{receipt_id}/items",
        json={"description_raw": "Sem valor", "unit_price_pvp_eur": "0.00"},
    )
    assert response.status_code == 422


def test_voiding_requires_a_reason(client: TestClient, receipt_id: str) -> None:
    assert (
        client.post(f"/api/supermarket/{receipt_id}/void", json={"reason": ""}).status_code == 422
    )
    ok = client.post(f"/api/supermarket/{receipt_id}/void", json={"reason": "devolvido"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "VOID"


def test_the_generic_parser_profile_cannot_be_deleted(client: TestClient) -> None:
    profiles = client.get("/api/parser-profiles").json()
    generic = next(profile for profile in profiles if profile["is_generic"])
    assert client.delete(f"/api/parser-profiles/{generic['id']}").status_code == 409


def test_a_category_in_use_cannot_be_retired_and_reports_the_count(
    client: TestClient,
) -> None:
    category = client.post("/api/categories", json={"display_name_pt": "Testes"}).json()
    client.post(
        "/api/master-products",
        json={"canonical_name": "Produto Categorizado", "category_id": category["id"]},
    )
    impact = client.get(f"/api/categories/{category['id']}/impact").json()
    assert impact["in_use"] is True
    assert impact["master_products"] == 1
    assert client.delete(f"/api/categories/{category['id']}").status_code == 409
