"""System initialization utilities."""

from typing import Dict, Any, Optional
import yaml
import os

from ..llm.base import BaseLLM
from ..llm.openai_client import OpenAIClient
from ..llm.ollama_client import OllamaClient
from ..functions.factory import create_registry
from ..agent.orchestrator import AgentOrchestrator


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}


def create_llm_client(
    provider: str = "ollama",
    model: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> BaseLLM:
    """
    Create LLM client based on provider.
    
    Args:
        provider: LLM provider (ollama or openrouter)
        model: Specific model to use (overrides config)
        config: Configuration dictionary
        
    Returns:
        BaseLLM instance
    """
    if config is None:
        config = load_config()
    
    llm_config = config.get('llm', {}) or {}
    models_config = llm_config.get('models', {}) or {}
    
    if provider not in models_config:
        raise ValueError(f"Unknown provider: {provider}")
    
    provider_config = models_config.get(provider, {}) or {}
    model_name = model or provider_config.get('model', '')
    temperature = provider_config.get('temperature', 0.1)
    max_tokens = provider_config.get('max_tokens', 4096)
    
    if provider == 'openrouter':
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            raise ValueError(f"OPENROUTER_API_KEY environment variable not set")
        
        base_url = provider_config.get('base_url')
        
        return OpenAIClient(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url
        )
    elif provider == 'ollama':
        return OllamaClient(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        raise ValueError(f"Provider '{provider}' not yet implemented")


def create_function_registry(kg_name: str = "wikidata"):
    """
    Create and populate function registry for a specific knowledge graph.
    
    Args:
        kg_name: Name of the knowledge graph (e.g., "wikidata")
        
    Returns:
        FunctionRegistry with functions registered for the specified knowledge graph
    """
    return create_registry(kg_name)


def _load_ontology_content(ontology_path: str) -> str:
    """
    Load and return the content of an ontology file.
    
    Args:
        ontology_path: Path to the ontology file (relative to /ontologies directory)
        
    Returns:
        Content of the ontology file as a string
    """
    # Get the base ontologies directory (relative to this file's location)
    base_dir = os.path.join(os.path.dirname(__file__), "../../ontologies")
    full_path = os.path.join(base_dir, ontology_path)
    
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Ontology file not found: {full_path}")
    
    with open(full_path, 'r', encoding='utf-8') as f:
        return f.read()


def create_agent(
    provider: str = "ollama",
    model: Optional[str] = None,
    max_iterations: int = None,
    enable_feedback: bool = True,
    max_feedback_loops: int = 2,
    verbose: bool = False,
    kg_name: str = "wikidata",
    ontologies: Optional[list] = None,
    event_callback=None
) -> AgentOrchestrator:
    """
    Create agent orchestrator with LLM and function registry.
    
    Args:
        provider: LLM provider
        model: Specific model to use
        max_iterations: Maximum iterations for agent (if None, uses config value)
        enable_feedback: Whether to enable feedback mechanism
        max_feedback_loops: Maximum feedback loops
        verbose: Whether to enable verbose logging
        kg_name: Knowledge graph name (e.g., "wikidata")
        ontologies: List of ontology file paths (relative to /ontologies directory)
        event_callback: Optional async callback for streaming events
        
    Returns:
        AgentOrchestrator instance
    """
    config = load_config()
    
    # Read agent configuration from config
    agent_config = config.get('agent', {}) or {}
    
    # Use config value if max_iterations not specified
    if max_iterations is None:
        max_iterations = agent_config.get('max_iterations', 20)
    
    # Use config values if not specified
    if enable_feedback:
        enable_feedback = agent_config.get('enable_feedback', True)
    if max_feedback_loops == 2:
        max_feedback_loops = agent_config.get('max_feedback_loops', 2)
    
    # Create LLM client
    llm = create_llm_client(provider=provider, model=model, config=config)
    
    # Create function registry for the specific knowledge graph
    function_registry = create_function_registry(kg_name)
    
    # Load ontology content if provided
    ontology_content = None
    if ontologies:
        ontology_sections = []
        for ontology_path in ontologies:
            try:
                content = _load_ontology_content(ontology_path)
                ontology_sections.append(f"## Ontology: {ontology_path}\n{content}")
            except FileNotFoundError as e:
                if verbose:
                    print(f"Warning: {e}")
        
        if ontology_sections:
            ontology_content = "\n\n".join(ontology_sections)
    
    # Create agent
    agent = AgentOrchestrator(
        llm=llm,
        function_registry=function_registry,
        max_iterations=max_iterations,
        enable_feedback=enable_feedback,
        max_feedback_loops=max_feedback_loops,
        verbose=verbose,
        ontology_content=ontology_content,
        event_callback=event_callback
    )
    
    return agent


def get_available_endpoints() -> Dict[str, str]:
    """Get available knowledge graph endpoints."""
    config = load_config()
    return config.get('endpoints', {})
