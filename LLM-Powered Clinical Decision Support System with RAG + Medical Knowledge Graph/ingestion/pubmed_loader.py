import logging
import os
import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from Bio import Entrez

from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / ".env")

if os.getenv("PUBMED_DISABLE_SSL_VERIFY", "False").lower() == "true":
    ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, length_function=None):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.length_function = length_function or len

        def split_text(self, text: str) -> List[str]:
            text = text or ""
            text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            if not text:
                return []

            chunks = []
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                if end == len(text):
                    break
                start = max(end - self.chunk_overlap, end)
            return chunks


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

SPECIALTIES = [
    "Cardiology",
    "Oncology",
    "Endocrinology",
    "Neurology",
    "Pediatrics",
    "Pharmacology",
    "Infectious Diseases",
]

@dataclass
class PubMedDocument:
    category: str
    pmid: str
    title: str
    abstract: str
    doi: Optional[str]
    publication_date: Optional[str]
    source_url: str
    chunks: List[str]

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "category": self.category,
            "pmid": self.pmid,
            "title": self.title,
            "abstract": self.abstract,
            "doi": self.doi,
            "publication_date": self.publication_date,
            "source_url": self.source_url,
            "chunks": self.chunks,
        }


class PubMedLoader:
    def __init__(
        self,
        email: str,
        api_key: Optional[str] = None,
        max_per_specialty: int = 100,
        batch_size: int = 20,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.email = email
        self.api_key = api_key
        self.max_per_specialty = max_per_specialty
        self.batch_size = batch_size
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        Entrez.email = self.email
        if self.api_key:
            Entrez.api_key = self.api_key

    def search_pubmed(self, term: str) -> List[str]:
        logger.info("Searching PubMed for category=%s max=%s", term, self.max_per_specialty)
        with Entrez.esearch(
            db="pubmed",
            term=term,
            retmax=self.max_per_specialty,
            sort="pub date",
            retmode="xml",
        ) as handle:
            result = Entrez.read(handle)
        ids = result.get("IdList", [])
        logger.info("Found %d paper ids for %s", len(ids), term)
        return ids

    def fetch_records(self, pmids: List[str], category: str) -> Iterator[PubMedDocument]:
        if not pmids:
            return

        logger.debug("Fetching batch of %d PubMed records for %s", len(pmids), category)
        with Entrez.efetch(
            db="pubmed",
            id=','.join(pmids),
            rettype="abstract",
            retmode="xml",
        ) as handle:
            xml_root = ET.parse(handle).getroot()

        for article_element in xml_root.findall('.//PubmedArticle'):
            document = self._parse_article(article_element, category)
            if document:
                yield document

    def _parse_article(self, article_element: ET.Element, category: str) -> Optional[PubMedDocument]:
        pmid = self._get_text(article_element.find('.//PMID'))
        title = self._get_text(article_element.find('.//ArticleTitle'))
        abstract = self._extract_abstract(article_element)
        doi = self._extract_doi(article_element)
        publication_date = self._extract_publication_date(article_element)
        source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        if not title and not abstract:
            logger.debug("Skipping empty PubMed record pmid=%s", pmid)
            return None

        full_text = "\n\n".join(filter(None, [title, abstract]))
        chunks = self.text_splitter.split_text(full_text)

        return PubMedDocument(
            category=category,
            pmid=pmid,
            title=title,
            abstract=abstract,
            doi=doi,
            publication_date=publication_date,
            source_url=source_url,
            chunks=chunks,
        )

    @staticmethod
    def _extract_abstract(article_element: ET.Element) -> str:
        abstract_parts = []
        for abstract_text in article_element.findall('.//AbstractText'):
            text = PubMedLoader._get_text(abstract_text)
            label = abstract_text.attrib.get('Label')
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        return '\n'.join(part for part in abstract_parts if part)

    @staticmethod
    def _extract_doi(article_element: ET.Element) -> Optional[str]:
        for article_id in article_element.findall('.//ArticleId'):
            if article_id.attrib.get('IdType') == 'doi':
                return PubMedLoader._get_text(article_id)
        return None

    @staticmethod
    def _extract_publication_date(article_element: ET.Element) -> Optional[str]:
        journal_pub_date = article_element.find('.//Journal/JournalIssue/PubDate')
        article_date = article_element.find('.//ArticleDate')
        for date_element in (article_date, journal_pub_date):
            if date_element is None:
                continue
            year = PubMedLoader._get_text(date_element.find('Year'))
            month = PubMedLoader._get_text(date_element.find('Month'))
            day = PubMedLoader._get_text(date_element.find('Day'))
            if year:
                try:
                    month_int = PubMedLoader._month_to_int(month)
                    date_obj = datetime(
                        int(year),
                        month_int if month_int else 1,
                        int(day) if day and day.isdigit() else 1,
                    )
                    return date_obj.date().isoformat()
                except ValueError:
                    return year

        return None

    @staticmethod
    def _month_to_int(month: Optional[str]) -> Optional[int]:
        if not month:
            return None
        try:
            return int(month)
        except ValueError:
            mapping = {
                'Jan': 1,
                'Feb': 2,
                'Mar': 3,
                'Apr': 4,
                'May': 5,
                'Jun': 6,
                'Jul': 7,
                'Aug': 8,
                'Sep': 9,
                'Oct': 10,
                'Nov': 11,
                'Dec': 12,
            }
            return mapping.get(month[:3].title())

    @staticmethod
    def _get_text(element: Optional[ET.Element]) -> str:
        return element.text.strip() if element is not None and element.text else ''

    @staticmethod
    def _chunk_list(items: List[str], size: int) -> Iterator[List[str]]:
        for start in range(0, len(items), size):
            yield items[start:start + size]

    def stream_documents(self, categories: Optional[List[str]] = None) -> Iterator[PubMedDocument]:
        categories = categories or SPECIALTIES
        for category in categories:
            ids = self.search_pubmed(category)
            downloaded = 0
            for batch in self._chunk_list(ids, self.batch_size):
                for document in self.fetch_records(batch, category):
                    downloaded += 1
                    yield document
            logger.info("Downloaded %d papers for %s", downloaded, category)

    def load_documents(self, categories: Optional[List[str]] = None) -> List[Dict[str, Optional[str]]]:
        return [doc.to_dict() for doc in self.stream_documents(categories)]


def main() -> None:
    email = os.getenv("PUBMED_EMAIL", "your.email@domain.com")
    api_key = os.getenv("PUBMED_API_KEY")
    if api_key and api_key.strip().upper() == "NONE":
        api_key = None
    loader = PubMedLoader(email=email, api_key=api_key, max_per_specialty=300)
    records = []

    for document in loader.stream_documents():
        records.append(document.to_dict())

    logger.info("Total articles loaded: %d", len(records))
    for category in SPECIALTIES:
        count = sum(1 for record in records if record["category"] == category)
        logger.info("Category %s: %d records", category, count)

    output_path = Path(__file__).resolve().parent / "pubmed_documents.json"
    with output_path.open("w", encoding="utf-8") as output_file:
        import json

        json.dump(records, output_file, indent=2, ensure_ascii=False)
    logger.info("Saved structured PubMed data to %s", output_path)


if __name__ == "__main__":
    main()
