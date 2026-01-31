"""Schema exploration functions for knowledge graphs."""

from typing import Dict, List, Optional, Any
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult
from ..sparql.qlever_client import QLeverClient


class GetEntityPropertiesFunction(BaseFunction):
    """Get all properties of an entity with their values."""
    
    def __init__(self):
        super().__init__(
            name="get_entity_properties",
            description="Get all properties of an entity with example values"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name",
                    required=True
                ),
                FunctionParameter(
                    name="entity",
                    type="string",
                    description="Entity IRI",
                    required=True
                ),
                FunctionParameter(
                    name="limit_per_property",
                    type="integer",
                    description="Maximum example values per property (default: 3)",
                    required=False
                ),
                FunctionParameter(
                    name="property_filter",
                    type="string",
                    description="Optional filter for property names/labels (e.g., 'label', 'description')",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        entity = kwargs.get("entity")
        limit_per_property = kwargs.get("limit_per_property", 3)
        property_filter = kwargs.get("property_filter")
        
        if not kg or not entity:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and entity"
            )
        
        try:
            # Get endpoint URL from config
            import yaml
            import os
            config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            endpoints = config.get('endpoints', {})
            endpoint_url = endpoints.get(kg)
            
            if not endpoint_url:
                return FunctionResult(
                    success=False,
                    error=f"Unknown knowledge graph: {kg}"
                )
            
            # First, get all distinct properties for the entity
            properties_query = f"""
            SELECT DISTINCT ?property (COUNT(?value) as ?value_count) WHERE {{
              <{entity}> ?property ?value .
            }}
            GROUP BY ?property
            ORDER BY DESC(?value_count)
            LIMIT 50
            """
            
            async with QLeverClient(endpoint_url) as client:
                # Get properties
                properties_result = await client.execute_query(properties_query)
                
                if not properties_result.success or not properties_result.results:
                    return FunctionResult(
                        success=True,
                        result={
                            'entity': entity,
                            'properties': [],
                            'total_properties': 0,
                            'message': 'No properties found for entity'
                        }
                    )
                
                # Get property details and example values for each property
                properties_with_details = []
                
                for prop_row in properties_result.results:
                    prop_uri = prop_row.get('property', '')
                    value_count = int(prop_row.get('value_count', '0')) if prop_row.get('value_count', '0').isdigit() else 0
                    
                    # Skip if property filter is specified and doesn't match
                    if property_filter:
                        # We'll check the label later after we fetch it
                        pass
                    
                    # Get property label
                    label_query = f"""
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    PREFIX schema: <http://schema.org/>
                    
                    SELECT ?label WHERE {{
                      <{prop_uri}> rdfs:label ?label .
                      FILTER(LANG(?label) = "en" || LANG(?label) = "")
                    }}
                    LIMIT 1
                    """
                    
                    label_result = await client.execute_query(label_query)
                    label = ''
                    if label_result.success and label_result.results:
                        label = label_result.results[0].get('label', '')
                    
                    # Apply property filter if specified
                    if property_filter and property_filter.lower() not in label.lower():
                        continue
                    
                    # Get example values
                    examples_query = f"""
                    SELECT ?value WHERE {{
                      <{entity}> <{prop_uri}> ?value .
                    }}
                    LIMIT {limit_per_property}
                    """
                    
                    examples_result = await client.execute_query(examples_query)
                    examples = []
                    if examples_result.success and examples_result.results:
                        for ex_row in examples_result.results:
                            examples.append(ex_row.get('value', ''))
                    
                    properties_with_details.append({
                        'property': prop_uri,
                        'label': label,
                        'value_count': value_count,
                        'examples': examples
                    })
                
                return FunctionResult(
                    success=True,
                    result={
                        'entity': entity,
                        'properties': properties_with_details,
                        'total_properties': len(properties_with_details)
                    }
                )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Get entity properties failed: {str(e)}"
            )


