import logging
from pathlib import Path
from typing import List

from graph.neo4j_builder import Neo4jGraph
from graph.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

TEST_QUERY = "treatment for hypertension and cardiac disease"


def verify_vector_store() -> bool:
    try:
        manager = VectorStoreManager()
        results = manager.search(TEST_QUERY, top_k=5)
        logger.info("ChromaDB returned %d results for test query.", len(results))

        for idx, hit in enumerate(results, start=1):
            logger.info("Result %d: id=%s specialty=%s doi=%s pmid=%s distance=%s", idx,
                        hit.get("id"),
                        hit.get("metadata", {}).get("specialty"),
                        hit.get("metadata", {}).get("doi"),
                        hit.get("metadata", {}).get("pmid"),
                        hit.get("distance"),
                        )

        return len(results) > 0
    except Exception as exc:
        logger.exception("Vector store verification failed: %s", exc)
        return False


def verify_neo4j() -> bool:
    graph = Neo4jGraph.from_env()
    if not hasattr(graph, "run_query"):
        logger.warning("Neo4j graph is not available.")
        return False

    node_count = graph.run_query("MATCH (n) RETURN count(n) AS count")
    rel_count = graph.run_query("MATCH ()-[r]->() RETURN count(r) AS count")

    nodes = node_count[0]["count"] if node_count else 0
    rels = rel_count[0]["count"] if rel_count else 0
    logger.info("Neo4j has %d nodes and %d relationships.", nodes, rels)

    if nodes > 0 and rels > 0:
        sample = graph.fetch_related("Hypertension", relationship_types=["TREATS", "INDICATES", "CONTRAINDICATED"], limit=3)
        logger.info("Sample related entities: %s", sample)
        return True

    return False


def main() -> None:
    logger.info("Running Phase 2 brain verification...")
    vector_ok = verify_vector_store()
    neo4j_ok = verify_neo4j()

    summary = [
        f"Vector store verification: {'PASS' if vector_ok else 'FAIL'}",
        f"Neo4j verification: {'PASS' if neo4j_ok else 'FAIL'}",
    ]
    logger.info("Verification summary: %s", " | ".join(summary))

    if not vector_ok or not neo4j_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
