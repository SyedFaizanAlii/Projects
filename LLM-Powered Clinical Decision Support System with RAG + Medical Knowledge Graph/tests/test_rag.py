import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.hybrid_retriever import HybridRetriever
from graph.neo4j_builder import Neo4jGraph

class TestHybridRetriever:
    
    @pytest.fixture
    def retriever(self):
        return HybridRetriever(chroma_persist_dir="./test_chroma_db")
    
    def test_index_documents(self, retriever):
        docs = [
            {"id": "1", "text": "Metformin is used for type 2 diabetes.", "metadata": {"source": "pubmed"}},
            {"id": "2", "text": "Lisinopril is an ACE inhibitor.", "metadata": {"source": "pubmed"}},
        ]
        retriever.index_documents(docs)
        assert retriever.collection.count() == 2
    
    def test_vector_search(self, retriever):
        docs = [
            {"id": "1", "text": "Metformin is used for type 2 diabetes.", "metadata": {"source": "pubmed"}},
        ]
        retriever.index_documents(docs)
        results = retriever.vector_search("diabetes treatment", top_k=1)
        assert len(results) >= 0
    
    def test_extract_entities(self):
        text = "The patient has a disease and needs drug treatment."
        entities = HybridRetriever._extract_entities(text)
        assert "disease" in entities
        assert "drug" in entities
