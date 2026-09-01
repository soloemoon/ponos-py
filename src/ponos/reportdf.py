from src.ponos.utilities import safe_sheet_name
from __future__ import annotations

from pathlib import Path
import win32com.client as win32

from typing import Mapping, Union, Optional, Any, Iterable, Sequence, Tuple
import xlwings as xw
import numpy as np
import polars as pl

from ponos import utilities

def export_parquet(
        df: pl.DataFrame,
        parquet_path: str | Path,
        create_dirs: bool = True,
        compression: str = "zstd",
        verbose: bool = True,
    ) -> Path:
        '''
        Export a Polars or Pandas Dataframe to a parquet file.

        Parameters
        ----------
        df:
            Input dataframe
        parquet_path:
            Destination file path (string or Path). Must end with `.parquet`.
        compression:
            Parquet compression codec. Common values: "zstd", "snappy", "gzip"
        create_dirs:
            If True, creates parent directories for `parquet_path` if needed.
        verbose:
            If True, prints a confirmation message.

        Returns
        -------
        Path
            The resolved output path written

        Raises
        ------
        ValueError
            If an unknown engine is provided.
        TypeError
            If `df` is not compatible with the selected engine.
        ImportError
            If `engine="pandas"` but pandas is not installed
        '''

        path = Path(parquet_path)

        if path.suffix.lower() != ".parquet":
            path = path.with_suffix(".parquet")

        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(df, pl.DataFrame):
            df.write_parquet(path, compression = compression)


        if verbose:
            print(f"DataFrame exported to Parquet: {path}")

        return path


def map_column(
    df: pl.DataFrame,
    *,
    column: str,
    mapping: dict,
    default: str | float | None = None,
    output_column: str | None = None,
) -> pl.DataFrame:
    '''
    Map values in a column to new values using a dictionary mapping.
    
    This function replaces values in a column based on a provided dictionary,
    similar to pandas' `map()` or SQL's CASE WHEN. It's useful for recoding
    categorical variables, standardizing values, or creating derived categories.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame.
    column : str
        Name of the column whose values will be mapped.
    mapping : dict
        Dictionary mapping old values to new values. Keys are the values to match,
        and values are the replacement values. Unmatched values become null or
        the default value if specified.
    default : str, float, or None, default None
        Value to use for entries not found in the mapping dictionary.
        If None, unmatched values become null.
    output_column : str or None, default None
        Name for the output column. If None, replaces the original column.
        If provided, creates a new column and keeps the original.

    Returns
    -------
    pl.DataFrame
        DataFrame with the mapped column values.

    Examples
    --------
    Map status codes to readable labels:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "id": [1, 2, 3, 4],
    ...     "status": [1, 2, 1, 3]
    ... })
    >>> result = map_column(
    ...     df,
    ...     column="status",
    ...     mapping={1: "Active", 2: "Pending", 3: "Closed"},
    ...     output_column="status_label"
    ... )
    
    Standardize country names:
    
    >>> df = pl.DataFrame({
    ...     "country_code": ["US", "USA", "United States", "UK", "GB"]
    ... })
    >>> result = map_column(
    ...     df,
    ...     column="country_code",
    ...     mapping={
    ...         "US": "United States",
    ...         "USA": "United States",
    ...         "United States": "United States",
    ...         "UK": "United Kingdom",
    ...         "GB": "United Kingdom"
    ...     }
    ... )
    
    Create category bins with default for outliers:
    
    >>> df = pl.DataFrame({
    ...     "score": [45, 72, 88, 95, 30]
    ... })
    >>> result = map_column(
    ...     df,
    ...     column="score",
    ...     mapping={45: "Low", 72: "Medium", 88: "High", 95: "High"},
    ...     default="Unknown",
    ...     output_column="score_category"
    ... )
    
    Map abbreviations to full text:
    
    >>> df = pl.DataFrame({
    ...     "dept": ["HR", "IT", "FIN", "HR", "MKT"]
    ... })
    >>> result = map_column(
    ...     df,
    ...     column="dept",
    ...     mapping={
    ...         "HR": "Human Resources",
    ...         "IT": "Information Technology",
    ...         "FIN": "Finance",
    ...         "MKT": "Marketing"
    ...     },
    ...     output_column="department_name"
    ... )
    
    Notes
    -----
    - The mapping is case-sensitive for string values
    - If a value in the column doesn't exist in the mapping dictionary:
      * It becomes null if default is None
      * It becomes the default value if default is specified
    - When output_column is None, the original column is replaced
    - When output_column is specified, both columns exist in the result
    - For complex transformations, consider using `mutate_df` with `pl.when().then()` chains
    - The function uses Polars' `replace()` internally for efficient mapping
    '''
    # Validate column exists
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    # Validate mapping is not empty
    if not mapping:
        raise ValueError("Mapping dictionary cannot be empty")
    
    # Determine output column name
    out_col = output_column if output_column is not None else column
    
    # Build when-then expression for mapping (more flexible than replace)
    # Start with the base column
    expr = pl.col(column)
    
    # Build a when-then chain for each mapping
    when_expr = None
    for old_val, new_val in mapping.items():
        if when_expr is None:
            when_expr = pl.when(expr == old_val).then(pl.lit(new_val))
        else:
            when_expr = when_expr.when(expr == old_val).then(pl.lit(new_val))
    
    # Add default or null for unmatched values
    if default is not None:
        mapped_expr = when_expr.otherwise(pl.lit(default)).alias(out_col)
    else:
        mapped_expr = when_expr.otherwise(None).alias(out_col)
    
    # Apply the mapping
    result = df.with_columns(mapped_expr)
    
    return result


