import os
from pathlib import Path
from typing import Callable, Sequence

import polars as pl


def filter_df(
    df: pl.DataFrame,
    *,
    columns: Sequence[str] | None = None,
    filter_column:str | None = None,
    filter_values: list | None = None
) -> pl.DataFrame:
    '''
    Filter a Polars DataFrame by selecting specific columns and filtering rows based on values in a specified column.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame to be filtered.
    columns : Sequence[str], optional
        A sequence of column names to select from the DataFrame. If None, all columns are selected.
    filter_column : str, optional
        The name of the column to filter on. If None, no row filtering is applied.
    filter_values : list, optional
        A list of values to filter the `filter_column` by. Only rows where the `filter_column` value is in this list will be kept.

    Returns
    -------
    pl.DataFrame
        A new Polars DataFrame that has been filtered according to the specified parameters.
    '''
    
    if columns is not None:
        df = df.select(columns)

    if filter_column is not None and filter_values is not None:
        df = df.filter(pl.col(filter_column).is_in(filter_values))

    return df


def pivot_wider(
    df: pl.DataFrame,
    *,
    index:str | Sequence[str] | None = None,
    on: str,
    values: str | Sequence[str] | None = None,
    aggregate_function: str = "sum",
    sort_columns: bool = False,
    separator: str = "_"    
) -> pl.DataFrame:
    '''
    Reshape a Polars DataFrame from long to wide format.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame to be reshaped.
    index : str or Sequence[str], optional
        Column(s) to use as the new index. If None, no index is set.
    on : str
        Column to pivot on. This column's unique values will become the new columns in the wide format.
    values : str or Sequence[str], optional
        Column(s) whose values will fill the new columns. If None, all remaining columns are used.
    aggregate_function : str, optional
        Function to aggregate values when there are multiple entries for the same index/on combination. Default is "sum".
    sort_columns : bool, optional
        Whether to sort the resulting columns alphabetically. Default is False.
    separator : str, optional
        Separator to use when combining column names in the wide format. Default is "_".

    Returns
    -------
    pl.DataFrame
        A new Polars DataFrame reshaped to wide format.
    '''
    
    if index is None:
        index_cols: list[str] = []
        temp_index_col = "_temp_pivot_index"
        while temp_index_col in df.columns: 
            temp_index_col = f"_{temp_index_col}"
        df_pivot = df.with_columns(pl.lit(1).alias(temp_index_col))
        pivot_index: list[str] = [temp_index_col]
    else:
        index_cols = [index] if isinstance(index, str) else [str(c) for c in index]
        df_pivot = df
        pivot_index = index_cols

    value_cols = [values] if isinstance(values, str) else [str(c) for c in values] 

    if not value_cols:
        raise ValueError("Values must contain at least one column name.")

    required_cols = set([str(on)] + value_cols + index_cols)
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in DataFrame: {missing_cols}")

    wide = df_pivot.pivot(
        index=pivot_index,
        on=str(on),
        values=value_cols,
        aggregate_function=aggregate_function,
        separator=separator
    )

    if index is None:
        wide = wide.drop(temp_index_col)

    if sort_columns:
        if index_cols:
            generated_cols = [c for c in wide.columns if c not in index_cols]
            wide = wide.select(index_cols + sorted(generated_cols, key=str))
        else:
            wide = wide.select(sorted(wide.columns, key=str))

    return wide


