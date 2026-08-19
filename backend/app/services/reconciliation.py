"""Hakediş mutabakatı servisi — eşleştirme ve fark üretimi (spec §7).

Akış (spec §7.1-7.5):

1. `settlement_records` çekilir, `order_line_id` eşleştirmesi `external_ref` üzerinden
   yapılır.
2. Her kalem türü için **beklenen** değer bizim hesabımızdan çıkarılır.
3. `|beklenen − gerçek| > eşik` → `reconciliation_diffs` kaydı + uyarı.
4. Dönem bazlı ekran: eşleşen %, açık farklar, "explained" işaretleme.
5. Eşleşmeyen kalemler (siparişi bulunamayan) ayrı kuyrukta.

## Eşleştirme anahtarı

Hakediş kaleminin `external_ref` alanı platformun referansıdır. Kavun'da bu referans
sipariş satırının `external_line_id`'si ya da siparişin `external_order_id`'si olabilir;
ikisi de denenir. Bulunamazsa kalem **eşleşmedi** kuyruğuna düşer — yanlış satıra
yazılan bir komisyon farkı, gerçek farkı gizlerdi.

## Idempotency

Aynı kalem için ikinci kez fark kaydı açılmaz (`settlement_record_id` tekil kontrol
edilir). Kullanıcının `explained`/`resolved` yaptığı kayıt yeniden `open`a düşmez —
insan kararı makine tarafından geri alınmaz.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import textfmt
from app.core.logging import get_logger
from app.models.enums import AlertSeverity, CostState, DiffStatus, SettlementRecordType
from app.models.identity import Store
from app.models.results import Alert, LineProfit, ReconciliationDiff
from app.models.transactions import Order, OrderLine, Return, Shipment
from app.reconciliation.engine import (
    DEFAULT_TOLERANCE,
    Expectation,
    compare,
    is_explainable_without_order,
)

log = get_logger("services.reconciliation")

ZERO = Decimal("0")
DIFF_ALERT = "hakedis_farki"


class ReconciliationError(RuntimeError):
    """Mutabakat akışının reddettiği durum."""


@dataclass
class RunSummary:
    """Bir mutabakat turunun özeti."""

    period: str
    records: int = 0
    matched: int = 0
    unmatched: int = 0
    within_tolerance: int = 0
    diffs: int = 0
    skipped: int = 0
    """Zaten fark kaydı açılmış kalemler."""

    total_diff: Decimal = ZERO
    unmatched_refs: list[str] = field(default_factory=list)

    @property
    def match_rate_pct(self) -> Decimal:
        """Eşleşme oranı — ekranın ana metriği (spec §7.4).

        Daha önceki turda işlenmiş kalemler (`skipped`) de eşleşmiş sayılır: onlar zaten
        eşleştirildiği için atlanıyor. Aksi halde aynı dönemi ikinci kez koşmak oranı
        düşürür ve ekran "mutabakat bozuluyor" gibi görünürdü.
        """
        if not self.records:
            return ZERO
        resolved = self.matched + self.skipped
        return (Decimal(resolved) / Decimal(self.records) * Decimal("100")).quantize(
            Decimal("0.01")
        )

    def as_dict(self) -> dict[str, Any]:
        """Log/JSON gösterimi."""
        return {
            "period": self.period,
            "records": self.records,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "within_tolerance": self.within_tolerance,
            "diffs": self.diffs,
            "skipped": self.skipped,
            "total_diff": str(self.total_diff),
            "match_rate_pct": str(self.match_rate_pct),
        }


def _line_for(session: Session, external_ref: str, store: Store) -> OrderLine | None:
    """Hakediş referansından sipariş satırını bulur.

    Önce satır referansı, sonra sipariş referansı denenir. `session.get()` kullanılmaz —
    birincil anahtar araması guard'a uğramaz (KVN-09'da bulunan sızıntı).
    """
    line = session.scalar(select(OrderLine).where(OrderLine.external_line_id == external_ref))
    if line is not None:
        return line

    order = session.scalar(
        select(Order).where(Order.store_id == store.id, Order.external_order_id == external_ref)
    )
    if order is None:
        return None
    # Sipariş referansı geldiyse tek satırlı siparişte satır kesindir; çok satırlıda
    # hangi satıra ait olduğu belirsizdir — belirsizi eşleştirmeyiz.
    lines = list(session.scalars(select(OrderLine).where(OrderLine.order_id == order.id)).all())
    return lines[0] if len(lines) == 1 else None


def expectation_for(
    session: Session, line: OrderLine, record_type: SettlementRecordType, store: Store
) -> Expectation | None:
    """Kalem türü için bizim beklediğimiz tutar (spec §7.2)."""
    profit = session.scalar(select(LineProfit).where(LineProfit.order_line_id == line.id))

    if record_type is SettlementRecordType.COMMISSION:
        if profit is None:
            return None
        return Expectation(record_type, profit.cost_commission, "line_profit")

    if record_type is SettlementRecordType.SALE:
        if profit is None:
            return Expectation(record_type, line.line_gross, "order_line")
        return Expectation(record_type, profit.revenue_gross, "line_profit")

    if record_type is SettlementRecordType.SERVICE_FEE:
        return Expectation(record_type, store.service_fee_per_order or ZERO, "store")

    if record_type is SettlementRecordType.CARGO:
        shipment = session.scalar(select(Shipment).where(Shipment.order_id == line.order_id))
        if shipment is None:
            return None
        expected = (
            shipment.cargo_cost_actual
            if shipment.cost_state is CostState.ACTUAL and shipment.cargo_cost_actual is not None
            else shipment.cargo_cost_estimated
        )
        return Expectation(record_type, expected, "shipment")

    if record_type is SettlementRecordType.REFUND:
        # İade tutarının karşılığı `line_profit`te DEĞİLDİR: motor iade tutarını gider
        # yazmaz (geliri geri çevirir, bkz. `app/engine/profit.py` iade modeli). Beklenen
        # değer bizim kendi iade kaydımızdır — platformun ödediğiyle karşılaştırılır.
        refunded = sum(
            (
                row.refund_amount
                for row in session.scalars(
                    select(Return).where(Return.order_line_id == line.id)
                ).all()
            ),
            ZERO,
        )
        return Expectation(record_type, refunded, "returns")

    return None


def _already_recorded(session: Session, record_id: uuid.UUID) -> bool:
    """Bu kalem için fark kaydı zaten var mı (idempotency)."""
    return (
        session.scalar(
            select(ReconciliationDiff).where(ReconciliationDiff.settlement_record_id == record_id)
        )
        is not None
    )


def run(
    session: Session,
    *,
    store: Store,
    period: str,
    tolerance: Decimal = DEFAULT_TOLERANCE,
    dry_run: bool = False,
) -> RunSummary:
    """Dönemin hakediş kalemlerini mutabık kılar (spec §7).

    `dry_run=True` iken hiçbir kayıt yazılmaz; sayımlar aynı biçimde döner.
    """
    from app.models.transactions import SettlementRecord

    summary = RunSummary(period=period)
    records = list(
        session.scalars(
            select(SettlementRecord)
            .where(SettlementRecord.store_id == store.id)
            .order_by(SettlementRecord.transaction_date)
        ).all()
    )
    # Dönem filtresi tarih üzerinden: `2026-08` → o ayın kalemleri.
    records = [row for row in records if f"{row.transaction_date:%Y-%m}" == period]
    summary.records = len(records)

    for record in records:
        if _already_recorded(session, record.id):
            summary.skipped += 1
            continue

        line = _line_for(session, record.external_ref, store)
        if line is None:
            if is_explainable_without_order(record.record_type):
                # Ceza/reklam siparişe bağlanmaz; mağaza gideridir (spec §6.3.7).
                summary.matched += 1
                summary.within_tolerance += 1
                continue
            summary.unmatched += 1
            summary.unmatched_refs.append(record.external_ref)
            if not dry_run:
                _write_diff(
                    session,
                    store=store,
                    period=period,
                    record=record,
                    expected=ZERO,
                    actual=record.amount,
                    note="Sipariş satırı eşleşmedi",
                )
                summary.diffs += 1
                summary.total_diff += abs(record.amount)
            continue

        expectation = expectation_for(session, line, record.record_type, store)
        if expectation is None:
            summary.unmatched += 1
            summary.unmatched_refs.append(record.external_ref)
            continue

        summary.matched += 1
        result = compare(expected=expectation.expected, actual=record.amount, tolerance=tolerance)
        if result.within_tolerance:
            summary.within_tolerance += 1
            if not dry_run:
                record.order_line_id = line.id
                record.matched = True
            continue

        summary.diffs += 1
        summary.total_diff += abs(result.diff)
        if not dry_run:
            record.order_line_id = line.id
            record.matched = True
            _write_diff(
                session,
                store=store,
                period=period,
                record=record,
                expected=result.expected,
                actual=result.actual,
                note=f"{record.record_type.value}: beklenen {result.expected}, gerçek {result.actual}",
            )

    if not dry_run:
        session.flush()
        if summary.diffs:
            _write_alert(session, store=store, summary=summary)
        session.flush()

    log.info("reconciliation.run", dry_run=dry_run, **summary.as_dict())
    return summary


def _write_diff(
    session: Session,
    *,
    store: Store,
    period: str,
    record: Any,
    expected: Decimal,
    actual: Decimal,
    note: str,
) -> None:
    """Fark kaydı (append-only: mevcut kayıt güncellenmez, yenisi açılır)."""
    session.add(
        ReconciliationDiff(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            store_id=store.id,
            period=period,
            settlement_record_id=record.id,
            expected=expected,
            actual=actual,
            diff=(actual - expected).quantize(Decimal("0.0001")),
            status=DiffStatus.OPEN,
            note=note,
        )
    )


def _write_alert(session: Session, *, store: Store, summary: RunSummary) -> None:
    """Dönem başına tek uyarı — fark başına uyarı gürültü olurdu."""
    session.add(
        Alert(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            type=DIFF_ALERT,
            severity=AlertSeverity.WARNING,
            entity_ref=f"period:{summary.period}",
            message=(
                f"{summary.period} hakedişinde {summary.diffs} fark bulundu "
                f"(toplam {textfmt.money(summary.total_diff)}); "
                f"eşleşme {textfmt.percent(summary.match_rate_pct)}."
            ),
            created_at=datetime.now(UTC),
        )
    )


def diffs(
    session: Session, *, period: str | None = None, status: DiffStatus | None = None
) -> list[ReconciliationDiff]:
    """Fark listesi — mutabakat ekranının kaynağı."""
    statement = select(ReconciliationDiff).order_by(ReconciliationDiff.created_at.desc())
    if period is not None:
        statement = statement.where(ReconciliationDiff.period == period)
    if status is not None:
        statement = statement.where(ReconciliationDiff.status == status)
    return list(session.scalars(statement).all())


@dataclass(frozen=True)
class DiffContext:
    """Fark satırı + hangi kaleme ve hangi siparişe ait olduğu.

    Ekranda "komisyon · #TY-8399102" yazmadan bir fark satırı işe yaramıyor: kullanıcı
    farkı açıklamak için önce **neyin** farkı olduğunu bilmek zorunda. Bu bilgi farkın
    kendisinde değil, bağlı olduğu hakediş kaleminde duruyor.
    """

    diff: ReconciliationDiff
    record_type: SettlementRecordType | None
    order_ref: str | None


def diff_contexts(
    session: Session, *, period: str | None = None, status: DiffStatus | None = None
) -> list[DiffContext]:
    """`diffs()` + kalem türü ve sipariş referansı (spec §7.4 ekranı).

    Bağlam **ayrı sorgularla** toplanır, `outerjoin` ile değil: marka guard'ı her
    marka-kapsamlı tabloya `brand_id = …` koşulu ekliyor ve bu koşul dış birleşimin
    ürettiği NULL satırları eleyerek dış birleşimi sessizce iç birleşime çeviriyor —
    bağlantısı kopmuş fark listeden düşerdi. Fark listesi asla kısalmamalı.
    """
    from app.models.transactions import SettlementRecord

    rows = diffs(session, period=period, status=status)

    record_ids = {row.settlement_record_id for row in rows if row.settlement_record_id}
    records = (
        {
            record.id: record
            for record in session.scalars(
                select(SettlementRecord).where(SettlementRecord.id.in_(record_ids))
            )
        }
        if record_ids
        else {}
    )

    line_ids = {record.order_line_id for record in records.values() if record.order_line_id}
    lines = (
        {
            line.id: line
            for line in session.scalars(select(OrderLine).where(OrderLine.id.in_(line_ids)))
        }
        if line_ids
        else {}
    )

    order_ids = {line.order_id for line in lines.values()}
    orders = (
        {
            order.id: order.external_order_id
            for order in session.scalars(select(Order).where(Order.id.in_(order_ids)))
        }
        if order_ids
        else {}
    )

    contexts: list[DiffContext] = []
    for row in rows:
        record = records.get(row.settlement_record_id) if row.settlement_record_id else None
        line = lines.get(record.order_line_id) if record and record.order_line_id else None
        contexts.append(
            DiffContext(
                diff=row,
                record_type=record.record_type if record else None,
                order_ref=orders.get(line.order_id) if line else None,
            )
        )
    return contexts


def explain(
    session: Session, *, diff_id: uuid.UUID, note: str, status: DiffStatus
) -> ReconciliationDiff:
    """Farkı "açıklandı"/"çözüldü" olarak işaretler (spec §7.4).

    Not zorunludur: açıklamasız kapatılan fark, kapatılmamış farktan daha tehlikelidir —
    bir daha kimse bakmaz.
    """
    if status is DiffStatus.OPEN:
        raise ReconciliationError("İşaretleme `explained` ya da `resolved` olmalı")
    if len(note.strip()) < 3:
        raise ReconciliationError("Açıklama zorunlu")

    record = session.scalar(select(ReconciliationDiff).where(ReconciliationDiff.id == diff_id))
    if record is None:
        raise ReconciliationError("Fark kaydı bulunamadı")

    record.status = status
    record.note = note.strip()
    session.flush()
    return record


@dataclass(frozen=True)
class PeriodSummary:
    """Dönem özeti — mutabakat ekranının üst şeridi."""

    period: str
    diff_count: int
    open_count: int
    explained_count: int
    resolved_count: int
    total_diff: Decimal
    open_diff: Decimal
    """Yalnızca AÇIK farkların toplamı — ekranın "ilgilenilecek tutar" rakamı."""

    record_count: int
    matched_count: int
    settlement_total: Decimal
    """Dönemin hakediş hacmi (kalem tutarlarının mutlak toplamı)."""

    @property
    def match_rate_pct(self) -> Decimal:
        """Eşleşen kalem oranı — kalem yoksa 0 (bölme değil, bilgi yokluğu)."""
        if not self.record_count:
            return ZERO
        return (Decimal(self.matched_count) / Decimal(self.record_count) * Decimal("100")).quantize(
            Decimal("0.01")
        )


def period_summary(session: Session, *, period: str) -> PeriodSummary:
    """Dönemin fark özeti + hakediş hacmi ve eşleşme oranı (spec §7.4)."""
    from app.models.transactions import SettlementRecord

    rows = diffs(session, period=period)
    in_period = func.to_char(SettlementRecord.transaction_date, "YYYY-MM") == period
    records, matched, volume = session.execute(
        select(
            func.count(),
            func.count().filter(SettlementRecord.matched.is_(True)),
            func.coalesce(func.sum(func.abs(SettlementRecord.amount)), 0),
        ).where(in_period)
    ).one()

    return PeriodSummary(
        period=period,
        diff_count=len(rows),
        open_count=sum(1 for row in rows if row.status is DiffStatus.OPEN),
        explained_count=sum(1 for row in rows if row.status is DiffStatus.EXPLAINED),
        resolved_count=sum(1 for row in rows if row.status is DiffStatus.RESOLVED),
        total_diff=sum((abs(row.diff) for row in rows), ZERO).quantize(Decimal("0.0001")),
        open_diff=sum(
            (abs(row.diff) for row in rows if row.status is DiffStatus.OPEN), ZERO
        ).quantize(Decimal("0.0001")),
        record_count=int(records),
        matched_count=int(matched),
        settlement_total=Decimal(volume).quantize(Decimal("0.0001")),
    )


def periods(session: Session) -> list[str]:
    """Fark kaydı olan dönemler (en yeni üstte)."""
    rows = session.scalars(select(ReconciliationDiff.period).distinct()).all()
    return sorted(set(rows), reverse=True)
