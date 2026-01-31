"""QLever SPARQL endpoint client."""

import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from pydantic import BaseModel, Field


class SPARQLResult(BaseModel):
    """Result of a SPARQL query execution."""
    
    success: bool = Field(..., description="Whether the query executed successfully")
    results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Query results")
    columns: Optional[List[str]] = Field(default=None, description="Column names")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    execution_time: Optional[float] = Field(default=None, description="Query execution time in seconds")


class QLeverClient:
    """Client for QLever SPARQL endpoints."""
    
    def __init__(self, endpoint_url: str, timeout: int = 60):
        """
        Initialize QLever client.
        
        Args:
            endpoint_url: URL of the QLever SPARQL endpoint
            timeout: Request timeout in seconds
        """
        self.endpoint_url = endpoint_url.rstrip('/')
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def execute_query(
        self,
        query: str,
        limit: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> SPARQLResult:
        """
        Execute a SPARQL query against the QLever endpoint.
        
        Args:
            query: SPARQL query string
            limit: Maximum number of results to return
            timeout: Query timeout in seconds
            
        Returns:
            SPARQLResult object
        """
        # Create a session for this request if not using context manager
        session = self.session or aiohttp.ClientSession()
        close_session = not self.session
        
        try:
            # Prepare query with limit if specified
            if limit is not None:
                if "LIMIT" not in query.upper():
                    query = f"{query} LIMIT {limit}"
            
            # Prepare request parameters
            # QLever expects timeout as a duration string (e.g., "60s")
            timeout_value = timeout or self.timeout
            params = {
                "query": query,
                "timeout": f"{timeout_value}s",
            }
            
            async with session.post(
                self.endpoint_url,
                data=params,
                timeout=aiohttp.ClientTimeout(total=timeout or self.timeout + 10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_qlever_response(data)
                else:
                    error_text = await response.text()
                    return SPARQLResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text[:200]}"
                    )
        except aiohttp.ClientError as e:
            return SPARQLResult(
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            return SPARQLResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
        finally:
            if close_session and session:
                await session.close()
    
    def _parse_qlever_response(self, data: Dict[str, Any]) -> SPARQLResult:
        """
        Parse QLever response format.
        
        Args:
            data: Raw response data from QLever
            
        Returns:
            Parsed SPARQLResult
        """
        try:
            # QLever returns results in a specific format
            if "results" in data and "bindings" in data["results"]:
                bindings = data["results"]["bindings"]
                
                # Convert bindings to list of dictionaries
                results = []
                for binding in bindings:
                    row = {}
                    for var_name, var_value in binding.items():
                        # Extract value based on type
                        if "value" in var_value:
                            row[var_name] = var_value["value"]
                        else:
                            row[var_name] = str(var_value)
                    results.append(row)
                
                # Extract column names
                columns = list(bindings[0].keys()) if bindings else []
                
                return SPARQLResult(
                    success=True,
                    results=results,
                    columns=columns,
                    execution_time=data.get("execution_time")
                )
            else:
                return SPARQLResult(
                    success=False,
                    error="Invalid response format from QLever"
                )
        except Exception as e:
            return SPARQLResult(
                success=False,
                error=f"Failed to parse response: {str(e)}"
            )
    
    async def test_connection(self) -> bool:
        """
        Test connection to the QLever endpoint.
        
        Returns:
            True if connection successful, False otherwise
        """
        test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
        result = await self.execute_query(test_query, limit=1)
        return result.success
    
    async def get_endpoint_info(self) -> Dict[str, Any]:
        """
        Get information about the QLever endpoint.
        
        Returns:
            Dictionary with endpoint information
        """
        # Try to get some basic stats
        queries = [
            ("triple_count", "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"),
            ("subject_count", "SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { ?s ?p ?o }"),
            ("predicate_count", "SELECT (COUNT(DISTINCT ?p) AS ?count) WHERE { ?s ?p ?o }"),
        ]
        
        info = {"endpoint": self.endpoint_url}
        
        for name, query in queries:
            result = await self.execute_query(query, limit=1)
            if result.success and result.results:
                info[name] = result.results[0].get("count", "unknown")
        
        return info