def pivot_longer(
    df: pl.DataFrame,
    *,
    cols: str | Sequence[str] | None = None,
    cols_exclude: str | Sequence[str] | None = None,
    names_to: str = "variable",
    values_to: str = "value",
) -> pl.DataFrame:
    '''
    Reshape a Polars DataFrame from wide to long (tall) format.
    
    This function "lengthens" data by pivoting multiple columns into two columns:
    one for the column names and one for their values. This is the inverse operation
    of pivot_wider and is useful for converting data from a wide format suitable for
    display into a long format suitable for analysis.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame to be reshaped.
    cols : str or Sequence[str], optional
        Column(s) to pivot into longer format. Can be:
        - A single column name (str)
        - A list of column names
        - None (default): pivots all columns except those in cols_exclude
    cols_exclude : str or Sequence[str], optional
        Column(s) to keep as identifier variables (not pivoted). These columns
        are repeated for each pivoted value. Ignored if cols is specified.
    names_to : str, default "variable"
        Name of the new column that will contain the original column names.
    values_to : str, default "value"
        Name of the new column that will contain the values from the pivoted columns.

    Returns
    -------
    pl.DataFrame
        A new Polars DataFrame reshaped to long format with columns:
        - All identifier columns (from cols_exclude or unpivoted columns)
        - names_to: contains the original column names
        - values_to: contains the corresponding values

    Examples
    --------
    Convert quarterly sales data from wide to long:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "product": ["A", "B", "C"],
    ...     "q1": [100, 150, 200],
    ...     "q2": [120, 160, 210],
    ...     "q3": [110, 155, 205],
    ...     "q4": [130, 170, 220]
    ... })
    >>> result = pivot_longer(
    ...     df,
    ...     cols=["q1", "q2", "q3", "q4"],
    ...     names_to="quarter",
    ...     values_to="sales"
    ... )
    
    Pivot all numeric columns, keeping ID columns:
    
    >>> df = pl.DataFrame({
    ...     "id": [1, 2],
    ...     "name": ["Alice", "Bob"],
    ...     "age": [25, 30],
    ...     "height": [165, 180],
    ...     "weight": [60, 75]
    ... })
    >>> result = pivot_longer(
    ...     df,
    ...     cols_exclude=["id", "name"],
    ...     names_to="metric",
    ...     values_to="measurement"
    ... )
    
    Reshape survey data with multiple questions:
    
    >>> survey = pl.DataFrame({
    ...     "respondent_id": [1, 2, 3],
    ...     "q1_score": [4, 5, 3],
    ...     "q2_score": [3, 4, 5],
    ...     "q3_score": [5, 5, 4]
    ... })
    >>> result = pivot_longer(
    ...     survey,
    ...     cols_exclude="respondent_id",
    ...     names_to="question",
    ...     values_to="score"
    ... )
    
    Notes
    -----
    - This function uses Polars' `melt()` method internally
    - At least one of `cols` or `cols_exclude` should be specified for clarity
    - If neither is specified, all columns are pivoted (usually not desired)
    - The resulting DataFrame will have more rows than the original
    - Original column order in the identifier variables is preserved
    - The order of pivoted columns in names_to follows their original order in the DataFrame
    '''
    # Determine which columns to pivot
    if cols is not None:
        # Explicitly specified columns to pivot
        cols_list = [cols] if isinstance(cols, str) else list(cols)
        
        # Validate that specified columns exist
        missing = [c for c in cols_list if c not in df.columns]
        if missing:
            raise ValueError(f"Columns not found in DataFrame: {missing}")
        
        # ID columns are everything not being pivoted
        id_vars = [c for c in df.columns if c not in cols_list]
        value_vars = cols_list
        
    elif cols_exclude is not None:
        # Exclude specified columns from pivoting (keep as identifiers)
        exclude_list = [cols_exclude] if isinstance(cols_exclude, str) else list(cols_exclude)
        
        # Validate that excluded columns exist
        missing = [c for c in exclude_list if c not in df.columns]
        if missing:
            raise ValueError(f"Columns to exclude not found in DataFrame: {missing}")
        
        id_vars = exclude_list
        value_vars = [c for c in df.columns if c not in exclude_list]
        
    else:
        # No specification: pivot all columns (no ID vars)
        id_vars = []
        value_vars = list(df.columns)
    
    # Perform the melt operation
    if id_vars:
        result = df.melt(
            id_vars=id_vars,
            value_vars=value_vars,
            variable_name=names_to,
            value_name=values_to
        )
    else:
        # No ID variables - melt everything
        result = df.melt(
            value_vars=value_vars,
            variable_name=names_to,
            value_name=values_to
        )
    
    return result


