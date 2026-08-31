from __future__ import annotations

import polars as pl
from typing import Mapping, Sequence

@dataclass(frozen=True, slots =True)
class MutateFrame:
    df: pl.DataFrame

def calc_day_diff(
    self,
    start_col: str,
    end_col: str,
    *,
    out_col: str = "diff_days",
    abs_diff: bool = False,
    parse_strings: bool = False,
    start_format: str | None = None,
    end_format: str | None = None,
    strict: bool = True
) -> MutateFrame:
    '''
    Add a column with the difference in days between two datetime columns.

    Computes: end_col - start_col (whole days).

    If parse_strings = True, will parse string columns into Datetime first using the provided formats 
    (or Polars inference if format is None)
    '''

    start_expr = pl.col(start_col)
    end_expr = pl.col(end_col)

    if parse_strings:
        start_expr = start_expr.str.strptime(
            pl.Datetime,
            format = start_format,
            strict = strict
        )

        end_expr = end_expr.str.strptime(
            pl.Datetime,
            format=end_format,
            strict = strict
        )


    diff_expr = (end_expr - start_expr).dt.total_days()

    if abs_diff:
        diff_expr = diff_expr.abs()

    out_df = self.df.with_columns(diff_expr.alias(out_col))
    return MutateFrame(out_df)

    def group_time_buckets(
        self,
        *,
        entity_col: str,
        date_col: str,
        period: str = "month", # "day" | "week" | "month" | "quarter"
        cohort_col: str = "cohort",
        cohort_index_col: str = "cohort_index",
    ) -> MutateFrame:
        '''
        Cohort an event-level dataset by each entity's first observed date, bucketed to a time period (day/week/month/quarter).
        Assumes `date_col` is Date/Datetime. If a string then parse.

        Parameters
        ----------
        entity_col:

        date_col:

        period:

        cohort_col:

        cohort_index_col:

        Returns
        -------
        df
        
        '''

        period_start, period_idx = self.period_expressions(date_col = date_col, period=period)

        cohorts = (
            self.df.select(
                pl.col(entity_col),
                period_start.alias("_period_start"),
                period_idx.alias("_period_idx")
            )
            .group_by(entity_col)
            .agg(
                pl.col("_period_start").min().alias(cohort_col),
                pl.col("_period_idx").min().alias("_cohort_idx")
            )
        )

        out_df = (
            self.df.join(cohorts, on=entity_col, how='left')
            .with_columns((period_idx - pl.col("_cohort_idx")).alias(cohort_index_col))
            .drop("_cohort_idx")
        )

        return MutateFrame(out_df)

    def add_characteristic_cohort(
        self,
        *,
        cohort_cols: Sequence[str],
        cohort_col: str = "cohort",
        sep: str = " | ",
        fill_null: str = "(null)",
        transforms: Mapping[str, pl.Expr] | None = None
    ) -> MutateFrame:

        '''
        Add a cohort label on one or more characteristic columns.
        
        Parameters
        -----------
        cohort_cols:
            Columns that define the cohort
        sep:

        fill_null:
            Default value to fill null columns with.

        transforms: 
            Optional per-column expression overrides (e.g. binning, normalization).
        '''

        transforms = transforms or {}

        parts: list[pl.Expr] = []
        for c in cohort_cols:
            expr = transforms.get(c, pl.col(c))
            parts.append(expr.cast(pl.Utf8).fill_null(fill_null).alias(c))
        
        cohort_expr = pl.concat_str(parts, separator=sep).alias(cohort_col)
        out_df = self.df.with_columns(cohort_expr)
        return MutateFrame(out_df)

   


    def bin_histogram(
        self,
        col: str,
        *,
        bin_count: int | None = None,
        bins: Sequence[float] | None = None,
        out_col: str | None = None,
        include_breakpoint: bool = False
    ) -> pl.DataFrame:

        '''
        Bin a numeric coulumn and return aggregated histogram counts

        Parameters
        __________
        col:
            Numeric column to bin
        bin_count:
            Number of equal width bins. Used when `bins` is not supplied.
        bins:
            Explicit breakpoints. Overwrites bin_count.
        out_col:
            Label for the count column. Defaults to ``"count"``.
        include_breakpoint:
            If True, the upper breakpoint is included as a separate column
        '''

       

    