""" 
    THIS FILE ESSENTIALLY CONSISTS OF FALLBACK FOR FETCHING ENVIRONMENT VARIABLES IF IT IS FOUND MISSING IN THE .ENV FILE 
    - WE USE PYDANTIC BASESETTINGS TO DEFINE THE ENVIRONMENT VARIABLES AND USE SETTINGSCONFIGDICT TO DEFINE WHAT VARIABLES TO FETCH 
      , WHERE TO FETCH AND HOW TO FETCH 
    - WE USE THE PYDANTIC FIELD TO ATTACH META DATA TO THE ENV VARIABLES LIKE DEFAULT VALUES IF NOT PROVIDED WITH ONE
    - WE USE THE PYDANTIC FIELD VALIDATOR TO WRITE A CLASS FUNCTION THAT WILL BE CALLED WHENEVER THE FIELD IS BEING USED OR CREATED
      TO VALIDATE THE INCOMING .ENV VARIABLE TO VALIDATE IT OR TO PERFORM FUNCTIONS ON ITS BEHALF LIKE CREATING A DIRECTORY
"""

import os 

# PATH IS USED TO REPRESENT FILES AND FOLDERS IN AN OBJECT ORIENTED WAY RATHER THAN JUST STRINGS You can do some_path / "subfolder" and it joins paths correctly on any OS.
from pathlib import Path

# PYDANTIC FIELD IS USED TO VALIDATE INCOMING DATA FIELDS ACROSS THE DEFINED TYPED FORMATS TO CHECK IF ITS TRUE 
# FIELD IS USED TO ADD ADDIONAL META DATA TO THE FIELDS LIKE DEFAULT VALUE AND DESCRIPTION 
# FIELD VALIDATOR IS A DECORATOR USED TO WRITE CUSTOM VALIDATION LOGIC AS CLASS METHODS FOR A SPECIFIC FIELD
from pydantic import Field, field_validator

# BASE SETTINGS IS A BASE CLASS USED TO AUTOMATICALLY POPULATE FIELDS FROM ENVIRONMENTAL VARIABLE (.ENV) AND NOT JUST FROM THE ARGUMENTS YOU PASS IN THE CODE
# SETTINGSCONFIGDICT IS A TYPED DICTIONARY TO CONGIURE HOW BASESETTINGS READS FROM THE ENVIRONMENTAL VARIABLE LIKE PREFIX OF THE VARIABLE IN THE .ENV FILE
# AND WHERE TO READ THE ENV FILE FROM 
from pydantic_settings import BaseSettings, SettingsConfigDict

from typing import List, Literal, Optional
# WE ARE SAYING PROJECT_ROOT WILL BE THE PARENT (PARENT(CURRENT_FILE)) RUNNING THE CODE, 
PROJECT_ROOT=Path(__file__).parent.parent

# ENV FILE WILL BE FOUND IN THE PROJECT ROOT FOLDER AS .ENV 
ENV_FILE_PATH=PROJECT_ROOT / ".env"

"""
    EVERY OTHER SETTINGS CLASS IN THIS FILE WILL INHERIT FROM BASECONFIGSETTINGS WHICH IS INHERITS PYDANTI BASE SETTINGS TO AUTOMATICALLY LOAD .ENV VARIABLES
    - WE CONFIGURE HOW THE BASE CONFIG SETTINGS LOADS THE .ENV VARIABLE THROUGH SETTINGS CONFIG DICT
    - ENV_FILE IS TO POINT WHERE TO LOOK FOR THE .ENV FILE look for a .env file in two places: the current working directory, 
    and the absolute project root. This is defensive — no matter what folder you run the script from, it can still find the .env file.
    - FROZEN IS SET TO TRUE - MEANING DO NOT CHANGE/MUTATE THE SETTINGS ONCE CREATED
    - extra=ignore - MEANING IF THERE ARE OTHER EXTRA .ENV VARIABLES IGNORE THEM FOR THIS SETTINGS 
    - env_nested_delimiter = __ - IS TO SAY WHENEVER YOU SEE __ IT IS NESTED .ENV VARIABLE (settings.arvix.rate_limitter -> .env -> arvix__rate_limitter)
    - case_sensitive = False - FETCH THE ENV VARIABLES AS MERE CHARACTERS SO (ARIX__RATE_LIMITTER = arvix_RaTE_liMItter)
"""
class BaseConfigSettings(BaseSettings):
    model_config=SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH]
        frozen=True,
        extra="ignore",
        env_nested_delimiter="__",
        case_sensitive=False
    )

""" 
    DEFINES THE 
    - WE ARE REDECLARING THE WHOLE SETTINGS SINCE WE ARE OVERRIDING THE CLASS IT WILL NOT INHERIT THE REST OF THE PARAMETERS FROM THE PARENT
    - env_prefix=ARVIX__ - MEANS FOR EVERY FIELD IN THE CLASS LOOKS FOR AN .ENV VARIABLE NAMED ARVIX__<FIELD_NAME> (ARVIX__RATE_LIMIT_DELAY)
"""
class ArxivSettings(BaseConfigSettings):
    model_config=SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH],
        extra="ignore",
        frozen=True,
        env_prefix="ARXIV__"
        case_sensitive=False,
    )
    base_url: str= "https://export.arxiv.org/api/query"
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    rate_limit_delay:float = 3.0
    timeout_seconds: int = 30
    max_results: int = 15 
    search_category: str = "cs.AI"
    download_max_retries: int = 3 
    download_retry_base: float = 5.0
    max_concurrent_downloads: int = 5
    max_concurrent_parsing: int = 1

    namespaces: dict = { 
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv" : "http://arxiv.org/schemas/atom",
    }
    @field_validator(pdf_cache_dir)
    @classmethod
    def validate_cache_dir(cls , v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v

class PDFParserSettings(BaseConfigSettings):
    model_config=SettingsConfigDict(
        env_file=[".env", ENV_FILE_PATH],
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
        env_prefix="PDF_PARSER__"
        case_sensitive=False
    ):
    max_pages: int = 30
    max_pdf_size_mb : int = 20 
    do_ocr: bool = False # OCR FOR SCANNED DOCUMENTS , BUT IS SLOW 
    do_table_structure : bool = True # EXTRACT TABLE STRUCTURE THROUGH DOCLING


# YET TO WRITE TO THE SETTINGS FOR CHUNKING SETTINGS, OPENSEARCH SETTINGS, LANGFUSE SETTINGS, REDIS SETTINGS AND TELEGRAM SETTINGS 

class Settings(BaseConfigSettings):
    app_version = "0.1.0"
    debug: bool = True
    environment: Literal["development", "staging", "production"] = "development"
    service_name: str = "rag-api"

    postgres_database_url: str = "postgresql://rag_user:password@localhost:5432/rag_db"
    postgres_pool_size: int = 20
    postgres_echo_sql: bool = False
    postgres_max_overflow: int = 0

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "ollma3.2:1b"
    ollama_timeout: int = 300 

    jina_api_key: int = ""
    # THE SETTINGS CLASS IS MORE LIKE THE TREE OBJECT 
    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)
    pdf_parser: PDFParserSettings = Field(default_factory=PDFParserSettings)
    @field_validator("postgres_database_url")
    @classmethod
    def postgres_database_url_validator(cls, v: str) -> str:
        if v.startswith("postgresql://") or v.startswith("postgresql+pscyopg_2://"):
            raise ValueError(f"ENV VARIABLE ERROR: Postgres database URL must start with postgresql:// or postgresql+psycopg2:// not {v}")
        return v 

def getting_settings() -> Settings:
    return Settings()