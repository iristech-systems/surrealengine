import surrealdb
from typing import Dict, Optional, Any, Type, Union, Protocol, runtime_checkable
from abc import ABC, abstractmethod
from .schemaless import SurrealEngine

@runtime_checkable
class BaseSurrealEngineConnection(Protocol):
    """Protocol defining the interface for SurrealDB connections.

    This protocol defines the common interface that both synchronous and
    asynchronous connections must implement.
    """
    url: Optional[str]
    namespace: Optional[str]
    database: Optional[str]
    username: Optional[str]
    password: Optional[str]
    client: Any

    @property
    def db(self) -> SurrealEngine:
        """Get dynamic table accessor."""
        ...

class ConnectionRegistry:
    """Global connection registry for SurrealDB.

    This class provides a centralized registry for managing database connections.
    It allows setting a default connection and registering named connections
    that can be retrieved throughout the application.

    Attributes:
        _default_async_connection: The default async connection to use when none is specified
        _default_sync_connection: The default sync connection to use when none is specified
        _async_connections: Dictionary of named async connections
        _sync_connections: Dictionary of named sync connections
    """

    _default_async_connection: Optional['SurrealEngineAsyncConnection'] = None
    _default_sync_connection: Optional['SurrealEngineSyncConnection'] = None
    _async_connections: Dict[str, 'SurrealEngineAsyncConnection'] = {}
    _sync_connections: Dict[str, 'SurrealEngineSyncConnection'] = {}

    @classmethod
    def set_default_async_connection(cls, connection: 'SurrealEngineAsyncConnection') -> None:
        """Set the default async connection.

        Args:
            connection: The async connection to set as default
        """
        cls._default_async_connection = connection

    @classmethod
    def set_default_sync_connection(cls, connection: 'SurrealEngineSyncConnection') -> None:
        """Set the default sync connection.

        Args:
            connection: The sync connection to set as default
        """
        cls._default_sync_connection = connection

    @classmethod
    def set_default_connection(cls, connection: Union['SurrealEngineAsyncConnection', 'SurrealEngineSyncConnection']) -> None:
        """Set the default connection based on its type.

        Args:
            connection: The connection to set as default
        """
        if isinstance(connection, SurrealEngineAsyncConnection):
            cls.set_default_async_connection(connection)
        elif isinstance(connection, SurrealEngineSyncConnection):
            cls.set_default_sync_connection(connection)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")

    @classmethod
    def get_default_async_connection(cls) -> 'SurrealEngineAsyncConnection':
        """Get the default async connection.

        Returns:
            The default async connection

        Raises:
            RuntimeError: If no default async connection has been set
        """
        if cls._default_async_connection is None:
            raise RuntimeError("No default async connection has been set. Call set_default_async_connection() first.")
        return cls._default_async_connection

    @classmethod
    def get_default_sync_connection(cls) -> 'SurrealEngineSyncConnection':
        """Get the default sync connection.

        Returns:
            The default sync connection

        Raises:
            RuntimeError: If no default sync connection has been set
        """
        if cls._default_sync_connection is None:
            raise RuntimeError("No default sync connection has been set. Call set_default_sync_connection() first.")
        return cls._default_sync_connection

    @classmethod
    def get_default_connection(cls, async_mode: bool = True) -> Union['SurrealEngineAsyncConnection', 'SurrealEngineSyncConnection']:
        """Get the default connection based on the mode.

        Args:
            async_mode: Whether to get the async or sync connection

        Returns:
            The default connection of the requested type

        Raises:
            RuntimeError: If no default connection of the requested type has been set
        """
        if async_mode:
            return cls.get_default_async_connection()
        else:
            return cls.get_default_sync_connection()

    @classmethod
    def add_async_connection(cls, name: str, connection: 'SurrealEngineAsyncConnection') -> None:
        """Add a named async connection to the registry.

        Args:
            name: The name to register the connection under
            connection: The async connection to register
        """
        cls._async_connections[name] = connection

    @classmethod
    def add_sync_connection(cls, name: str, connection: 'SurrealEngineSyncConnection') -> None:
        """Add a named sync connection to the registry.

        Args:
            name: The name to register the connection under
            connection: The sync connection to register
        """
        cls._sync_connections[name] = connection

    @classmethod
    def add_connection(cls, name: str, connection: Union['SurrealEngineAsyncConnection', 'SurrealEngineSyncConnection']) -> None:
        """Add a named connection to the registry based on its type.

        Args:
            name: The name to register the connection under
            connection: The connection to register
        """
        if isinstance(connection, SurrealEngineAsyncConnection):
            cls.add_async_connection(name, connection)
        elif isinstance(connection, SurrealEngineSyncConnection):
            cls.add_sync_connection(name, connection)
        else:
            raise TypeError(f"Unsupported connection type: {type(connection)}")

    @classmethod
    def get_async_connection(cls, name: str) -> 'SurrealEngineAsyncConnection':
        """Get a named async connection from the registry.

        Args:
            name: The name of the async connection to retrieve

        Returns:
            The requested async connection

        Raises:
            KeyError: If no async connection with the given name exists
        """
        if name not in cls._async_connections:
            raise KeyError(f"No async connection named '{name}' exists.")
        return cls._async_connections[name]

    @classmethod
    def get_sync_connection(cls, name: str) -> 'SurrealEngineSyncConnection':
        """Get a named sync connection from the registry.

        Args:
            name: The name of the sync connection to retrieve

        Returns:
            The requested sync connection

        Raises:
            KeyError: If no sync connection with the given name exists
        """
        if name not in cls._sync_connections:
            raise KeyError(f"No sync connection named '{name}' exists.")
        return cls._sync_connections[name]

    @classmethod
    def get_connection(cls, name: str, async_mode: bool = True) -> Union['SurrealEngineAsyncConnection', 'SurrealEngineSyncConnection']:
        """Get a named connection from the registry based on the mode.

        Args:
            name: The name of the connection to retrieve
            async_mode: Whether to get an async or sync connection

        Returns:
            The requested connection of the requested type

        Raises:
            KeyError: If no connection of the requested type with the given name exists
        """
        if async_mode:
            return cls.get_async_connection(name)
        else:
            return cls.get_sync_connection(name)


