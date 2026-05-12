import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bias.audit import DemographicBiasAuditor, Demographic

class TestBiasAuditor:
    
    @pytest.fixture
    def auditor(self):
        return DemographicBiasAuditor()
    
    def test_generate_variants(self):
        variants = DemographicBiasAuditor._generate_demographic_variants(Demographic.GENDER)
        assert len(variants) == 2
        assert variants[0][0] == "male"
        assert variants[1][0] == "female"
    
    def test_compute_similarity(self):
        sim = DemographicBiasAuditor._compute_similarity("hello world", "hello world")
        assert sim == 1.0
        
        sim = DemographicBiasAuditor._compute_similarity("hello", "goodbye")
        assert sim < 1.0
    
    def test_classify_severity(self):
        assert DemographicBiasAuditor._classify_severity(0.95) == "low"
        assert DemographicBiasAuditor._classify_severity(0.80) == "medium"
        assert DemographicBiasAuditor._classify_severity(0.50) == "high"
    
    def test_audit_response(self, auditor):
        def mock_response_func(query, demographics):
            return "Sample clinical response"
        
        report = auditor.audit_response(
            "What is the treatment for hypertension?",
            mock_response_func,
            demographics=[Demographic.GENDER],
            threshold=0.85,
        )
        
        assert "query" in report
        assert report["total_tests"] > 0
