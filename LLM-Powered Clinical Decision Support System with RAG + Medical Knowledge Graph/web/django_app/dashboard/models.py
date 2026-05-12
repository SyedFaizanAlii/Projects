from django.db import models
from django.utils import timezone

class ClinicalQuery(models.Model):
    query_text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    patient_demographic = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = "clinical_queries"
    
    def __str__(self):
        return self.query_text[:100]

class QueryResponse(models.Model):
    query = models.ForeignKey(ClinicalQuery, on_delete=models.CASCADE)
    response_text = models.TextField()
    sources = models.JSONField(default=list)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "query_responses"
    
    def __str__(self):
        return f"Response to {self.query_id}"

class BiasAuditLog(models.Model):
    query = models.ForeignKey(ClinicalQuery, on_delete=models.CASCADE)
    audit_result = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "bias_audit_logs"
