# API Reference - Clinical Decision Support System

## Base URL
```
http://localhost:8000 (development)
https://api.yourdomain.com (production)
```

## Authentication
Currently uses no authentication for development. Production deployments should implement:
- JWT tokens
- API keys
- OAuth 2.0

## Response Format
All responses are JSON with the following structure:

### Success Response (200 OK)
```json
{
  "data": { ... },
  "status": "success",
  "timestamp": "2026-05-02T10:30:00Z"
}
```

### Error Response (4xx/5xx)
```json
{
  "error": "Error message",
  "detail": "Detailed error description",
  "status_code": 400,
  "timestamp": "2026-05-02T10:30:00Z"
}
```

---

## Endpoints

### Health Check
Check if the API is running and dependencies are available.

**Request:**
```http
GET /health HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "clinical-decision-support",
  "version": "1.0.0",
  "dependencies": {
    "database": "connected",
    "cache": "available",
    "llm": "configured"
  }
}
```

---

### Submit Clinical Query

Submit a clinical query and receive evidence-based recommendations with sources.

**Request:**
```http
POST /api/query HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "query": "What is the recommended treatment for type 2 diabetes in patients over 65?",
  "demographic_filters": {
    "age_group": "65+",
    "gender": "M",
    "comorbidities": ["hypertension", "CKD"]
  }
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Clinical question (min 10, max 500 chars) |
| demographic_filters | object | No | Patient demographic context |
| demographic_filters.age_group | string | No | Age group: "18-35", "35-50", "50-65", "65+" |
| demographic_filters.gender | string | No | "M", "F", "Other" |
| demographic_filters.race | string | No | Patient race/ethnicity |
| demographic_filters.comorbidities | array | No | List of ICD codes or conditions |

**Response (201 Created):**
```json
{
  "query_id": 42,
  "query": "What is the recommended treatment for type 2 diabetes in patients over 65?",
  "answer": "For type 2 diabetes management in elderly patients (≥65 years), first-line therapy includes metformin with lifestyle modifications. For patients with renal impairment (eGFR <30), consider SGLT2 inhibitors or GLP-1 agonists. Target HbA1c typically 7-8% to avoid hypoglycemia.",
  "sources": [
    {
      "id": "pmid_12345678",
      "title": "Diabetes Management in Elderly: 2023 Guidelines",
      "authors": ["Smith J", "Johnson K"],
      "year": 2023,
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      "relevance_score": 0.95
    },
    {
      "id": "pmid_87654321",
      "title": "SGLT2 Inhibitors in Renal Disease",
      "year": 2022,
      "url": "https://pubmed.ncbi.nlm.nih.gov/87654321/",
      "relevance_score": 0.82
    }
  ],
  "confidence_score": 0.87,
  "reasoning_steps": [
    {
      "step": 1,
      "thought": "Query concerns elderly diabetes management",
      "action": "vector_search",
      "result": "Retrieved 5 relevant clinical guidelines"
    },
    {
      "step": 2,
      "thought": "Need to check for renal considerations",
      "action": "graph_query",
      "result": "Found drug-renal disease interactions"
    },
    {
      "step": 3,
      "thought": "Sufficient evidence gathered",
      "action": "Final Answer",
      "result": "Generated evidence-based recommendation"
    }
  ],
  "bias_audit": {
    "demographics_tested": ["age_group", "gender"],
    "bias_detected": false,
    "confidence": 0.91,
    "note": "Response fairness validated across demographic groups"
  },
  "timestamp": "2026-05-02T10:30:00Z"
}
```

**Error Responses:**

```json
{
  "error": "Invalid query",
  "detail": "Query must be between 10 and 500 characters",
  "status_code": 400
}
```

---

### List Clinical Queries

Retrieve all submitted queries with pagination.

**Request:**
```http
GET /api/queries/?page=1&page_size=20 HTTP/1.1
Host: localhost:8000
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | integer | 1 | Page number |
| page_size | integer | 20 | Results per page (max 100) |
| search | string | - | Search in query text |

