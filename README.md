# NLtoSPARQL: Natural Language to SPARQL Query Generation

A proof-of-concept system for generating SPARQL queries from natural language input using Large Language Models (LLMs) with function-calling capabilities. Supports both cloud LLM APIs (via OpenRouter) and local models (via Ollama). Currently works with wikidata only.

## Features

- **Function-Calling LLMs**: Implements GRASP-inspired approach with functions for exploring knowledge graphs
- **Multi-LLM Support**: Switch between models served locally by Ollama or in the cloud via OpenRouter
- **QLever Integration**: Works with QLever SPARQL endpoints
- **Query Validation**: Basic SPARQL syntax validation (IN IMPLEMENTATION)
- **CLI Interface**: User interaction happens via cli, --verbose strongly suggested

## Architecture

The system follows a modular architecture:

```
src/
├── llm/              # LLM provider implementations
├── functions/        # Function-calling system
├── sparql/          # SPARQL execution and validation
├── agent/           # Reasoning agent and instructions
└── cli/             # Command-line interface
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd nltosparql
```

2. Install dependencies:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Configuration

Edit `config/default.yaml` or set environment variables:

- `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)
- `QLEVER_ENDPOINT`: Default QLever endpoint

## Usage

### Basic Usage

```bash
# Generate SPARQL query for a natural language question
nltosparql query --provider ollama --endpoint wikidata --verbose "Who was the Governor of Ohio by the end of 2011?"
```

### Available Commands

```bash
# Show help
nltosparql --help

# List available QLever endpoints
nltosparql endpoints list

# Test connection to an endpoint
nltosparql endpoints test --endpoint wikidata

# Interactive mode (experimental, do not use)
nltosparql interactive
```

## Function-Calling System

The system provides the following functions for LLMs to explore knowledge graphs:

1. **search_entity(kg, query)**: Search for entities in the knowledge graph
2. **search_property(kg, query)**: Search for properties
3. **list_triples(kg, subj, prop, obj)**: List triples with constraints
4. **execute_query(kg, sparql)**: Execute SPARQL query and return results
5. **validate_query(kg, sparql)**: Validate SPARQL query
6. **answer(kg, sparql, answer)**: Provide final answer

## Development

### Setting up Development Environment

```bash
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black src/
isort src/
mypy src/
```

## Project Structure

- `src/llm/`: LLM provider implementations (OpenAI-like, Ollama)
- `src/functions/`: Function definitions and registry
- `src/sparql/`: QLever client and query validation
- `src/agent/`: Reasoning agent pattern
- `src/cli/`: Command-line interface
- `config/`: Configuration files

## License

This is an educational project.

## Acknowledgments

- Inspired by GRASP: Generic Reasoning And SPARQL Generation across Knowledge Graphs
- Uses QLever SPARQL endpoints from University of Freiburg
- Built with Python and modern LLM libraries
