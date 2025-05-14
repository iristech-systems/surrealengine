import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.surrealengine import Document, StringField, IntField, FloatField, ListField, DictField, generate_schema_statements

# Define a Document class with some fields marked with define_schema=True
class Product(Document):
    # This field will be defined in the schema even for SCHEMALESS tables
    name = StringField(required=True, define_schema=True)
    
    # This field will be defined in the schema even for SCHEMALESS tables
    price = FloatField(define_schema=True)
    
    # This field won't be defined in the schema for SCHEMALESS tables
    description = StringField()
    
    # Other fields that won't be defined in the schema for SCHEMALESS tables
    tags = ListField()
    metadata = DictField()

# Generate schema statements for SCHEMAFULL table
print("SCHEMAFULL statements:")
statements = generate_schema_statements(Product, schemafull=True)
for stmt in statements:
    print(stmt)

print("\n" + "-" * 50 + "\n")

# Generate schema statements for SCHEMALESS table
# Only fields with define_schema=True should be included
print("SCHEMALESS statements:")
statements = generate_schema_statements(Product, schemafull=False)
for stmt in statements:
    print(stmt)