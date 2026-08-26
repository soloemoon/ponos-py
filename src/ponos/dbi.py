from __future__ import annotations

import os
from pathlib import Path
from typing import Union

import polars as pl

import snowflake.connector
import pyodbc
import adbc_driver_manager

from ponos import utilities

class DBI:
    def __init__(self) -> None:
        ''' 
        Provides settings to connect directly to a database
        '''

        self.user =(
            os.environ.get("SNOWFLAKE_USER")
            or os.environ.get("USER")
            or os.environ.get("USERNAME")
        )

    @classmethod
    def connectSnowflake(
        self, 
        account: str, 
        warehouse: str, 
        database: str ,
        schema: str, 
        role: str, 
        authenticator: str = 'externalbrower'
    ):
        '''
        Connect to Snowflake. Defailvia an external browser (SSO)
        '''

        return snowflake.connector.connect(
            account = account,
            user = self.user,
            authenticator = authenticator,
            role = role,
            warehouse=warehouse,
            database = database,
            schema = schema
        )

    @classmethod
    def connectODBC(
        self, 
        dsn_name: str | None = None,
        connection_string: str | None = None,
        **kwargs,
    ) -> pyodbc.Connection:

        '''
        Connect to a database via ODBC.

        Parameters
        -----------
        dsn:
            DSN name configured in the ODBC source. Ignored if a connection string is provided.
        connection_string:
            ODBC connection string. Ignored if dsn and kwargs are supplied.
        **kwargs:
            Additional keyword arguments passed to  pyodbc.connect when building from a DSN.

        Returns
        --------
        pyodbc.Connection

        Raises
        --------
        ValueError:
            If neither dsn or connection_string is provided.
        pyodbc.Error:
            If the driver raises a connection error
        '''

        if connection_string:
            return pyodbc.connect(connection_string)

        if dsn_name:
            return pyodbc.connect(f"DSN={dsn_name}", **kwargs)

        raise ValueError("Provide a dsn name or full connection string")

    @classmethod
    def connectADBC(
        self,
        driver: str,
        uri: str | None = None,
        **kwargs
    ) -> adbc_driver_manager.dbapi.Connection:
        '''
        Connect to a database via ADBC (Arrow Database Connectivity).

        Parameters
        -----------
        driver:
            ADBC driver entrypoint or shared-library path. e.g. adbc_driver_postgresql.dbapi
        uri:
            Connection URI to the driver. E.g. postgresql://user:pass@host:5432/dbname
        **kwargs:
            Additional driver specific init parameters forwarded to abdc_driver_manager.dbapi.connect.
        Returns
        -------
        adbc_driver_manager.dbapi.Connection

        Raises
        ------
        adbc_driver_manager.ProgrammingError:
            If the driver cannot be loaded or the connection fails.
        '''

        if uri:
            kwargs["uri"] = uri
        return adbc_driver_manager.dbapi.connect(driver=driver, **kwargs)

    @classmethod
    def get_query(
            self,
            conn,
            query: str | Path,
            engine: str = 'polars',
            dbi_engine: str = 'odbc'
    ) -> pl.DataFrame:

        '''
            Read a SQL file and/or execute a query against a database.

            Parameters
            ----------
            conn:
                An open database connection. 
            query:
                File path to a `.sql` file or query text to run
            engine:
                Execution/return engine:
                - `"polars"` (default): returns `polars.DataFrame`
            dbi_engine:
                - `"odbc"` (default): Executes query using a default connection string
                - `"adbc"`: Executes query using an ADBC connection string (URI)
            
            Returns
            --------
            polars.DataFrame 
                Query results in the DataFrame type corresponding to `engine`
            
            Raises
            ------
            ValueError
                If `engine` is not `"polars"` .
            FileNotFoundError / OSError
                If `query` cannot be read
            Exception
                Any database/driver errors raised while executing the SQL.
        '''
        sql = self.read_sql(query)
        db_eng = dbi_engine.lower().strip()
        eng = engine.lower().strip()

        if db_eng == "adbc":
            return pl.read_database_uri(query=sql, uri=conn)

        if eng == "polars":
            return pl.read_database(query=sql, connection=conn)


        raise ValueError("Engine must be weither 'polars'")

    @classmethod
    def export_parquet(
        self,
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

        if isinstance(df, pd.DataFrame):
            df.to_parquet(path, compression = compression)

        if verbose:
            print(f"DataFrame exported to Parquet: {path}")

        return path

        






            
