"""Property discovery functions for exploring knowledge graph schemas."""

from typing import Dict, List, Optional, Any
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult
from ..sparql.qlever_client import QLeverClient


class DiscoverPropertiesFunction(BaseFunction):
    """Discover properties related to a concept for an entity."""
    
    def __init__(self):
        super().__init__(
            name="discover_properties",
            description="Discover properties related to a specific concept for a given entity"
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
                    name="concept",
                    type="string",
                    description="Concept to search for in property labels/descriptions (e.g., 'capital', 'population', 'birth date')",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of properties to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        entity = kwargs.get("entity")
        concept = kwargs.get("concept")
        limit = kwargs.get("limit", 10)
        
        # Convert limit to integer if it's a string
        if isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                limit = 10
        
        if not kg or not entity or not concept:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg, entity, and concept"
            )
        
        try:
            # For Wikidata, use the Wikidata Search API
            if kg == "wikidata":
                from ..sparql.wikidata_search_client import WikidataSearchClient
                
                async with WikidataSearchClient() as wikidata_client:
                    # Search for properties using Wikidata API
                    search_results = await wikidata_client.search_properties(
                        query=concept,
                        limit=limit,
                        language="en"
                    )
                    
                    if search_results:
                        # Get entity properties from QLever to check which have values
                        import yaml
                        import os
                        config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
                        with open(config_path, 'r') as f:
                            config = yaml.safe_load(f)
                        
                        endpoints = config.get('endpoints', {})
                        endpoint_url = endpoints.get(kg)
                        
                        entity_properties = []
                        if endpoint_url:
                            # Get properties that actually exist for this entity
                            entity_properties_query = f"""
                            SELECT DISTINCT ?property WHERE {{
                              <{entity}> ?property ?value .
                            }}
                            LIMIT 100
                            """
                            async with QLeverClient(endpoint_url) as client:
                                entity_props_result = await client.execute_query(entity_properties_query)
                                if entity_props_result.success and entity_props_result.results:
                                    entity_properties = [row.get('property', '') for row in entity_props_result.results]
                    
                        # Format results
                        discovered_properties = []
                        for result in search_results:
                            # Convert Wikidata ID to full URI
                            property_uri = f"http://www.wikidata.org/prop/direct/{result.id}"
                            
                            # Check if this property has values for the entity
                            has_values = property_uri in entity_properties
                            
                            discovered_properties.append({
                                'property': property_uri,
                                'wikidata_id': result.id,
                                'label': result.label,
                                'description': result.description or '',
                                'has_values_for_entity': has_values
                            })
                        
                        # Sort: properties with values for entity first, then by label
                        discovered_properties.sort(key=lambda x: (not x['has_values_for_entity'], x.get('label', '')))
                        
                        return FunctionResult(
                            success=True,
                            result={
                                'entity': entity,
                                'concept': concept,
                                'properties': discovered_properties[:limit],
                                'total_found': len(discovered_properties)
                            }
                        )
                    else:
                        return FunctionResult(
                            success=True,
                            result={
                                'entity': entity,
                                'concept': concept,
                                'properties': [],
                                'total_found': 0,
                                'message': 'No properties found matching the concept'
                            }
                        )
            
            # For other knowledge graphs, use SPARQL search
            else:
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
                
                # First, get properties that actually exist for this entity
                entity_properties_query = f"""
                SELECT DISTINCT ?property (COUNT(?value) as ?count) WHERE {{
                  <{entity}> ?property ?value .
                }}
                GROUP BY ?property
                ORDER BY DESC(?count)
                LIMIT 20
                """
                
                # Then search for property labels/descriptions matching the concept
                property_search_query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX schema: <http://schema.org/>
                
                SELECT DISTINCT ?property ?label ?description WHERE {{
                  {{
                    ?property rdfs:label ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property skos:altLabel ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property schema:name ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property rdfs:comment ?description .
                    FILTER(CONTAINS(LCASE(?description), LCASE("{concept}")))
                  }}
                  OPTIONAL {{ ?property rdfs:comment ?description . }}
                  FILTER(LANG(?label) = "en" || LANG(?label) = "" || LANG(?description) = "en" || LANG(?description) = "")
                }}
                LIMIT {limit}
                """
                
                async with QLeverClient(endpoint_url) as client:
                    # Get properties of the entity
                    entity_props_result = await client.execute_query(entity_properties_query)
                    
                    # Search for properties matching the concept
                    search_result = await client.execute_query(property_search_query)
                    
                    # Combine results
                    entity_properties = []
                    if entity_props_result.success and entity_props_result.results:
                        for row in entity_props_result.results:
                            prop = row.get('property', '')
                            count = row.get('count', '0')
                            entity_properties.append({
                                'property': prop,
                                'value_count': int(count) if count.isdigit() else 0,
                                'has_values_for_entity': True
                            })
                    
                    discovered_properties = []
                    if search_result.success and search_result.results:
                        for row in search_result.results:
                            prop = row.get('property', '')
                            label = row.get('label', '')
                            description = row.get('description', '')
                            
                            # Check if this property exists for the entity
                            has_values = any(p['property'] == prop for p in entity_properties)
                            
                            discovered_properties.append({
                                'property': prop,
                                'label': label,
                                'description': description,
                                'has_values_for_entity': has_values
                            })
                    
                    # Sort: properties with values for entity first, then by relevance
                    discovered_properties.sort(key=lambda x: (not x['has_values_for_entity'], x.get('label', '')))
                    
                    return FunctionResult(
                        success=True,
                        result={
                            'entity': entity,
                            'concept': concept,
                            'properties': discovered_properties[:limit],
                            'total_found': len(discovered_properties)
                        }
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Property discovery failed: {str(e)}"
            )


class SearchPropertyByConceptFunction(BaseFunction):
    """Search for properties by concept across the knowledge graph."""
    
    def __init__(self):
        super().__init__(
            name="search_property_by_concept",
            description="Search for properties with labels or descriptions matching a concept"
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
                    name="concept",
                    type="string",
                    description="Concept to search for (e.g., 'capital', 'population', 'author')",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of properties to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        concept = kwargs.get("concept")
        limit = kwargs.get("limit", 10)
        
        # Convert limit to integer if it's a string
        if isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                limit = 10
        
        if not kg or not concept:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and concept"
            )
        
        try:
            # For Wikidata, use the Wikidata Search API
            if kg == "wikidata":
                from ..sparql.wikidata_search_client import WikidataSearchClient
                
                async with WikidataSearchClient() as wikidata_client:
                    # Search for properties using Wikidata API
                    search_results = await wikidata_client.search_properties(
                        query=concept,
                        limit=limit,
                        language="en"
                    )
                    
                    if search_results:
                        properties = []
                        for result in search_results:
                            # Convert Wikidata ID to full URI
                            property_uri = f"http://www.wikidata.org/prop/direct/{result.id}"
                            
                            properties.append({
                                'property': property_uri,
                                'wikidata_id': result.id,
                                'label': result.label,
                                'description': result.description or '',
                            })
                        
                        return FunctionResult(
                            success=True,
                            result={
                                'concept': concept,
                                'properties': properties,
                                'total_found': len(properties)
                            }
                        )
                    else:
                        return FunctionResult(
                            success=True,
                            result={
                                'concept': concept,
                                'properties': [],
                                'total_found': 0,
                                'message': 'No properties found matching the concept'
                            }
                        )
            
            # For other knowledge graphs, use SPARQL search
            else:
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
                
                # Search for properties matching the concept
                query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX schema: <http://schema.org/>
                
                SELECT DISTINCT ?property ?label ?description (COUNT(?usage) as ?usage_count) WHERE {{
                  {{
                    ?property rdfs:label ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property skos:altLabel ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property schema:name ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{concept}")))
                  }} UNION {{
                    ?property rdfs:comment ?description .
                    FILTER(CONTAINS(LCASE(?description), LCASE("{concept}")))
                  }}
                  OPTIONAL {{ ?property rdfs:comment ?description . }}
                  OPTIONAL {{ ?s ?property ?o . BIND(1 as ?usage) }}
                  FILTER(LANG(?label) = "en" || LANG(?label) = "" || LANG(?description) = "en" || LANG(?description) = "")
                }}
                GROUP BY ?property ?label ?description
                ORDER BY DESC(?usage_count)
                LIMIT {limit}
                """
                
                async with QLeverClient(endpoint_url) as client:
                    result = await client.execute_query(query)
                    
                    if result.success and result.results:
                        properties = []
                        for row in result.results:
                            prop = row.get('property', '')
                            label = row.get('label', '')
                            description = row.get('description', '')
                            usage_count = row.get('usage_count', '0')
                            
                            properties.append({
                                'property': prop,
                                'label': label,
                                'description': description,
                                'usage_count': int(usage_count) if usage_count.isdigit() else 0
                            })
                        
                        return FunctionResult(
                            success=True,
                            result={
                                'concept': concept,
                                'properties': properties,
                                'total_found': len(properties)
                            }
                        )
                    else:
                        return FunctionResult(
                            success=True,
                            result={
                                'concept': concept,
                                'properties': [],
                                'total_found': 0,
                                'message': 'No properties found matching the concept'
                            }
                        )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Property search failed: {str(e)}"
            )


