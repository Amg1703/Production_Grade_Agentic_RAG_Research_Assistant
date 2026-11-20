"""
    Typed application settings.

    - Pydantic BaseSettings loads every field from environment variables / the .env file,
      falling back to the defaults declared here.
    - SettingsConfigDict controls where the .env file lives and how variables are matched.
    - Field adds metadata (defaults, factories); field_validator runs custom validation,
      e.g. creating the PDF cache directory or checking the Postgres URL scheme.
"""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# PROJECT_ROOT IS TWO LEVELS UP FROM THIS FILE (src/config.py -> project root)
PROJECT_ROOT = Path(__file__).parent.parent

# THE .ENV FILE LIVES IN THE PROJECT ROOT
ENV_FILE_PATH = PROJECT_ROOT / ".env"


class BaseConfigSettings(BaseSettings):
    """
    Every settings class inherits from this.
    - env_file: look for .env in the current directory AND the project root, so scripts work from any folder
    - frozen=True: settings are immutable once created
    - extra="ignore": unrelated variables in .env are ignored
    - env_nested_delimiter="__": ARXIV__RATE_LIMIT_DELAY -> settings.arxiv.rate_limit_delay
    - case_sensitive=False: variable names are matched case-insensitively
    """

    model_config = SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH],
        frozen=True,
        extra="ignore",
        env_nested_delimiter="__",
        case_sensitive=False,
    )


class ArxivSettings(BaseConfigSettings):
    """arXiv ingestion settings. env_prefix="ARXIV__" means every field reads ARXIV__<FIELD_NAME>."""

    model_config = SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH],
        extra="ignore",
        frozen=True,
        env_prefix="ARXIV__",
        case_sensitive=False,
    )

    base_url: str = "https://export.arxiv.org/api/query"
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    rate_limit_delay: float = 3.0  # arXiv asks for >= 3s between requests
    timeout_seconds: int = 30
    max_results: int = 15
    search_category: str = "cs.AI"
    download_max_retries: int = 3
    download_retry_base: float = 5.0  # exponential backoff base, seconds
    max_concurrent_downloads: int = 5
    max_concurrent_parsing: int = 1

    namespaces: dict[str, str] = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    @field_validator("pdf_cache_dir")
    @classmethod
    def validate_cache_dir(cls, v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v


class PDFParserSettings(BaseConfigSettings):
    """PDF parsing settings (Docling). env_prefix="PDF_PARSER__"."""

    model_config = SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH],
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
        env_prefix="PDF_PARSER__",
        case_sensitive=False,
    )

    max_pages: int = 30
    max_pdf_size_mb: int = 20
    do_ocr: bool = False  # OCR for scanned documents (slow)
    do_table_structure: bool = True  # extract table structure through Docling


# NEXT: chunking, OpenSearch, Langfuse and Redis settings


class Settings(BaseConfigSettings):
    """Root of the settings tree."""

    app_version: str = "0.1.0"
    debug: bool = True
    environment: Literal["development", "staging", "production"] = "development"
    service_name: str = "rag-api"

    postgres_database_url: str = "postgresql://rag_user:password@localhost:5432/rag_db"
    postgres_pool_size: int = 20
    postgres_echo_sql: bool = False
    postgres_max_overflow: int = 0

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_timeout: int = 300

    jina_api_key: str = ""

    # NESTED SETTINGS TREE
    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)
    pdf_parser: PDFParserSettings = Field(default_factory=PDFParserSettings)

    @field_validator("postgres_database_url")
    @classmethod
    def postgres_database_url_validator(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError(
                f"Postgres database URL must start with postgresql:// or postgresql+psycopg2://, got {v!r}"
            )
        return v


def get_settings() -> Settings:
    """
    The single entry point every module uses: settings = get_settings()
    Builds Settings, which builds the nested ArxivSettings, PDFParserSettings, ... from defaults + .env overrides.
    """
    return Settings()
