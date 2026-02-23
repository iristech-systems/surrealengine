from typing import List, Optional

class Analyzer:
    """Base class for SurrealDB Text Analyzers.
    
    This class can be used to define custom tokenizers and filters for Full-Text Search.
    """
    def __init__(self, name: str, tokenizers: Optional[List[str]] = None, filters: Optional[List[str]] = None):
        self.name = name
        self.tokenizers = tokenizers or []
        self.filters = filters or []

    def to_sql(self) -> str:
        """Convert the Analyzer definition to a SurrealQL DEFINE ANALYZER query."""
        query_parts = [f"DEFINE ANALYZER {self.name}"]
        
        if self.tokenizers:
            query_parts.append(f"TOKENIZERS {','.join(self.tokenizers)}")
            
        if self.filters:
            query_parts.append(f"FILTERS {','.join(self.filters)}")
            
        return " ".join(query_parts)

# Pre-defined common analyzers for developer convenience

# Basic English Analyzer with Stemming
StandardEnglishAnalyzer = Analyzer(
    name="standard_english",
    tokenizers=["blank", "punct"],
    filters=["lowercase", "snowball(english)"]
)

# Autocomplete / Prefix matching Analyzer
AutocompleteAnalyzer = Analyzer(
    name="autocomplete",
    tokenizers=["blank", "punct"],
    filters=["lowercase", "edgengram(2, 10)"]
)

# Case-insensitive Exact Match Analyzer (No tokenization)
ExactMatchAnalyzer = Analyzer(
    name="exact_match",
    tokenizers=["blank"], 
    filters=["lowercase"]
)