class GetPropertyDetailsFunction(BaseFunction):
    """Get detailed information about a property."""
    
    def __init__(self):
        super().__init__(
            name="get_property_details",
            description="Get detailed information about a property including domain, range, and description"
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
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        property_uri = kwargs.get("property")
        
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
            
            # Query for property details
            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX schema: <http://schema.org/>
            
            SELECT ?label ?description ?domain ?range ?type (COUNT(?s) as ?usage_count) WHERE {{
              <{property_uri}> rdfs:label ?label .
              OPTIONAL {{ <{property_uri}> rdfs:comment ?description . }}
              OPTIONAL {{ <{property_uri}> rdfs:domain ?domain . }}
              OPTIONAL {{ <{property_uri}> rdfs:range ?range . }}
              OPTIONAL {{ <{property_uri}> rdf:type ?type . }}
              OPTIONAL {{ ?s <{property_uri}> ?o . }}
              FILTER(LANG(?label) = "en" || LANG(?label) = "")
              FILTER(LANG(?description) = "en" || LANG(?description) = "")
            }}
            GROUP BY ?label ?description ?domain ?range ?type
            LIMIT 1
            """
            
            # Also get example values
            example_query = f"""
            SELECT ?subject ?object WHERE {{
              ?subject <{property_uri}> ?object .
            }}
            LIMIT 5
            """
            
            async with QLeverClient(endpoint_url) as client:
                # Get property details
                details_result = await client.execute_query(query)
                
                # Get example values
                example_result = await client.execute_query(example_query)
                
                if details_result.success and details_result.results:
                    row = details_result.results[0]
                    
                    details = {
                        'property': property_uri,
                        'label': row.get('label', ''),
                        'description': row.get('description', ''),
                        'domain': row.get('domain', ''),
                        'range': row.get('range', ''),
                        'type': row.get('type', ''),
                        'usage_count': int(row.get('usage_count', '0')) if row.get('usage_count', '0').isdigit() else 0
                    }
                    
                    # Add examples if available
                    examples = []
                    if example_result.success and example_result.results:
                        for ex_row in example_result.results:
                            examples.append({
                                'subject': ex_row.get('subject', ''),
                                'object': ex_row.get('object', '')
                            })
                    
                    details['examples'] = examples
                    
                    return FunctionResult(
                        success=True,
                        result=details
                    )
                else:
                    return FunctionResult(
                        success=False,
                        error=f"Could not retrieve details for property: {property_uri}"
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Get property details failed: {str(e)}"
            )
