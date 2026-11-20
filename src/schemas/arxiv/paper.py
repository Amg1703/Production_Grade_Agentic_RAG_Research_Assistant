"""Schemas for papers returned by the arXiv API."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArxivPaper(BaseModel):
    arxiv_id: str = Field(description="arXiv identifier, e.g. 2401.01234v1")
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: datetime
    pdf_url: str
