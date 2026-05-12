#!/usr/bin/env python
"""
Run full Neo4j ingestion pipeline with PubMed medical dataset.
"""
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
root_dir = Path(__file__).resolve().parent
load_dotenv(root_dir / ".env")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from graph.neo4j_builder import Neo4jGraph, NullNeo4jGraph, load_documents_from_json

def main():
    """Execute ingestion pipeline."""
    json_path = root_dir / "ingestion" / "pubmed_documents.json"
    
    # Load documents
    logger.info(f"Loading PubMed data from {json_path}")
    try:
        documents = load_documents_from_json(str(json_path))
        logger.info(f"✓ Loaded {len(documents)} medical documents")
    except Exception as e:
        logger.error(f"Failed to load documents: {e}")
        return
    
    # Connect to Neo4j
    logger.info("Connecting to Neo4j...")
    graph = Neo4jGraph.from_env()
    if isinstance(graph, NullNeo4jGraph):
        logger.error("❌ Neo4j connection failed. Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        return
    logger.info("✓ Connected to Neo4j")
    
    # Clear existing data (optional - comment out to preserve)
    # logger.info("Clearing existing graph data...")
    # graph.run_query("MATCH (n) DETACH DELETE n")
    
    # Ingest documents
    logger.info(f"Ingesting {len(documents)} documents into Neo4j...")
    try:
        graph.ingest_documents(documents, chunk_limit=None)
        logger.info("✓ Ingestion complete")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return
    
    # Show statistics
    logger.info("\n=== INGESTION STATISTICS ===")
    node_counts = graph.run_query("MATCH (n) RETURN labels(n) AS labels, count(n) AS count")
    logger.info(f"Node counts by label: {node_counts}")
    
    total_nodes = graph.run_query("MATCH (n) RETURN count(n) AS total")
    if total_nodes:
        logger.info(f"✓ Total nodes: {total_nodes[0]['total']}")
    
    rel_counts = graph.run_query("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count")
    logger.info(f"Relationships: {rel_counts}")
    
    total_rels = graph.run_query("MATCH ()-[r]->() RETURN count(r) AS total")
    if total_rels:
        logger.info(f"✓ Total relationships: {total_rels[0]['total']}")
    
    graph.close()
    logger.info("\n✓ Ingestion pipeline complete!")

if __name__ == "__main__":
    main()