def export_formatted_excel(
    df: pl.DataFrame,
    output_path: str | Path,
    overwrite: bool = True,
    visible:bool = False,
    # Layout options
    bold_header_row: bool = True,
    header_fill_rgb: tuple[int, int, int] = (31, 78, 121),
    header_font_rgb: tuple[int, int, int] = (255, 255, 255),
    freeze_header_row: bool = True,
    autofit_columns: bool = True,
    add_excel_table: bool = False,
    default_number_format: str | None = "0.0",
    column_formats: dict[str, dict[str | int, dict[str, Any]]] | None = None,
    conditional_formats: dict[str, dict[str, Any]] | None = None,
    clear_existing_conditional_formats: bool = True,
    coerce_unsupported_to_str: bool = True,
) -> str:
    '''
    Export a Polars DataFrame to an Excel file with formatting options.

    Parameters
    ----------
    output_path : str or Path
        Destination file path for the Excel file. Must end with `.xlsx`.
    df : pl.DataFrame
        Input Polars DataFrame to export.
    overwrite : bool, default True
        If True, overwrites the existing file at `output_path`. If False and the file exists, raises an error.
    visible : bool, default False
        If True, opens Excel in a visible window during export. Useful for debugging formatting issues.
    
    Layout Options
    --------------
    bold_header_row : bool, default True
        If True, makes the header row bold.
    header_fill_rgb : tuple of int (R, G, B), default (31, 78, 121)
        RGB color for the header row background fill.
    header_font_rgb : tuple of int (R, G, B), default (255, 255, 255)
        RGB color for the header row font.
    freeze_header_row : bool, default True
        If True, freezes the header row so it remains visible when scrolling.
    autofit_columns : bool, default True
        If True, automatically adjusts column widths to fit content.
    add_as_excel_table : bool, default False
        If True, adds the data as an Excel Table object for better filtering and styling.
    default_number_format : str or None, default "0.0"
        Default number format applied to numeric columns. Set to None to skip formatting.
    column_formats : dict or None
        Optional dictionary specifying custom formats for specific columns. 

        Supported options (per column):
        - "number_format": str, e.g., "$#,##0.00" for currency, "mm/dd/yyyy" for dates
        - "font_color": str, e.g., "red", "blue"
        - width: int, column width in characters
        - wrap_text: bool, whether to wrap text in the cell
        - horizontal_alignment: str, e.g., "center", "left", "right"
        - "vertical_alignment": str, e.g., "top", "middle", "bottom"
        Example: {"Sales": {"number_format": "$#,##0.00"}, "Date": {"number_format": "mm/dd/yyyy"}}
    conditional_formats : dict or None
        Optional dictionary specifying conditional formatting rules for specific columns. Dict keyed by sheet_name.
        Example: {"Sales": {"type": "cell", "criteria": ">", "value": 1000, "format": {"font_color": "red"}}}
    coerce_column_types : dict or None
        Optional dictionary specifying column type coercion before export. 
        Example: {"Date": "datetime", "Sales": "float"}

    Returns
    -------
    str
        The resolved output path of the exported Excel file. from module import names
    '''
    output_path = Path(output_path).with_suffix(".xlsx")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {output_path}. Set overwrite=True to replace it.")
    
    # Excel Constants
    XL_COND_CELL_VALUE = 1
    XL_COND_EXPRESSION = 2

    XL_OP = {
        "between": 1,
        "not_between": 2,
        "equal": 3,
        "not_equal": 4,
        "greater_than": 5,
        "less_than": 6,
        "greater_than_or_equal": 7,
        "less_than_or_equal": 8,
    }

    XL_H_ALIGN = {"left": -4131, "center": -4108, "right": -4152}
    XL_V_ALIGN = {"top": -4160, "middle": -4108, "bottom": -4107}

    def _get_columns(df: Any) -> list[str]:
        cols = getattr(df, "columns", None)
        if cols is None:
            raise TypeError(f"Input must have a 'columns' attribute, got {type(df)}")
        return [str(c) for c in list(cols)]

    def _get_shape(df: Any) -> tuple[int, int]:
        shape = getattr(df, "shape", None)
        if shape is None:
            raise TypeError(f"Input must have a 'shape' attribute, got {type(df)}")
        return int(shape[0]), int(shape[1])  # rows, cols

    def _df_to_rows_2d(
        df: Any,
        nrows: int,
        ncols: int
    ) -> list[list[Any]]:

        to_numpy = getattr(df, "to_numpy", None)
        if callable(to_numpy):
            arr = to_numpy()
            arr = np.asarray(arr)

            if arr.ndim == 1 and ncols == 1:
                arr = arr.reshape(-1, 1)
            if arr.ndim != 2:
                raise ValueError(f"Expected 2D array, got {arr.ndim}D array")

            if coerce_unsupported_to_str:
                obj = arr.astype(object, copy=False)
                out: list[list[Any]] = obj.tolist()

                for i in range(len(out)):
                    for j in range(len(out[i])):
                        val = out[i][j]
                        if val is None or isinstance(val, (int, float, str, bool)):
                            continue

                        if isinstance(val, (np.generic,)):
                            continue

                        try:
                            import datetime as _dt
                            if isinstance(val, (_dt.datetime, _dt.date, _dt.time)):
                                continue
                        except Exception:  # noqa: BLE001
                            pass

                        out[i][j] = str(val)
                return out

            return arr.tolist()
        
        rows = getattr(df, "rows", None)
        if callable(rows):
            return [list(r) for r in rows()]

        raise TypeError(f"Input must have a 'to_numpy' or 'rows' method, got {type(df)}")
    
    def _data_bounds(nrows: int, ncols: int) -> Tuple[int, int, int, int]:
            return (nrows+1, ncols)

    def _data_body_range(ws: xw.Sheet, nrows_incl_header: int, ncols: int) -> xw.Range:
            if nrows_incl_header <=1 or ncols <=0:
                return ws.range("A1")
            return ws.range((2,1), (nrows_incl_header, ncols))

    def _col_body_range(
            ws: xw.Sheet, 
            col_idx_1based: int,
            nrows_incl_header: int
        ) -> xw.Range:
            if nrows_incl_header <=1:
                return ws.range((2, col_idx_1based), (2, col_idx_1based))
            return ws.range((2, col_idx_1based), (nrows_incl_header, col_idx_1based))

    def _resolve_range(
            ws: xw.Sheet,
            columns: list[str],
            nrows_incl_header: int,
            ncols: int,
            spec:str
        ) -> xw.Range:
            if spec=="data":
                return _data_body_range(ws, nrows_incl_header, ncols)

            if spec.lower().startswith("col:"):
                col_name = spec.split(":", 1)[1].strip()
                if col_name not in columns:
                    raise ValueError(f"Column '{col_name}' not found in DataFrame columns: {columns}")
                col_idx = columns.index(col_name) + 1
                return _col_body_range(ws, col_idx, nrows_incl_header)

            return ws.range(spec)

    def _apply_header_format(
            ws: xw.Sheet,
            ncols: int,
        ) -> None:
            if ncols <= 0:
                return
            header_range = ws.range((1, 1), (1, ncols))
            if bold_header_row:
                header_range.api.Font.Bold = True
            header_range.color = header_fill_rgb
            header_range.font.color = header_font_rgb


    def _apply_column_formats(
            ws: xw.Sheet,
            columns: list[str],
            nrows_incl_header: int,
            fmts: dict[str, dict[str, Any]]
        ) -> None:
        
            for col_key, opts in fmts.items():
                if isinstance(col_key, int):
                    col_idx = col_key
                else:
                    if col_key not in columns:
                        raise ValueError(f"Column '{col_key}' not found in DataFrame columns: {columns}")
                    col_idx = columns.index(col_key) + 1  # 1-based index

                rng = _col_body_range(ws, col_idx, nrows_incl_header)

                if opts.get("number_format") is not None:
                    rng.number_format = opts["number_format"]
                if opts.get("wrap") is not None:
                    rng.api.WrapText = bool(opts["wrap"])

                if opts.get("horizontal") is not None:
                    key = str(opts["horizontal"]).lower()
                    if key not in XL_H_ALIGN:
                        raise ValueError(f"Invalid horizontal alignment: {opts['horizontal']}. Must be one of {list(XL_H_ALIGN.keys())}")
                    rng.api.HorizontalAlignment = XL_H_ALIGN[key]

                if opts.get("vertical") is not None:
                    key = str(opts["vertical"]).lower()
                    if key not in XL_V_ALIGN:
                        raise ValueError(f"Invalid vertical alignment: {opts['vertical']}. Must be one of {list(XL_V_ALIGN.keys())}")
                    rng.api.VerticalAlignment = XL_V_ALIGN[key]

                if opts.get("width") is not None:
                    ws.range((1, col_idx), (1, col_idx)).column_width = float(opts["width"])

    def _infer_numeric_columns_from_body(
            body: list[list[Any]],
            ncols: int
        ) -> set[int]:
            numeric_cols: set[int] = set()
            for col_idx in range(ncols):
                is_numeric = True
                for row in body:
                    if col_idx >= len(row):
                        continue
                    val = row[col_idx]
                    if val is None:
                        continue
                    if not isinstance(val, (int, float, np.integer, np.floating)):
                        is_numeric = False
                        break
                if is_numeric:
                    numeric_cols.add(col_idx)
            return numeric_cols

    def _apply_conditional_formats(
            ws: xw.Sheet,
            columns: list[str],
            nrows_incl_header: int,
            cond_fmts: dict[str, dict[str, Any]],
            clear_existing: bool = True
        ) -> None:
            if clear_existing:
                ws.api.Cells.FormatConditions.Delete()

            for col_key, opts in cond_fmts.items():
                rng = _resolve_range(ws, columns, nrows_incl_header, len(columns), f"col:{col_key}")

                if opts.get("type") == "cell":
                    rng.api.FormatConditions.Add(
                        Type=XL_COND_CELL_VALUE,
                        Operator=XL_OP[opts["criteria"]],
                        Formula1=str(opts["value"])
                    )
                elif opts.get("type") == "expression":
                    rng.api.FormatConditions.Add(
                        Type=XL_COND_EXPRESSION,
                        Formula1=opts["formula"]
                    )
                else:
                    raise ValueError(f"Invalid conditional format type: {opts.get('type')}. Must be 'cell' or 'expression'.")

                fmt = opts.get("format", {})
                if fmt.get("font_color") is not None:
                    rng.api.FormatConditions(1).Font.Color = fmt["font_color"]
                if fmt.get("fill_color") is not None:
                    rng.api.FormatConditions(1).Interior.Color = fmt["fill_color"]
        

    def _write_sheet(
            ws: xw.Sheet,
            df_any: Any,
        ) -> None:
            columns = _get_columns(df_any)
            nrows, ncols = _get_shape(df_any)

            body = _df_to_rows_2d(df_any, nrows, ncols)
            ws.range("A1").value = [columns] + body
            nrows_incl_header = _data_bounds(nrows, ncols)
            _apply_header_format(ws, ncols)

            if default_number_format is not None and nrows_incl_header > 1 and ncols >0:
                for col_idx in _infer_numeric_columns_from_body(body, ncols):
                    _col_body_range(ws, col_idx, nrows_incl_header).number_format = default_number_format

            if add_excel_table and ncols >0 and nrows_incl_header >1:
                data_rng = ws.range((1, 1), (nrows_incl_header, ncols))
                try:
                    ws.api.ListObject.Add(SourceType=1, Source=data_rng.api, XlListObjectHasHeaders=1)
                except Exception:  # noqa: BLE001, S110
                    pass

            if freeze_header_row:
                ws.activate()
                ws.range("A2").select()
                ws.api.Application.ActiveWindow.FreezePanes = True

            if column_formats and ws.name in column_formats:
                _apply_column_formats(ws, columns, nrows_incl_header, column_formats[ws.name])

            if conditional_formats and ws.name in conditional_formats:
                _apply_conditional_formats(ws, columns, nrows_incl_header, conditional_formats[ws.name], clear_existing_conditional_formats)

            if autofit_columns:
                try:
                    ws.autofit("c")
                except Exception:  # noqa: BLE001
                    ws.autofit()

    with xw.App(visible = visible, add_book=False) as app:
        app.display_alerts = False
        app.screens_updating = False

        wb=app.books.add()

        for sht in list(wb.sheets):
            try:
                sht.delete()
            except Exception:  # noqa: BLE001
                pass

        used = set()

        for requested_name, df_any in df.items():
            if df_any is None:
                continue

            name = safe_sheet_name(str(requested_name))
            base = name
            i = 2
            while name in used:
                suffix = f"_{i}"
                name = (base[:31-len(suffix)] + suffix) if len(base) + len(suffix) > 31 else base + suffix
                i += 1
            used.add(name)

            ws = wb.sheets.add(name)
            _write_sheet(ws, df_any)

        wb.save(str(output_path))
        wb.close()

    return str(output_path)



    