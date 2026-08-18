"""`raw_events` aylık partition yönetimi (spec §5.3).

Partition'lı tabloda yazma anında uygun partition yoksa INSERT hata verir. Bu yüzden
migration açılışta bir pencere kadar partition açar, ilerleyen aylar buradaki yardımcıyla
(KVN-06'da zamanlanmış job) açılır. `raw_events_default` güvenlik ağıdır: hiçbir ayla
eşleşmeyen satır oraya düşer, veri kaybolmaz.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

PARTITIONED_TABLE = "raw_events"


def month_bounds(moment: date) -> tuple[date, date]:
    """Verilen tarihin ayının [başlangıç, bitiş) sınırlarını döndürür."""
    start = date(moment.year, moment.month, 1)
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def partition_name(moment: date) -> str:
    """Ay partition'ının tablo adı: `raw_events_2026_08`."""
    return f"{PARTITIONED_TABLE}_{moment:%Y_%m}"


def create_partition_sql(moment: date) -> str:
    """Verilen ay için `CREATE TABLE ... PARTITION OF` ifadesi."""
    start, end = month_bounds(moment)
    return (
        f"CREATE TABLE IF NOT EXISTS {partition_name(start)} PARTITION OF {PARTITIONED_TABLE} "
        f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
    )


def ensure_monthly_partition(connection: Connection, moment: date) -> str:
    """Verilen ayın partition'ını (yoksa) oluşturur ve adını döndürür."""
    connection.execute(text(create_partition_sql(moment)))
    return partition_name(month_bounds(moment)[0])
