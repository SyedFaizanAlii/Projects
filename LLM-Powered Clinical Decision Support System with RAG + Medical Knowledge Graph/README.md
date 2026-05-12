# LLM-Powered Clinical Decision Support System with RAG + Medical Knowledge Graph

A healthcare AI platform supporting explainable clinical retrieval and reasoning from structured medical knowledge and literature. This repository combines:

- PubMed ingestion and PDF parsing
- ChromaDB vector retrieval with medical embeddings
- Neo4j knowledge graph construction and multi-hop reasoning
- LangChain ReAct-style orchestration for hybrid retrieval
- Bias audit module for demographic fairness analysis
- Django web frontend with query interface and source citations
- FastAPI integration endpoint for hospital system connectivity

## Architecture

1. Knowledge Ingestion: `ingestion/pubmed_loader.py`
2. Vector Store: `rag/hybrid_retriever.py`
3. Knowledge Graph: `graph/neo4j_builder.py`
4. Agent Orchestration: `agents/react_agent.py`
5. Bias Audit: `bias/audit.py`
6. Frontend: `web/django_app/`
7. REST API: `api/main.py`

## Quick start

1. Create a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Start the FastAPI service:

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

3. Start the Django web interface:

```powershell
cd web/django_app
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

## Notes

- Configure Neo4j credentials via environment variables: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Add `OPENAI_API_KEY` for OpenAI-based LLM support
- The loaders and retriever modules include safe defaults and stubbed fallback logic for local development
