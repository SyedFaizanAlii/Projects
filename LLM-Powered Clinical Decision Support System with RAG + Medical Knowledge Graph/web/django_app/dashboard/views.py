import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE importing any ML modules
_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env")

if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ClinicalQuery, QueryResponse
from .serializers import ClinicalQuerySerializer, QueryResponseSerializer
from agents.react_agent import ReactAgent
from rag.hybrid_retriever import HybridRetriever
from graph.neo4j_builder import Neo4jGraph

logger = logging.getLogger(__name__)

_agent_instance = None


def get_agent():
    global _agent_instance
    if _agent_instance is None:
        graph = Neo4jGraph.from_env()
        retriever = HybridRetriever()
        retriever.set_graph(graph)
        _agent_instance = ReactAgent(retriever, graph)
    return _agent_instance


def index(request):
    return render(request, "dashboard/index.html")


class ClinicalQueryViewSet(viewsets.ModelViewSet):
    queryset = ClinicalQuery.objects.all()
    serializer_class = ClinicalQuerySerializer

    @action(detail=False, methods=["post"])
    def submit_query(self, request):
        query_text = request.data.get("query_text", "").strip()

        if not query_text:
            return Response(
                {"error": "query_text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = ClinicalQuery.objects.create(query_text=query_text)

        try:
            agent = get_agent()
            payload = agent.answer(query_text)
        except Exception as exc:
            import traceback
            logger.error("Agent.answer() failed: %s\n%s", exc, traceback.format_exc())
            return Response(
                {"error": f"Clinical engine error: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        sources_raw = payload.get("sources", [])
        sources_str = json.dumps(sources_raw, ensure_ascii=False) if isinstance(sources_raw, list) else "[]"

        response_obj = QueryResponse.objects.create(
            query=query,
            response_text=payload.get("answer", "No response generated."),
            sources=sources_str,
            confidence_score=float(payload.get("confidence", 0.0)),
        )

        response_dict = QueryResponseSerializer(response_obj).data
        response_dict["sources"] = sources_raw  # return as list, not JSON string

        return Response(
            {
                "query": ClinicalQuerySerializer(query).data,
                "response": response_dict,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def get_response(self, request, pk=None):
        query = self.get_object()
        responses = QueryResponse.objects.filter(query=query)
        return Response(QueryResponseSerializer(responses, many=True).data)


class QueryResponseViewSet(viewsets.ModelViewSet):
    queryset = QueryResponse.objects.all()
    serializer_class = QueryResponseSerializer
