import sys
sys.path.insert(0, '.')

from neo4j import GraphDatabase
import json

output = {"tests": []}

# Test 1: Default neo4j/neo4j credentials
try:
    driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "neo4j"))
    with driver.session() as session:
        result = session.run("RETURN 1")
        result.single()
    driver.close()
    output["tests"].append({"name": "neo4j/neo4j", "result": "SUCCESS"})
except Exception as e:
    output["tests"].append({"name": "neo4j/neo4j", "result": "FAILED", "error": str(e)})

# Test 2: admin/neo4j credentials
try:
    driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("admin", "neo4j"))
    with driver.session() as session:
        result = session.run("RETURN 1")
        result.single()
    driver.close()
    output["tests"].append({"name": "admin/neo4j", "result": "SUCCESS"})
except Exception as e:
    output["tests"].append({"name": "admin/neo4j", "result": "FAILED", "error": str(e)})

# Test 3: Credentials from .env
try:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1")
        result.single()
    driver.close()
    output["tests"].append({"name": f"{user}/{password}", "result": "SUCCESS"})
except Exception as e:
    output["tests"].append({"name": "from .env", "result": "FAILED", "error": str(e)})

with open("neo4j_auth_test_results.json", "w") as f:
    json.dump(output, f, indent=2)

print("Results written to neo4j_auth_test_results.json")
