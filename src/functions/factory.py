"""Factory for creating function registries for different knowledge graphs."""

from typing import Dict, Optional
from .registry import FunctionRegistry
from .base import BaseFunction

# Import all available functions
from .search import SearchEntityFunction, SearchPropertyFunction, ListTriplesFunction, ExecuteQueryFunction
from .discovery import DiscoverPropertiesFunction
from .exploration import (
    GetEntityPropertiesFunction,
    FindRelationshipPathsFunction,
    ExplorePropertyValuesFunction
)
from .answer import AnswerFunction


class FunctionRegistryFactory:
    """Factory for creating function registries for different knowledge graphs."""
    
    def __init__(self):
        # Cache for created registries
        self._registry_cache: Dict[str, FunctionRegistry] = {}
        
        # Map of knowledge graph names to their specific function sets
        self._kg_function_sets = {
            'wikidata': self._create_wikidata_functions,
            'generic': self._create_generic_functions,
        }
    
    def _create_wikidata_functions(self) -> Dict[str, BaseFunction]:
        """Create functions optimized for Wikidata."""
        return {
            'search_entity': SearchEntityFunction(),
            'search_property': SearchPropertyFunction(),
            'list_triples': ListTriplesFunction(),
            'execute_query': ExecuteQueryFunction(),
            'discover_properties': DiscoverPropertiesFunction(),
            'get_entity_properties': GetEntityPropertiesFunction(),
            'find_relationship_paths': FindRelationshipPathsFunction(),
            'explore_property_values': ExplorePropertyValuesFunction(),
            'answer': AnswerFunction(),
        }
    
    def _create_generic_functions(self) -> Dict[str, BaseFunction]:
        """Create generic functions for any SPARQL endpoint."""
        # For now, use the same functions as Wikidata but they'll work generically
        # In the future, we could create specialized generic versions
        return self._create_wikidata_functions()
    
    def create_registry(self, kg_name: str = "wikidata") -> FunctionRegistry:
        """
        Create a function registry for a specific knowledge graph.
        
        Args:
            kg_name: Name of the knowledge graph (e.g., "wikidata", "dbpedia")
            
        Returns:
            FunctionRegistry configured for the specified knowledge graph
        """
        # Check cache first
        if kg_name in self._registry_cache:
            return self._registry_cache[kg_name]
        
        # Get the appropriate function creator
        if kg_name in self._kg_function_sets:
            function_creator = self._kg_function_sets[kg_name]
        else:
            # Default to generic for unknown knowledge graphs
            function_creator = self._kg_function_sets['generic']
        
        # Create registry and register functions
        registry = FunctionRegistry(kg_name=kg_name)
        functions = function_creator()
        
        for name, function in functions.items():
            registry.register(function)
        
        # Cache the registry
        self._registry_cache[kg_name] = registry
        
        return registry
    
    def get_available_kg_names(self) -> list:
        """Get list of available knowledge graph names."""
        return list(self._kg_function_sets.keys())
    
    def clear_cache(self) -> None:
        """Clear the registry cache."""
        self._registry_cache.clear()


# Global factory instance
_factory_instance: Optional[FunctionRegistryFactory] = None


def get_function_registry_factory() -> FunctionRegistryFactory:
    """Get the global function registry factory instance."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = FunctionRegistryFactory()
    return _factory_instance


def create_registry(kg_name: str = "wikidata") -> FunctionRegistry:
    """
    Convenience function to create a registry for a knowledge graph.
    
    Args:
        kg_name: Name of the knowledge graph
        
    Returns:
        FunctionRegistry configured for the specified knowledge graph
    """
    factory = get_function_registry_factory()
    return factory.create_registry(kg_name)