"""
    arXiv API client.

    - Searches the Atom feed at export.arxiv.org for the newest papers in a category
    - Respects arXiv's rate limit by sleeping between requests
    - Downloads PDFs into a local cache with retries and exponential backoff
    Uses only the standard library (urllib + ElementTree) so it runs in both the API and Airflow images.
"""

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from src.config import ArxivSettings
from src.schemas.arxiv.paper import ArxivPaper


class ArxivClient:
    def __init__(self, settings: ArxivSettings):
        self.settings = settings
        self._last_request = 0.0

    def _respect_rate_limit(self) -> None:
        """Sleep so consecutive requests are at least rate_limit_delay seconds apart."""
        wait = self.settings.rate_limit_delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _get(self, url: str) -> bytes:
        self._respect_rate_limit()
        request = urllib.request.Request(url, headers={"User-Agent": "rag-research-assistant/0.1"})
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
            return response.read()

    def fetch_papers(
        self, max_results: int | None = None, start: int = 0, category: str | None = None
    ) -> list[ArxivPaper]:
        """Return the newest papers in a category, newest first."""
        params = {
            "search_query": f"cat:{category or self.settings.search_category}",
            "start": start,
            "max_results": max_results or self.settings.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        xml = self._get(f"{self.settings.base_url}?{urllib.parse.urlencode(params)}")
        return self._parse_feed(xml)

    def _parse_feed(self, xml: bytes) -> list[ArxivPaper]:
        ns = self.settings.namespaces
        root = ET.fromstring(xml)
        papers: list[ArxivPaper] = []
        for entry in root.findall("atom:entry", ns):
            arxiv_id = entry.findtext("atom:id", default="", namespaces=ns).rsplit("/abs/", 1)[-1]
            pdf_url = next(
                (link.get("href", "") for link in entry.findall("atom:link", ns) if link.get("title") == "pdf"),
                f"https://arxiv.org/pdf/{arxiv_id}",
            )
            published = entry.findtext("atom:published", default="", namespaces=ns).replace("Z", "+00:00")
            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=" ".join(entry.findtext("atom:title", default="", namespaces=ns).split()),
                    authors=[
                        a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)
                    ],
                    abstract=" ".join(entry.findtext("atom:summary", default="", namespaces=ns).split()),
                    categories=[c.get("term", "") for c in entry.findall("atom:category", ns)],
                    published=datetime.fromisoformat(published),
                    pdf_url=pdf_url,
                )
            )
        return papers

    def download_pdf(self, paper: ArxivPaper) -> Path:
        """Download a paper's PDF into the cache (skipped if already cached), retrying with exponential backoff."""
        target = Path(self.settings.pdf_cache_dir) / f"{paper.arxiv_id.replace('/', '_')}.pdf"
        if target.exists() and target.stat().st_size > 0:
            return target

        last_error: Exception | None = None
        for attempt in range(self.settings.download_max_retries):
            try:
                target.write_bytes(self._get(paper.pdf_url))
                return target
            except Exception as error:  # network errors, timeouts, HTTP 5xx
                last_error = error
                time.sleep(self.settings.download_retry_base * (2**attempt))
        raise RuntimeError(f"Failed to download {paper.arxiv_id} after retries") from last_error
