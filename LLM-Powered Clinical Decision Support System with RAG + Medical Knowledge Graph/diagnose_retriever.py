#!/usr/bin/env python
"""
Diagnostic script to verify HybridRetriever is pulling from both Neo4j and ChromaDB.
Tests vector search, graph search, and hybrid retrieval.
"""
import logging
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent
load_dotenv(root_dir / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from rag.hybrid_retriever import HybridRetriever
from graph.neo4j_builder import Neo4jGraph, NullNeo4jGraph

def diagnose():
    """Run diagnostic tests on the retrieval system."""
    logger.info("=" * 80)
    logger.info("HYBRID RETRIEVER DIAGNOSTICS")
    logger.info("=" * 80)
    
    # Test 1: Neo4j Connection
    logger.info("\n[TEST 1] Neo4j Graph Connection")
    logger.info("-" * 80)
    try:
        graph = Neo4jGraph.from_env()
        if isinstance(graph, NullNeo4jGraph):
            logger.error("❌ Neo4j is unavailable. Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
            return
        
        # Count nodes
        node_count_result = graph.run_query("MATCH (n) RETURN count(n) AS total")
        node_count = node_count_result[0]['total'] if node_count_result else 0
        
        # Count relationships
        rel_count_result = graph.run_query("MATCH ()-[r]->() RETURN count(r) AS total")
        rel_count = rel_count_result[0]['total'] if rel_count_result else 0
        
        logger.info(f"✓ Neo4j connected successfully")
        logger.info(f"  • Nodes: {node_count}")
        logger.info(f"  • Relationships: {rel_count}")
        
        if node_count < 10:
            logger.warning(f"⚠ Low node count ({node_count}). Run 'python run_ingestion.py' first.")
        
        graph.close()
    except Exception as e:
        logger.error(f"❌ Neo4j test failed: {e}")
        return
    
    # Test 2: HybridRetriever Initialization
    logger.info("\n[TEST 2] HybridRetriever Initialization")
    logger.info("-" * 80)
    try:
        retriever = HybridRetriever()
        logger.info(f"✓ HybridRetriever initialized")
        logger.info(f"  • Chroma dir: {retriever.chroma_persist_dir}")
        logger.info(f"  • Embedding model: {retriever.embedding_model}")
        logger.info(f"  • Graph active: {retriever.graph_is_active}")
    except Exception as e:
        logger.error(f"❌ HybridRetriever initialization failed: {e}")
        return
    
    # Test 3: Vector Search (ChromaDB)
    logger.info("\n[TEST 3] Vector Search (ChromaDB)")
    logger.info("-" * 80)
    try:
        retriever._ensure_vector_manager()
        if retriever.vector_manager is None:
            logger.warning("⚠ Vector manager is None. ChromaDB may not be indexed.")
            logger.info("   Run 'python index_vectors.py' to populate ChromaDB")
        else:
            # Test query
            query = "heart failure"
            results = retriever.vector_search(query, top_k=3)
            
            if results:
                logger.info(f"✓ Vector search returned {len(results)} results for '{query}'")
                for i, hit in enumerate(results, 1):
                    meta = hit.get("metadata", {})
                    distance = hit.get("distance", 0.0)
                    snippet = hit.get("document", "")[:100]
                    logger.info(f"  [{i}] Distance: {distance:.3f} | {snippet}...")
            else:
                logger.warning(f"⚠ Vector search returned 0 results for '{query}'")
                logger.info("   ChromaDB may be empty. Run 'python index_vectors.py'")
    except Exception as e:
        logger.error(f"❌ Vector search test failed: {e}")
    
    # Test 4: Graph Search (Neo4j)
    logger.info("\n[TEST 4] Graph Search (Neo4j)")
    logger.info("-" * 80)
    try:
        query = "heart failure"
        results = retriever.graph_search(query, top_k=5)
        
        if results:
            logger.info(f"✓ Graph search returned {len(results)} results for '{query}'")
            for i, row in enumerate(results, 1):
                logger.info(f"  [{i}] {row.get('source')} --[{row.get('relation')}]--> {row.get('target')}")
        else:
            logger.warning(f"⚠ Graph search returned 0 results for '{query}'")
            logger.info("   Neo4j may not have relevant entities. Check ingestion results.")
    except Exception as e:
        logger.error(f"❌ Graph search test failed: {e}")
    
    # Test 5: Hybrid Search (Combined)
    logger.info("\n[TEST 5] Hybrid Search (Combined Neo4j + ChromaDB)")
    logger.info("-" * 80)
    try:
        query = "What are the symptoms and treatments for heart failure?"
        result = retriever.hybrid_search(query, top_k=5)
        
        vector_count = len(result.get("vector_results", []))
        graph_count = len(result.get("graph_results", []))
        has_evidence = result.get("has_evidence", False)
        
        logger.info(f"✓ Hybrid search completed for: '{query}'")
        logger.info(f"  • Vector results: {vector_count}")
        logger.info(f"  • Graph results: {graph_count}")
        logger.info(f"  • Has evidence: {has_evidence}")
        
        if has_evidence:
            context_preview = result.get("context", "")[:300]
            logger.info(f"  • Context: {context_preview}...")
        else:
            logger.warning("⚠ No evidence found. Ensure both Neo4j and ChromaDB are populated.")
    except Exception as e:
        logger.error(f"❌ Hybrid search test failed: {e}")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTICS COMPLETE")
    logger.info("=" * 80)
    logger.info("\n✓ Next steps:")
    logger.info("  1. If Neo4j nodes < 10: Run 'python run_ingestion.py'")
    logger.info("  2. If vector results = 0: Run 'python index_vectors.py'")
    logger.info("  3. If graph results = 0: Check Neo4j for entity 'Heart Failure'")
    logger.info("  4. Restart Django/FastAPI after fixing any issues")

if __name__ == "__main__":
    diagnose()