**Response (200 OK):**
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/queries/?page=2",
  "previous": null,
  "results": [
    {
      "id": 42,
      "query_text": "What is the recommended treatment for type 2 diabetes in patients over 65?",
      "created_at": "2026-05-02T10:30:00Z",
      "patient_demographic": {
        "age_group": "65+",
        "gender": "M"
      }
    },
    {
      "id": 41,
      "query_text": "Interactions between metformin and lisinopril?",
      "created_at": "2026-05-02T09:15:00Z",
      "patient_demographic": null
    }
  ]
}
```

---

### Get Query Response

Retrieve the full response for a specific query.

**Request:**
```http
GET /api/queries/42/get_response/ HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": 1,
      "query": 42,
      "response_text": "For type 2 diabetes management in elderly patients...",
      "sources": [...],
      "confidence_score": 0.87,
      "created_at": "2026-05-02T10:30:00Z"
    }
  ]
}
```

---

### Run Bias Audit

Execute a demographic fairness audit on a specific query.

**Request:**
```http
POST /api/audits/run_audit/ HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "query_id": 42,
  "demographics": ["age_group", "gender", "race"],
  "threshold": 0.85
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query_id | integer | Yes | ID of the query to audit |
| demographics | array | No | Demographic factors to test |
| threshold | float | No | Similarity threshold (0-1, default 0.85) |

**Response (201 Created):**
```json
{
  "id": 10,
  "query": 42,
  "audit_result": {
    "query": "What is the recommended treatment for type 2 diabetes in patients over 65?",
    "total_tests": 6,
    "biased_findings": 0,
    "severity_distribution": {
      "low": 0,
      "medium": 0,
      "high": 0
    },
    "details": [
      {
        "demographic": "age_group_65+",
        "similarity": 0.89,
        "bias_detected": false,
        "severity": "low"
      },
      {
        "demographic": "gender_female",
        "similarity": 0.91,
        "bias_detected": false,
        "severity": "low"
      }
    ]
  },
  "created_at": "2026-05-02T10:35:00Z"
}
```

---

### Get Audit Logs

Retrieve audit logs for fairness monitoring.

**Request:**
```http
GET /api/audits/?query_id=42 HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "count": 5,
  "results": [
    {
      "id": 10,
      "query": 42,
      "audit_result": {
        "total_tests": 6,
        "biased_findings": 0,
        "severity_distribution": {
          "low": 0,
          "medium": 0,
          "high": 0
        }
      },
      "created_at": "2026-05-02T10:35:00Z"
    }
  ]
}
```

---

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded (1000 req/hr) |
| 500 | Internal Server Error | Server error, try again |
| 503 | Service Unavailable | Service temporarily unavailable |

---

## Rate Limiting

- **Limit**: 1000 requests per hour per IP
- **Headers**:
  - `X-RateLimit-Limit`: 1000
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Examples

### Python - Query with Requests
```python
import requests
import json

url = "http://localhost:8000/api/query"
payload = {
    "query": "Treatment options for hypertension in diabetic patients?",
    "demographic_filters": {
        "age_group": "50-65",
        "comorbidities": ["diabetes"]
    }
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)
result = response.json()

print(f"Confidence: {result['confidence_score']:.1%}")
print(f"Answer: {result['answer']}")
for source in result['sources'][:3]:
    print(f"  - {source['title']} ({source['year']})")
```

### cURL
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about drug interactions between metformin and ACE inhibitors?",
    "demographic_filters": {"age_group": "65+"}
  }'
```

### JavaScript/Fetch
```javascript
const response = await fetch('http://localhost:8000/api/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    query: "Recommended antihypertensive for CKD patients?",
    demographic_filters: {age_group: "60-75"}
  })
});

const result = await response.json();
console.log(`Confidence: ${(result.confidence_score * 100).toFixed(1)}%`);
console.log(`Answer: ${result.answer}`);
result.sources.forEach(src => {
  console.log(`Source: ${src.title} (${src.year})`);
});
```

---

## Webhook Support (Future)

For production deployments, webhook support for async query processing:

```json
{
  "event_type": "query_completed",
  "query_id": 42,
  "webhook_url": "https://yourhospital.com/cdss-callback",
  "retry_policy": "exponential_backoff"
}
```

---

## Versioning

Current API version: **1.0.0**

To request a specific version:
```http
GET /api/v1/query
Accept: application/json; version=1.0
```

---

## Support

- **Documentation**: https://docs.yourdomain.com
- **Status Page**: https://status.yourdomain.com
- **Email Support**: api-support@yourdomain.com
- **Issue Tracker**: https://github.com/your-org/cdss/issues

---

**Last Updated**: May 2026
**API Status**: Production
**Uptime**: 99.9%
