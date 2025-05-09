import surrealdb
from .schemaless import SurrealEngine

class ConnectionRegistry:
    """Global connection registry for SurrealDB."""

    _default_connection = None
    _connections = {}

    @classmethod
    def set_default_connection(cls, connection):
        """Set the default connection."""
        cls._default_connection = connection

    @classmethod
    def get_default_connection(cls):
        """Get the default connection."""
        if cls._default_connection is None:
            raise RuntimeError("No default connection has been set. Call set_default_connection() first.")
        return cls._default_connection

    @classmethod
    def add_connection(cls, name, connection):
        """Add a named connection."""
        cls._connections[name] = connection

    @classmethod
    def get_connection(cls, name):
        """Get a named connection."""
        if name not in cls._connections:
            raise KeyError(f"No connection named '{name}' exists.")
        return cls._connections[name]


class SurrealEngineConnection:
    """Connection manager for SurrealDB."""

    def __init__(self, url=None, namespace=None, database=None, username=None, password=None, name=None,
                 make_default=False):
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

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    @property
    def db(self):
        """Get dynamic table accessor."""
        return SurrealEngine(self)

    async def connect(self):
        """Connect to the database."""
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

    async def disconnect(self):
        """Disconnect from the database."""
        if self.client:
            await self.client.close()
            self.client = None

    async def transaction(self, coroutines):
        """Execute multiple operations in a transaction."""
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