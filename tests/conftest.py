"""
Shared fixtures for search function tests.

Provides an in-memory rdflib-backed mock for QLeverClient so that
search_entity and search_property can be tested without a running
Fuseki instance.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rdflib import Graph, URIRef
from rdflib.plugins.sparql import prepareQuery

from src.functions.base import FunctionResult
from src.functions.search import SearchEntityFunction, SearchPropertyFunction
from src.sparql.qlever_client import QLeverClient, SPARQLResult
from tests.kg_generator import generate_trains_kg, TRAIN


# ── In-memory SPARQL result adapter ────────────────────────────────

class InMemorySPARQLBackend:
    """
    Executes SPARQL SELECT queries against an rdflib Graph and
    returns results in the same shape as QLeverClient.
    """

    def __init__(self, graph: Graph):
        self._graph = graph

    def execute(self, sparql: str) -> SPARQLResult:
        try:
            q = prepareQuery(sparql)
            results = self._graph.query(q)
        except Exception as exc:
            return SPARQLResult(
                success=False,
                error=f"SPARQL parse/execution error: {exc}",
            )

        # Convert rdflib results to list-of-dict format
        rows: List[Dict[str, Any]] = []
        columns: List[str] = []
        try:
            for binding in results:
                row = {}
                for var_name in results.vars:
                    var_name_str = str(var_name)
                    value = binding.get(var_name)
                    row[var_name_str] = str(value) if value is not None else ""
                rows.append(row)
            columns = [str(v) for v in results.vars]
        except Exception:
            # Boolean result (ASK query) or empty
            pass

        return SPARQLResult(
            success=True,
            results=rows,
            columns=columns,
        )


class MockQLeverClient:
    """
    Drop-in replacement for QLeverClient that delegates
    SPARQL execution to an in-memory rdflib Graph.
    """

    def __init__(self, graph: Graph, endpoint_url: str = "mock://test"):
        self._graph = graph
        self._backend = InMemorySPARQLBackend(graph)
        self.endpoint_url = endpoint_url
        self.timeout = 60
        self.session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute_query(
        self, query: str, limit: Optional[int] = None, timeout: Optional[int] = None
    ) -> SPARQLResult:
        # rdflib doesn't handle LIMIT the same way in all cases;
        # we strip any trailing LIMIT and let the query handle it natively.
        result = self._backend.execute(query)
        return result


# ── Configuration override ──────────────────────────────────────────

# The config YAML that will be used instead of the real config/default.yaml.
# It adds a "test-trains" endpoint that points to our mock.
_MOCK_CONFIG = {
    "endpoints": {
        "test-trains": "mock://test-trains",
        "wikidata": "https://qlever.dev/api/wikidata",
    },
    "functions": {
        "max_search_results": 10,
    },
    "agent": {
        "max_iterations": 20,
    },
}


def _mock_yaml_load(config_content: Dict[str, Any]):
    """Return a callable that mimics yaml.safe_load."""
    return config_content


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def test_graph() -> Graph:
    """Return a fully populated trains knowledge graph."""
    return generate_trains_kg()


@pytest.fixture
def mock_qlever_client(test_graph: Graph):
    """Return a MockQLeverClient wrapping the test graph."""
    return MockQLeverClient(test_graph)


@pytest.fixture
def search_entity():
    """Create a SearchEntityFunction instance."""
    return SearchEntityFunction()


@pytest.fixture
def search_property():
    """Create a SearchPropertyFunction instance."""
    return SearchPropertyFunction()


@pytest.fixture
def mock_config():
    """Return the mock config dict used in place of config/default.yaml."""
    return dict(_MOCK_CONFIG)  # copy to prevent mutation between tests


@pytest.fixture(autouse=True)
def _patch_search_environment(test_graph: Graph, mock_config: Dict[str, Any]):
    """
    Automatically patch QLeverClient and yaml loading in search.py
    so that ANY test in this directory uses the in-memory graph.
    """
    # Patch QLeverClient constructor to return our mock
    with patch(
        "src.functions.search.QLeverClient",
        side_effect=lambda url, *a, **kw: MockQLeverClient(test_graph, url),
    ):
        # Patch yaml.safe_load to return mock config
        with patch(
            "yaml.safe_load",
            return_value=mock_config,
        ):
            yield