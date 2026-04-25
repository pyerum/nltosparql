"""FastAPI web application for NLtoSPARQL with SSE streaming."""

import asyncio
import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..utils.system_init import create_agent, load_config

app = FastAPI(title="NLtoSPARQL Web", version="0.1.0")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class QueryRequest(BaseModel):
    question: str
    provider: str = "ollama"
    model: Optional[str] = None
    endpoint: str = "wikidata"
    ontology: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/config")
async def get_config():
    """Return available providers, models, endpoints, and ontologies."""
    config = load_config()

    # Providers and models
    llm_config = config.get("llm", {}) or {}
    models_config = llm_config.get("models", {}) or {}
    providers = {
        name: {"model": cfg.get("model", ""), "models": [cfg.get("model", "")]}
        for name, cfg in models_config.items()
    }

    # Endpoints
    endpoints = config.get("endpoints", {})

    # Ontologies
    ontologies_dir = os.path.join(os.path.dirname(__file__), "../../ontologies")
    ontologies = []
    if os.path.isdir(ontologies_dir):
        ontologies = [f for f in os.listdir(ontologies_dir) if f.endswith(".ttl")]

    return {
        "providers": providers,
        "endpoints": list(endpoints.keys()),
        "ontologies": ontologies,
    }


@app.post("/api/query")
async def query_sse(request: QueryRequest):
    """Stream agent execution via Server-Sent Events."""

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def event_callback(event_type: str, data: Dict[str, Any]):
            await queue.put((event_type, data))

        async def run_agent():
            try:
                ontologies = [request.ontology] if request.ontology else None
                agent = create_agent(
                    provider=request.provider,
                    model=request.model,
                    verbose=True,
                    kg_name=request.endpoint,
                    ontologies=ontologies,
                    event_callback=event_callback,
                )
                result = await agent.process_question(
                    request.question, kg_name=request.endpoint
                )
                await queue.put(("final", result))
            except Exception as e:
                await queue.put(("final", {"status": "error", "error": str(e)}))

        # Start agent in background
        task = asyncio.create_task(run_agent())

        while True:
            try:
                event_type, data = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield f"event: error\ndata: {json.dumps({'message': 'Timeout waiting for agent'})}\n\n"
                break

            if event_type == "final":
                yield f"event: final\ndata: {json.dumps(data)}\n\n"
                break
            else:
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main():
    """Entry point for the web server."""
    import uvicorn

    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8419, reload=False)


if __name__ == "__main__":
    main()
