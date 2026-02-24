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


def create_agent(
    provider: str = "ollama",
    model: Optional[str] = None,
    max_iterations: int = 20,
    enable_feedback: bool = True,
    max_feedback_loops: int = 2,
    verbose: bool = False,
    kg_name: str = "wikidata"
) -> AgentOrchestrator:
    """
    Create agent orchestrator with LLM and function registry.
    
    Args:
        provider: LLM provider
        model: Specific model to use
        max_iterations: Maximum iterations for agent
        enable_feedback: Whether to enable feedback mechanism
        max_feedback_loops: Maximum feedback loops
        verbose: Whether to enable verbose logging
        kg_name: Knowledge graph name (e.g., "wikidata")
        
    Returns:
        AgentOrchestrator instance
    """
    config = load_config()
    
    # Create LLM client
    llm = create_llm_client(provider=provider, model=model, config=config)
    
    # Create function registry for the specific knowledge graph
    function_registry = create_function_registry(kg_name)
    
    # Create agent
    agent = AgentOrchestrator(
        llm=llm,
        function_registry=function_registry,
        max_iterations=max_iterations,
        enable_feedback=enable_feedback,
        max_feedback_loops=max_feedback_loops,
        verbose=verbose
    )
    
    return agent


def get_available_endpoints() -> Dict[str, str]:
    """Get available knowledge graph endpoints."""
    config = load_config()
    return config.get('endpoints', {})
