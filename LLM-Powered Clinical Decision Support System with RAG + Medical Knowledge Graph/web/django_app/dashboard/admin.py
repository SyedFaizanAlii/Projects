from django.contrib import admin
from .models import ClinicalQuery, QueryResponse, BiasAuditLog

@admin.register(ClinicalQuery)
class ClinicalQueryAdmin(admin.ModelAdmin):
    list_display = ["id", "query_text", "created_at"]
    search_fields = ["query_text"]
    list_filter = ["created_at"]

@admin.register(QueryResponse)
class QueryResponseAdmin(admin.ModelAdmin):
    list_display = ["id", "query", "confidence_score", "created_at"]
    list_filter = ["created_at", "confidence_score"]

@admin.register(BiasAuditLog)
class BiasAuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "query", "created_at"]
    list_filter = ["created_at"]
