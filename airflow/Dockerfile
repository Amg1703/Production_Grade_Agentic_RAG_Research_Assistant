# Airflow image for the ingestion DAGs.
# The project's src/ is mounted at /opt/airflow/src and PYTHONPATH=/opt/airflow,
# so DAGs can `from src.services.arxiv.factory import make_arxiv_client`.
FROM apache/airflow:2.10.5-python3.12

RUN pip install --no-cache-dir "pydantic>=2.7" "pydantic-settings>=2.3"

# Single-container dev mode: metadata DB init, scheduler, webserver (port 8080)
CMD ["standalone"]
