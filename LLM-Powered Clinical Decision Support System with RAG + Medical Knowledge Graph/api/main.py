import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agents.react_agent import ReactAgent
from rag.hybrid_retriever import HybridRetriever
from graph.neo4j_builder import Neo4jGraph

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logger = logging.getLogger(__name__)
app = FastAPI(title="CDSS Hybrid Retrieval API")

class QueryRequest(BaseModel):
    query: str
    demographic_filters: dict | None = None

@app.on_event("startup")
def startup_event():
    logger.info("API startup_event beginning")
    app.state.graph = Neo4jGraph.from_env()
    logger.info("Neo4jGraph initialized: %s", type(app.state.graph).__name__)
    try:
        app.state.retriever = HybridRetriever(graph=app.state.graph)
        logger.info("HybridRetriever initialized")
    except Exception as exc:
        logger.warning("HybridRetriever startup failed: %s. Falling back to minimal retriever.", exc)
        app.state.retriever = HybridRetriever(graph=app.state.graph)
    app.state.retriever.set_graph(app.state.graph)
    logger.info("Retriever graph set")
    app.state.agent = ReactAgent(app.state.retriever, app.state.graph)
    logger.info("ReactAgent initialized")

@app.on_event("shutdown")
def shutdown_event():
    app.state.graph.close()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "clinical-decision-support"}

@app.post("/api/query")
def query_clinical_assistant(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    response = app.state.agent.answer(request.query, demographic_filters=request.demographic_filters)
    return response
