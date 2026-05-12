import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)

from rag.hybrid_retriever import HybridRetriever
from graph.neo4j_builder import Neo4jGraph

try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:
    Cerebras = None

logger = logging.getLogger(__name__)


class ReactAgent:
    """ReAct agent for clinical queries — RAG + Cerebras LLM synthesis."""

    def __init__(self, retriever: HybridRetriever, graph: Neo4jGraph, model: str = "llama3.1-8b"):
        self.retriever = retriever
        self.graph = graph
        self.model = os.getenv("LLM_MODEL", model)
        self.cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
        self.ai_enabled = bool(self.cerebras_api_key) and Cerebras is not None

    def answer(self, query: str, demographic_filters: Optional[Dict[str, Any]] = None, max_steps: int = 3) -> Dict[str, Any]:
        """
        Process a clinical query using ChromaDB RAG + Cerebras LLM.
        Returns: answer, sources (document only), confidence (evidence-based).
        """
        evidence = self.retriever.hybrid_search(query, top_k=10)
        vector_results = evidence.get("vector_results", [])

        # Build sources from ChromaDB documents only (graph relationships are internal)
        sources = self._build_doc_sources(vector_results)

        # Compute confidence from retrieval quality (distance scores)
        confidence = self._compute_confidence(vector_results)

        if not evidence.get("has_evidence") or not vector_results:
            return {
                "query": query,
                "answer": (
                    "No relevant medical evidence was found in the database for this query. "
                    "Try rephrasing your question or using more specific medical terminology."
                ),
                "sources": [],
                "confidence": 0.0,
                "steps": [],
            }

        # Synthesize answer with LLM if available, else local summary
        if self.ai_enabled:
            answer_text = self._synthesize_with_llm(query, evidence)
        else:
            answer_text = self._local_summary(vector_results)

        return {
            "query": query,
            "answer": answer_text,
            "sources": sources,
            "confidence": confidence,
            "steps": [],
        }

    def _build_doc_sources(self, vector_results: List[Dict]) -> List[Dict]:
        """Build clean document source cards from ChromaDB results."""
        sources = []
        seen_pmids = set()
        for item in vector_results:
            meta = item.get("metadata", {})
            pmid = meta.get("pmid", "")
            # Deduplicate by PMID so we don't show the same paper twice
            if pmid and pmid in seen_pmids:
                continue
            if pmid:
                seen_pmids.add(pmid)

            doi = meta.get("doi", "")
            pubmed_url = meta.get("source_url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            title = meta.get("title", "")
            specialty = meta.get("specialty", "")
            pub_date = meta.get("publication_date", "")
            # Get a clean abstract snippet (not the chunked text which has title prepended)
            snippet = item.get("document", "")
            # Strip the title from the snippet if it starts with it
            if title and snippet.startswith(title):
                snippet = snippet[len(title):].lstrip("\n ")
            snippet = snippet[:280]

            sources.append({
                "type": "document",
                "pmid": pmid,
                "title": title,
                "specialty": specialty,
                "publication_date": pub_date,
                "doi": doi,
                "pubmed_url": pubmed_url,
                "snippet": snippet,
                "distance": item.get("distance", 1.0),
            })
        return sources[:8]  # cap at 8 cards

    def _compute_confidence(self, vector_results: List[Dict]) -> float:
        """
        Compute confidence from ChromaDB cosine distances.
        Distance 0 = perfect match, distance 1 = completely dissimilar.
        We invert and scale: similarity = 1 - distance.
        """
        if not vector_results:
            return 0.0
        # Average similarity of top 5 results
        distances = [r.get("distance", 1.0) for r in vector_results[:5]]
        avg_similarity = 1.0 - (sum(distances) / len(distances))
        # Scale to a user-friendly 0–1 range with a floor of 0.1 if evidence exists
        confidence = max(0.1, min(0.97, avg_similarity))
        return round(confidence, 2)

    def _synthesize_with_llm(self, query: str, evidence: Dict) -> str:
        """Use Cerebras LLM to synthesize clinical answer from retrieved evidence."""
        context = evidence.get("context", "")
        prompt = (
            "You are a clinical decision support assistant. "
            "Answer the question below using ONLY the evidence provided. "
            "Be concise, clinical, and precise. Use numbered points where appropriate. "
            "Do NOT say 'insufficient evidence' unless the evidence truly contains nothing relevant. "
            "Do NOT fabricate drug names, dosages, or facts not present in the evidence.\n\n"
            f"{context}\n\n"
            f"Clinical Question: {query}\n"
            "Answer:"
        )
        try:
            client = Cerebras(api_key=self.cerebras_api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                max_tokens=600,
            )
            text = response.choices[0].message.content.strip()
            if not text or (len(text) < 80 and "insufficient" in text.lower()):
                return self._local_summary(evidence.get("vector_results", []))
            return text
        except Exception as e:
            logger.warning("Cerebras LLM call failed: %s. Using local summary.", e)
            return self._local_summary(evidence.get("vector_results", []))

    def _local_summary(self, vector_results: List) -> str:
        """Build a summary from vector results without LLM."""
        if not vector_results:
            return "No relevant clinical evidence was found in the database."
        parts = [f"Based on {len(vector_results)} retrieved PubMed documents:\n"]
        for i, r in enumerate(vector_results[:3], 1):
            meta = r.get("metadata", {})
            title = meta.get("title", "")
            snippet = r.get("document", "")[:250]
            parts.append(f"[{i}] {title}\n{snippet}\n")
        return "\n".join(parts)