def separate_column(
    df: pl.DataFrame,
    *,
    column: str,
    into: Sequence[str],
    sep: str = "_",
    remove: bool = True,
    fill: str | None = None,
) -> pl.DataFrame:
    '''
    Split a column into multiple new columns based on a delimiter.
    
    This function takes a single column containing delimited text and separates it
    into multiple columns. It's useful for splitting combined data like "city_state",
    "last_first" names, or "year_month_day" dates into their component parts.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame.
    column : str
        Name of the column to split.
    into : Sequence[str]
        Names for the new columns that will be created from the split.
        The number of names should match the expected number of parts after splitting.
    sep : str, default "_"
        Delimiter/separator to split on. Can be:
        - A literal string (e.g., "_", "-", "|")
        - A regex pattern if more complex splitting is needed
    remove : bool, default True
        If True, removes the original column after splitting.
        If False, keeps the original column alongside the new ones.
    fill : str or None, default None
        Value to use when there aren't enough pieces after splitting.
        If None, missing pieces will be null.
        Common values: "", "NA", "unknown"

    Returns
    -------
    pl.DataFrame
        DataFrame with new columns added (and optionally the original column removed).

    Examples
    --------
    Split city and state from combined column:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "id": [1, 2, 3],
    ...     "location": ["Chicago_IL", "Miami_FL", "Seattle_WA"]
    ... })
    >>> result = separate_column(
    ...     df,
    ...     column="location",
    ...     into=["city", "state"],
    ...     sep="_"
    ... )
    
    Split date components:
    
    >>> df = pl.DataFrame({
    ...     "date_str": ["2026-01-15", "2026-02-20", "2026-03-10"]
    ... })
    >>> result = separate_column(
    ...     df,
    ...     column="date_str",
    ...     into=["year", "month", "day"],
    ...     sep="-",
    ...     remove=False
    ... )
    
    Handle missing pieces with fill value:
    
    >>> df = pl.DataFrame({
    ...     "name": ["John_Doe", "Jane_Smith_Jr", "Bob"]
    ... })
    >>> result = separate_column(
    ...     df,
    ...     column="name",
    ...     into=["first", "last", "suffix"],
    ...     sep="_",
    ...     fill=""
    ... )
    
    Split email addresses:
    
    >>> df = pl.DataFrame({
    ...     "email": ["john@example.com", "jane@company.org"]
    ... })
    >>> result = separate_column(
    ...     df,
    ...     column="email",
    ...     into=["username", "domain"],
    ...     sep="@"
    ... )
    
    Notes
    -----
    - Uses Polars' string split functionality internally
    - If the input column contains fewer pieces than `into` specifies,
      the extra columns will contain nulls (or `fill` if specified)
    - If the input column contains more pieces than `into` specifies,
      the extra pieces are discarded
    - The original column position is preserved when adding new columns
    - All new columns will be of type String
    - For regex patterns in `sep`, use standard Polars regex syntax
    '''
    # Validate that the column exists
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    # Validate into is not empty
    if not into or len(into) == 0:
        raise ValueError("'into' must contain at least one column name")
    
    # Find the position of the original column
    col_index = df.columns.index(column)
    
    # Split the column into a list
    split_expr = pl.col(column).str.split(sep)
    
    # Create expressions for each new column
    new_col_exprs = []
    for i, new_col_name in enumerate(into):
        # Get the i-th element from the split list
        expr = split_expr.list.get(i, null_on_oob=True)
        
        # Apply fill value if specified
        if fill is not None:
            expr = expr.fill_null(fill)
        
        new_col_exprs.append(expr.alias(new_col_name))
    
    # Add all new columns at once
    result = df.with_columns(new_col_exprs)
    
    # Reorder columns to insert new ones at the original column's position
    original_cols = df.columns
    new_cols = list(into)
    
    # Build the final column order
    if remove:
        # Remove original column and insert new ones in its place
        final_cols = (
            original_cols[:col_index] + 
            new_cols + 
            original_cols[col_index + 1:]
        )
    else:
        # Keep original column and insert new ones after it
        final_cols = (
            original_cols[:col_index + 1] + 
            new_cols + 
            original_cols[col_index + 1:]
        )
    
    # Select columns in the desired order
    result = result.select(final_cols)
    
    return result


