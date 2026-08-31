from __future__ import annotations
import os
from pathlib import Path
from typing import Union, Callable

import polars as pl


def create_file_path(
    base_dir: Union[str, Path],
    folder: Union[str, Path],
    file_name: str,
    create_dirs: bool = True,
) -> str:
    '''
    Construct a file path by joining a base directory, folder, and filename.
    
    This utility function safely combines path components using pathlib, creates
    the directory structure if needed, and returns a string representation of the
    complete file path. It validates that folder and filename are non-empty before
    constructing the path.

    Parameters
    ----------
    base_dir : str or Path
        The base directory path. Can be absolute or relative.
    folder : str or Path
        Subdirectory or nested folder path within base_dir. Must be non-empty.
    file_name : str
        The name of the file including extension. Must be non-empty.
    create_dirs : bool, default True
        If True, creates all parent directories if they don't exist.
        If False, only constructs the path without creating directories.

    Returns
    -------
    str
        Complete file path as a string in the format: base_dir/folder/file_name
        Path separators are automatically adjusted for the operating system.

    Raises
    ------
    ValueError
        If folder is empty, None, or an empty string.
    ValueError
        If file_name is empty, None, or an empty string.
    OSError
        If directory creation fails due to permissions or other OS errors.

    Examples
    --------
    Create a path and automatically create directories:
    
    >>> create_file_path("/data", "reports", "sales.csv")
    '/data/reports/sales.csv'
    
    Create a path with nested folders (all directories created automatically):
    
    >>> create_file_path("C:/Users/Documents", "projects/2026/Q3", "analysis.xlsx")
    'C:/Users/Documents/projects/2026/Q3/analysis.xlsx'
    
    Use Path objects as inputs:
    
    >>> from pathlib import Path
    >>> base = Path.home() / "workspace"
    >>> create_file_path(base, "output", "results.parquet")
    '/home/user/workspace/output/results.parquet'
    
    Construct path without creating directories:
    
    >>> create_file_path("/data", "reports", "sales.csv", create_dirs=False)
    '/data/reports/sales.csv'
    
    Notes
    -----
    - Directories are created with default permissions (mkdir -p behavior)
    - If create_dirs=True and directories already exist, no error is raised
    - Path separators are handled automatically by pathlib for cross-platform compatibility
    - The returned path is a string, not a Path object
    - Only the directory structure is created; the file itself is not created
    '''
    if not folder:
        raise ValueError("Folder must be a non-empty string")
    if not file_name:
        raise ValueError("Filename must be a non-empty string")

    full_path = Path(base_dir) / folder / file_name
    
    if create_dirs:
        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(full_path)


def safe_divide(
    numerator: pl.Expr,
    denominator: pl.Expr
) -> pl.Expr:
    '''
    Perform safe division with float semantics, preventing division by zero.
    
    Casts both operands to Float64 and replaces zero denominators with null,
    ensuring division operations never raise errors. This is useful for
    calculating rates, ratios, or percentages where zero denominators may occur.

    Parameters
    ----------
    numerator : pl.Expr
        Polars expression for the numerator (dividend).
    denominator : pl.Expr
        Polars expression for the denominator (divisor).

    Returns
    -------
    pl.Expr
        Polars expression representing the division result as Float64.
        Returns null when the denominator is zero or null.

    Examples
    --------
    Calculate conversion rates safely:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "conversions": [10, 5, 0, 8],
    ...     "visits": [100, 50, 0, 200]
    ... })
    >>> result = df.with_columns(
    ...     rate=safe_divide(pl.col("conversions"), pl.col("visits"))
    ... )
    
    Calculate percentage change:
    
    >>> df = pl.DataFrame({
    ...     "current": [120, 0, 150],
    ...     "previous": [100, 100, 0]
    ... })
    >>> result = df.with_columns(
    ...     pct_change=safe_divide(
    ...         pl.col("current") - pl.col("previous"),
    ...         pl.col("previous")
    ...     ) * 100
    ... )
    
    Notes
    -----
    - Both numerator and denominator are automatically cast to Float64
    - Zero denominators are replaced with null (not epsilon or a small value)
    - Null numerators or denominators propagate as null in the result
    - This follows SQL semantics where division by zero returns null
    - Use `.fill_null(0)` or `.fill_nan(0)` after this function if you need
      a specific default value instead of null
    '''
    num = numerator.cast(pl.Float64)
    den = denominator.cast(pl.Float64)
    safe_den = pl.when(den == 0).then(None).otherwise(den)
    return num / safe_den

def read_sql(query_path: str | Path) -> str:
    '''
    Read SQL from a file or return SQL query text as-is.
    
    This function intelligently handles both SQL file paths and raw SQL query strings.
    If the input looks like a SQL query (contains newlines or starts with SQL keywords),
    it returns the string directly. Otherwise, it treats the input as a file path and
    reads the .sql file contents.

    Parameters
    ----------
    query_path : str or Path
        Either:
        - Path to a .sql file (string or Path object)
        - Raw SQL query text (multi-line or starting with SELECT/WITH)

    Returns
    -------
    str
        SQL query text, stripped of leading/trailing whitespace.

    Raises
    ------
    ValueError
        If query_path is a file path but doesn't have a .sql extension.
    FileNotFoundError
        If the .sql file doesn't exist.
    OSError
        If the .sql file cannot be read due to permissions or encoding issues.

    Examples
    --------
    Read from a SQL file:
    
    >>> sql = read_sql("queries/users.sql")
    
    Pass raw SQL query text:
    
    >>> sql = read_sql("SELECT * FROM users WHERE active = 1")
    
    Multi-line SQL query:
    
    >>> query = """
    ... SELECT user_id, name
    ... FROM users
    ... WHERE created_date > '2026-01-01'
    ... """
    >>> sql = read_sql(query)
    
    Use Path object:
    
    >>> from pathlib import Path
    >>> sql = read_sql(Path("analysis") / "report.sql")
    
    Notes
    -----
    - SQL files are read with UTF-8 encoding
    - Leading and trailing whitespace is always stripped from results
    - Query detection checks for newlines or keywords: SELECT, WITH
    - File extension checking is case-insensitive (.sql, .SQL, .Sql all work)
    '''
    raw_path = str(query_path).strip()
    
    # Check if this looks like a SQL query rather than a file path
    upper = raw_path.upper()
    if "\n" in raw_path or upper.startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
        return raw_path
    
    # Treat as file path
    p = Path(raw_path)
    
    if p.suffix.lower() != ".sql":
        raise ValueError(
            f"File path must have .sql extension, got: {p.suffix or '(no extension)'}"
        )
    
    if not p.exists():
        raise FileNotFoundError(f"SQL file not found: {p}")
    
    return p.read_text(encoding='utf-8').strip()





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


