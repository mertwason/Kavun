"""Brand-scope guard'ı — fail-closed marka izolasyonu (spec §3A.2).

İki katmanlı çalışır:

1. **Fail-closed:** marka bağlamı olmayan bir oturumda `brand_id` taşıyan tabloya
   sorgu atılırsa `BrandScopeViolation` fırlatılır. Sessizce "tüm markalar" dönmez.
2. **Otomatik filtre:** marka bağlamı varsa sorguya `brand_id = <aktif marka>` koşulu
   eklenir — hem ORM varlıkları (`with_loader_criteria`, ilişki yüklemeleri dahil) hem
   de sorgunun üst seviye FROM tabloları için. Geliştirici filtreyi unutsa bile karşı
   markanın verisi dönmez.

Alt sorgu (subquery/CTE) içinde kalan marka-kapsamlı tablolar otomatik filtre alamaz;
bu durumda sorgunun kendi `brand_id` koşulunu taşıması gerekir, taşımıyorsa guard
yine fail-closed davranır.

Bypass yalnızca iki yolla mümkündür ve ikisi de açıkça istenir:
- `holding_scope()` — markalar arası konsolide rapor (spec §3A.3), audit'e yazılır
- `system_scope()` — seed / replay / sync gibi arka plan işleri

Bilinen sınır 1: guard yalnızca `brand_id` sütunu OLAN tablolara bakar. `sku_costs` gibi
ürüne/siparişe dolaylı bağlı tablolar ürün üzerinden sorgulanmalıdır; onların
izolasyonu API katmanının join'lerine bağlıdır.

Bilinen sınır 2 (KVN-09'da canlı testte yakalandı): **`Session.get()` kullanılmaz.**
Birincil anahtar araması identity map'ten dönebilir; o yol hiçbir sorgu üretmediği için
guard'a da uğramaz ve başka markanın kaydı sızar. Marka verisi her zaman `select()` ile
okunur — negatif testi `tests/test_analytics.py` içindedir.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Column, Delete, Select, Table, Update
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria
from sqlalchemy.sql import Join, visitors
from sqlalchemy.sql.elements import BinaryExpression

from app.core.context import RequestContext, current_context

BRAND_COLUMN = "brand_id"


# Sınıf adı spec §3A.2'de birebir bu şekilde geçer (Error son eki eklenmez).
class BrandScopeViolation(RuntimeError):  # noqa: N818
    """Marka filtresi olmayan sorgu — izolasyon ihlali (fail-closed)."""

    def __init__(self, tables: set[str]) -> None:
        self.tables = tables
        listed = ", ".join(sorted(tables))
        super().__init__(
            f"Marka bağlamı olmadan marka-kapsamlı tabloya sorgu: {listed}. "
            "Bir workspace bağlamı (brand_scope) açın; markalar arası erişim için "
            "holding_scope(), arka plan işleri için system_scope() kullanın."
        )


def brand_scoped_tables(statement: Any) -> set[str]:
    """Sorgunun herhangi bir yerinde geçen, `brand_id` taşıyan tabloların adları."""
    return {
        element.name
        for element in visitors.iterate(statement, {"column_collections": False})
        if isinstance(element, Table) and BRAND_COLUMN in element.c
    }


def top_level_scoped_tables(statement: Any) -> list[Table]:
    """Sorgunun üst seviye FROM'undaki marka-kapsamlı tablolar.

    Alt sorgular ve alias'lar dahil edilmez: onlara `WHERE` eklemek sorgunun
    anlamını değiştirebilir.
    """
    froms: list[Any] = []
    if hasattr(statement, "get_final_froms"):
        froms = list(statement.get_final_froms())
    elif getattr(statement, "table", None) is not None:  # UPDATE / DELETE
        froms = [statement.table]

    found: list[Table] = []
    stack = list(froms)
    while stack:
        element = stack.pop()
        if isinstance(element, Table):
            if BRAND_COLUMN in element.c:
                found.append(element)
        elif isinstance(element, Join):
            stack.extend([element.left, element.right])
    return found


def has_brand_filter(statement: Any) -> bool:
    """Sorgunun herhangi bir yerinde `brand_id` üzerine bir karşılaştırma var mı.

    Alt sorgular da taranır: filtre alt sorgunun içinde olabilir.
    """
    for element in visitors.iterate(statement, {"column_collections": False}):
        if not isinstance(element, BinaryExpression):
            continue
        for side in (element.left, element.right):
            if isinstance(side, Column) and side.name == BRAND_COLUMN:
                return True
    return False


def _scoped_entities(state: ORMExecuteState) -> list[Any]:
    """Sorgudaki, `brand_id` taşıyan ORM sınıfları."""
    entities: list[Any] = []
    for mapper in state.all_mappers:
        if BRAND_COLUMN in mapper.columns:
            entities.append(mapper.class_)
    return entities


def enforce_brand_scope(state: ORMExecuteState) -> None:
    """`do_orm_execute` dinleyicisi: izolasyonu uygular."""
    if not (state.is_select or state.is_update or state.is_delete):
        return

    tables = brand_scoped_tables(state.statement)
    if not tables:
        return

    context: RequestContext | None = current_context()
    if context is None or (context.scoped and context.brand_id is None):
        raise BrandScopeViolation(tables)

    if not context.scoped:
        # Holding görünümü / sistem işi: çağıran bilinçli olarak filtresiz istedi.
        return

    brand_id = context.brand_id
    statement = state.statement
    covered: set[str] = set()

    # 1) ORM varlıkları — ilişki yüklemeleri ve alias'lar dahil kapsanır.
    for entity in _scoped_entities(state):
        statement = statement.options(
            with_loader_criteria(
                entity,
                getattr(entity, BRAND_COLUMN) == brand_id,
                include_aliases=True,
            )
        )
        covered.add(entity.__tablename__)

    # 2) Üst seviye FROM tabloları — count/aggregate gibi ORM varlığı olmayan sorgular.
    for table in top_level_scoped_tables(statement):
        # SELECT / UPDATE / DELETE üçü de `.where()` destekler; tip bilgisi ortak
        # `Executable` üzerinden geldiği için burada daraltılır.
        statement = cast("Select[Any] | Update | Delete", statement).where(
            table.c[BRAND_COLUMN] == brand_id
        )
        covered.add(table.name)

    # 3) Yalnızca alt sorguda kalan tablolar kendi filtresini taşımalı.
    if tables - covered and not has_brand_filter(statement):
        raise BrandScopeViolation(tables - covered)

    state.statement = statement


def install_brand_scope_guard(session_class: type[Session] = Session) -> None:
    """Guard'ı Session sınıfına bağlar. Uygulama açılışında bir kez çağrılır."""
    from sqlalchemy import event

    if not event.contains(session_class, "do_orm_execute", enforce_brand_scope):
        event.listen(session_class, "do_orm_execute", enforce_brand_scope)
