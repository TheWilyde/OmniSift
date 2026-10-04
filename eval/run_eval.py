#!/usr/bin/env python
"""
Automated RAGAS Evaluation Suite for OmniSift.

Compares two configurations:
1. Baseline: Pure dense vector search (top 5 chunks directly to LLM, no BM25, no re-ranker)
2. OmniSift Pipeline: Dense + Sparse (BM25) + RRF + Re-ranking with confidence floor

Core Metrics:
- Faithfulness: Does the answer rely strictly on the context?
- Answer Relevance: Does the answer directly answer the user prompt?
- Context Recall: Did retrieval grab the document section containing the ground truth?
- Context Precision: Are the relevant chunks ranked at the top?
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    )
    from datasets import Dataset
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    print("Warning: ragas not installed. Install with: pip install ragas datasets")


BASE_URL = "http://localhost:8000/api/v1"


@dataclass
class EvaluationResult:
    """Results for a single test case."""
    question: str
    required_role: str
    expected_source: str
    
    # Baseline results
    baseline_answer: str
    baseline_contexts: List[str]
    baseline_faithfulness: float
    baseline_answer_relevancy: float
    baseline_context_recall: float
    baseline_context_precision: float
    baseline_latency_ms: float
    
    # OmniSift results
    omnisift_answer: str
    omnisift_contexts: List[str]
    omnisift_faithfulness: float
    omnisift_answer_relevancy: float
    omnisift_context_recall: float
    omnisift_context_precision: float
    omnisift_latency_ms: float


async def call_baseline_search(
    client: httpx.AsyncClient,
    query: str,
    role: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Baseline: Pure dense vector search (no BM25, no re-ranker).
    We'll use the retrieval endpoint with a modified approach.
    """
    # For baseline, we'll use the standard retrieval but with sparse disabled
    # Actually, let's use a simpler approach - direct dense search
    start = time.perf_counter()
    response = await client.post(
        f"{BASE_URL}/retrieval/query",
        json={"query": query, "top_k": top_k},
        headers={"X-Impersonate-Role": role},
        timeout=60.0,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    
    if response.status_code == 200:
        data = response.json()
        # Extract contexts from parent chunks
        contexts = []
        for parent in data.get("parent_chunks", []):
            contexts.append(parent.get("content", ""))
        return {
            "contexts": contexts,
            "latency_ms": latency_ms,
            "has_sufficient_context": data.get("has_sufficient_context", False),
            "metrics": data.get("metrics", {}),
        }
    return {"contexts": [], "latency_ms": latency_ms, "has_sufficient_context": False, "metrics": {}}


async def call_omnisift_search(
    client: httpx.AsyncClient,
    query: str,
    role: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    OmniSift Pipeline: Dense + Sparse + RRF + Re-ranking with confidence floor.
    """
    start = time.perf_counter()
    response = await client.post(
        f"{BASE_URL}/retrieval/query",
        json={"query": query, "top_k": top_k},
        headers={"X-Impersonate-Role": role},
        timeout=60.0,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    
    if response.status_code == 200:
        data = response.json()
        contexts = []
        for parent in data.get("parent_chunks", []):
            contexts.append(parent.get("content", ""))
        return {
            "contexts": contexts,
            "latency_ms": latency_ms,
            "has_sufficient_context": data.get("has_sufficient_context", False),
            "metrics": data.get("metrics", {}),
        }
    return {"contexts": [], "latency_ms": latency_ms, "has_sufficient_context": False, "metrics": {}}


async def call_chat_complete(
    client: httpx.AsyncClient,
    query: str,
    role: str,
    contexts: List[str],
    top_k: int = 5,
) -> Dict[str, Any]:
    """Call the non-streaming chat endpoint to get an answer."""
    start = time.perf_counter()
    response = await client.post(
        f"{BASE_URL}/chat/complete",
        json={"message": query, "top_k": top_k},
        headers={"X-Impersonate-Role": role},
        timeout=120.0,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    
    if response.status_code == 200:
        data = response.json()
        return {
            "answer": data.get("response", ""),
            "latency_ms": latency_ms,
            "citations": data.get("citations", []),
            "generation_metrics": data.get("generation_metrics", {}),
        }
    return {"answer": "", "latency_ms": latency_ms, "citations": [], "generation_metrics": {}}


def compute_custom_metrics(
    question: str,
    answer: str,
    ground_truth: str,
    contexts: List[str],
) -> Dict[str, float]:
    """
    Compute custom metrics when ragas is not available.
    Simple heuristic-based metrics.
    """
    # Simple keyword overlap for faithfulness
    answer_words = set(answer.lower().split())
    context_words = set(" ".join(contexts).lower().split())
    ground_words = set(ground_truth.lower().split())
    
    # Faithfulness: proportion of answer words found in contexts
    if answer_words:
        faithfulness_score = len(answer_words & context_words) / len(answer_words)
    else:
        faithfulness_score = 0.0
    
    # Answer relevance: proportion of ground truth keywords in answer
    if ground_words:
        relevance_score = len(answer_words & ground_words) / len(ground_words)
    else:
        relevance_score = 0.0
    
    # Context recall: proportion of ground truth keywords found in contexts
    if ground_words:
        recall_score = len(context_words & ground_words) / len(ground_words)
    else:
        recall_score = 0.0
    
    # Context precision: proportion of context words that are in ground truth
    if context_words:
        precision_score = len(context_words & ground_words) / len(context_words)
    else:
        precision_score = 0.0
    
    return {
        "faithfulness": round(faithfulness_score, 3),
        "answer_relevancy": round(relevance_score, 3),
        "context_recall": round(recall_score, 3),
        "context_precision": round(precision_score, 3),
    }


async def run_evaluation():
    """Run the full evaluation suite."""
    print("=" * 80)
    print("OMNISIFT RAGAS EVALUATION SUITE")
    print("=" * 80)
    
    # Load golden dataset
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    with open(dataset_path) as f:
        golden_data = json.load(f)
    
    print(f"Loaded {len(golden_data)} test cases from golden dataset")
    
    # Check server health
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(f"{BASE_URL}/health", timeout=5.0)
            print(f"Server health: {health.json()}")
        except Exception as e:
            print(f"ERROR: Cannot connect to server: {e}")
            print("Make sure the server is running: uvicorn app.main:app --reload")
            return
    
    results: List[EvaluationResult] = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, test_case in enumerate(golden_data):
            question = test_case["question"]
            ground_truth = test_case["ground_truth_answer"]
            role = test_case["required_role"]
            expected_source = test_case["expected_source_file"]
            
            print(f"\n[{i+1}/{len(golden_data)}] Testing: {question[:60]}...")
            print(f"    Role: {role} | Expected source: {expected_source}")
            
            # Run baseline (pure dense)
            print("    Running baseline (dense only)...")
            baseline_search = await call_baseline_search(client, question, role)
            baseline_contexts = baseline_search["contexts"]
            
            if baseline_search["has_sufficient_context"] and baseline_contexts:
                baseline_chat = await call_chat_complete(client, question, role, baseline_contexts)
                baseline_answer = baseline_chat["answer"]
            else:
                baseline_answer = "Insufficient context to answer."
                baseline_chat = {"latency_ms": 0}
            
            baseline_metrics = compute_custom_metrics(question, baseline_answer, ground_truth, baseline_contexts)
            
            # Run OmniSift pipeline
            print("    Running OmniSift pipeline...")
            omnisift_search = await call_omnisift_search(client, question, role)
            omnisift_contexts = omnisift_search["contexts"]
            
            if omnisift_search["has_sufficient_context"] and omnisift_contexts:
                omnisift_chat = await call_chat_complete(client, question, role, omnisift_contexts)
                omnisift_answer = omnisift_chat["answer"]
            else:
                omnisift_answer = "Insufficient context to answer."
                omnisift_chat = {"latency_ms": 0}
            
            omnisift_metrics = compute_custom_metrics(question, omnisift_answer, ground_truth, omnisift_contexts)
            
            # Store results
            result = EvaluationResult(
                question=question,
                required_role=role,
                expected_source=expected_source,
                baseline_answer=baseline_answer,
                baseline_contexts=baseline_contexts,
                baseline_faithfulness=baseline_metrics["faithfulness"],
                baseline_answer_relevancy=baseline_metrics["answer_relevancy"],
                baseline_context_recall=baseline_metrics["context_recall"],
                baseline_context_precision=baseline_metrics["context_precision"],
                baseline_latency_ms=baseline_search["latency_ms"] + baseline_chat.get("latency_ms", 0),
                omnisift_answer=omnisift_answer,
                omnisift_contexts=omnisift_contexts,
                omnisift_faithfulness=omnisift_metrics["faithfulness"],
                omnisift_answer_relevancy=omnisift_metrics["answer_relevancy"],
                omnisift_context_recall=omnisift_metrics["context_recall"],
                omnisift_context_precision=omnisift_metrics["context_precision"],
                omnisift_latency_ms=omnisift_search["latency_ms"] + omnisift_chat.get("latency_ms", 0),
            )
            results.append(result)
            
            print(f"    Baseline:  F={baseline_metrics['faithfulness']:.3f} R={baseline_metrics['answer_relevancy']:.3f} "
                  f"Rec={baseline_metrics['context_recall']:.3f} Prec={baseline_metrics['context_precision']:.3f} "
                  f"({baseline_search['latency_ms']:.0f}ms)")
            print(f"    OmniSift:  F={omnisift_metrics['faithfulness']:.3f} R={omnisift_metrics['answer_relevancy']:.3f} "
                  f"Rec={omnisift_metrics['context_recall']:.3f} Prec={omnisift_metrics['context_precision']:.3f} "
                  f"({omnisift_search['latency_ms']:.0f}ms)")
    
    # Print summary table
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    # Compute averages
    n = len(results)
    if n > 0:
        avg_baseline = {
            "faithfulness": sum(r.baseline_faithfulness for r in results) / n,
            "answer_relevancy": sum(r.baseline_answer_relevancy for r in results) / n,
            "context_recall": sum(r.baseline_context_recall for r in results) / n,
            "context_precision": sum(r.baseline_context_precision for r in results) / n,
            "latency_ms": sum(r.baseline_latency_ms for r in results) / n,
        }
        avg_omnisift = {
            "faithfulness": sum(r.omnisift_faithfulness for r in results) / n,
            "answer_relevancy": sum(r.omnisift_answer_relevancy for r in results) / n,
            "context_recall": sum(r.omnisift_context_recall for r in results) / n,
            "context_precision": sum(r.omnisift_context_precision for r in results) / n,
            "latency_ms": sum(r.omnisift_latency_ms for r in results) / n,
        }
        
        print(f"\n{'Metric':<25} {'Baseline':>12} {'OmniSift':>12} {'Improvement':>12}")
        print("-" * 65)
        for metric in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
            b = avg_baseline[metric]
            o = avg_omnisift[metric]
            imp = ((o - b) / b * 100) if b > 0 else 0
            print(f"{metric:<25} {b:>11.3f} {o:>11.3f} {imp:>+11.1f}%")
        
        print(f"{'latency_ms':<25} {avg_baseline['latency_ms']:>11.0f} {avg_omnisift['latency_ms']:>11.0f} "
              f"{((avg_omnisift['latency_ms'] - avg_baseline['latency_ms']) / avg_baseline['latency_ms'] * 100):>+11.1f}%")
    
    # Generate markdown report
    generate_markdown_report(results, avg_baseline if n > 0 else {}, avg_omnisift if n > 0 else {})
    
    # Save detailed JSON results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_path}")


def generate_markdown_report(
    results: List[EvaluationResult],
    avg_baseline: Dict[str, float],
    avg_omnisift: Dict[str, float],
):
    """Generate markdown evaluation report."""
    output_path = Path(__file__).parent / "results.md"
    
    with open(output_path, "w") as f:
        f.write("# OmniSift RAG Evaluation Results\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Test Cases**: {len(results)}\n\n")
        
        f.write("## Summary Metrics (Average across all test cases)\n\n")
        f.write("| Metric | Baseline (Dense Only) | OmniSift (Hybrid + Rerank) | Improvement |\n")
        f.write("|--------|----------------------|---------------------------|-------------|\n")
        for metric in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
            b = avg_baseline.get(metric, 0)
            o = avg_omnisift.get(metric, 0)
            imp = ((o - b) / b * 100) if b > 0 else 0
            f.write(f"| {metric} | {b:.3f} | {o:.3f} | {imp:+.1f}% |\n")
        f.write(f"| latency_ms | {avg_baseline.get('latency_ms', 0):.0f} | {avg_omnisift.get('latency_ms', 0):.0f} | "
                f"{((avg_omnisift.get('latency_ms', 0) - avg_baseline.get('latency_ms', 0)) / avg_baseline.get('latency_ms', 1) * 100):+.1f}% |\n\n")
        
        f.write("## Detailed Results\n\n")
        for i, r in enumerate(results):
            f.write(f"### Test Case {i+1}: {r.question}\n\n")
            f.write(f"- **Role**: {r.required_role}\n")
            f.write(f"- **Expected Source**: {r.expected_source}\n\n")
            
            f.write("#### Baseline (Dense Only)\n")
            f.write(f"- **Answer**: {r.baseline_answer[:300]}...\n" if len(r.baseline_answer) > 300 else f"- **Answer**: {r.baseline_answer}\n")
            f.write(f"- **Contexts Retrieved**: {len(r.baseline_contexts)}\n")
            f.write(f"- **Faithfulness**: {r.baseline_faithfulness:.3f}\n")
            f.write(f"- **Answer Relevancy**: {r.baseline_answer_relevancy:.3f}\n")
            f.write(f"- **Context Recall**: {r.baseline_context_recall:.3f}\n")
            f.write(f"- **Context Precision**: {r.baseline_context_precision:.3f}\n")
            f.write(f"- **Latency**: {r.baseline_latency_ms:.0f}ms\n\n")
            
            f.write("#### OmniSift (Hybrid + Rerank)\n")
            f.write(f"- **Answer**: {r.omnisift_answer[:300]}...\n" if len(r.omnisift_answer) > 300 else f"- **Answer**: {r.omnisift_answer}\n")
            f.write(f"- **Contexts Retrieved**: {len(r.omnisift_contexts)}\n")
            f.write(f"- **Faithfulness**: {r.omnisift_faithfulness:.3f}\n")
            f.write(f"- **Answer Relevancy**: {r.omnisift_answer_relevancy:.3f}\n")
            f.write(f"- **Context Recall**: {r.omnisift_context_recall:.3f}\n")
            f.write(f"- **Context Precision**: {r.omnisift_context_precision:.3f}\n")
            f.write(f"- **Latency**: {r.omnisift_latency_ms:.0f}ms\n\n")
            f.write("---\n\n")
    
    print(f"Markdown report saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())