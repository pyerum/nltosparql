# System Architecture

## High-Level Flow

```mermaid
graph TD
    User["User Query"] --> CLI
    CLI --> Agent["AgentOrchestrator"]
    Agent <--> LLM["LLM (Ollama/OpenRouter)"]
    Agent <--> Functions["Function Registry"]
    Functions --> GenericSPARQL["Generic SPARQL Endpoint"]
    Functions --> WikidataAPI["Wikidata API"]
    Agent --> Response["Final Answer"]
    
    subgraph "Knowledge Graph Support"
        GenericSPARQL --> Config["Configurable Endpoints"]
        WikidataAPI --> WikidataConfig["Wikidata-specific"]
    end
```

## Agent Loop

```mermaid
sequenceDiagram
    participant U as User
    participant A as AgentOrchestrator
    participant L as LLM
    participant F as FunctionRegistry
    participant KG as Knowledge Graph

    U->>A: "What countries border Spain?"
    A->>L: Generate (with system prompt + functions)
    L-->>A: function_call: search_entity
    A->>F: execute(search_entity, {query: "Spain"})
    F-->>A: result
    A->>L: Generate (with result)
    L-->>A: function_call: discover_properties
    A->>F: execute(discover_properties, {entity: Q29, concept: "border"})
    F-->>A: P47 = "shares border with"
    A->>L: Generate (with result)
    L-->>A: function_call: execute_query
    A->>F: execute(execute_query, {sparql: SELECT...})
    F->>KG: SPARQL query (QLever, Wikidata API, Fuseki, etc)
    KG-->>F: Query response
    F-->>A: results
    A->>L: Generate (with results)
    L-->>A: function_call: answer
    A-->>U: Final Answer
```

## Function Categories

```mermaid
graph TB
    subgraph Functions
        S[search_entity<br/>search_property<br/>list_triples<br/>execute_query]
        D[discover_properties<br/>search_property_by_concept<br/>get_property_details]
        E[get_entity_properties<br/>find_relationship_paths<br/>explore_property_values]
        A[answer<br/>cancel]
    end
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| AgentOrchestrator | src/agent/orchestrator.py | Main loop: LLM → functions → LLM |
| FunctionRegistry | src/functions/registry.py | Register & execute functions |
| LLM Clients | src/llm/*.py | Ollama / OpenRouter wrappers |
| WikidataClient | src/sparql/wikidata_search_client.py | Entity/property search |
| QLeverClient | src/sparql/qlever_client.py | SPARQL query execution |
