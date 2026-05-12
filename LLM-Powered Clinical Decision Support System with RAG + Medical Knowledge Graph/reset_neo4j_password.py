#!/usr/bin/env python
"""Reset Neo4j password using default credentials."""
import time
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

max_retries = 5
retry_count = 0

while retry_count < max_retries:
    try:
        print(f"Attempt {retry_count + 1}/{max_retries}: Connecting to Neo4j...")
        driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "neo4j"))
        
        with driver.session() as session:
            print("Connected! Resetting password...")
            session.run("ALTER USER neo4j SET PASSWORD 'neo4j123'")
            print("SUCCESS: Password changed to 'neo4j123'")
        
        driver.close()
        break
        
    except AuthError as e:
        print(f"Auth error: {e}")
        print("This is expected if credentials don't match.")
        retry_count += 1
        if retry_count < max_retries:
            print(f"Retrying in 2 seconds...")
            time.sleep(2)
    except ServiceUnavailable as e:
        print(f"Service unavailable: {e}")
        retry_count += 1
        if retry_count < max_retries:
            print(f"Waiting for Neo4j to start... retrying in 3 seconds")
            time.sleep(3)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        retry_count += 1
        if retry_count < max_retries:
            time.sleep(2)

if retry_count >= max_retries:
    print("FAILED: Could not reset password after", max_retries, "attempts")
    print("Please manually reset via Neo4j Desktop or Neo4j Browser")
