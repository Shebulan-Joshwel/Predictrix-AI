"""
Batch-runs the agent against every question in sample_questions.json and
saves a report -- so instead of testing one question at a time by hand,
you run this once and see everything: what it answered, how many search
iterations it took, and (for 1C questions specifically) whether it caught
any source conflicts along the way.

Usage:
    python -m src.agent.batch_test                     # all 1C questions only
    python -m src.agent.batch_test --track all          # every question, any track
    python -m src.agent.batch_test --limit 3            # just the first 3, quick check
"""

import argparse
import json
import time
from pathlib import Path

from src.agent.agent_loop import answer_question


def load_questions(path: str = "data/sample_questions.json", track_filter: str = "1C"):
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    if track_filter != "all":
        questions = [q for q in questions if q["track"].startswith(track_filter)]
    return questions


def run_batch(track_filter: str = "1C", limit: int | None = None, output_path: str = "data/processed/batch_results.json"):
    questions = load_questions(track_filter=track_filter)
    if limit:
        questions = questions[:limit]

    print(f"Running {len(questions)} question(s) (track filter: {track_filter})\n")

    results = []
    for i, q in enumerate(questions):
        print(f"[{i+1}/{len(questions)}] {q['qid']}: {q['question']}")
        start = time.time()
        try:
            result = answer_question(q["question"], verbose=False)
            elapsed = time.time() - start
            iterations = len(result["trace"])
            print(f"  -> {result['answer'][:150]}")
            if result.get("conflict_found"):
                print(f"  [conflict resolved: {result.get('conflict_summary', '')}]")
            print(f"  ({iterations} iterations, {elapsed:.1f}s)\n")
            results.append({
                "qid": q["qid"],
                "question": q["question"],
                "answer": result["answer"],
                "confidence": result.get("confidence"),
                "conflict_found": result.get("conflict_found"),
                "conflict_summary": result.get("conflict_summary", ""),
                "iterations": iterations,
                "elapsed_seconds": round(elapsed, 1),
                "trace": result["trace"],
            })
        except Exception as e:
            print(f"  -> ERROR: {e}\n")
            results.append({"qid": q["qid"], "question": q["question"], "error": str(e)})

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved full results to {output_path}")
    print(f"Done: {len([r for r in results if 'answer' in r])}/{len(results)} answered without error")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", default="1C", help="'1C' (default) or 'all'")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_batch(track_filter=args.track, limit=args.limit)