def collapse_rows(
    df: pl.DataFrame,
    *,
    group_by: str | Sequence[str],
    agg_cols: dict[str, str | Sequence[str]] | None = None,
    default_agg: str = "first",
    concat_sep: str = ", ",
) -> pl.DataFrame:
    '''
    Collapse multiple rows into single rows based on grouping column(s).
    
    This function groups rows by one or more columns and aggregates the other columns,
    reducing multiple rows per group to a single row. You can specify different
    aggregation functions for different columns, or use a default aggregation for all.

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame.
    group_by : str or Sequence[str]
        Column(s) to group by. Rows with the same values in these columns will be
        collapsed into a single row.
    agg_cols : dict[str, str | Sequence[str]], optional
        Dictionary mapping column names to aggregation functions. Each key is a column
        name, and each value is either:
        - A single aggregation function name (str): "first", "last", "mean", "sum",
          "min", "max", "count", "n_unique", "list", "concat"
        - A list of aggregation function names (creates multiple output columns)
        
        If None or if a column is not specified, uses default_agg.
    default_agg : str, default "first"
        Default aggregation function for columns not specified in agg_cols.
        Common options: "first", "last", "mean", "sum", "min", "max", "list"
    concat_sep : str, default ", "
        Separator to use when aggregating with the "concat" function.
        Only applies to columns using the "concat" aggregation.

    Returns
    -------
    pl.DataFrame
        DataFrame with one row per unique combination of group_by columns,
        with other columns aggregated according to the specifications.

    Examples
    --------
    Collapse duplicate customer records, keeping the first occurrence:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "customer_id": [1, 1, 1, 2, 2],
    ...     "name": ["Alice", "Alice", "Alice", "Bob", "Bob"],
    ...     "order_date": ["2026-01-01", "2026-01-15", "2026-02-01", 
    ...                    "2026-01-10", "2026-01-20"],
    ...     "amount": [100, 150, 200, 75, 125]
    ... })
    >>> result = collapse_rows(
    ...     df,
    ...     group_by="customer_id",
    ...     agg_cols={"amount": "sum", "order_date": "first"},
    ...     default_agg="first"
    ... )
    
    Collapse with multiple aggregations per column:
    
    >>> df = pl.DataFrame({
    ...     "product": ["A", "A", "B", "B", "B"],
    ...     "sale_date": ["2026-01-01", "2026-01-02", "2026-01-01", 
    ...                   "2026-01-03", "2026-01-05"],
    ...     "quantity": [10, 15, 5, 8, 12]
    ... })
    >>> result = collapse_rows(
    ...     df,
    ...     group_by="product",
    ...     agg_cols={
    ...         "quantity": ["sum", "mean", "max"],
    ...         "sale_date": ["first", "last", "count"]
    ...     }
    ... )
    
    Create a list of all values per group:
    
    >>> df = pl.DataFrame({
    ...     "user_id": [1, 1, 2, 2, 2],
    ...     "page_visited": ["home", "about", "home", "products", "checkout"]
    ... })
    >>> result = collapse_rows(
    ...     df,
    ...     group_by="user_id",
    ...     agg_cols={"page_visited": "list"}
    ... )
    
    Use custom separator for string concatenation:
    
    >>> df = pl.DataFrame({
    ...     "order_id": [1, 1, 2, 2],
    ...     "item": ["Apple", "Banana", "Milk", "Bread"]
    ... })
    >>> result = collapse_rows(
    ...     df,
    ...     group_by="order_id",
    ...     agg_cols={"item": "concat"},
    ...     concat_sep=" | "
    ... )
    
    Collapse sensor readings by device:
    
    >>> df = pl.DataFrame({
    ...     "device_id": [1, 1, 1, 2, 2],
    ...     "timestamp": ["10:00", "10:15", "10:30", "10:05", "10:20"],
    ...     "temperature": [20.5, 21.0, 20.8, 19.5, 19.8],
    ...     "humidity": [45, 46, 44, 50, 51]
    ... })
    >>> result = collapse_rows(
    ...     df,
    ...     group_by="device_id",
    ...     agg_cols={
    ...         "temperature": "mean",
    ...         "humidity": "mean",
    ...         "timestamp": "list"
    ...     }
    ... )
    
    Notes
    -----
    - Available aggregation functions:
      * "first": First non-null value
      * "last": Last non-null value  
      * "mean": Average (numeric columns only)
      * "sum": Sum (numeric columns only)
      * "min": Minimum value
      * "max": Maximum value
      * "count": Count of non-null values
      * "n_unique": Count of unique values
      * "list": Collect all values into a list
      * "concat": Concatenate string values with custom separator (see concat_sep)
    - When using multiple aggregations for a column, output columns are named
      as "columnname_aggfunction" (e.g., "quantity_sum", "quantity_mean")
    - The original row order within groups affects "first" and "last" aggregations
    - Null values are typically ignored by aggregation functions
    - The concat_sep parameter applies globally to all "concat" aggregations
    '''
    # Normalize group_by to list
    group_cols = [group_by] if isinstance(group_by, str) else list(group_by)
    
    # Validate group columns exist
    missing = [c for c in group_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Group columns not found in DataFrame: {missing}")
    
    # Get columns that need aggregation (all except group_by columns)
    agg_candidates = [c for c in df.columns if c not in group_cols]
    
    # Build aggregation expressions
    agg_exprs = []
    
    # Helper function to create aggregation expression
    def make_agg_expr(col: str, agg_func: str, suffix: str = "") -> pl.Expr:
        col_expr = pl.col(col)
        alias_name = f"{col}_{agg_func}" if suffix else col
        
        if agg_func == "first":
            return col_expr.first().alias(alias_name)
        elif agg_func == "last":
            return col_expr.last().alias(alias_name)
        elif agg_func == "mean":
            return col_expr.mean().alias(alias_name)
        elif agg_func == "sum":
            return col_expr.sum().alias(alias_name)
        elif agg_func == "min":
            return col_expr.min().alias(alias_name)
        elif agg_func == "max":
            return col_expr.max().alias(alias_name)
        elif agg_func == "count":
            return col_expr.count().alias(alias_name)
        elif agg_func == "n_unique":
            return col_expr.n_unique().alias(alias_name)
        elif agg_func == "list":
            return col_expr.alias(alias_name)
        elif agg_func == "concat":
            return col_expr.str.concat(delimiter=concat_sep).alias(alias_name)
        else:
            raise ValueError(
                f"Unknown aggregation function: '{agg_func}'. "
                f"Valid options: first, last, mean, sum, min, max, count, n_unique, list, concat"
            )
    
    # Process each column that needs aggregation
    for col in agg_candidates:
        if agg_cols and col in agg_cols:
            # Use specified aggregation(s)
            agg_spec = agg_cols[col]
            
            if isinstance(agg_spec, str):
                # Single aggregation
                agg_exprs.append(make_agg_expr(col, agg_spec))
            else:
                # Multiple aggregations for this column
                for agg_func in agg_spec:
                    agg_exprs.append(make_agg_expr(col, agg_func, suffix=f"_{agg_func}"))
        else:
            # Use default aggregation
            agg_exprs.append(make_agg_expr(col, default_agg))
    
    # Perform the groupby and aggregation
    result = df.group_by(group_cols, maintain_order=True).agg(agg_exprs)
    
    return result


def expand_list_column(
    df: pl.DataFrame,
    *,
    column: str,
    mode: str = "rows",
    into: Sequence[str] | None = None,
    fill: str | None = None,
) -> pl.DataFrame:
    '''
    Expand a column containing lists into either separate rows or separate columns.
    
    This function takes a column with list values and expands it in one of two ways:
    - "rows" mode: Each list element becomes a new row (unnest/explode)
    - "columns" mode: Each list element becomes a new column (unnest wider)

    Parameters
    ----------
    df : pl.DataFrame
        The input Polars DataFrame.
    column : str
        Name of the column containing lists to expand.
    mode : str, default "rows"
        Expansion mode:
        - "rows": Expand list elements into separate rows (one row per element)
        - "columns": Expand list elements into separate columns (one column per position)
    into : Sequence[str], optional
        Column names for the expanded elements. Only used in "columns" mode.
        If None, columns are named as "column_0", "column_1", etc.
    fill : str or None, default None
        Value to use when lists have different lengths (columns mode only).
        If None, shorter lists result in null values.

    Returns
    -------
    pl.DataFrame
        DataFrame with the list column expanded according to the specified mode.

    Examples
    --------
    Expand lists into separate rows:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "user_id": [1, 2, 3],
    ...     "pages": [
    ...         ["home", "about"],
    ...         ["products", "checkout", "confirmation"],
    ...         ["home"]
    ...     ]
    ... })
    >>> result = expand_list_column(df, column="pages", mode="rows")
    
    Expand lists into separate columns with custom names:
    
    >>> df = pl.DataFrame({
    ...     "order_id": [1, 2],
    ...     "items": [
    ...         ["laptop", "mouse", "keyboard"],
    ...         ["phone", "case"]
    ...     ]
    ... })
    >>> result = expand_list_column(
    ...     df,
    ...     column="items",
    ...     mode="columns",
    ...     into=["item_1", "item_2", "item_3"],
    ...     fill="(none)"
    ... )
    
    Expand coordinate pairs:
    
    >>> df = pl.DataFrame({
    ...     "location": ["A", "B", "C"],
    ...     "coords": [[41.8, -87.6], [25.8, -80.2], [47.6, -122.3]]
    ... })
    >>> result = expand_list_column(
    ...     df,
    ...     column="coords",
    ...     mode="columns",
    ...     into=["latitude", "longitude"]
    ... )
    
    Expand tags across rows:
    
    >>> df = pl.DataFrame({
    ...     "post_id": [101, 102, 103],
    ...     "tags": [
    ...         ["python", "data"],
    ...         ["rust", "polars", "dataframes"],
    ...         ["tutorial"]
    ...     ]
    ... })
    >>> result = expand_list_column(df, column="tags", mode="rows")
    
    Notes
    -----
    - In "rows" mode, the resulting DataFrame will have more rows than the original
    - In "columns" mode, the list column is replaced with multiple columns
    - Lists with null values are preserved as null in both modes
    - In "rows" mode, all other columns are duplicated for each list element
    - In "columns" mode, if lists have different lengths:
      * Shorter lists get null (or fill value) for missing positions
      * Longer lists are truncated to the number of columns specified
    - The original column is removed in both modes
    '''
    # Validate column exists
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    # Validate column contains lists
    if df[column].dtype.base_type() != pl.List:
        raise ValueError(
            f"Column '{column}' must contain lists. "
            f"Found type: {df[column].dtype}"
        )
    
    if mode == "rows":
        # Expand into separate rows (explode/unnest)
        result = df.explode(column)
        return result
        
    elif mode == "columns":
        # Expand into separate columns (unnest wider)
        
        # Get the maximum list length to determine number of columns needed
        max_len = df.select(pl.col(column).list.len().max()).item()
        
        if max_len is None or max_len == 0:
            # All lists are empty or null
            return df.drop(column)
        
        # Determine column names
        if into is not None:
            col_names = list(into)
            num_cols = len(col_names)
        else:
            num_cols = max_len
            col_names = [f"{column}_{i}" for i in range(num_cols)]
        
        # Create expressions to extract each list element
        new_col_exprs = []
        for i, col_name in enumerate(col_names):
            expr = pl.col(column).list.get(i, null_on_oob=True)
            
            # Apply fill value if specified
            if fill is not None:
                expr = expr.fill_null(fill)
            
            new_col_exprs.append(expr.alias(col_name))
        
        # Add new columns and remove the original list column
        result = df.with_columns(new_col_exprs).drop(column)
        
        return result
        
    else:
        raise ValueError(
            f"Invalid mode: '{mode}'. Must be 'rows' or 'columns'"
        )


def mutate_df(
    df: pl.DataFrame,
    column_specs: dict[str, pl.Expr | Callable[[pl.DataFrame], pl.Expr]],
) -> pl.DataFrame:
    '''
    Add new columns to a Polars DataFrame based on user-defined logic.
    
    This function provides a flexible way to add multiple columns at once using
    either Polars expressions or callable functions that generate expressions.
    Columns are added in the order they appear in column_specs, allowing later
    columns to reference earlier ones.

    Parameters
    ----------
    df : pl.DataFrame
        Input DataFrame to which columns will be added.
    column_specs : dict[str, pl.Expr | Callable]
        Dictionary mapping new column names to their definitions:
        - **pl.Expr**: A Polars expression defining the column logic
        - **Callable**: A function that takes the DataFrame and returns a pl.Expr
          (useful when you need to reference the evolving DataFrame)

    Returns
    -------
    pl.DataFrame
        DataFrame with new columns added. Original columns are preserved.

    Examples
    --------
    Add columns using simple expressions:
    
    >>> import polars as pl
    >>> df = pl.DataFrame({
    ...     "a": [1, 2, 3],
    ...     "b": [10, 20, 30]
    ... })
    >>> result = mutate_df(df, {
    ...     "sum": pl.col("a") + pl.col("b"),
    ...     "product": pl.col("a") * pl.col("b"),
    ...     "ratio": pl.col("b") / pl.col("a")
    ... })
    
    Add columns where later columns reference earlier new columns:
    
    >>> df = pl.DataFrame({
    ...     "revenue": [1000, 2000, 1500],
    ...     "cost": [600, 1200, 900]
    ... })
    >>> result = mutate_df(df, {
    ...     "profit": pl.col("revenue") - pl.col("cost"),
    ...     "profit_margin": pl.col("profit") / pl.col("revenue") * 100
    ... })
    
    Use callable functions for complex logic:
    
    >>> df = pl.DataFrame({
    ...     "sales_q1": [100, 200],
    ...     "sales_q2": [150, 180],
    ...     "sales_q3": [120, 220],
    ...     "sales_q4": [180, 240]
    ... })
    >>> result = mutate_df(df, {
    ...     "total_sales": lambda d: pl.sum_horizontal(
    ...         pl.col("sales_q1"), pl.col("sales_q2"), 
    ...         pl.col("sales_q3"), pl.col("sales_q4")
    ...     ),
    ...     "avg_quarterly": lambda d: pl.col("total_sales") / 4
    ... })
    
    Combine with safeDivide for robust calculations:
    
    >>> from ponos.utilities import safeDivide
    >>> df = pl.DataFrame({
    ...     "conversions": [10, 5, 0],
    ...     "visits": [100, 0, 50]
    ... })
    >>> result = mutate_df(df, {
    ...     "conversion_rate": safeDivide(pl.col("conversions"), pl.col("visits")),
    ...     "rate_pct": pl.col("conversion_rate") * 100
    ... })
    
    Notes
    -----
    - Columns are added sequentially, so later columns can reference earlier ones
    - The original DataFrame is not modified; a new DataFrame is returned
    - If a column name already exists, it will be overwritten
    - Callable functions receive the DataFrame as it exists after previous columns
      have been added, enabling dependent column creation
    - For complex transformations, consider using pl.Expr directly for better
      performance, as callables add overhead
    '''
    result = df
    
    for col_name, col_spec in column_specs.items():
        if callable(col_spec):
            # Call the function with the current DataFrame to get the expression
            expr = col_spec(result)
        else:
            # Use the expression directly
            expr = col_spec
        
        # Add the column with an alias to ensure it has the correct name
        result = result.with_columns(expr.alias(col_name))
    
    return result


def map_column(
        df: pl.DataFrame,
        col: str,
        mapping: dict[str, str],
        *,
        out_col: str | None = None,
        default: str | None = None
    ):

        '''
        Replace values in a string column using a lookup dictionary.

        Parameters
        __________
        col:
            Name of the column to map
        mapping:
            ``{old_value: new_value}`` dictionary
        out_col:
            Output column name. Defaults to overwriting `col`.
        default:
            Value for keys absent from `mapping`. ``None`` preserves the original value for unmatched rows.
        '''

        result = df
        # Ensure df is passed as an argument
        if 'df' not in locals():
            raise ValueError("DataFrame 'df' must be provided as an argument to map_column.")
        target = out_col or col

        if default is None:
            expr = pl.col(col).replace(mapping).alias(target)
        else:
            expr = pl.col(col).replace(mapping, default = default).alias(target)

        return result.with_columns(expr)

