import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

try:
    from langchain_openai import OpenAI
except ImportError:  # pragma: no cover
    try:
        from langchain.llms import OpenAI
    except ImportError:
        OpenAI = None

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

NODE_LABELS = {"Disease": "Disease", "Drug": "Drug", "Symptom": "Symptom"}
RELATIONSHIP_TYPES = {"TREATS", "INDICATES", "CONTRAINDICATED"}


class NullNeo4jGraph:
    def close(self):
        return None

    def run_query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []

    def ingest_relationships(self, facts: List[Dict[str, str]]):
        return None

    def ingest_documents(self, documents: List[Dict[str, Any]], **kwargs):
        return None

    def fetch_related(self, entity_name: str, relationship_types: List[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    def find_direct_relationships(self, search_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        return []


class Neo4jGraph:
    def __init__(self, uri: str, user: str, password: str, llm_model: str = "gpt-4"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.llm_model = llm_model
        self.llm = self._initialize_llm()

    @classmethod
    def from_env(cls):
        uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j12345")
        llm_model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

        try:
            graph = cls(uri, user, password, llm_model=llm_model)
            with graph.driver.session() as session:
                session.run("RETURN 1")
            return graph
        except Exception as exc:
            logger.warning("Neo4j connection failed (%s): %s. Falling back to no-op graph.", exc.__class__.__name__, exc)
            return NullNeo4jGraph()

    def _initialize_llm(self):
        if OpenAI is None:
            logger.warning("LangChain OpenAI client is unavailable. Graph extraction will use a simple fallback parser.")
            return None

        try:
            return OpenAI(model_name=self.llm_model, temperature=0)
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI model %s: %s. Falling back to simple extraction.", self.llm_model, exc)
            return None

    def close(self):
        if self.driver:
            self.driver.close()

    def run_query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def ingest_relationships(self, facts: List[Dict[str, str]]):
        if not facts:
            return

        with self.driver.session() as session:
            for fact in facts:
                source_label = NODE_LABELS.get(fact.get("source_type"), "Entity")
                target_label = NODE_LABELS.get(fact.get("target_type"), "Entity")
                relation = fact.get("relation", "RELATED")
                relation = relation if relation in RELATIONSHIP_TYPES else "RELATED"

                query = (
                    f"MERGE (a:{source_label} {{name: $source}}) "
                    f"MERGE (b:{target_label} {{name: $target}}) "
                    f"MERGE (a)-[r:{relation}]->(b)"
                )
                session.run(
                    query,
                    source=fact.get("source"),
                    target=fact.get("target"),
                )

    def ingest_documents(self, documents: List[Dict[str, Any]], chunk_limit: Optional[int] = None, batch_size: int = 20):
        facts_batch: List[Dict[str, str]] = []
        processed_chunks = 0

        for document in documents:
            chunks = document.get("chunks", [])
            if chunk_limit is not None:
                chunks = chunks[:chunk_limit]

            for chunk in chunks:
                processed_chunks += 1
                facts = self.extract_graph_facts(chunk)
                if facts:
                    facts_batch.extend(facts)

                if len(facts_batch) >= batch_size:
                    self.ingest_relationships(facts_batch)
                    facts_batch = []

        if facts_batch:
            self.ingest_relationships(facts_batch)

        logger.info("Ingested graph facts from %d chunks into Neo4j.", processed_chunks)

    def extract_graph_facts(self, text: str) -> List[Dict[str, str]]:
        if self.llm is not None:
            return self._extract_with_llm(text)

        return self._fallback_extract_facts(text)

    def _extract_with_llm(self, text: str) -> List[Dict[str, str]]:
        prompt = (
            "Extract medical entities and relationships from the text below. "
            "Only return JSON. Use entity labels Disease, Drug, Symptom and relationships TREATS, INDICATES, CONTRAINDICATED. "
            "Return an array of objects with keys: source, source_type, relation, target. "
            "Text:\n" + text
        )

        try:
            raw_response = self.llm(prompt)
            cleaned = self._clean_llm_response(raw_response)
            facts = json.loads(cleaned)
            if isinstance(facts, list):
                return [self._normalize_fact(fact) for fact in facts if self._is_valid_fact(fact)]
        except Exception as exc:
            logger.warning("LLM extraction failed: %s. Falling back to simple parser.", exc)

        return self._fallback_extract_facts(text)

    @staticmethod
    def _clean_llm_response(response: str) -> str:
        if "```json" in response:
            response = response.split("```json", 1)[1]
        if "```" in response:
            response = response.split("```", 1)[0]
        return response.strip()

    @staticmethod
    def _normalize_fact(fact: Dict[str, Any]) -> Dict[str, str]:
        return {
            "source": str(fact.get("source", "")).strip(),
            "source_type": str(fact.get("source_type", "")).strip().title(),
            "relation": str(fact.get("relation", "")).strip().upper(),
            "target": str(fact.get("target", "")).strip(),
            "target_type": str(fact.get("target_type", "")).strip().title(),
        }

    @staticmethod
    def _is_valid_fact(fact: Dict[str, Any]) -> bool:
        return (
            isinstance(fact, dict)
            and fact.get("source")
            and fact.get("target")
            and fact.get("relation")
        )

    @staticmethod
    def _fallback_extract_facts(text: str) -> List[Dict[str, str]]:
        """Extract medical facts from text using pattern matching and keyword detection."""
        text_lower = text.lower()
        facts: List[Dict[str, str]] = []
        
        # Disease-related keywords
        diseases = ["heart failure", "kidney disease", "diabetes", "hypertension", "cancer", "stroke", 
                   "infection", "sepsis", "pneumonia", "fibrillation", "myocardial infarction", "arrhythmia",
                   "left ventricular hypertrophy", "chronic kidney disease", "acute kidney injury", "disease"]
        
        # Symptom-related keywords
        symptoms = ["chest pain", "shortness of breath", "fever", "fatigue", "hypertension", "hypotension",
                   "tachycardia", "bradycardia", "edema", "swelling", "weakness", "palpitations", "dizziness"]
        
        # Drug/Treatment keywords
        drugs = ["inhibitor", "agonist", "antagonist", "therapy", "medication", "drug", "treatment",
                "sodium-glucose cotransporter", "ace inhibitor", "beta blocker", "diuretic", "antibiotic",
                "chemotherapy", "immunotherapy", "antibody", "vaccine", "finerenone"]
        
        # Extract diseases
        found_diseases = [d for d in diseases if d in text_lower]
        
        # Extract symptoms
        found_symptoms = [s for s in symptoms if s in text_lower]
        
        # Extract drug mentions
        found_drugs = [d for d in drugs if d in text_lower]
        
        # Build relationships: Symptom -> Disease (INDICATES)
        for symptom in found_symptoms:
            for disease in found_diseases:
                if symptom != disease:
                    facts.append({
                        "source": symptom.title(),
                        "source_type": "Symptom",
                        "relation": "INDICATES",
                        "target": disease.title(),
                        "target_type": "Disease",
                    })
                    break  # Limit to one disease per symptom
        
        # Build relationships: Drug -> Disease (TREATS)
        for drug in found_drugs:
            for disease in found_diseases:
                facts.append({
                    "source": drug.title(),
                    "source_type": "Drug",
                    "relation": "TREATS",
                    "target": disease.title(),
                    "target_type": "Disease",
                })
                break  # Limit to one disease per drug
        
        # If we found diseases but no relationships, create at least one
        if not facts and found_diseases:
            disease = found_diseases[0]
            facts.append({
                "source": "Clinical Evidence",
                "source_type": "Symptom",
                "relation": "INDICATES",
                "target": disease.title(),
                "target_type": "Disease",
            })
        
        return facts

    def find_direct_relationships(self, search_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not search_text:
            return []

        query = (
            "MATCH (a)-[r]-(b) "
            "WHERE toLower(a.name) CONTAINS toLower($text) OR toLower(b.name) CONTAINS toLower($text) "
            "RETURN a.name AS source, labels(a)[0] AS source_type, type(r) AS relation, "
            "b.name AS target, labels(b)[0] AS target_type LIMIT $limit"
        )
        return self.run_query(query, {"text": search_text, "limit": limit})

    def fetch_related(self, entity_name: str, relationship_types: List[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        relation_filter = ""
        if relationship_types:
            relation_filter = f"WHERE type(r) IN [{', '.join(repr(t) for t in relationship_types)}]"

        query = (
            "MATCH (a {name: $name})-[r]->(b) "
            f"{relation_filter} " if relation_filter else ""
            "RETURN b.name AS related, type(r) AS relation LIMIT $limit"
        )
        return self.run_query(query, {"name": entity_name, "limit": limit})


def load_documents_from_json(path: str):
    from pathlib import Path

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"PubMed JSON data not found at {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return [item for item in data if isinstance(item, dict)]


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    json_path = root_dir / "ingestion" / "pubmed_documents.json"
    logger.info("Loading PubMed ingestion data from %s", json_path)
    documents = load_documents_from_json(str(json_path))

    graph = Neo4jGraph.from_env()
    if isinstance(graph, NullNeo4jGraph):
        logger.error("Neo4j is unavailable. Ensure NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are configured.")
        return

    graph.ingest_documents(documents)
    logger.info("Neo4j ingestion complete.")

    counts = graph.run_query("MATCH (n) RETURN labels(n) AS labels, count(n) AS count")
    logger.info("Node labels summary: %s", counts)


if __name__ == "__main__":
    main()
