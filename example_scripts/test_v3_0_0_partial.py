import asyncio
from surrealengine.document import Document
from surrealengine.fields import StringField, ReferenceField, IncomingReferenceField, ComputedField, SetField
from surrealengine.schema import generate_schema_statements_from_module
import test_v3_0_0_partial  # Import self to generate schema

class Comment(Document):
    # Standard field, NO schema generated
    text = StringField()
    # Explicit schema defined for the incoming reference!
    author = IncomingReferenceField('User', define_schema=True)

class User(Document):
    # Standard field, NO schema generated
    name = StringField()
    # Explicit schema defined for the outgoing reference!
    comments = ReferenceField(Comment, reference=True, define_schema=True)

def test_schema_generation():
    statements = generate_schema_statements_from_module("test_v3_0_0_partial", schemafull=False)
    
    user_statements = statements.get('User', [])
    comment_statements = statements.get('Comment', [])
    
    user_sql = "\n".join(user_statements)
    comment_sql = "\n".join(comment_statements)
    
    print("User Table Schema (SCHEMALESS):")
    print(user_sql)
    print("\nComment Table Schema (SCHEMALESS):")
    print(comment_sql)
    
    assert "DEFINE TABLE user SCHEMALESS" in user_sql
    assert "DEFINE FIELD name" not in user_sql
    assert "DEFINE FIELD comments" in user_sql
    
    assert "DEFINE TABLE comment SCHEMALESS" in comment_sql
    assert "DEFINE FIELD text" not in comment_sql
    assert "DEFINE FIELD author ON comment TYPE any COMPUTED <~user" in comment_sql
    
    print("\nAll assertions passed for partial schemas!")

if __name__ == "__main__":
    test_schema_generation()
