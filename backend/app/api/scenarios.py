"""Fiyat senaryosu uçları (spec §12A.4).

`evaluate` kaydetmeden hesaplar, `compare` en fazla 3 senaryoyu yan yana koyar,
`target-margin` hedef marjı tutturan fiyatı kapalı formülle çözer.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.catalog import Product
from app.models.enums import UserRole
from app.models.identity import Channel, Store
from app.models.workspace import PricingScenario
from app.schemas.scenarios import (
    CompareIn,
    ScenarioInputIn,
    ScenarioResultOut,
    TargetMarginIn,
    TargetMarginOut,
)
from app.services import scenarios

router = APIRouter(prefix="/{brand_slug}/scenarios", tags=["scenarios"])


def _result_out(result: scenarios.ScenarioResult) -> ScenarioResultOut:
    return ScenarioResultOut(
        scenario_id=result.scenario_id,
        name=result.name,
        product_id=result.product_id,
        sku=result.sku,
        satis_fiyati=result.satis_fiyati,
        musteri_odedigi=result.musteri_odedigi,
        adet=result.adet,
        birim_kar=result.birim_kar,
        marj_pct=result.marj_pct,
        toplam_kar=result.toplam_kar,
        basabas_fiyat=result.basabas_fiyat,
        commission_rate=result.commission_rate,
        commission_source=result.commission_source,
        cargo_cost=result.cargo_cost,
        service_fee=result.service_fee,
        warnings=list(result.breakdown.warnings),
        waterfall=[{"key": key, "amount": amount} for key, amount in result.breakdown.waterfall],
    )


def _product(workspace: Workspace, product_id: uuid.UUID) -> Product:
    product = workspace.session.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")
    return product


def _store(workspace: Workspace) -> Store:
    """Markanın Trendyol mağazası (yoksa ilki) — senaryo hizmet bedelini oradan alır."""
    rows = workspace.session.scalars(select(Store).order_by(Store.name)).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mağaza tanımlı değil")
    channels = {row.id: row.code for row in workspace.session.scalars(select(Channel)).all()}
    for store in rows:
        if channels.get(store.channel_id) is not None and channels[store.channel_id].value == (
            "trendyol"
        ):
            return store
    return rows[0]


def _to_input(payload: ScenarioInputIn) -> scenarios.ScenarioInput:
    return scenarios.ScenarioInput(
        name=payload.name,
        satis_fiyati=payload.satis_fiyati,
        kampanya_indirim_pct=payload.kampanya_indirim_pct,
        kampanya_satici_pay_pct=payload.kampanya_satici_pay_pct,
        kargo_kim_oder=payload.kargo_kim_oder,
        adet_varsayimi=payload.adet_varsayimi,
        commission_mode=payload.commission_mode,
        pinned_commission_rate=payload.pinned_commission_rate,
        future_tariff_date=payload.future_tariff_date,
        kargo_tahmini=payload.kargo_tahmini,
    )


@router.post(
    "/evaluate", response_model=ScenarioResultOut, summary="Senaryoyu hesapla (kaydetmeden)"
)
def evaluate_scenario(
    payload: ScenarioInputIn,
    workspace: Workspace = Depends(get_workspace),
) -> ScenarioResultOut:
    """Deterministik hesap: girdi → kâr motoru → sonuç (spec §12A.4)."""
    product = _product(workspace, payload.product_id)
    result = scenarios.evaluate(
        workspace.session,
        product=product,
        store=_store(workspace),
        scenario=_to_input(payload),
        on_date=date.today(),
    )
    return _result_out(result)


@router.get("", response_model=list[ScenarioResultOut], summary="Kayıtlı senaryolar + sonuçları")
def list_scenarios(
    workspace: Workspace = Depends(get_workspace),
    product_id: uuid.UUID | None = None,
) -> list[ScenarioResultOut]:
    """Markanın senaryoları, güncel tarife ve maliyetle yeniden hesaplanmış."""
    statement = select(PricingScenario).order_by(PricingScenario.created_at.desc())
    if product_id is not None:
        statement = statement.where(PricingScenario.product_id == product_id)
    records = workspace.session.scalars(statement).all()

    store = _store(workspace)
    today = date.today()
    results: list[ScenarioResultOut] = []
    for record in records:
        product = workspace.session.scalar(select(Product).where(Product.id == record.product_id))
        if product is None:
            continue
        results.append(
            _result_out(
                scenarios.evaluate(
                    workspace.session,
                    product=product,
                    store=store,
                    scenario=scenarios.from_record(record),
                    on_date=today,
                )
            )
        )
    return results


@router.post(
    "",
    response_model=ScenarioResultOut,
    status_code=status.HTTP_201_CREATED,
    summary="Senaryo kaydet",
)
def create_scenario(
    payload: ScenarioInputIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> ScenarioResultOut:
    """Senaryoyu kaydeder ve sonucunu döner."""
    product = _product(workspace, payload.product_id)
    record = PricingScenario(
        tenant_id=workspace.brand.tenant_id,
        brand_id=workspace.brand_id,
        product_id=product.id,
        name=payload.name,
        satis_fiyati=payload.satis_fiyati,
        kampanya_indirim_pct=payload.kampanya_indirim_pct,
        kampanya_satici_pay_pct=payload.kampanya_satici_pay_pct,
        kargo_kim_oder=payload.kargo_kim_oder,
        adet_varsayimi=payload.adet_varsayimi,
        commission_mode=payload.commission_mode,
        pinned_commission_rate=payload.pinned_commission_rate,
        future_tariff_date=payload.future_tariff_date,
        kargo_tahmini=payload.kargo_tahmini,
        created_by=workspace.claims.email,
    )
    workspace.session.add(record)
    workspace.session.flush()

    result = scenarios.evaluate(
        workspace.session,
        product=product,
        store=_store(workspace),
        scenario=scenarios.from_record(record),
        on_date=date.today(),
    )
    workspace.session.commit()
    return _result_out(result)


@router.post(
    "/compare", response_model=list[ScenarioResultOut], summary="En fazla 3 senaryoyu karşılaştır"
)
def compare_scenarios(
    payload: CompareIn,
    workspace: Workspace = Depends(get_workspace),
) -> list[ScenarioResultOut]:
    """Kayıtlı senaryolar ve/veya anlık girdiler yan yana hesaplanır (spec §12A.4)."""
    store = _store(workspace)
    today = date.today()
    prepared: list[tuple[Product, Store, scenarios.ScenarioInput]] = []

    for scenario_id in payload.scenario_ids:
        record = workspace.session.scalar(
            select(PricingScenario).where(PricingScenario.id == scenario_id)
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")
        prepared.append(
            (
                _product(workspace, record.product_id),
                store,
                scenarios.from_record(record, cargo_estimate=None),
            )
        )

    for item in payload.inputs:
        prepared.append((_product(workspace, item.product_id), store, _to_input(item)))

    try:
        results = scenarios.compare(workspace.session, scenarios=prepared, on_date=today)
    except scenarios.ScenarioError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return [_result_out(result) for result in results]


@router.post(
    "/target-margin",
    response_model=TargetMarginOut,
    summary="Hedef marj için gereken fiyatı çöz",
)
def solve_target_margin(
    payload: TargetMarginIn,
    workspace: Workspace = Depends(get_workspace),
) -> TargetMarginOut:
    """Kapalı formül çözümü — iterasyon yok (spec §12A.4)."""
    product = _product(workspace, payload.product_id)
    solved = scenarios.solve_target_margin(
        workspace.session,
        product=product,
        store=_store(workspace),
        target_margin_pct=payload.hedef_marj_pct,
        scenario=_to_input(payload),
        on_date=date.today(),
    )
    return TargetMarginOut(
        target_margin_pct=solved.target_margin_pct,
        price=solved.price,
        reachable=solved.reachable,
        message=solved.message,
        result=_result_out(solved.result) if solved.result else None,
    )


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export", summary="Senaryoları xlsx olarak indir")
def export_scenarios(workspace: Workspace = Depends(get_workspace)) -> Response:
    """Export edilen dosya import şablonudur; sonuç sütunları hesaplanmış gelir."""
    store = _store(workspace)
    today = date.today()
    records = workspace.session.scalars(
        select(PricingScenario).order_by(PricingScenario.created_at.desc())
    ).all()

    results: list[scenarios.ScenarioResult] = []
    inputs: list[scenarios.ScenarioInput] = []
    for record in records:
        product = workspace.session.scalar(select(Product).where(Product.id == record.product_id))
        if product is None:
            continue
        scenario = scenarios.from_record(record)
        inputs.append(scenario)
        results.append(
            scenarios.evaluate(
                workspace.session, product=product, store=store, scenario=scenario, on_date=today
            )
        )

    payload = scenarios.build_scenario_workbook(results, inputs=inputs)
    # Marka öneki (spec §3A.2): dosya karışıklığı insan seviyesinde de önlenir.
    filename = f"{workspace.brand.slug}-senaryolar-{today.isoformat()}.xlsx"
    return Response(
        content=payload,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", summary="Senaryo dosyası yükle → hesaplanmış dosya iner")
async def import_scenarios(
    file: UploadFile = File(..., description="Kavun senaryo şablonuyla üretilmiş xlsx"),
    workspace: Workspace = Depends(get_workspace),
) -> Response:
    """§12A.4: yüklenen senaryolar hesaplanır ve sonuç sütunlarıyla dolu dosya döner.

    Kayıt oluşturmaz — dosya bir hesap makinesi gibi çalışır.
    """
    payload = await file.read()
    store = _store(workspace)
    today = date.today()
    try:
        prepared = scenarios.parse_scenario_workbook(workspace.session, payload)
        results = [
            scenarios.evaluate(
                workspace.session, product=product, store=store, scenario=scenario, on_date=today
            )
            for product, scenario in prepared
        ]
    except scenarios.ScenarioError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    filled = scenarios.build_scenario_workbook(
        results, inputs=[scenario for _, scenario in prepared]
    )
    return Response(
        content=filled,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="hesaplanmis-{file.filename or "senaryolar.xlsx"}"'
        },
    )
