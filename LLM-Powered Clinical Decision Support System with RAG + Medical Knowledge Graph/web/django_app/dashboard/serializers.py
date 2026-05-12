from rest_framework import serializers
from .models import ClinicalQuery, QueryResponse


class ClinicalQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalQuery
        fields = ["id", "query_text", "created_at"]


class QueryResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryResponse
        fields = ["id", "query", "response_text", "sources", "confidence_score", "created_at"]
