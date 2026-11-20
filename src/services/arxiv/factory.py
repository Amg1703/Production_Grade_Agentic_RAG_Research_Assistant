"""
    Factory for ArxivClient so construction lives in one place:
        client = make_arxiv_client()
    instead of building settings and the client by hand everywhere.
"""

from src.config import get_settings

from .client import ArxivClient


def make_arxiv_client() -> ArxivClient:
    settings = get_settings()
    return ArxivClient(settings=settings.arxiv)
