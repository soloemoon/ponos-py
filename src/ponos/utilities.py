from __future__ import annotations
import os
from pathlib import Path
from typing import Union

import polars as pl

def safe_divide(
    numerator: pl.Expr,
    denominator: pl.Expr
) -> pl.Expr:
    '''
    Divde safely with float semantics. Casts both sides to Float64 and prevents null denominator.
    '''
    num = numerator.cast(pl.Float64)
    den = denominator.cast(pl.Float64)
    safe_den = pl.when(den ==0).then(None).otherwise(den)
    return num / safe_den

def read_sql(
    self,
    query_path: str | Path
) -> str:

    p = Path(query_path)

    if p.suffix.lower() != ".sql":
        raise ValueError(f"query_path must be a .sql file, got {p}")
    return p.read_text(encoding='utf-8').strip()

@staticmethod
def period_expressions(
    *,
    date_col: str,
    period: str
) -> tuple[pl.Expr, pl.Expr]:

    if period not in {"day", "week", "month", "quarter"}:
        raise ValueError("period must be one of: day, week, month, quarter")

    dt = pl.col(date_col)

    if period == "day":
        period_start = dt.cast(pl.Date)
        period_idx = period_start.cast(pl.Int32)
        
    elif period == "week":
        period_start = dt.dt.truncate("1w").cast(pl.Date)
        period_idx = (dt.dt.iso_year() * 53 * dt.dt.week()).cast(pl.Int32)

    elif period == "month":
        period_start = dt.dt.truncate("1mo").cast(pl.Date)
        period_idx = (dt.dt.year() * 12 + dt.dt.month()).cast(pl.Int32)

    else:
        period_start = dt.dt.truncate("1q").cast(pl.Date)
        period_idx = (
            dt.dt.year() * 4 + ((dt.dt.month()-1) // 3 + 1)
        ).cast(pl.Int32)

    return period_start, period_idx

