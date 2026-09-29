import asyncio
from surrealengine.document import Document
from surrealengine.fields import StringField, ReferenceField, IncomingReferenceField, ComputedField, SetField
from surrealengine.schema import generate_schema_statements_from_module
import test_v3_0_0_schema  # Import self to generate schema

class Comment(Document):
    text = StringField()
    author = IncomingReferenceField('User')

class User(Document):
    name = StringField()
    comments = ReferenceField(Comment, reference=True)
    tags = SetField(StringField())
    score = ComputedField("{ rating * 10 }", field_type=StringField())

def test_schema_generation():
    statements = generate_schema_statements_from_module("test_v3_0_0_schema")
    
    user_statements = statements.get('User', [])
    comment_statements = statements.get('Comment', [])
    
    user_sql = "\n".join(user_statements)
    comment_sql = "\n".join(comment_statements)
    
    print("User Table Schema:")
    print(user_sql)
    print("\nComment Table Schema:")
    print(comment_sql)
    
    assert "REFERENCE" in user_sql, "REFERENCE constraint should be applied to comments"
    assert "set<" in user_sql, "Sets must use the native set<...> type"
    assert "VALUE $value.distinct()" not in user_sql, (
        "Native set types are deduplicated by SurrealDB 3.x itself; "
        "$value.distinct() was removed for the set type in 3.x"
    )
    assert "COMPUTED { rating * 10 }" in user_sql, "Computed fields must use COMPUTED clause"
    
    assert "COMPUTED <~user" in comment_sql, "Incoming references must use COMPUTED <~model"
    print("\nAll assertions passed!")

if __name__ == "__main__":
    test_schema_generation()
