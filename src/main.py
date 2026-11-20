"""FastAPI entry point for the research assistant API."""

from fastapi import FastAPI, HTTPException, Query

from src.config import get_settings
from src.schemas.arxiv.paper import ArxivPaper
from src.services.arxiv.factory import make_arxiv_client

settings = get_settings()

app = FastAPI(title="Agentic RAG Research Assistant", version=settings.app_version)


@app.get("/v1/api/health")
def health() -> dict:
    """Liveness probe used by the Docker Compose health check."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/v1/papers/latest", response_model=list[ArxivPaper])
def latest_papers(max_results: int = Query(5, ge=1, le=50), category: str | None = None) -> list[ArxivPaper]:
    """Fetch the newest arXiv papers in a category (defaults to ARXIV__SEARCH_CATEGORY)."""
    try:
        return make_arxiv_client().fetch_papers(max_results=max_results, category=category)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"arXiv request failed: {error}") from error
