#!/usr/bin/env python
"""Test Neo4j connection with configured credentials."""
from neo4j import GraphDatabase

# Test with credentials from .env
uri = "bolt://127.0.0.1:7687"
user = "neo4j"
password = "test12345678"

print("Testing Neo4j connection...")
print("URI: " + uri)
print("User: " + user)

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1")
        print("SUCCESS: Connection works!")
        print("Result: " + str(result.single()))
    driver.close()
except Exception as exc:
    print("FAILED: " + str(type(exc).__name__))
    print("Error: " + str(exc))
