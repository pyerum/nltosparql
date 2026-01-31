"""Wikidata REST API client for entity and property search."""

import aiohttp
import asyncio
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json


@dataclass
class WikidataSearchResult:
    """Result from Wikidata Search API."""
    id: str
    label: str
    description: Optional[str] = None
    url: Optional[str] = None
    concepturi: Optional[str] = None
    match: Optional[Dict[str, Any]] = None


class WikidataSearchClient:
    """Client for Wikidata REST API."""
    
    def __init__(self, access_token: Optional[str] = None):
        self.base_url = "https://www.wikidata.org/w/api.php"
        self.access_token = access_token or os.getenv("WIKIDATA_ACCESS_TOKEN")
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "NL-to-SPARQL System/1.0",
                "Accept": "application/json"
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def search_entities(
        self, 
        query: str, 
        language: str = "en",
        limit: int = 10,
        search_type: str = "item"
    ) -> List[WikidataSearchResult]:
        """
        Search for entities in Wikidata using MediaWiki API.
        
        Args:
            query: Search query
            language: Language code (default: "en")
            limit: Maximum number of results (default: 10)
            search_type: "item" for Q entities, "property" for P entities
            
        Returns:
            List of WikidataSearchResult objects
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "NL-to-SPARQL System/1.0",
                    "Accept": "application/json"
                }
            )
        
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": language,
            "type": search_type,
            "search": query,
            "limit": limit,
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    for item in data.get("search", []):
                        result = WikidataSearchResult(
                            id=item.get("id", ""),
                            label=item.get("label", ""),
                            description=item.get("description"),
                            url=item.get("url"),
                            concepturi=item.get("concepturi"),
                            match=item.get("match")
                        )
                        results.append(result)
                    
                    return results
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed: {response.status} - {error_text}")
                        
        except Exception as e:
            raise Exception(f"Search failed: {str(e)}")
    
    async def get_entity_info(
        self, 
        entity_id: str,
        language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an entity.
        
        Args:
            entity_id: Wikidata entity ID (e.g., "Q142", "P31")
            language: Language code (default: "en")
            
        Returns:
            Dictionary with entity information
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "User-Agent": "NL-to-SPARQL System/1.0",
                    "Accept": "application/json"
                }
            )
        
        params = {
            "action": "wbgetentities",
            "format": "json",
            "ids": entity_id,
            "languages": language,
            "props": "labels|descriptions|aliases|claims|sitelinks",
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("entities", {}).get(entity_id)
                else:
                    return None
        except Exception:
            return None
    
    async def search_properties(
        self, 
        query: str, 
        language: str = "en",
        limit: int = 10
    ) -> List[WikidataSearchResult]:
        """
        Search for properties in Wikidata.
        
        Args:
            query: Search query
            language: Language code (default: "en")
            limit: Maximum number of results (default: 10)
            
        Returns:
            List of WikidataSearchResult objects
        """
        return await self.search_entities(
            query=query,
            language=language,
            limit=limit,
            search_type="property"
        )


async def test_wikidata_search():
    """Test the Wikidata Search API client."""
    client = WikidataSearchClient()
    
    async with client:
        # Test entity search
        print("Searching for 'France'...")
        results = []
        try:
            results = await client.search_entities("France", limit=5)
            print(f"Found {len(results)} results:")
            for result in results:
                print(f"  {result.id}: {result.label} - {result.description}")
        except Exception as e:
            print(f"Error searching entities: {e}")
        
        # Test property search
        print("\nSearching for 'capital' properties...")
        try:
            properties = await client.search_properties("capital", limit=5)
            print(f"Found {len(properties)} properties:")
            for prop in properties:
                print(f"  {prop.id}: {prop.label} - {prop.description}")
        except Exception as e:
            print(f"Error searching properties: {e}")
        
        # Test entity info
        if results:
            print(f"\nGetting info for {results[0].id}...")
            try:
                info = await client.get_entity_info(results[0].id)
                if info:
                    print(f"  Label: {info.get('labels', {}).get('en', {}).get('value', 'N/A')}")
                    print(f"  Description: {info.get('descriptions', {}).get('en', {}).get('value', 'N/A')}")
            except Exception as e:
                print(f"Error getting entity info: {e}")


if __name__ == "__main__":
    asyncio.run(test_wikidata_search())
