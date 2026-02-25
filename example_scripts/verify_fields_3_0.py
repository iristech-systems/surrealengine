import asyncio
from typing import Dict, Any
from surrealengine import Document, StringField, IntField, DictField, DecimalField, SetField, OptionField, EmbeddedField
from surrealengine.schema import generate_schema_statements

class SubDoc(Document):
    name = StringField()

class TestModel(Document):
    # DictField should be object FLEXIBLE
    preferences = DictField()
    
    # Typed DictField
    metadata = DictField(field_type=StringField())
    
    # DecimalField should be decimal
    price = DecimalField()
    
    # SetField should be set<string>
    tags = SetField(StringField())
    
    # OptionField(DictField) should NOT have option<>
    optional_dict = OptionField(DictField())
    
    # OptionField(EmbeddedField) should NOT have option<>
    optional_doc = OptionField(EmbeddedField(SubDoc))
    
    # OptionField(StringField) SHOULD have option<>
    optional_str = OptionField(StringField())

    # Nested DictField
    nested_dict = DictField(schema={
        "key1": StringField(),
        "key2": IntField()
    })

    class Meta:
        collection = "test_model"

def verify():
    statements = generate_schema_statements(TestModel)
    for stmt in statements:
        print(stmt)
        
    # Assertions
    statements_str = "\n".join(statements)
    
    assert "preferences ON test_model TYPE object FLEXIBLE" in statements_str
    assert "price ON test_model TYPE decimal" in statements_str
    assert "tags ON test_model TYPE set<string>;" in statements_str # No VALUE clause
    assert "optional_dict ON test_model TYPE object FLEXIBLE" in statements_str
    assert "optional_doc ON test_model TYPE object" in statements_str
    assert "optional_str ON test_model TYPE option<string>" in statements_str
    
    # Recursive DictField checks
    assert "nested_dict ON test_model TYPE object FLEXIBLE" in statements_str
    assert "nested_dict.key1 ON test_model TYPE string" in statements_str
    assert "nested_dict.key2 ON test_model TYPE int" in statements_str
    
    print("\n✅ All schema assertions passed!")

if __name__ == "__main__":
    verify()
