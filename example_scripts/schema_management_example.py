import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from src.surrealengine import (
    Document, StringField, IntField, FloatField, BooleanField, DateTimeField,
    ListField, ReferenceField, create_connection, generate_schema_statements,
    generate_schema_statements_from_module
)


# Define document models with schema information
class Person(Document):
    """Person document model with basic information."""

    name = StringField(required=True, define_schema=True)
    email = StringField(required=True, define_schema=True)
    age = IntField(min_value=0, define_schema=True)
    active = BooleanField(default=True, define_schema=True)

    # Fields without define_schema=True won't be included in SCHEMALESS tables
    notes = StringField()

    class Meta:
        collection = "people"
        indexes = [
            {"name": "person_email_idx", "fields": ["email"], "unique": True},
            {"name": "person_name_idx", "fields": ["name"]}
        ]


class Address(Document):
    """Address document model."""

    street = StringField(required=True, define_schema=True)
    city = StringField(required=True, define_schema=True)
    state = StringField(define_schema=True)
    postal_code = StringField(define_schema=True)
    country = StringField(required=True, define_schema=True)

    # Reference to a person
    resident = ReferenceField(Person, define_schema=True)

    class Meta:
        collection = "addresses"
        indexes = [
            {"name": "address_resident_idx", "fields": ["resident"]}
        ]


class Organization(Document):
    """Organization document model."""

    name = StringField(required=True, define_schema=True)
    industry = StringField(define_schema=True)
    founded_year = IntField(define_schema=True)

    # List of members (references to Person)
    members = ListField(field_type=ReferenceField(Person), define_schema=True)

    class Meta:
        collection = "organizations"
        indexes = [
            {"name": "org_name_idx", "fields": ["name"], "unique": True}
        ]


async def main():
    # Connect to the database
    connection = create_connection(
        url="ws://db:8000/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True
    )

    await connection.connect()
    print("Connected to SurrealDB")

    try:
        # Generate schema statements for SCHEMAFULL tables
        print("\n=== SCHEMAFULL Schema Statements ===")

        # For Person model
        print("\nPerson Schema (SCHEMAFULL):")
        person_statements = generate_schema_statements(Person, schemafull=True)
        for stmt in person_statements:
            print(stmt)

        # For Address model
        print("\nAddress Schema (SCHEMAFULL):")
        address_statements = generate_schema_statements(Address, schemafull=True)
        for stmt in address_statements:
            print(stmt)

        # For Organization model
        print("\nOrganization Schema (SCHEMAFULL):")
        org_statements = generate_schema_statements(Organization, schemafull=True)
        for stmt in org_statements:
            print(stmt)

        # Generate schema statements for SCHEMALESS tables
        # Only fields with define_schema=True will be included
        print("\n=== SCHEMALESS Schema Statements ===")

        # For Person model
        print("\nPerson Schema (SCHEMALESS):")
        person_statements = generate_schema_statements(Person, schemafull=False)
        for stmt in person_statements:
            print(stmt)

        # For Address model
        print("\nAddress Schema (SCHEMALESS):")
        address_statements = generate_schema_statements(Address, schemafull=False)
        for stmt in address_statements:
            print(stmt)

        # For Organization model
        print("\nOrganization Schema (SCHEMALESS):")
        org_statements = generate_schema_statements(Organization, schemafull=False)
        for stmt in org_statements:
            print(stmt)

        # Create tables in the database
        print("\n=== Creating Tables in Database ===")

        # Create tables with SCHEMAFULL option
        await Person.create_table(connection, schemafull=True)
        await Address.create_table(connection, schemafull=True)
        await Organization.create_table(connection, schemafull=True)

        # Create indexes
        await Person.create_indexes(connection)
        await Address.create_indexes(connection)
        await Organization.create_indexes(connection)

        print("Successfully created all tables and indexes")

        # Create a person to test the schema
        person = Person(
            name="Jane Smith",
            email="jane.smith@example.com",
            age=35,
            notes="This field won't be in the schema for SCHEMALESS tables"
        )

        await person.save()
        print(f"\nCreated person: {person.name} (ID: {person.id})")

        # Create an address linked to the person
        address = Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            postal_code="12345",
            country="USA",
            resident=person
        )

        await address.save()
        print(f"Created address for {person.name}: {address.street}, {address.city}")

        # Create an organization with the person as a member
        org = Organization(
            name="Tech Innovations Inc.",
            industry="Technology",
            founded_year=2010,
            members=[person]
        )

        await org.save()
        print(f"Created organization: {org.name} with {person.name} as a member")

        # Retrieve the data to verify schema
        retrieved_person = await Person.objects.get(id=person.id)
        retrieved_address = await Address.objects.get(resident=person.id)
        retrieved_org = await Organization.objects.get(name="Tech Innovations Inc.")

        print("\n=== Verification of Schema ===")
        print(f"Retrieved person: {retrieved_person.name}, {retrieved_person.email}")
        print(f"Retrieved address: {retrieved_address.street}, {retrieved_address.city}")
        print(f"Retrieved organization: {retrieved_org.name}, {retrieved_org.industry}")

    finally:
        # Clean up - delete all created documents
        if 'org' in locals() and org.id:
            await org.delete()

        if 'address' in locals() and address.id:
            await address.delete()

        if 'person' in locals() and person.id:
            await person.delete()

        # Disconnect from the database
        await connection.disconnect()
        print("\nCleaned up and disconnected from SurrealDB")


# Run the async example
if __name__ == "__main__":
    asyncio.run(main())