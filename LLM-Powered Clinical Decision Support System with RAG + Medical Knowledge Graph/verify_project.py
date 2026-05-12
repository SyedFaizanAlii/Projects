#!/usr/bin/env python3
"""
Quick diagnostic to debug retrieval system failures.
"""
import logging
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent
load_dotenv(root_dir / ".env")

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Test 1: ChromaDB directly
logger.info("\n=== TEST 1: ChromaDB Direct ===")
try:
    from graph.vector_store_manager import VectorStoreManager
    manager = VectorStoreManager()
    logger.info(f"ChromaDB path: {manager.persist_dir}")
    logger.info(f"Collection count: {manager.collection.count()}")
    
    if manager.collection.count() == 0:
        logger.warning("❌ ChromaDB is EMPTY - need to run index_vectors.py")
    else:
        logger.info(f"✓ ChromaDB has {manager.collection.count()} documents")
except Exception as e:
    logger.error(f"ChromaDB test failed: {e}")

# Test 2: Neo4j directly
logger.info("\n=== TEST 2: Neo4j Direct ===")
try:
    from graph.neo4j_builder import Neo4jGraph, NullNeo4jGraph
    graph = Neo4jGraph.from_env()
    
    if isinstance(graph, NullNeo4jGraph):
        logger.error("❌ Neo4j is unavailable")
    else:
        count_result = graph.run_query("MATCH (n) RETURN count(n) AS c")
        count = count_result[0]['c'] if count_result else 0
        logger.info(f"✓ Neo4j has {count} nodes")
        
        # Try a specific query
        heart_failure = graph.run_query("MATCH (n {name: 'Heart Failure'}) RETURN n LIMIT 1")
        if heart_failure:
            logger.info("✓ Found 'Heart Failure' node")
        else:
            logger.warning("⚠ 'Heart Failure' node not found")
        
        graph.close()
except Exception as e:
    logger.error(f"❌ Neo4j test failed: {e}")

# Test 3: HybridRetriever initialization
logger.info("\n=== TEST 3: HybridRetriever ===")
try:
    from rag.hybrid_retriever import HybridRetriever
    retriever = HybridRetriever()
    logger.info("✓ HybridRetriever initialized")
    logger.info(f"  Graph active: {retriever.graph_is_active}")
except Exception as e:
    logger.error(f"❌ HybridRetriever init failed: {e}")

# Test 4: Vector search
logger.info("\n=== TEST 4: Vector Search ===")
try:
    retriever._ensure_vector_manager()
    if retriever.vector_manager is None:
        logger.error("❌ Vector manager is None")
    else:
        results = retriever.vector_search("heart failure", top_k=5)
        logger.info(f"Vector search results: {len(results)}")
        if not results:
            logger.error("❌ Vector search returned 0 results - need index_vectors.py")
        for r in results[:3]:
            logger.info(f"  - {r.get('metadata', {}).get('pmid')}: {r.get('document', '')[:80]}...")
except Exception as e:
    logger.error(f"❌ Vector search failed: {e}")

# Test 5: Graph search
logger.info("\n=== TEST 5: Graph Search ===")
try:
    results = retriever.graph_search("heart failure", top_k=5)
    logger.info(f"Graph search results: {len(results)}")
    if not results:
        logger.warning("⚠ Graph search returned 0 results")
    for r in results[:3]:
        logger.info(f"  - {r.get('source')} --[{r.get('relation')}]--> {r.get('target')}")
except Exception as e:
    logger.error(f"❌ Graph search failed: {e}")

# Test 6: Hybrid search
logger.info("\n=== TEST 6: Hybrid Search ===")
try:
    result = retriever.hybrid_search("heart failure treatment", top_k=10)
    logger.info(f"Has evidence: {result.get('has_evidence')}")
    logger.info(f"Vector results: {len(result.get('vector_results', []))}")
    logger.info(f"Graph results: {len(result.get('graph_results', []))}")
    
    if not result.get('has_evidence'):
        logger.error("❌ NO EVIDENCE FOUND - This is why you get 'Unable to process'")
    else:
        logger.info("✓ Evidence found, should return results")
except Exception as e:
    logger.error(f"❌ Hybrid search failed: {e}")

# Test 7: Clinical Agent answer
logger.info("\n=== TEST 7: Clinical Agent ===")
try:
    from main_ai import ClinicalAgent
    agent = ClinicalAgent()
    logger.info(f"Agent ready: {agent.is_ready()}")
    
    result = agent.answer("What is heart failure?")
    logger.info(f"Answer: {result.get('answer', 'NO ANSWER')[:200]}...")
    logger.info(f"Confidence: {result.get('confidence', 0)}")
    logger.info(f"Sources: {len(result.get('sources', []))}")
except Exception as e:
    logger.error(f"❌ Clinical agent failed: {e}")

logger.info("\n" + "="*80)
logger.info("DIAGNOSIS COMPLETE - Check output above for ❌ errors")
logger.info("="*80)
