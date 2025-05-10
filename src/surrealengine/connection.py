import surrealdb
from typing import Dict, Optional, Any, Type
from .schemaless import SurrealEngine

class ConnectionRegistry:
    """Global connection registry for SurrealDB.

    This class provides a centralized registry for managing database connections.
    It allows setting a default connection and registering named connections
    that can be retrieved throughout the application.

    Attributes:
        _default_connection: The default connection to use when none is specified
        _connections: Dictionary of named connections
    """

    _default_connection: Optional['SurrealEngineConnection'] = None
    _connections: Dict[str, 'SurrealEngineConnection'] = {}

    @classmethod
    def set_default_connection(cls, connection: 'SurrealEngineConnection') -> None:
        """Set the default connection.

        Args:
            connection: The connection to set as default
        """
        cls._default_connection = connection

    @classmethod
    def get_default_connection(cls) -> 'SurrealEngineConnection':
        """Get the default connection.

        Returns:
            The default connection

        Raises:
            RuntimeError: If no default connection has been set
        """
        if cls._default_connection is None:
            raise RuntimeError("No default connection has been set. Call set_default_connection() first.")
        return cls._default_connection

    @classmethod
    def add_connection(cls, name: str, connection: 'SurrealEngineConnection') -> None:
        """Add a named connection to the registry.

        Args:
            name: The name to register the connection under
            connection: The connection to register
        """
        cls._connections[name] = connection

    @classmethod
    def get_connection(cls, name: str) -> 'SurrealEngineConnection':
        """Get a named connection from the registry.

        Args:
            name: The name of the connection to retrieve

        Returns:
            The requested connection

        Raises:
            KeyError: If no connection with the given name exists
        """
        if name not in cls._connections:
            raise KeyError(f"No connection named '{name}' exists.")
        return cls._connections[name]


class SurrealEngineConnection:
    """Connection manager for SurrealDB.

    This class manages the connection to a SurrealDB database, providing methods
    for connecting, disconnecting, and executing transactions. It also provides
    access to the database through the db property.

    Attributes:
        url: The URL of the SurrealDB server
        namespace: The namespace to use
        database: The database to use
        username: The username for authentication
        password: The password for authentication
        client: The SurrealDB client instance
    """

    def __init__(self, url: Optional[str] = None, namespace: Optional[str] = None, 
                 database: Optional[str] = None, username: Optional[str] = None, 
                 password: Optional[str] = None, name: Optional[str] = None,
                 make_default: bool = False) -> None:
        """Initialize a new SurrealEngineConnection.

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
            ConnectionRegistry.add_connection(name, self)
        if make_default or name is None:
            ConnectionRegistry.set_default_connection(self)

    async def __aenter__(self) -> 'SurrealEngineConnection':
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
