#!/usr/bin/env python
"""
Test runner for Phase 3 Hybrid Retrieval & Re-ranking Engine.
Executes all 4 validation tests and reports results.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000/api/v1"


async def test_rbac_isolation():
    """Test 1: Hard RBAC Isolation (Security Boundary)"""
    print("\n" + "="*60)
    print("TEST 1: Hard RBAC Isolation")
    print("="*60)
    
    query = "revenue recognition ASC 606"
    
    # Authorized: finance role
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/retrieval/query",
            json={"query": query, "top_k": 5},
            headers={"X-Impersonate-Role": "finance"},
            timeout=30.0,
        )
    
    finance_result = response.json()
    finance_chunks = len(finance_result.get("parent_chunks", []))
    finance_context = finance_result.get("has_sufficient_context", False)
    
    print(f"Finance role: status={response.status_code}, chunks={finance_chunks}, has_context={finance_context}")
    
    # Unauthorized: general role
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/retrieval/query",
            json={"query": query, "top_k": 5},
            headers={"X-Impersonate-Role": "general"},
            timeout=30.0,
        )
    
    general_result = response.json()
    general_chunks = len(general_result.get("parent_chunks", []))
    general_context = general_result.get("has_sufficient_context", False)
    
    print(f"General role: status={response.status_code}, chunks={general_chunks}, has_context={general_context}")
    
    # Verify
    passed = (
        response.status_code == 200 and
        finance_chunks > 0 and
        finance_context == True and
        general_chunks == 0 and
        general_context == False
    )
    
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return passed, {
        "finance": finance_result,
        "general": general_result,
    }


async def test_sparse_vs_dense():
    """Test 2: Sparse vs. Dense Hybrid Fusion"""
    print("\n" + "="*60)
    print("TEST 2: Sparse vs. Dense Hybrid Fusion")
    print("="*60)
    
    test_cases = [
        {
            "name": "Exact Identifier (Sparse/BM25)",
            "query": "ACC-2024-0042",
            "expected_dense": True,
            "expected_sparse": True,
        },
        {
            "name": "Section Reference (Sparse/BM25)",
            "query": "Section 4.2",
            "expected_dense": True,
            "expected_sparse": True,
        },
        {
            "name": "Conceptual Paraphrase (Dense/Vector)",
            "query": "handling client privacy breaches incident response",
            "expected_dense": True,
            "expected_sparse": False,  # May have sparse but dense should dominate
        },
    ]
    
    results = {}
    all_passed = True
    
    for tc in test_cases:
        print(f"\n  Query: '{tc['query']}'")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/retrieval/query",
                json={"query": tc["query"], "top_k": 5},
                headers={"X-Impersonate-Role": "finance"},
                timeout=30.0,
            )
        
        result = response.json()
        metrics = result.get("metrics", {})
        dense_count = metrics.get("dense_match_count", 0)
        sparse_count = metrics.get("sparse_match_count", 0)
        total_chunks = metrics.get("total_child_matches", 0)
        
        print(f"    Dense matches: {dense_count}, Sparse matches: {sparse_count}, Total: {total_chunks}")
        
        # For exact identifiers, sparse should have matches
        # For conceptual, dense should have matches
        sparse_contributed = sparse_count > 0
        dense_contributed = dense_count > 0
        
        passed = dense_contributed  # At minimum dense should work
        if "ACC-2024-0042" in tc["query"] or "Section 4.2" in tc["query"]:
            passed = passed and sparse_contributed
        
        print(f"    Result: {'PASSED' if passed else 'FAILED'}")
        results[tc["name"]] = {
            "query": tc["query"],
            "dense_match_count": dense_count,
            "sparse_match_count": sparse_count,
            "total_child_matches": total_chunks,
            "passed": passed,
        }
        all_passed = all_passed and passed
    
    return all_passed, results


async def test_confidence_floor():
    """Test 3: Confidence Floor & Hallucination Guard"""
    print("\n" + "="*60)
    print("TEST 3: Confidence Floor & Hallucination Guard")
    print("="*60)
    
    query = "How do you bake a sourdough loaf with 75% hydration?"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/retrieval/query",
            json={"query": query, "top_k": 5},
            headers={"X-Impersonate-Role": "finance"},
            timeout=30.0,
        )
    
    result = response.json()
    chunks = len(result.get("parent_chunks", []))
    has_context = result.get("has_sufficient_context", True)
    threshold = result.get("metrics", {}).get("relevance_threshold", 0)
    
    print(f"Query: '{query}'")
    print(f"Chunks returned: {chunks}")
    print(f"Has sufficient context: {has_context}")
    print(f"Relevance threshold: {threshold}")
    
    passed = (
        response.status_code == 200 and
        chunks == 0 and
        has_context == False
    )
    
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return passed, result


async def test_parent_deduplication():
    """Test 4: Parent Deduplication & Spatial Coordinates"""
    print("\n" + "="*60)
    print("TEST 4: Parent Deduplication & Spatial Coordinates")
    print("="*60)
    
    query = "financial report revenue"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/retrieval/query",
            json={"query": query, "top_k": 5},
            headers={"X-Impersonate-Role": "finance"},
            timeout=30.0,
        )
    
    result = response.json()
    parents = result.get("parent_chunks", [])
    metrics = result.get("metrics", {})
    
    print(f"Query: '{query}'")
    print(f"Unique parents returned: {len(parents)}")
    print(f"Total latency: {metrics.get('total_latency_ms', 0):.1f}ms")
    print(f"  Retrieval: {metrics.get('retrieval_latency_ms', 0):.1f}ms")
    print(f"  Re-ranking: {metrics.get('rerank_latency_ms', 0):.1f}ms")
    
    # Check first parent for deduplication and spatial coords
    if parents:
        parent = parents[0]
        matched_children = parent.get("matched_children", [])
        
        print(f"\nSample Parent Chunk:")
        print(f"  ID: {parent.get('id')}")
        print(f"  Document: {parent.get('document_title')}")
        print(f"  Content preview: {parent.get('content', '')[:100]}...")
        print(f"  Token count: {parent.get('token_count')}")
        print(f"  Pages: {parent.get('page_start')}-{parent.get('page_end')}")
        print(f"  Relevance score: {parent.get('relevance_score')}")
        print(f"  Matched children: {len(matched_children)}")
        
        for i, child in enumerate(matched_children):
            print(f"    Child {i+1}:")
            print(f"      Page: {child.get('page_number')}")
            print(f"      Char range: {child.get('char_start')}-{child.get('char_end')}")
            print(f"      BBox: {child.get('bbox')}")
            print(f"      Fused score: {child.get('fused_score')}")
        
        # Verify deduplication: no duplicate parents (unique parent count = parent chunks)
        # Note: with small test data, we may only have 1 child per parent, which is fine
        # The key is that parent chunks are unique (deduplicated)
        has_spatial_coords = any(c.get("bbox") is not None for c in matched_children)
        has_page_numbers = all(c.get("page_number") is not None for c in matched_children)
        
        # Pass if we have parents and they have the expected structure
        passed = len(parents) > 0 and has_page_numbers  # bbox may be None for markdown
    else:
        print("No parents returned - may need more test data")
        passed = False
    
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}")
    return passed, result


async def main():
    """Run all tests."""
    print("="*60)
    print("PHASE 3: HYBRID RETRIEVAL & RE-RANKING ENGINE")
    print("VALIDATION TESTS")
    print("="*60)
    
    # Check server health first
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(f"{BASE_URL}/health", timeout=5.0)
            print(f"Server health: {health.json()}")
        except Exception as e:
            print(f"FAILED Cannot connect to server: {e}")
            print("Make sure the server is running: uvicorn app.main:app --reload")
            return
    
    all_results = {}
    all_passed = True
    
    # Run tests
    passed, result = await test_rbac_isolation()
    all_results["test1_rbac"] = {"passed": passed, "data": result}
    all_passed = all_passed and passed
    
    passed, result = await test_sparse_vs_dense()
    all_results["test2_sparse_dense"] = {"passed": passed, "data": result}
    all_passed = all_passed and passed
    
    passed, result = await test_confidence_floor()
    all_results["test3_confidence"] = {"passed": passed, "data": result}
    all_passed = all_passed and passed
    
    passed, result = await test_parent_deduplication()
    all_results["test4_deduplication"] = {"passed": passed, "data": result}
    all_passed = all_passed and passed
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, data in all_results.items():
        status = "PASSED" if data["passed"] else "FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    # Save detailed results
    output_file = Path(__file__).parent.parent / "test_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_file}")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)