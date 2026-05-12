#!/usr/bin/env python
"""
Populate ChromaDB with PubMed medical documents and their embeddings.
This enables vector similarity search for the RAG system.
"""
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
root_dir = Path(__file__).resolve().parent
load_dotenv(root_dir / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from graph.vector_store_manager import VectorStoreManager

def main():
    """Execute vector store indexing pipeline."""
    logger.info("=" * 70)
    logger.info("CHROMADB VECTOR STORE INDEXING")
    logger.info("=" * 70)
    
    # Initialize vector store manager
    logger.info("\n1. Initializing ChromaDB vector store...")
    try:
        manager = VectorStoreManager()
        logger.info(f"   ✓ ChromaDB initialized at {manager.persist_dir}")
    except Exception as e:
        logger.error(f"   ❌ Failed to initialize ChromaDB: {e}")
        return
    
    # Load documents from JSON
    logger.info("\n2. Loading PubMed documents from JSON...")
    try:
        documents = manager.load_documents_from_json()
        if not documents:
            logger.warning("   ⚠ No documents found in JSON file")
            return
        logger.info(f"   ✓ Loaded {len(documents)} document chunks")
    except Exception as e:
        logger.error(f"   ❌ Failed to load documents: {e}")
        return
    
    # Index documents with embeddings
    logger.info("\n3. Generating embeddings and indexing documents...")
    logger.info(f"   Using model: {manager.embedding_model}")
    try:
        manager.index_documents(documents)
        logger.info(f"   ✓ Successfully indexed {len(documents)} documents into ChromaDB")
    except Exception as e:
        logger.error(f"   ❌ Indexing failed: {e}")
        return
    
    # Verify indexing with a test query
    logger.info("\n4. Testing vector search...")
    try:
        test_query = "heart failure treatment"
        results = manager.search(test_query, top_k=3)
        logger.info(f"   ✓ Test query: '{test_query}'")
        logger.info(f"   ✓ Found {len(results)} results:")
        for i, hit in enumerate(results, 1):
            meta = hit.get("metadata", {})
            snippet = hit.get("document", "")[:150]
            logger.info(f"      [{i}] PMID={meta.get('pmid')} | {snippet}...")
    except Exception as e:
        logger.error(f"   ⚠ Test search failed: {e}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ ChromaDB vector store ready for RAG queries!")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