class SurrealEngineAsyncConnection:
    """Asynchronous connection manager for SurrealDB.

    This class manages the asynchronous connection to a SurrealDB database, providing methods
    for connecting, disconnecting, and executing transactions. It also provides
    access to the database through the db property.

    Attributes:
        url: The URL of the SurrealDB server
        namespace: The namespace to use
        database: The database to use
        username: The username for authentication
        password: The password for authentication
        client: The SurrealDB async client instance
    """

    def __init__(self, url: Optional[str] = None, namespace: Optional[str] = None, 
                 database: Optional[str] = None, username: Optional[str] = None, 
                 password: Optional[str] = None, name: Optional[str] = None,
                 make_default: bool = False) -> None:
        """Initialize a new SurrealEngineAsyncConnection.

        Args:
            url: The URL of the SurrealDB server
            namespace: The namespace to use
            database: The database to use
            username: The username for authentication
            password: The password for authentication
            name: The name to register this connection under in the registry
            make_default: Whether to set this connection as the default
        """
        self.url = url
        self.namespace = namespace
        self.database = database
        self.username = username
        self.password = password
        self.client = None

        if name:
            ConnectionRegistry.add_async_connection(name, self)
        if make_default or name is None:
            ConnectionRegistry.set_default_async_connection(self)

    async def __aenter__(self) -> 'SurrealEngineAsyncConnection':
        """Enter the async context manager.

        Returns:
            The connection instance
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], 
                        exc_val: Optional[BaseException], 
                        exc_tb: Optional[Any]) -> None:
        """Exit the async context manager.

        Args:
            exc_type: The exception type, if an exception was raised
            exc_val: The exception value, if an exception was raised
            exc_tb: The exception traceback, if an exception was raised
        """
        await self.disconnect()

    @property
    def db(self) -> SurrealEngine:
        """Get dynamic table accessor.

        Returns:
            A SurrealEngine instance for accessing tables dynamically
        """
        return SurrealEngine(self)

    async def connect(self) -> Any:
        """Connect to the database.

        This method creates a new client if one doesn't exist, signs in if
        credentials are provided, and sets the namespace and database.

        Returns:
            The SurrealDB client instance
        """
        if not self.client:
            # Create the client directly
            self.client = surrealdb.AsyncSurreal(self.url)

            # Sign in if credentials are provided
            if self.username and self.password:
                await self.client.signin({"username": self.username, "password": self.password})

            # Use namespace and database
            if self.namespace and self.database:
                await self.client.use(self.namespace, self.database)

        return self.client

    async def disconnect(self) -> None:
        """Disconnect from the database.

        This method closes the client connection if one exists.
        """
        if self.client:
            await self.client.close()
            self.client = None

    async def transaction(self, coroutines: list) -> list:
        """Execute multiple operations in a transaction.

        This method executes a list of coroutines within a transaction,
        committing the transaction if all operations succeed or canceling
        it if any operation fails.

        Args:
            coroutines: List of coroutines to execute in the transaction

        Returns:
            List of results from the coroutines

        Raises:
            Exception: If any operation in the transaction fails
        """
        await self.client.query("BEGIN TRANSACTION;")
        try:
            results = []
            for coro in coroutines:
                result = await coro
                results.append(result)
            await self.client.query("COMMIT TRANSACTION;")
            return results
        except Exception as e:
            await self.client.query("CANCEL TRANSACTION;")
            raise e


def create_connection(url: Optional[str] = None, namespace: Optional[str] = None, 
                  database: Optional[str] = None, username: Optional[str] = None, 
                  password: Optional[str] = None, name: Optional[str] = None,
                  make_default: bool = False, async_mode: bool = True) -> Union['SurrealEngineAsyncConnection', 'SurrealEngineSyncConnection']:
    """Factory function to create a connection of the appropriate type.

    Args:
        url: The URL of the SurrealDB server
        namespace: The namespace to use
        database: The database to use
        username: The username for authentication
        password: The password for authentication
        name: The name to register this connection under in the registry
        make_default: Whether to set this connection as the default
        async_mode: Whether to create an async or sync connection

    Returns:
        A connection of the requested type
    """
    if async_mode:
        return SurrealEngineAsyncConnection(url, namespace, database, username, password, name, make_default)
    else:
        return SurrealEngineSyncConnection(url, namespace, database, username, password, name, make_default)


class SurrealEngineSyncConnection:
    """Synchronous connection manager for SurrealDB.

    This class manages the synchronous connection to a SurrealDB database, providing methods
    for connecting, disconnecting, and executing transactions. It also provides
    access to the database through the db property.

    Attributes:
        url: The URL of the SurrealDB server
        namespace: The namespace to use
        database: The database to use
        username: The username for authentication
        password: The password for authentication
        client: The SurrealDB sync client instance
    """

    def __init__(self, url: Optional[str] = None, namespace: Optional[str] = None, 
                 database: Optional[str] = None, username: Optional[str] = None, 
                 password: Optional[str] = None, name: Optional[str] = None,
                 make_default: bool = False) -> None:
        """Initialize a new SurrealEngineSyncConnection.

        Args:
            url: The URL of the SurrealDB server
            namespace: The namespace to use
            database: The database to use
            username: The username for authentication
            password: The password for authentication
            name: The name to register this connection under in the registry
            make_default: Whether to set this connection as the default
        """
        self.url = url
        self.namespace = namespace
        self.database = database
        self.username = username
        self.password = password
        self.client = None

        if name:
            ConnectionRegistry.add_sync_connection(name, self)
        if make_default or name is None:
            ConnectionRegistry.set_default_sync_connection(self)

    def __enter__(self) -> 'SurrealEngineSyncConnection':
        """Enter the sync context manager.

        Returns:
            The connection instance
        """
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], 
                exc_val: Optional[BaseException], 
                exc_tb: Optional[Any]) -> None:
        """Exit the sync context manager.

        Args:
            exc_type: The exception type, if an exception was raised
            exc_val: The exception value, if an exception was raised
            exc_tb: The exception traceback, if an exception was raised
        """
        self.disconnect()

    @property
    def db(self) -> SurrealEngine:
        """Get dynamic table accessor.

        Returns:
            A SurrealEngine instance for accessing tables dynamically
        """
        return SurrealEngine(self)

    def connect(self) -> Any:
        """Connect to the database.

        This method creates a new client if one doesn't exist, signs in if
        credentials are provided, and sets the namespace and database.

        Returns:
            The SurrealDB client instance
        """
        if not self.client:
            # Create the client directly
            self.client = surrealdb.Surreal(self.url)

            # Sign in if credentials are provided
            if self.username and self.password:
                self.client.signin({"username": self.username, "password": self.password})

            # Use namespace and database
            if self.namespace and self.database:
                self.client.use(self.namespace, self.database)

        return self.client

    def disconnect(self) -> None:
        """Disconnect from the database.

        This method closes the client connection if one exists.
        """
        if self.client:
            self.client.close()
            self.client = None

    def transaction(self, callables: list) -> list:
        """Execute multiple operations in a transaction.

        This method executes a list of callables within a transaction,
        committing the transaction if all operations succeed or canceling
        it if any operation fails.

        Args:
            callables: List of callables to execute in the transaction

        Returns:
            List of results from the callables

        Raises:
            Exception: If any operation in the transaction fails
        """
        self.client.query("BEGIN TRANSACTION;")
        try:
            results = []
            for func in callables:
                result = func()
                results.append(result)
            self.client.query("COMMIT TRANSACTION;")
            return results
        except Exception as e:
            self.client.query("CANCEL TRANSACTION;")
            raise e
