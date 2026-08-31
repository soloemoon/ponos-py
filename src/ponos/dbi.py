from __future__ import annotations

import os
from pathlib import Path

import polars as pl
import snowflake.connector
import pyodbc
import adbc_driver_manager

from ponos import utilities

class DBI:
    def __init__(
        self,
        odbc_name: str | None = None,
        connection_string: str | None = None,
        uri: str | None = None,
        driver: str | None = None,
        account: str | None = None, 
        warehouse: str | None = None, 
        database: str | None = None,
        schema: str | None = None, 
        role: str | None = None, 
        authenticator: str = 'externalbrowser'
    ) -> None:
        '''
        Initialize a database connection interface with support for multiple connection types.

        Configures connection parameters for Snowflake, ODBC, or ADBC database connections.
        The user is automatically detected from environment variables (SNOWFLAKE_USER, USER, or USERNAME).

        Parameters
        ----------
        connection_type : str, default 'snowflake'
            Type of database connection to configure. Options:
            - 'snowflake': Use Snowflake connector
            - 'odbc': Use ODBC connection
            - 'adbc': Use Arrow Database Connectivity
        odbc_name : str or None, default None
            DSN (Data Source Name) configured in ODBC sources. Used for ODBC connections.
        connection_string : str or None, default None
            Full ODBC connection string. Takes precedence over odbc_name if both are provided.
        uri : str or None, default None
            Connection URI for ADBC connections (e.g., 'postgresql://user:pass@host:5432/dbname').
        driver : str or None, default None
            ADBC driver entrypoint or shared-library path (e.g., 'adbc_driver_postgresql.dbapi').
        account : str or None, default None
            Snowflake account identifier (e.g., 'xy12345.us-east-1').
        warehouse : str or None, default None
            Snowflake warehouse name for compute resources.
        database : str or None, default None
            Snowflake database name.
        schema : str or None, default None
            Snowflake schema name within the database.
        role : str or None, default None
            Snowflake role to use for the connection.
        authenticator : str, default 'externalbrowser'
            Snowflake authentication method. Common values:
            - 'externalbrowser': SSO via web browser
            - 'snowflake': Username/password
            - 'oauth': OAuth token authentication

        Attributes
        ----------
        user : str
            Username detected from environment variables (SNOWFLAKE_USER, USER, or USERNAME).
        _snowflake_conn : snowflake.connector.SnowflakeConnection or None
            Cached Snowflake connection object, reused by connectSnowflake().

        Examples
        --------
        Create a Snowflake connection configuration:

        >>> dbi = DBI(
        ...     connection_type='snowflake',
        ...     account='xy12345.us-east-1',
        ...     warehouse='COMPUTE_WH',
        ...     database='ANALYTICS',
        ...     schema='PUBLIC',
        ...     role='ANALYST'
        ... )
        >>> conn = dbi.connectSnowflake()

        Create an ODBC connection configuration:

        >>> dbi = DBI(
        ...     connection_type='odbc',
        ...     odbc_name='MyDataSource'
        ... )
        >>> conn = dbi.connectODBC()

        Create an ADBC connection configuration:

        >>> dbi = DBI(
        ...     connection_type='adbc',
        ...     driver='adbc_driver_postgresql.dbapi',
        ...     uri='postgresql://localhost:5432/mydb'
        ... )
        >>> conn = dbi.connectADBC(driver=dbi.driver, uri=dbi.uri)
        '''
        self.user = (
            os.environ.get("SNOWFLAKE_USER")
            or os.environ.get("USER")
            or os.environ.get("USERNAME")
        )

        self._snowflake_conn: snowflake.connector.SnowflakeConnection | None = None

        # ODBC configuration
        self.odbc_name = odbc_name
        self.connection_string = connection_string

        # ADBC configuration
        self.uri = uri
        self.driver = driver

        # Snowflake configuration (always set to avoid AttributeError)
        self.account = account
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.role = role
        self.authenticator = authenticator


    def connectSnowflake(self) -> snowflake.connector.SnowflakeConnection:
        '''
        Connect to Snowflake. Reuses an existing open connection if available.
        
        Returns
        -------
        snowflake.connector.SnowflakeConnection
            Active Snowflake connection object.
            
        Raises
        ------
        snowflake.connector.Error
            If the connection cannot be established.
        '''
        # Reuse existing connection if it's still open
        if self._snowflake_conn is not None:
            try:
                if not self._snowflake_conn.is_closed():
                    return self._snowflake_conn
            except Exception:
                # If connection health cannot be checked, create a fresh one
                pass

        # Create new connection
        self._snowflake_conn = snowflake.connector.connect(
            account=self.account,
            user=self.user,
            authenticator=self.authenticator,
            role=self.role,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema
        )

        return self._snowflake_conn

    def connectODBC(self, **kwargs) -> pyodbc.Connection:
        '''
        Connect to a database via ODBC.

        Parameters
        ----------
        **kwargs
            Additional keyword arguments passed to pyodbc.connect when using DSN.
            Ignored if connection_string was provided in __init__.

        Returns
        -------
        pyodbc.Connection
            Active ODBC connection object.

        Raises
        ------
        ValueError
            If neither odbc_name nor connection_string was provided in __init__.
        pyodbc.Error
            If the driver raises a connection error.
        '''
        # Prioritize DSN over connection string
        if self.odbc_name:
                    return pyodbc.connect(f"DSN={self.odbc_name}", **kwargs)

        if self.connection_string:
            return pyodbc.connect(self.connection_string)

        raise ValueError(
            "Either 'odbc_name' or 'connection_string' must be provided in __init__"
        )

    def connectADBC(
        self,
        driver: str | None = None,
        uri: str | None = None,
        **kwargs
    ) -> adbc_driver_manager.dbapi.Connection:
        '''
        Connect to a database via ADBC (Arrow Database Connectivity).

        Parameters
        ----------
        driver : str or None, default None
            ADBC driver entrypoint or shared-library path 
            (e.g., 'adbc_driver_postgresql.dbapi'). If None, uses driver from __init__.
        uri : str or None, default None
            Connection URI (e.g., 'postgresql://user:pass@host:5432/dbname').
            If None, uses uri from __init__.
        **kwargs
            Additional driver-specific parameters forwarded to adbc_driver_manager.dbapi.connect.

        Returns
        -------
        adbc_driver_manager.dbapi.Connection
            Active ADBC connection object.

        Raises
        ------
        ValueError
            If no driver is provided either as parameter or in __init__.
        adbc_driver_manager.ProgrammingError
            If the driver cannot be loaded or the connection fails.
        '''
        # Use parameter if provided, otherwise fall back to instance attribute
        _driver = driver or self.driver
        _uri = uri or self.uri
        
        if _driver is None:
            raise ValueError(
                "driver must be provided either in __init__ or as a parameter"
            )
        
        if _uri:
            kwargs["uri"] = _uri
            
        return adbc_driver_manager.dbapi.connect(driver=_driver, **kwargs)

    def get_query(
        self,
        conn,
        query: str | Path
    ) -> pl.DataFrame:
        '''
        Execute a SQL query against a database and return results as a Polars DataFrame.

        Parameters
        ----------
        conn
            An open database connection (ODBC, ADBC, or Snowflake). 
            Ignored if self.uri is configured (uses URI-based connection instead).
        query : str or Path
            SQL query text or path to a .sql file.
        
        Returns
        -------
        pl.DataFrame 
            Query results as a Polars DataFrame.
        
        Raises
        ------
        FileNotFoundError
            If query is a file path that doesn't exist.
        OSError
            If query file cannot be read.
        Exception
            Database/driver errors raised during query execution.
        
        Examples
        --------
        Execute a SQL string:
        
        >>> dbi = DBI(connection_type='odbc', odbc_name='MyDB')
        >>> conn = dbi.connectODBC()
        >>> df = dbi.get_query(conn, "SELECT * FROM users WHERE active = 1")
        
        Execute from a SQL file:
        
        >>> df = dbi.get_query(conn, Path("queries/monthly_report.sql"))
        '''
        sql = utilities.read_sql(query)

        # Use ADBC URI method if configured, otherwise use standard connection
        if self.uri:
            return pl.read_database_uri(query=sql, uri=self.uri)
        
        return pl.read_database(query=sql, connection=conn)
    
    def close_snowflake(self) -> None:
        '''
        Close the cached Snowflake connection if one exists.
        
        This is useful for explicitly releasing resources when done with database operations.
        '''
        if self._snowflake_conn is not None:
            try:
                self._snowflake_conn.close()
            except Exception:
                pass
            finally:
                self._snowflake_conn = None

            
