import subprocess
import sys

# Run ingestion script
result = subprocess.run([sys.executable, "run_ingestion.py"], cwd=r"e:\Projects\LLM-Powered Clinical Decision Support System with RAG + Medical Knowledge Graph")
sys.exit(result.returncode)
