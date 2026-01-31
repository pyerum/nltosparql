"""Search functions for exploring knowledge graphs."""

import re
from typing import Dict, List, Optional, Any
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult
from ..sparql.qlever_client import QLeverClient


class SearchEntityFunction(BaseFunction):
    """Search for entities in a knowledge graph."""
    
    def __init__(self):
        super().__init__(
            name="search_entity",
            description="Search for entities (subjects or objects) in a knowledge graph"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name (e.g., 'wikidata', 'dblp', 'dbpedia')",
                    required=True
                ),
                FunctionParameter(
                    name="query",
                    type="string",
                    description="Search query for entities",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of results to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        query = kwargs.get("query")
        limit = kwargs.get("limit", 10)
        
        if not kg or not query:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and query"
            )
        
        try:
            # For Wikidata, use the Wikidata Search API
            if kg == "wikidata":
                from ..sparql.wikidata_search_client import WikidataSearchClient
                
                async with WikidataSearchClient() as wikidata_client:
                    # Search for entities
                    search_results = await wikidata_client.search_entities(
                        query=query,
                        limit=limit,
                        search_type="item"
                    )
                    
                    if search_results:
                        # Format results
                        formatted_results = []
                        for result in search_results:
                            # Convert Wikidata ID to full URI
                            entity_uri = f"http://www.wikidata.org/entity/{result.id}"
                            
                            formatted_results.append({
                                'entity': entity_uri,
                                'label': result.label,
                                'description': result.description,
                                'wikidata_id': result.id,
                                'url': result.url,
                                'concepturi': result.concepturi
                            })
                        
                        return FunctionResult(
                            success=True,
                            result={
                                'count': len(formatted_results),
                                'results': formatted_results,
                                'message': f'Found {len(formatted_results)} entities'
                            }
                        )
                    else:
                        return FunctionResult(
                            success=True,
                            result={
                                'count': 0,
                                'results': [],
                                'message': 'No entities found'
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
                
                # Generic search for other knowledge graphs
                search_query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX schema: <http://schema.org/>
                
                SELECT DISTINCT ?entity ?label ?description WHERE {{
                  {{
                    ?entity rdfs:label ?label .
                    FILTER(REGEX(LCASE(?label), LCASE("{query}")))
                  }} UNION {{
                    ?entity skos:altLabel ?label .
                    FILTER(REGEX(LCASE(?label), LCASE("{query}")))
                  }} UNION {{
                    ?entity schema:name ?label .
                    FILTER(REGEX(LCASE(?label), LCASE("{query}")))
                  }}
                  OPTIONAL {{ ?entity schema:description ?description . }}
                  FILTER(LANG(?label) = "en" || LANG(?label) = "")
                }}
                LIMIT {limit}
                """
                
                async with QLeverClient(endpoint_url) as client:
                    result = await client.execute_query(search_query)
                    
                    if result.success and result.results:
                        # Format results
                        formatted_results = []
                        for row in result.results:
                            entity = row.get('entity', '')
                            label = row.get('label', '')
                            description = row.get('description', '')
                            
                            formatted_results.append({
                                'entity': entity,
                                'label': label,
                                'description': description
                            })
                        
                        return FunctionResult(
                            success=True,
                            result={
                                'count': len(formatted_results),
                                'results': formatted_results
                            }
                        )
                    else:
                        return FunctionResult(
                            success=True,
                            result={
                                'count': 0,
                                'results': [],
                                'message': 'No entities found'
                            }
                        )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )


class SearchPropertyFunction(BaseFunction):
    """Search for properties in a knowledge graph."""
    
    def __init__(self):
        super().__init__(
            name="search_property",
            description="Search for properties (predicates) in a knowledge graph"
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
                    name="query",
                    type="string",
                    description="Search query for properties",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of results to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        query = kwargs.get("query")
        limit = kwargs.get("limit", 10)
        
        if not kg or not query:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and query"
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
            
            # Search for properties
            search_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            
            SELECT DISTINCT ?property ?label ?description WHERE {{
              {{
                ?property rdfs:label ?label .
                FILTER(CONTAINS(LCASE(?label), LCASE("{query}")))
              }} UNION {{
                ?property skos:altLabel ?label .
                FILTER(CONTAINS(LCASE(?label), LCASE("{query}")))
              }}
              OPTIONAL {{ ?property rdfs:comment ?description . }}
              FILTER(LANG(?label) = "en" || LANG(?label) = "")
              FILTER(STRSTARTS(STR(?property), "http://www.w3.org/1999/02/22-rdf-syntax-ns#") = false)
            }}
            LIMIT {limit}
            """
            
            async with QLeverClient(endpoint_url) as client:
                result = await client.execute_query(search_query)
                
                if result.success and result.results:
                    # Format results
                    formatted_results = []
                    for row in result.results:
                        property_uri = row.get('property', '')
                        label = row.get('label', '')
                        description = row.get('description', '')
                        
                        formatted_results.append({
                            'property': property_uri,
                            'label': label,
                            'description': description
                        })
                    
                    return FunctionResult(
                        success=True,
                        result={
                            'count': len(formatted_results),
                            'results': formatted_results
                        }
                    )
                else:
                    return FunctionResult(
                        success=True,
                        result={
                            'count': 0,
                            'results': [],
                            'message': 'No properties found'
                        }
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )


class ListTriplesFunction(BaseFunction):
    """List triples from a knowledge graph with constraints."""
    
    def __init__(self):
        super().__init__(
            name="list_triples",
            description="List triples from a knowledge graph with optional constraints"
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
                    name="subject",
                    type="string",
                    description="Subject IRI (optional)",
                    required=False
                ),
                FunctionParameter(
                    name="property",
                    type="string",
                    description="Property IRI (optional)",
                    required=False
                ),
                FunctionParameter(
                    name="object",
                    type="string",
                    description="Object IRI or literal (optional)",
                    required=False
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of triples to return (default: 10)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        subject = kwargs.get("subject")
        property_ = kwargs.get("property")
        object_ = kwargs.get("object")
        limit = kwargs.get("limit", 10)
        
        if not kg:
            return FunctionResult(
                success=False,
                error="Missing required parameter: kg"
            )
        
        # At least one constraint should be provided
        if not subject and not property_ and not object_:
            return FunctionResult(
                success=False,
                error="At least one of subject, property, or object must be provided"
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
            
            # Build SPARQL query with constraints
            where_clauses = []
            
            if subject:
                where_clauses.append(f"?s = <{subject}>")
            else:
                where_clauses.append("?s ?p ?o")
            
            if property_:
                where_clauses.append(f"?p = <{property_}>")
            
            if object_:
                # Check if object is an IRI or literal
                if object_.startswith("http://") or object_.startswith("https://"):
                    where_clauses.append(f"?o = <{object_}>")
                else:
                    where_clauses.append(f'?o = "{object_}"')
            
            where_clause = " . ".join(where_clauses)
            
            query = f"""
            SELECT ?s ?p ?o WHERE {{
              {where_clause}
            }}
            LIMIT {limit}
            """
            
            async with QLeverClient(endpoint_url) as client:
                result = await client.execute_query(query)
                
                if result.success:
                    # Format results
                    formatted_results = []
                    for row in result.results:
                        formatted_results.append({
                            'subject': row.get('s', ''),
                            'property': row.get('p', ''),
                            'object': row.get('o', '')
                        })
                    
                    return FunctionResult(
                        success=True,
                        result={
                            'count': len(formatted_results),
                            'triples': formatted_results
                        }
                    )
                else:
                    return FunctionResult(
                        success=False,
                        error=f"Query failed: {result.error}"
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"List triples failed: {str(e)}"
            )


class ExecuteQueryFunction(BaseFunction):
    """Execute a SPARQL query on a knowledge graph."""
    
    def __init__(self):
        super().__init__(
            name="execute_query",
            description="Execute a SPARQL query on a knowledge graph and return results"
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
                    name="sparql",
                    type="string",
                    description="SPARQL query to execute",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of rows to return (default: all)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        sparql = kwargs.get("sparql")
        limit = kwargs.get("limit")
        
        if not kg or not sparql:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and sparql"
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
            
            # Apply limit if specified
            query = sparql
            if limit and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"
            
            async with QLeverClient(endpoint_url) as client:
                result = await client.execute_query(query)
                
                if result.success:
                    rows = result.results or []
                    columns = result.columns or []
                    return FunctionResult(
                        success=True,
                        result={
                            'columns': columns,
                            'rows': rows,
                            'count': len(rows),
                            'execution_time': result.execution_time
                        }
                    )
                else:
                    return FunctionResult(
                        success=False,
                        error=f"Query execution failed: {result.error}"
                    )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Execute query failed: {str(e)}"
            )
