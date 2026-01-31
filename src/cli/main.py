"""Command-line interface for NLtoSPARQL."""

import asyncio
import os
from typing import Optional
import click
import yaml
from dotenv import load_dotenv

from ..llm.openai_client import OpenAIClient
from ..llm.ollama_client import OllamaClient
from ..sparql.qlever_client import QLeverClient


# Load environment variables
load_dotenv()


@click.group()
@click.version_option(package_name="nltosparql")
def cli():
    """NLtoSPARQL: Generate SPARQL queries from natural language using LLMs."""
    pass


def load_config() -> dict:
    """Load configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        click.echo(f"Warning: Config file not found at {config_path}", err=True)
        return {}


@cli.command()
@click.argument('question')
@click.option('--provider', '-p', default='openai', 
              type=click.Choice(['openai', 'anthropic', 'ollama', 'deepseek']),
              help='LLM provider to use')
@click.option('--endpoint', '-e', default='wikidata',
              help='QLever endpoint to use (e.g., wikidata, dblp, dbpedia)')
@click.option('--model', '-m', default=None,
              help='Specific model to use (overrides config)')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose output')
def query(question: str, provider: str, endpoint: str, model: Optional[str], verbose: bool):
    """Generate a SPARQL query for a natural language question."""
    config = load_config()
    
    # Get endpoint URL
    endpoints = config.get('endpoints', {})
    endpoint_url = endpoints.get(endpoint)
    if not endpoint_url:
        click.echo(f"Error: Unknown endpoint '{endpoint}'. Available: {', '.join(endpoints.keys())}", err=True)
        return
    
    # Get LLM configuration
    llm_config = config.get('llm', {}) or {}
    models_config = llm_config.get('models', {}) or {}
    
    if provider not in models_config:
        click.echo(f"Error: No configuration found for provider '{provider}'", err=True)
        return
    
    provider_config = models_config.get(provider, {}) or {}
    model_name = model or provider_config.get('model', '')
    temperature = provider_config.get('temperature', 0.1)
    max_tokens = provider_config.get('max_tokens', 2000)
    
    if verbose:
        click.echo(f"Using provider: {provider}")
        click.echo(f"Using model: {model_name}")
        click.echo(f"Using endpoint: {endpoint} ({endpoint_url})")
        click.echo(f"Question: {question}")
    
    # Initialize LLM client
    llm_client = None
    if provider in ['openai', 'deepseek']:
        # For OpenAI-compatible APIs (OpenAI, DeepSeek)
        env_var_name = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var_name)
        if not api_key:
            click.echo(f"Error: {env_var_name} environment variable not set", err=True)
            return
        
        # Get base URL from config if specified
        base_url = provider_config.get('base_url')
        
        llm_client = OpenAIClient(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url
        )
    elif provider == 'ollama':
        llm_client = OllamaClient(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        click.echo(f"Error: Provider '{provider}' not yet implemented", err=True)
        return
    
    # Initialize QLever client
    qlever_client = QLeverClient(endpoint_url)
    
    # Run the query generation
    asyncio.run(run_query_generation(
        question=question,
        llm_client=llm_client,
        qlever_client=qlever_client,
        verbose=verbose,
        provider=provider,
        endpoint=endpoint
    ))


async def run_query_generation(question: str, llm_client, qlever_client, verbose: bool, provider: str, endpoint: str):
    """Run the query generation process using the agent."""
    click.echo("Generating SPARQL query using agent...")
    
    try:
        # Import here to avoid circular imports
        from src.utils.system_init import create_agent
        
        # Create agent
        agent = create_agent(
            provider=provider,
            verbose=verbose
        )
        
        # Process question
        result = await agent.process_question(question, kg_name=endpoint)
        
        # Display results based on status
        if result['status'] == 'success':
            click.echo("\n" + "=" * 60)
            click.echo("SUCCESS: SPARQL query generated")
            click.echo("=" * 60)
            
            result_data = result['result']
            click.echo(f"\nKnowledge Graph: {result_data.get('knowledge_graph', 'N/A')}")
            click.echo(f"\nSPARQL Query:")
            click.echo("-" * 40)
            click.echo(result_data.get('sparql_query', 'N/A'))
            click.echo("-" * 40)
            
            if result_data.get('answer'):
                click.echo(f"\nAnswer: {result_data.get('answer')}")
            
            if result_data.get('explanation'):
                click.echo(f"\nExplanation: {result_data.get('explanation')}")
            
            # Show execution summary
            summary = agent.get_execution_summary()
            click.echo(f"\nExecution Summary:")
            click.echo(f"  Iterations: {summary['total_iterations']}")
            click.echo(f"  Function calls: {summary['total_function_calls']}")
            click.echo(f"  Successful: {summary['successful_function_calls']}")
            click.echo(f"  Failed: {summary['failed_function_calls']}")
            
            if verbose:
                click.echo(f"\nFunction call breakdown:")
                for func_name, count in summary['function_call_breakdown'].items():
                    click.echo(f"  {func_name}: {count}")
        
        elif result['status'] == 'cancelled':
            click.echo("\n" + "=" * 60)
            click.echo("CANCELLED: Could not generate satisfactory query")
            click.echo("=" * 60)
            
            result_data = result['result']
            click.echo(f"\nExplanation: {result_data.get('explanation', 'N/A')}")
            
            if result_data.get('best_attempt'):
                click.echo(f"\nBest attempt:")
                click.echo("-" * 40)
                click.echo(str(result_data.get('best_attempt')))
                click.echo("-" * 40)
        
        elif result['status'] == 'timeout':
            click.echo("\n" + "=" * 60)
            click.echo("TIMEOUT: Exceeded maximum iterations")
            click.echo("=" * 60)
            click.echo(f"\nError: {result.get('error', 'Unknown error')}")
            
            summary = agent.get_execution_summary()
            click.echo(f"\nProgress before timeout:")
            click.echo(f"  Iterations: {summary['total_iterations']}")
            click.echo(f"  Function calls: {summary['total_function_calls']}")
            
            # Show best attempt if available
            if result.get('best_attempt'):
                click.echo(f"\nBest attempt found:")
                click.echo("-" * 40)
                
                if result.get('best_sparql'):
                    click.echo(f"SPARQL Query:")
                    click.echo(result['best_sparql'])
                    click.echo()
                
                if result.get('best_answer'):
                    click.echo(f"Answer: {result['best_answer']}")
                    click.echo()
                
                # Show the full best attempt object if verbose
                if verbose:
                    click.echo(f"Full best attempt data:")
                    click.echo(str(result['best_attempt']))
                
                click.echo("-" * 40)
            else:
                click.echo(f"\nNo complete query or answer found in attempts.")
        
        elif result['status'] == 'error':
            click.echo("\n" + "=" * 60)
            click.echo("ERROR: Failed to generate query")
            click.echo("=" * 60)
            click.echo(f"\nError: {result.get('error', 'Unknown error')}")
        
        # Test the QLever connection if verbose
        if verbose:
            click.echo("\n" + "=" * 60)
            click.echo("Testing QLever connection...")
            connected = await qlever_client.test_connection()
            if connected:
                click.echo("Connected to QLever endpoint")
            else:
                click.echo("Failed to connect to QLever endpoint")
    
    except Exception as e:
        click.echo(f"\nError during query generation: {e}")
        if verbose:
            import traceback
            click.echo(f"\nTraceback:")
            click.echo(traceback.format_exc())


@cli.group()
def endpoints():
    """Manage QLever endpoints."""
    pass


@endpoints.command('list')
def endpoints_list():
    """List available QLever endpoints."""
    config = load_config()
    endpoints = config.get('endpoints', {})
    
    click.echo("Available QLever endpoints:")
    for name, url in endpoints.items():
        click.echo(f"  {name}: {url}")


@endpoints.command('test')
@click.option('--endpoint', '-e', default='wikidata',
              help='Endpoint to test')
def endpoints_test(endpoint: str):
    """Test connection to a QLever endpoint."""
    config = load_config()
    endpoints = config.get('endpoints', {}) or {}
    
    endpoint_url = endpoints.get(endpoint)
    if not endpoint_url:
        click.echo(f"Error: Unknown endpoint '{endpoint}'", err=True)
        return
    
    click.echo(f"Testing connection to {endpoint} ({endpoint_url})...")
    
    async def test():
        async with QLeverClient(endpoint_url) as client:
            connected = await client.test_connection()
            if connected:
                click.echo("Connection successful")
                # Get endpoint info
                info = await client.get_endpoint_info()
                if info:
                    triple_count = info.get('triple_count', 'unknown')
                    subject_count = info.get('subject_count', 'unknown')
                    predicate_count = info.get('predicate_count', 'unknown')
                    click.echo(f"  Triple count: {triple_count}")
                    click.echo(f"  Subject count: {subject_count}")
                    click.echo(f"  Predicate count: {predicate_count}")
                else:
                    click.echo("  Could not retrieve endpoint information")
            else:
                click.echo("Connection failed")
    
    asyncio.run(test())


@cli.command()
@click.option('--provider', '-p', default='openai',
              type=click.Choice(['openai', 'anthropic', 'ollama', 'deepseek']),
              help='LLM provider to test')
def test(provider: str):
    """Test LLM provider connection."""
    config = load_config()
    llm_config = config.get('llm', {})
    if not llm_config:
        llm_config = {}
    
    models_config = llm_config.get('models', {})
    if not models_config:
        models_config = {}
    
    if provider not in models_config:
        click.echo(f"Error: No configuration found for provider '{provider}'", err=True)
        return
    
    provider_config = models_config.get(provider, {})
    if not provider_config:
        provider_config = {}
    
    model_name = provider_config.get('model', '')
    
    click.echo(f"Testing {provider} connection with model '{model_name}'...")
    
    if provider in ['openai', 'deepseek']:
        env_var_name = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var_name)
        if not api_key:
            click.echo(f"Error: {env_var_name} environment variable not set", err=True)
            return
        
        async def test_openai_compatible():
            try:
                base_url = provider_config.get('base_url')
                client = OpenAIClient(
                    model=model_name,
                    api_key=api_key,
                    base_url=base_url if base_url else None
                )
                # Simple test message
                from ..llm.base import LLMMessage
                messages = [LLMMessage(role="user", content="Hello, are you working?")]
                response = await client.generate(messages)
                click.echo(f"✓ {provider} connection successful")
                click.echo(f"  Response: {response.content[:100]}...")
            except Exception as e:
                click.echo(f"✗ {provider} connection failed: {e}")
        
        asyncio.run(test_openai_compatible())
    
    elif provider == 'ollama':
        async def test_ollama():
            try:
                client = OllamaClient(model=model_name)
                from ..llm.base import LLMMessage
                messages = [LLMMessage(role="user", content="Hello, are you working?")]
                response = await client.generate(messages)
                click.echo(f"Ollama connection successful")
                click.echo(f"  Response: {response.content[:100]}...")
            except Exception as e:
                click.echo(f"Ollama connection failed: {e}")
        
        asyncio.run(test_ollama())
    
    else:
        click.echo(f"Error: Provider '{provider}' not yet implemented", err=True)


@cli.command()
@click.argument('query')
@click.option('--endpoint', '-e', default='wikidata',
              help='QLever endpoint to use for validation')
@click.option('--explain', is_flag=True,
              help='Use EXPLAIN to validate query')
@click.option('--format', 'format_query', is_flag=True,
              help='Format the query for better readability')
def validate(query: str, endpoint: str, explain: bool, format_query: bool):
    """Validate a SPARQL query."""
    config = load_config()
    endpoints = config.get('endpoints', {}) or {}
    endpoint_url = endpoints.get(endpoint)
    
    if not endpoint_url:
        click.echo(f"Error: Unknown endpoint '{endpoint}'", err=True)
        return
    
    async def run_validation():
        from src.sparql.validator import QueryValidator
        from src.sparql.qlever_client import QLeverClient
        
        # Format query if requested
        if format_query:
            query_formatted = QueryValidator.format_query(query)
            click.echo("Formatted query:")
            click.echo("=" * 50)
            click.echo(query_formatted)
            click.echo("=" * 50)
        
        # First, do syntax validation
        click.echo("Performing syntax validation...")
        is_valid, errors = QueryValidator.validate_syntax(query)
        
        if not is_valid:
            click.echo("✗ Syntax validation failed:")
            for error in errors:
                click.echo(f"  - {error}")
            return
        
        click.echo("✓ Syntax validation passed")
        
        # Extract query information
        variables = QueryValidator.extract_variables(query)
        prefixes = QueryValidator.extract_prefixes(query)
        
        click.echo(f"\nQuery information:")
        click.echo(f"  Variables: {', '.join(variables) if variables else 'None'}")
        click.echo(f"  Prefixes: {len(prefixes)} found")
        for prefix, uri in prefixes.items():
            click.echo(f"    {prefix}: {uri}")
        
        # Validate with endpoint
        click.echo(f"\nValidating with endpoint {endpoint}...")
        async with QLeverClient(endpoint_url) as client:
            is_valid, error, result = await QueryValidator.validate_with_endpoint(
                client, query, explain
            )
            
            if is_valid:
                click.echo("Endpoint validation passed")
                if explain and result:
                    click.echo(f"\nEXPLAIN result: {result}")
            else:
                click.echo(f"Endpoint validation failed: {error}")
    
    asyncio.run(run_validation())


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()
