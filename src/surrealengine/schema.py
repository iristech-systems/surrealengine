"""
Schema management utilities for SurrealEngine.

This module provides utilities for discovering document classes, generating
schema statements, and creating database tables from Python modules. It supports
both synchronous and asynchronous operations for schema management.

Functions:
    get_document_classes: Discover document classes in a module
    create_tables_from_module: Create database tables from document classes
    generate_schema_statements: Generate SQL schema statements
    generate_schema_statements_from_module: Generate schema from a module
"""
import inspect
import importlib
from typing import Any, Dict, List, Optional, Type, Union, Set

from .document import Document


def get_document_classes(module_name: str) -> List[Type[Document]]:
    """Get all Document classes defined in a module.

    Args:
        module_name: The name of the module to search

    Returns:
        A list of Document classes defined in the module
    """
    module = importlib.import_module(module_name)
    document_classes = []

    for name, obj in inspect.getmembers(module):
        # Check if it's a class and a subclass of Document (but not Document itself)
        if (inspect.isclass(obj) and 
            issubclass(obj, Document) and 
            obj.__module__ == module_name and
            obj != Document):
            document_classes.append(obj)

    return document_classes


async def create_tables_from_module(module_name: str, connection: Optional[Any] = None, 
                                   schemafull: bool = True) -> None:
    """Create tables for all Document classes in a module asynchronously.

    Args:
        module_name: The name of the module containing Document classes
        connection: Optional connection to use
        schemafull: Whether to create SCHEMAFULL tables (default: True)
    """
    document_classes = get_document_classes(module_name)

    for doc_class in document_classes:
        await doc_class.create_table(connection=connection, schemafull=schemafull)


def create_tables_from_module_sync(module_name: str, connection: Optional[Any] = None,
                                  schemafull: bool = True) -> None:
    """Create tables for all Document classes in a module synchronously.

    Args:
        module_name: The name of the module containing Document classes
        connection: Optional connection to use
        schemafull: Whether to create SCHEMAFULL tables (default: True)
    """
    document_classes = get_document_classes(module_name)

    for doc_class in document_classes:
        doc_class.create_table_sync(connection=connection, schemafull=schemafull)


def generate_schema_statements(document_class: Type[Document], schemafull: bool = True) -> List[str]:
    """Generate SurrealDB schema statements for a Document class.

    This function generates DEFINE TABLE and DEFINE FIELD statements for a Document class
    without executing them. This is useful for generating schema migration scripts.

    Args:
        document_class: The Document class to generate statements for
        schemafull: Whether to generate SCHEMAFULL tables (default: True)

    Returns:
        A list of SurrealDB schema statements
    """
    statements = []
    collection_name = document_class._get_collection_name()

    # Generate DEFINE TABLE statement
    schema_type = "SCHEMAFULL" if schemafull else "SCHEMALESS"
    table_stmt = f"DEFINE TABLE {collection_name} {schema_type}"

    # Add comment if available
    if document_class.__doc__:
        # Clean up docstring and escape single quotes
        doc = document_class.__doc__.strip().replace("'", "''")
        if doc:
            table_stmt += f" COMMENT '{doc}'"

    statements.append(table_stmt + ";")

    # Generate DEFINE FIELD statements if schemafull or if field is marked with define_schema=True
    for field_name, field in document_class._fields.items():
        # Skip id field as it's handled by SurrealDB
        if field_name == document_class._meta.get('id_field', 'id'):
            continue

        # Only define fields if schemafull or if field is explicitly marked for schema definition
        if schemafull or field.define_schema:
            field_type = document_class._get_field_type_for_surreal(field)
            field_stmt = f"DEFINE FIELD {field.db_field} ON {collection_name} TYPE {field_type}"

            # Add constraints
            if field.required:
                field_stmt += " ASSERT $value != NONE"

            # Add comment if available
            if hasattr(field, '__doc__') and field.__doc__:
                # Clean up docstring and escape single quotes
                doc = field.__doc__.strip().replace("'", "''")
                if doc:
                    field_stmt += f" COMMENT '{doc}'"

            statements.append(field_stmt + ";")

    return statements


def generate_schema_statements_from_module(module_name: str, schemafull: bool = True) -> Dict[str, List[str]]:
    """Generate SurrealDB schema statements for all Document classes in a module.

    Args:
        module_name: The name of the module containing Document classes
        schemafull: Whether to generate SCHEMAFULL tables (default: True)

    Returns:
        A dictionary mapping class names to lists of SurrealDB schema statements
    """
    document_classes = get_document_classes(module_name)
    schema_statements = {}

    for doc_class in document_classes:
        class_name = doc_class.__name__
        statements = generate_schema_statements(doc_class, schemafull=schemafull)
        schema_statements[class_name] = statements

    return schema_statements
