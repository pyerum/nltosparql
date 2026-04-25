"""Function registry and factory for NL-to-SPARQL system."""

from .registry import FunctionRegistry
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult

# Import all functions
from .search import SearchEntityFunction, SearchPropertyFunction, ListTriplesFunction, ExecuteQueryFunction
from .discovery import DiscoverPropertiesFunction
from .exploration import (
    GetEntityPropertiesFunction,
    FindRelationshipPathsFunction,
    ExplorePropertyValuesFunction
)
from .answer import AnswerFunction

__all__ = [
    # Core classes
    'FunctionRegistry',
    'BaseFunction',
    'FunctionDefinition',
    'FunctionParameter',
    'FunctionResult',
    
    # Functions
    'SearchEntityFunction',
    'SearchPropertyFunction',
    'DiscoverPropertiesFunction',
    'GetEntityPropertiesFunction',
    'FindRelationshipPathsFunction',
    'ExplorePropertyValuesFunction',
    'AnswerFunction'
]
