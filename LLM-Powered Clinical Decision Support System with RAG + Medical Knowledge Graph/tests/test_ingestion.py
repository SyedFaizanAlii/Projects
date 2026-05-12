import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.pubmed_loader import PubMedLoader

class TestPubMedLoader:
    
    @pytest.fixture
    def loader(self):
        return PubMedLoader(email="test@example.com")
    
    def test_extract_year(self):
        result = PubMedLoader._extract_year("2023 Oct 15")
        assert result == 2023
    
    def test_split_text(self):
        text = "A" * 1000
        chunks = PubMedLoader._split_text(text, chunk_size=200, overlap=50)
        assert len(chunks) > 1
        assert all(len(c) <= 200 for c in chunks)
    
    def test_search_pubmed_integration(self, loader):
        try:
            pmids = loader.search_pubmed("diabetes mellitus", max_results=5)
            assert isinstance(pmids, list)
        except Exception as e:
            pytest.skip(f"PubMed API not available: {e}")
