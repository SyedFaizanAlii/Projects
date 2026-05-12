from graph.vector_store_manager import VectorStoreManager

vsm = VectorStoreManager()
print("Total docs in collection:", vsm.collection.count())

# Test 1: No filter - raw semantic search
print("\n--- No filter ---")
res1 = vsm.search("drug interactions with metformin", top_k=3)
for r in res1:
    print(r["document"][:150])

# Test 2: With keyword filter
print("\n--- With 'metformin' filter ---")
res2 = vsm.search("drug interactions with metformin", top_k=3, filter_keywords=["metformin"])
print("Results:", len(res2))
for r in res2:
    print(r["document"][:150])
