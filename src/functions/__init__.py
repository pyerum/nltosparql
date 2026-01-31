"""Functions for NL-to-SPARQL conversion."""

from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult
from .search import (
    SearchEntityFunction,
    SearchPropertyFunction,
    ListTriplesFunction,
    ExecuteQueryFunction
)
from .answer import AnswerFunction, CancelFunction
from .discovery import (
    DiscoverPropertiesFunction,
    SearchPropertyByConceptFunction,
    GetPropertyDetailsFunction
)
from .exploration import (
    GetEntityPropertiesFunction,
    FindRelationshipPathsFunction,
    ExplorePropertyValuesFunction
)
from .examples import (
    GetSimilarExamplesFunction,
    GetPropertyPatternsFunction
)
from .registry import FunctionRegistry

__all__ = [
    # Base classes
    'BaseFunction',
    'FunctionDefinition',
    'FunctionParameter',
    'FunctionResult',
    'FunctionRegistry',
    
    # Search functions
    'SearchEntityFunction',
    'SearchPropertyFunction',
    'ListTriplesFunction',
    'ExecuteQueryFunction',
    
    # Answer functions
    'AnswerFunction',
    'CancelFunction',
    
    # Discovery functions
    'DiscoverPropertiesFunction',
    'SearchPropertyByConceptFunction',
    'GetPropertyDetailsFunction',
    
    # Exploration functions
    'GetEntityPropertiesFunction',
    'FindRelationshipPathsFunction',
    'ExplorePropertyValuesFunction',
    
    # Example functions
    'GetSimilarExamplesFunction',
    'GetPropertyPatternsFunction',
]
