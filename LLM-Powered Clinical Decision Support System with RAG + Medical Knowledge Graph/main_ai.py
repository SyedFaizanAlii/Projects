import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path)

from graph.neo4j_builder import Neo4jGraph
from rag.hybrid_retriever import HybridRetriever

try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:  # pragma: no cover
    Cerebras = None

try:
    from langchain.chat_models import init_chat_model
    from langchain.tools import tool
    LANGCHAIN_AVAILABLE = True
except Exception:
    init_chat_model = None
    tool = None
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_MODEL_NAME = os.getenv("LLM_MODEL", "gpt-3.5-turbo")


class ClinicalAgent:
    def __init__(self, model_name: Optional[str] = None, max_steps: int = 3):
        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.max_steps = max_steps
        self.retriever = HybridRetriever()
        self.graph = self.retriever.graph
        self.cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
        self.llm = self._initialize_llm()
        self.tools = {
            "research_tool": self._research_tool,
            "knowledge_graph_tool": self._knowledge_graph_tool,
        }

    def _initialize_llm(self):
        return None

    def is_ready(self) -> bool:
        return bool(self.cerebras_api_key)

    def answer(self, query: str) -> Dict[str, Any]:
        evidence = self.retriever.hybrid_search(query, top_k=10)
        if not evidence["has_evidence"]:
            return self._insufficient_evidence_response(query)

        if self.cerebras_api_key is None and self.llm is None:
            return self._fallback_answer(query, evidence)

        will_use_langchain = LANGCHAIN_AVAILABLE and self.llm is not None
        if will_use_langchain:
            try:
                return self._run_react_agent(query)
            except Exception as exc:
                logger.warning("LangChain agent execution failed: %s", exc)

        return self._run_prompt_agent(query)

    def _run_react_agent(self, query: str) -> Dict[str, Any]:
        history: List[Dict[str, str]] = []

        for step in range(self.max_steps):
            prompt = self._build_prompt(query, history)
            model_response = self._call_llm(prompt)
            thought, action, action_input = self._parse_agent_response(model_response)

            if action == "Final Answer":
                return self._build_answer(query, model_response, history)

            observation = self._execute_tool(action, action_input)
            history.append(
                {
                    "thought": thought,
                    "action": action,
                    "action_input": action_input,
                    "observation": observation,
                }
            )

        return self._fallback_answer(query, self.retriever.hybrid_search(query, top_k=10))

    def _run_prompt_agent(self, query: str) -> Dict[str, Any]:
        evidence = self.retriever.hybrid_search(query, top_k=10)
        logger.info("Evidence has_evidence=%s, vector_results=%d", evidence["has_evidence"], len(evidence["vector_results"]))
        prompt = self._build_direct_answer_prompt(query, evidence)
        logger.info("Prompt context length: %d chars", len(prompt))
        model_response = self._call_llm(prompt)
        logger.info("LLM response: %s", model_response[:500])
        # Only treat as insufficient if the response is ONLY that phrase, not if it contains useful content after it
        stripped = model_response.strip().lower()
        is_only_insufficient = (
            stripped == "insufficient medical evidence in the current database."
            or (stripped.startswith("insufficient medical evidence") and len(stripped) < 120)
        )
        if is_only_insufficient:
            return self._insufficient_evidence_response(query)
        return {
            "query": query,
            "answer": model_response.strip(),
            "sources": self._build_source_list(evidence),
            "confidence": 0.76,
            "reasoning": "Direct evidence-enabled summary from ChromaDB and Neo4j.",
            "ready": True,
        }

    def _fallback_answer(self, query: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        vector_results = evidence.get("vector_results", [])
        graph_results = evidence.get("graph_results", [])
        answer_parts: List[str] = []

        if vector_results:
            answer_parts.append("Relevant clinical research snippets were found in ChromaDB.")
        if graph_results:
            answer_parts.append("Related Neo4j clinical relationships were identified.")

        if not answer_parts:
            return self._insufficient_evidence_response(query)

        return {
            "query": query,
            "answer": " ".join(answer_parts),
            "sources": self._build_source_list(evidence),
            "confidence": 0.55,
            "reasoning": "Fallback summary without an external LLM.",
            "ready": True,
        }

    def _build_source_list(self, evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
        sources = []
        for item in evidence.get("vector_results", []):
            meta = item.get("metadata", {})
            sources.append(
                {
                    "type": "document",
                    "reference": meta.get("doi") or meta.get("source_url") or meta.get("pmid"),
                    "snippet": item.get("document", "")[:180],
                }
            )
        for item in evidence.get("graph_results", []):
            sources.append(
                {
                    "type": "graph",
                    "reference": item.get("relation", "related"),
                    "snippet": f"{item.get('source')} -> {item.get('target')}",
                }
            )
        return sources

    def _build_prompt(self, query: str, history: List[Dict[str, str]]) -> str:
        tool_descriptions = (
            "research_tool: Retrieve the top 5 most relevant research snippets from ChromaDB for a clinical query."
            "\nknowledge_graph_tool: Query Neo4j for direct clinical relationships such as Symptoms, Diseases, Drugs, and Treatments."
        )

        history_text = "\n".join(
            f"Step {idx + 1} - Action: {step['action']} Input: {step['action_input']} Observation: {step['observation']}"
            for idx, step in enumerate(history)
        )

        return (
            "You are a medical reasoning agent. Use only the evidence returned by the tools. "
            "If the evidence is unavailable or insufficient, answer exactly: Insufficient medical evidence in the current database.\n\n"
            f"Tools:\n{tool_descriptions}\n\n"
            f"Query: {query}\n\n"
            "Respond in the format:\n"
            "Thought: <analysis>\n"
            "Action: <research_tool|knowledge_graph_tool|Final Answer>\n"
            "Action Input: <input to the action>\n"
            f"Previous observations:\n{history_text}\n"
        )

    def _build_direct_answer_prompt(self, query: str, evidence: Dict[str, Any]) -> str:
        return (
            "You are a clinical decision support assistant. Answer only using the evidence below. "
            "If the evidence is missing, reply: Insufficient medical evidence in the current database.\n\n"
            f"{evidence.get('context', '')}\n\n"
            f"Question: {query}\n"
        )

    def _parse_agent_response(self, response: str) -> tuple[str, str, str]:
        thought = ""
        action = "Final Answer"
        action_input = response.strip()

        for line in response.splitlines():
            if line.startswith("Thought:"):
                thought = line.replace("Thought:", "", 1).strip()
            elif line.startswith("Action:"):
                action = line.replace("Action:", "", 1).strip()
            elif line.startswith("Action Input:"):
                action_input = line.replace("Action Input:", "", 1).strip()

        return thought, action, action_input

    def _execute_tool(self, action: str, action_input: str) -> str:
        executor = self.tools.get(action)
        if executor is None:
            return f"Unknown tool: {action}"
        try:
            return executor(action_input)
        except Exception as exc:
            return f"Tool execution error: {exc}"

    def _research_tool(self, query: str) -> str:
        results = self.retriever.vector_search(query, top_k=5)
        if not results:
            return "No research snippets found for this query."

        lines = ["Research snippets:"]
        for item in results:
            meta = item.get("metadata", {})
            lines.append(
                f"- {item.get('document', '')[:220]} "
                f"(PMID={meta.get('pmid','n/a')}, DOI={meta.get('doi','n/a')})"
            )
        return "\n".join(lines)

    def _knowledge_graph_tool(self, query: str) -> str:
        results = self.retriever.graph_search(query, top_k=5)
        if not results:
            return "No graph relationships found for this query."

        lines = ["Knowledge graph matches:"]
        for row in results:
            lines.append(
                f"- {row.get('source','Unknown')} ({row.get('source_type','Entity')}) "
                f"{row.get('relation','RELATED')} {row.get('target','Unknown')} "
                f"({row.get('target_type','Entity')})"
            )
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        if Cerebras is None or self.cerebras_api_key is None:
            return "Insufficient medical evidence in the current database."

        client = Cerebras(api_key=self.cerebras_api_key)
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _build_answer(self, query: str, final_text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        if not history:
            return self._insufficient_evidence_response(query)

        return {
            "query": query,
            "answer": final_text.strip(),
            "sources": [
                {
                    "type": "tool",
                    "reference": step["action"],
                    "snippet": step["observation"][:200],
                }
                for step in history
            ],
            "confidence": 0.85,
            "reasoning": "Evidence grounded by ChromaDB and Neo4j retrieval.",
            "ready": True,
        }

    def _insufficient_evidence_response(self, query: str) -> Dict[str, Any]:
        return {
            "query": query,
            "answer": "Insufficient medical evidence in the current database.",
            "sources": [],
            "confidence": 0.0,
            "reasoning": "No vector or graph evidence was available for this query.",
            "ready": True,
        }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the clinical ReAct AI assistant.")
    parser.add_argument("query", nargs="*", help="Medical question to ask the assistant.")
    args = parser.parse_args()

    if not args.query:
        print("Please provide a medical query. Example: python main_ai.py \"What is the best treatment for type 2 diabetes?\"")
        sys.exit(1)

    question = " ".join(args.query).strip()
    agent = ClinicalAgent()

    print("Thinking engine is live and ready for testing.")
    if not agent.is_ready():
        logger.warning("OpenAI API key not configured or LangChain ChatOpenAI unavailable. Using fallback evidence synthesis.")

    result = agent.answer(question)
    print("\n=== Clinical Assistant Response ===")
    print(result["answer"].encode("ascii", "replace").decode())
    print("\nSources:")
    for source in result.get("sources", []):
        snippet = (source.get("snippet") or "").encode("ascii", "replace").decode()
        print(f"- [{source.get('type')}] {source.get('reference')}: {snippet}")


if __name__ == "__main__":
    main()
