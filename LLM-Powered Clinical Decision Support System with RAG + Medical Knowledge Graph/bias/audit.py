import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class Demographic(str, Enum):
    GENDER = "gender"
    AGE = "age"
    RACE = "race"
    ETHNICITY = "ethnicity"
    SOCIOECONOMIC = "socioeconomic_status"

@dataclass
class BiasAuditResult:
    query: str
    demographic: str
    baseline_answer: str
    variant_answer: str
    similarity_score: float
    bias_detected: bool
    severity: str  # low, medium, high

class DemographicBiasAuditor:
    """Audit clinical responses for demographic fairness disparities."""
    
    def __init__(self):
        self.audit_results: List[BiasAuditResult] = []
    
    def audit_response(
        self,
        query: str,
        response_func,
        demographics: List[Demographic] = None,
        threshold: float = 0.85,
    ) -> Dict[str, Any]:
        """
        Generate variant responses with demographic context and compare for bias.
        
        Args:
            query: Clinical query
            response_func: Callable that generates response given (query, demographics_dict)
            demographics: Demographic categories to test
            threshold: Similarity threshold above which responses are considered biased
        
        Returns:
            Audit report with bias findings and severity.
        """
        demographics = demographics or [d for d in Demographic]
        
        baseline_response = response_func(query, demographics={})
        
        findings = []
        for demo in demographics:
            variants = self._generate_demographic_variants(demo)
            for variant_label, variant_dict in variants:
                variant_response = response_func(query, demographics=variant_dict)
                similarity = self._compute_similarity(baseline_response, variant_response)
                
                is_biased = similarity < threshold
                severity = self._classify_severity(similarity)
                
                result = BiasAuditResult(
                    query=query,
                    demographic=f"{demo.value}_{variant_label}",
                    baseline_answer=baseline_response[:200],
                    variant_answer=variant_response[:200],
                    similarity_score=similarity,
                    bias_detected=is_biased,
                    severity=severity,
                )
                self.audit_results.append(result)
                findings.append(result)
        
        return {
            "query": query,
            "total_tests": len(findings),
            "biased_findings": sum(1 for f in findings if f.bias_detected),
            "severity_distribution": self._distribution_by_severity(findings),
            "details": [
                {
                    "demographic": f.demographic,
                    "similarity": round(f.similarity_score, 3),
                    "bias_detected": f.bias_detected,
                    "severity": f.severity,
                }
                for f in findings
            ],
        }
    
    @staticmethod
    def _generate_demographic_variants(demographic: Demographic) -> List[tuple[str, Dict]]:
        """Generate demographic context variants for testing."""
        variants_map = {
            Demographic.GENDER: [
                ("male", {"gender": "male"}),
                ("female", {"gender": "female"}),
            ],
            Demographic.AGE: [
                ("young", {"age_group": "18-35"}),
                ("elderly", {"age_group": "65+"}),
            ],
            Demographic.RACE: [
                ("group_a", {"race": "race_a"}),
                ("group_b", {"race": "race_b"}),
            ],
            Demographic.ETHNICITY: [
                ("group_x", {"ethnicity": "group_x"}),
                ("group_y", {"ethnicity": "group_y"}),
            ],
            Demographic.SOCIOECONOMIC: [
                ("low", {"ses": "low"}),
                ("high", {"ses": "high"}),
            ],
        }
        return variants_map.get(demographic, [])
    
    @staticmethod
    def _compute_similarity(text1: str, text2: str) -> float:
        """Compute semantic similarity between two responses (0-1)."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()
    
    @staticmethod
    def _classify_severity(similarity: float) -> str:
        """Classify bias severity based on response divergence."""
        if similarity > 0.90:
            return "low"
        elif similarity > 0.75:
            return "medium"
        else:
            return "high"
    
    @staticmethod
    def _distribution_by_severity(results: List[BiasAuditResult]) -> Dict[str, int]:
        """Count bias findings by severity."""
        return {
            "low": sum(1 for r in results if r.severity == "low" and r.bias_detected),
            "medium": sum(1 for r in results if r.severity == "medium" and r.bias_detected),
            "high": sum(1 for r in results if r.severity == "high" and r.bias_detected),
        }
    
    def generate_report(self, output_path: str = "bias_audit_report.json"):
        """Export audit findings to JSON report."""
        report = {
            "total_audits": len(self.audit_results),
            "total_biased": sum(1 for r in self.audit_results if r.bias_detected),
            "severity_summary": {
                "low": sum(1 for r in self.audit_results if r.severity == "low" and r.bias_detected),
                "medium": sum(1 for r in self.audit_results if r.severity == "medium" and r.bias_detected),
                "high": sum(1 for r in self.audit_results if r.severity == "high" and r.bias_detected),
            },
            "details": [
                {
                    "query": r.query,
                    "demographic": r.demographic,
                    "similarity": r.similarity_score,
                    "bias_detected": r.bias_detected,
                    "severity": r.severity,
                }
                for r in self.audit_results
            ],
        }
        
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return output_path
