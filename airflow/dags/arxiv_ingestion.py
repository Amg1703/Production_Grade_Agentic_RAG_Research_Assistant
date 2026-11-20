"""
    Daily arXiv ingestion DAG.

    fetch_latest_papers -> download_pdfs
    Fetches the newest papers in ARXIV__SEARCH_CATEGORY and caches their PDFs.
    Parsing (Docling), chunking and indexing into OpenSearch are added as the next tasks.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="arxiv_paper_ingestion",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ingestion", "arxiv"],
)
def arxiv_paper_ingestion():
    @task()
    def fetch_latest_papers() -> list[dict]:
        from src.services.arxiv.factory import make_arxiv_client

        papers = make_arxiv_client().fetch_papers()
        return [paper.model_dump(mode="json") for paper in papers]

    @task()
    def download_pdfs(papers: list[dict]) -> list[str]:
        from src.schemas.arxiv.paper import ArxivPaper
        from src.services.arxiv.factory import make_arxiv_client

        client = make_arxiv_client()
        paths = []
        for raw in papers:
            try:
                paths.append(str(client.download_pdf(ArxivPaper.model_validate(raw))))
            except RuntimeError as error:
                print(f"skipping {raw['arxiv_id']}: {error}")
        return paths

    download_pdfs(fetch_latest_papers())


arxiv_paper_ingestion()
