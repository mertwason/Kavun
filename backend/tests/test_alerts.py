"""KVN-EK-06: uyarı listesi, filtreler ve acknowledge akışı (spec §10.6).

Kabul: uyarılar seviyeye/türe/duruma göre filtrelenebilir, "gördüm" işareti
`acknowledged_at` yazar, işaret geri alınamaz ve kapatılan uyarı SİLİNMEZ.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.main import create_app
from app.models.enums import AlertSeverity, UserRole
from app.models.identity import Brand, Store
from app.models.results import Alert
from app.services import alerts as service
from tests.profit_factories import make_store


@pytest.fixture
def store(db_session: Session) -> Iterator[Store]:
    """Mağaza + marka bağlamı."""
    with system_scope():
        record = make_store(db_session)
        brand = db_session.get(Brand, record.brand_id)
    assert brand is not None
    context = RequestContext(
        tenant_id=brand.tenant_id,
        user_id=None,
        brand_id=brand.id,
        brand_slug=brand.slug,
        role=UserRole.ADMIN,
    )
    with use_context(context):
        yield record


def _alert(
    db_session: Session,
    store: Store,
    *,
    severity: AlertSeverity = AlertSeverity.WARNING,
    alert_type: str = "negatif_stok",
    acknowledged: bool = False,
    age_hours: int = 1,
) -> Alert:
    alert = Alert(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        type=alert_type,
        severity=severity,
        message=f"{alert_type} uyarısı",
        created_at=datetime.now(UTC) - timedelta(hours=age_hours),
        acknowledged_at=datetime.now(UTC) if acknowledged else None,
    )
    db_session.add(alert)
    db_session.flush()
    return alert


# --- listeleme ve filtreler --------------------------------------------------


def test_alerts_are_returned_newest_first(db_session: Session, store: Store) -> None:
    """En yeni uyarı üstte olmalı."""
    _alert(db_session, store, alert_type="eski", age_hours=48)
    _alert(db_session, store, alert_type="yeni", age_hours=1)

    rows = service.alerts(db_session)

    assert [row.type for row in rows] == ["yeni", "eski"]


def test_severity_filter(db_session: Session, store: Store) -> None:
    """Seviye filtresi yalnızca o seviyeyi getirir."""
    _alert(db_session, store, severity=AlertSeverity.CRITICAL, alert_type="kritik")
    _alert(db_session, store, severity=AlertSeverity.INFO, alert_type="bilgi")

    rows = service.alerts(db_session, severity=AlertSeverity.CRITICAL)

    assert [row.type for row in rows] == ["kritik"]


def test_type_filter(db_session: Session, store: Store) -> None:
    """Tür filtresi çalışır."""
    _alert(db_session, store, alert_type="msrp_ihlali")
    _alert(db_session, store, alert_type="negatif_stok")

    rows = service.alerts(db_session, alert_type="msrp_ihlali")

    assert [row.type for row in rows] == ["msrp_ihlali"]


def test_open_and_acknowledged_filters(db_session: Session, store: Store) -> None:
    """Açık ve kapatılmış uyarılar ayrı ayrı listelenebilir."""
    _alert(db_session, store, alert_type="acik")
    _alert(db_session, store, alert_type="kapali", acknowledged=True)

    assert [row.type for row in service.alerts(db_session, acknowledged=False)] == ["acik"]
    assert [row.type for row in service.alerts(db_session, acknowledged=True)] == ["kapali"]
    assert len(service.alerts(db_session)) == 2


def test_counts_group_by_severity(db_session: Session, store: Store) -> None:
    """Özet seviye bazlı açık sayıları verir; kapatılmışlar ayrı sayılır."""
    _alert(db_session, store, severity=AlertSeverity.CRITICAL)
    _alert(db_session, store, severity=AlertSeverity.WARNING)
    _alert(db_session, store, severity=AlertSeverity.WARNING)
    _alert(db_session, store, severity=AlertSeverity.INFO, acknowledged=True)

    counts = service.counts(db_session)

    assert counts.critical_open == 1
    assert counts.warning_open == 2
    assert counts.info_open == 0
    assert counts.open == 3
    assert counts.acknowledged == 1
    assert counts.total == 4


def test_types_are_distinct_and_sorted(db_session: Session, store: Store) -> None:
    """Filtre listesi tekil ve sıralı gelir."""
    _alert(db_session, store, alert_type="msrp_ihlali")
    _alert(db_session, store, alert_type="negatif_stok")
    _alert(db_session, store, alert_type="negatif_stok")

    assert service.types(db_session) == ["msrp_ihlali", "negatif_stok"]


# --- acknowledge -------------------------------------------------------------


def test_acknowledge_writes_the_timestamp(db_session: Session, store: Store) -> None:
    """ "Gördüm" işareti `acknowledged_at` yazar (spec §10.6)."""
    alert = _alert(db_session, store)

    service.acknowledge(db_session, alert.id)

    assert alert.acknowledged_at is not None


def test_acknowledge_is_idempotent(db_session: Session, store: Store) -> None:
    """İkinci çağrı ilk damgayı bozmaz — "görüldü" zamanı geriye alınmaz."""
    alert = _alert(db_session, store)
    first = service.acknowledge(db_session, alert.id).acknowledged_at

    second = service.acknowledge(db_session, alert.id).acknowledged_at

    assert first == second


def test_acknowledged_alert_is_kept_not_deleted(db_session: Session, store: Store) -> None:
    """Kapatılan uyarı silinmez; filtreyle geri görülebilir."""
    alert = _alert(db_session, store)

    service.acknowledge(db_session, alert.id)

    assert db_session.get(Alert, alert.id) is not None
    assert [row.id for row in service.alerts(db_session, acknowledged=True)] == [alert.id]


def test_unknown_alert_raises(db_session: Session, store: Store) -> None:
    """Olmayan uyarı sessizce başarı dönmez."""
    with pytest.raises(service.AlertNotFoundError):
        service.acknowledge(db_session, uuid.uuid4())


# --- API ---------------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Store) -> Iterator[TestClient]:
    """Test oturumuna bağlı API istemcisi."""

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _headers(api: TestClient, brand: str = "alessi") -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": "mert@mokkalabs.com", "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_lists_and_filters(api: TestClient, db_session: Session, store: Store) -> None:
    """Uç filtreleri destekler."""
    _alert(db_session, store, severity=AlertSeverity.CRITICAL, alert_type="msrp_ihlali")
    _alert(db_session, store, severity=AlertSeverity.INFO, alert_type="negatif_stok")
    headers = _headers(api, store.brand.slug if hasattr(store, "brand") else "alessi")

    everything = api.get("/alessi/alerts", headers=headers)
    critical = api.get("/alessi/alerts?severity=critical", headers=headers)

    assert everything.status_code == 200, everything.text
    assert len(everything.json()) == 2
    assert [row["type"] for row in critical.json()] == ["msrp_ihlali"]


def test_api_summary_reports_counts(api: TestClient, db_session: Session, store: Store) -> None:
    """Özet ucu KPI şeridini besler."""
    _alert(db_session, store, severity=AlertSeverity.CRITICAL)
    _alert(db_session, store, severity=AlertSeverity.INFO, acknowledged=True)

    body = api.get("/alessi/alerts/summary", headers=_headers(api)).json()

    assert body["critical_open"] == 1
    assert body["acknowledged"] == 1
    assert body["total"] == 2
    assert "negatif_stok" in body["types"]


def test_api_acknowledge_marks_alert(api: TestClient, db_session: Session, store: Store) -> None:
    """Uç `acknowledged_at` yazar ve güncel kaydı döner."""
    alert = _alert(db_session, store)

    response = api.post(f"/alessi/alerts/{alert.id}/acknowledge", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json()["acknowledged_at"] is not None


def test_api_unknown_alert_is_404(api: TestClient) -> None:
    """Olmayan uyarı 404 döner."""
    response = api.post(f"/alessi/alerts/{uuid.uuid4()}/acknowledge", headers=_headers(api))

    assert response.status_code == 404


def test_alert_of_another_brand_is_invisible(
    api: TestClient, db_session: Session, store: Store
) -> None:
    """Başka markanın uyarısı listede görünmez (CLAUDE.md §2)."""
    _alert(db_session, store, alert_type="alessi_uyarisi")

    other = api.get("/kahveji/alerts", headers=_headers(api, "kahveji"))

    assert other.status_code == 200
    assert other.json() == []


def test_acknowledging_another_brands_alert_is_404(
    api: TestClient, db_session: Session, store: Store
) -> None:
    """Karşı markanın uyarısı kapatılamaz — varlığı da sızdırılmaz."""
    alert = _alert(db_session, store)

    response = api.post(f"/kahveji/alerts/{alert.id}/acknowledge", headers=_headers(api, "kahveji"))

    assert response.status_code == 404
    untouched = db_session.scalar(select(Alert).where(Alert.id == alert.id))
    assert untouched is not None
    assert untouched.acknowledged_at is None
