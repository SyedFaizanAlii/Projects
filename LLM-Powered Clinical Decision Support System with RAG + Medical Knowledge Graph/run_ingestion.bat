@echo off
cd /d "e:\Projects\LLM-Powered Clinical Decision Support System with RAG + Medical Knowledge Graph"
.\.venv\Scripts\activate.bat
python run_ingestion.py
pause