class FindRelationshipPathsFunction(BaseFunction):
    """Find relationship paths between two entities."""
    
    def __init__(self):
        super().__init__(
            name="find_relationship_paths",
            description="Find how two entities are connected in the knowledge graph"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name",
                    required=True
                ),
                FunctionParameter(
                    name="entity1",
                    type="string",
                    description="First entity IRI",
                    required=True
                ),
                FunctionParameter(
                    name="entity2",
                    type="string",
                    description="Second entity IRI",
                    required=True
                ),
                FunctionParameter(
                    name="max_path_length",
                    type="integer",
                    description="Maximum path length to search (default: 3)",
                    required=False
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of paths to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        entity1 = kwargs.get("entity1")
        entity2 = kwargs.get("entity2")
        max_path_length = kwargs.get("max_path_length", 3)
        limit = kwargs.get("limit", 10)
        
        if not kg or not entity1 or not entity2:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg, entity1, and entity2"
            )
        
        try:
            # Get endpoint URL from config
            import yaml
            import os
            config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            endpoints = config.get('endpoints', {})
            endpoint_url = endpoints.get(kg)
            
            if not endpoint_url:
                return FunctionResult(
                    success=False,
                    error=f"Unknown knowledge graph: {kg}"
                )
            
            # Build path finding query
            # This is a simplified path finding query - in production, you might want
            # a more sophisticated approach for large knowledge graphs
            path_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?path ?path_length WHERE {{
              {{
                # Direct connection
                SELECT (CONCAT(STR(?p1), " → ", STR(?o1)) as ?path) (1 as ?path_length) WHERE {{
                  <{entity1}> ?p1 ?o1 .
                  FILTER(?o1 = <{entity2}>)
                }}
                LIMIT {limit}
              }}
              UNION
              {{
                # Two-hop connection (if max_path_length >= 2)
                SELECT (CONCAT(STR(?p1), " → ", STR(?mid), " → ", STR(?p2)) as ?path) (2 as ?path_length) WHERE {{
                  <{entity1}> ?p1 ?mid .
                  ?mid ?p2 <{entity2}> .
                  FILTER(?mid != <{entity1}> && ?mid != <{entity2}>)
                }}
                LIMIT {limit}
              }}
            }}
            ORDER BY ?path_length
            LIMIT {limit}
            """
            
            # For longer paths, we'd need a more complex query
            # This is a simplified version for demonstration
            
            async with QLeverClient(endpoint_url) as client:
                result = await client.execute_query(path_query)
                
                if result.success:
                    paths = []
                    for row in result.results:
                        path = row.get('path', '')
                        path_length = int(row.get('path_length', '0')) if row.get('path_length', '0').isdigit() else 0
                        
                        paths.append({
                            'path': path,
                            'length': path_length
                        })
                    
                    # Also check for direct properties
                    direct_query = f"""
                    SELECT ?property ?label WHERE {{
                      <{entity1}> ?property <{entity2}> .
                      OPTIONAL {{
                        ?property rdfs:label ?label .
                        FILTER(LANG(?label) = "en" || LANG(?label) = "")
                      }}
                    }}
                    LIMIT 5
                    """
                    
                    direct_result = await client.execute_query(direct_query)
                    direct_connections = []
                    if direct_result.success and direct_result.results:
                        for d_row in direct_result.results:
                            direct_connections.append({
                                'property': d_row.get('property', ''),
                                'label': d_row.get('label', '')
                            })
                    
                    return FunctionResult(
                        success=True,
                        result={
                            'entity1': entity1,
                            'entity2': entity2,
                            'paths': paths,
                            'direct_connections': direct_connections,
                            'total_paths_found': len(paths)
                        }
                    )
                else:
                    return FunctionResult(
                        success=True,
                        result={
                            'entity1': entity1,
                            'entity2': entity2,
                            'paths': [],
                            'direct_connections': [],
                            'total_paths_found': 0,
                            'message': 'No paths found between entities'
                        }
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Find relationship paths failed: {str(e)}"
            )


class ExplorePropertyValuesFunction(BaseFunction):
    """Explore values of a property across the knowledge graph."""
    
    def __init__(self):
        super().__init__(
            name="explore_property_values",
            description="Explore example values and usage patterns of a property"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name",
                    required=True
                ),
                FunctionParameter(
                    name="property",
                    type="string",
                    description="Property IRI",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of examples to return (default: 10)",
                    required=False
                ),
                FunctionParameter(
                    name="value_type",
                    type="string",
                    description="Filter by value type: 'entity', 'literal', or 'any' (default: 'any')",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        property_uri = kwargs.get("property")
        limit = kwargs.get("limit", 10)
        value_type = kwargs.get("value_type", "any")
        
        if not kg or not property_uri:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and property"
            )
        
        try:
            # Get endpoint URL from config
            import yaml
            import os
            config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            endpoints = config.get('endpoints', {})
            endpoint_url = endpoints.get(kg)
            
            if not endpoint_url:
                return FunctionResult(
                    success=False,
                    error=f"Unknown knowledge graph: {kg}"
                )
            
            # Build query based on value type
            if value_type == "entity":
                value_filter = "FILTER(isIRI(?value))"
            elif value_type == "literal":
                value_filter = "FILTER(isLiteral(?value))"
            else:
                value_filter = ""
            
            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?subject ?value (COUNT(*) as ?usage_count) WHERE {{
              ?subject <{property_uri}> ?value .
              {value_filter}
            }}
            GROUP BY ?subject ?value
            ORDER BY DESC(?usage_count)
            LIMIT {limit}
            """
            
            # Also get statistics about the property
            stats_query = f"""
            SELECT 
              (COUNT(DISTINCT ?subject) as ?subject_count)
              (COUNT(DISTINCT ?value) as ?value_count)
              (COUNT(*) as ?total_uses)
            WHERE {{
              ?subject <{property_uri}> ?value .
            }}
            """
            
            async with QLeverClient(endpoint_url) as client:
                # Get examples
                examples_result = await client.execute_query(query)
                
                # Get statistics
                stats_result = await client.execute_query(stats_query)
                
                examples = []
                if examples_result.success and examples_result.results:
                    for row in examples_result.results:
                        examples.append({
                            'subject': row.get('subject', ''),
                            'value': row.get('value', ''),
                            'usage_count': int(row.get('usage_count', '1')) if row.get('usage_count', '1').isdigit() else 1
                        })
                
                stats = {}
                if stats_result.success and stats_result.results:
                    stats_row = stats_result.results[0]
                    stats = {
                        'subject_count': int(stats_row.get('subject_count', '0')) if stats_row.get('subject_count', '0').isdigit() else 0,
                        'value_count': int(stats_row.get('value_count', '0')) if stats_row.get('value_count', '0').isdigit() else 0,
                        'total_uses': int(stats_row.get('total_uses', '0')) if stats_row.get('total_uses', '0').isdigit() else 0
                    }
                
                return FunctionResult(
                    success=True,
                    result={
                        'property': property_uri,
                        'examples': examples,
                        'statistics': stats,
                        'value_type_filter': value_type
                    }
                )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Explore property values failed: {str(e)}"
            )
