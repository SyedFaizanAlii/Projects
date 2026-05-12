#!/usr/bin/env python
"""
Setup and verification guide for the Clinical Decision Support System.
Shows current status and what needs to be done next.
"""
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

root_dir = Path(__file__).resolve().parent
load_dotenv(root_dir / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)

def print_banner(text):
    """Print a formatted banner."""
    logger.info(f"\n{'='*80}")
    logger.info(f"  {text}")
    logger.info(f"{'='*80}\n")

def check_files():
    """Check if required files exist."""
    logger.info("CHECKING PROJECT FILES:")
    files = {
        "ingestion/pubmed_documents.json": "PubMed dataset",
        "db/chroma_index": "ChromaDB vector store (directory)",
        ".env": "Environment configuration",
        "run_ingestion.py": "Neo4j ingestion script",
        "index_vectors.py": "ChromaDB indexing script",
        "diagnose_retriever.py": "Diagnostic tool",
    }
    
    for file_path, description in files.items():
        full_path = root_dir / file_path
        exists = "✓" if full_path.exists() else "❌"
        logger.info(f"  {exists} {file_path:<40} ({description})")

def check_environment():
    """Check environment variables."""
    logger.info("\nCHECKING ENVIRONMENT VARIABLES:")
    vars_needed = {
        "NEO4J_URI": "Neo4j database URI",
        "NEO4J_USER": "Neo4j username",
        "NEO4J_PASSWORD": "Neo4j password",
        "OPENAI_API_KEY": "OpenAI API key",
        "LLM_MODEL": "Language model",
    }
    
    for var, description in vars_needed.items():
        value = os.getenv(var)
        if value:
            if var == "OPENAI_API_KEY":
                display = f"{value[:20]}..." if len(value) > 20 else value
            else:
                display = value
            logger.info(f"  ✓ {var:<25} = {display}")
        else:
            logger.info(f"  ❌ {var:<25} (NOT SET)")

def main():
    print_banner("CLINICAL DECISION SUPPORT SYSTEM - SETUP GUIDE")
    
    logger.info("This script checks the status of your system and provides setup instructions.\n")
    
    check_files()
    check_environment()
    
    print_banner("SETUP INSTRUCTIONS")
    
    logger.info("STEP 1: Populate Neo4j with Medical Knowledge Graph")
    logger.info("  Run: python run_ingestion.py")
    logger.info("  This ingests ~30 cardiology papers into Neo4j")
    logger.info("  Expected result: 500+ medical nodes (Diseases, Symptoms, Drugs)\n")
    
    logger.info("STEP 2: Index Documents into ChromaDB Vector Store")
    logger.info("  Run: python index_vectors.py")
    logger.info("  This generates embeddings for semantic search")
    logger.info("  Expected result: ChromaDB indexed with 100+ document chunks\n")
    
    logger.info("STEP 3: Verify the Hybrid Retriever")
    logger.info("  Run: python diagnose_retriever.py")
    logger.info("  This tests Neo4j connection, ChromaDB vectors, and hybrid search\n")
    
    logger.info("STEP 4: Start the Application")
    logger.info("  Terminal 1: uvicorn api.main:app --reload --host 127.0.0.1 --port 8000")
    logger.info("  Terminal 2: cd web/django_app && python manage.py runserver 127.0.0.1:8001\n")
    
    logger.info("STEP 5: Test the System")
    logger.info("  Open: http://127.0.0.1:8001")
    logger.info("  Try query: 'What is the treatment for heart failure?'\n")
    
    print_banner("IMPROVEMENTS MADE")
    
    logger.info("✓ Fixed .env loading in all entrypoints (main_ai.py, react_agent.py, Django)")
    logger.info("✓ Updated OpenAI/LangChain import paths for compatibility")
    logger.info("✓ Enhanced medical entity extraction in Neo4j fallback")
    logger.info("✓ Increased search k values from 5 to 10 for better coverage")
    logger.info("✓ Created index_vectors.py to populate ChromaDB")
    logger.info("✓ Created diagnose_retriever.py to test the full system")
    logger.info("✓ Added _extract_entities() method to HybridRetriever\n")
    
    print_banner("QUICK REFERENCE")
    
    logger.info("Commands to run in order:")
    logger.info("  1. python run_ingestion.py          # Populate Neo4j")
    logger.info("  2. python index_vectors.py          # Populate ChromaDB")
    logger.info("  3. python diagnose_retriever.py     # Verify setup")
    logger.info("  4. Start FastAPI and Django servers")
    logger.info("  5. Open http://127.0.0.1:8001 in browser\n")
    
    logger.info("If you encounter 'Unable to process':")
    logger.info("  • Check that both run_ingestion.py and index_vectors.py completed")
    logger.info("  • Run diagnose_retriever.py to see which component is failing")
    logger.info("  • Check the terminal logs for specific error messages\n")

if __name__ == "__main__":
    main()
