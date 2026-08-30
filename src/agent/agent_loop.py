"""
THE MAIN AGENT LOOP -- searches, reads, decides if it has enough, repeats.

CHANGES FROM THE FIRST VERSION:
1. Uses the hybrid search tool now (semantic + keyword), not pure vector search.
2. HONEST UNCERTAINTY: the agent can now say it doesn't have enough evidence
   instead of being forced to guess. This is a deliberate trade-off -- a
   wrong confident answer is worse than an honest "insufficient evidence"
   for a system that's meant to demonstrate reasoning, not just produce
   text. Reflected in the "confidence" field and in what happens when we
   run out of search iterations.
3. CONFLICT SPECIALIST: right before returning a final answer, we hand it
   to a separate agent (conflict_agent.py) whose only job is checking for
   disagreeing sources. Skipped automatically if only one source was used
   (no wasted API call on easy questions).
"""

import json
import os

from openai import OpenAI

from src.agent.search_tool import search_corpus, SearchResult
from src.agent.conflict_agent import check_for_conflicts


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
AGENT_MODEL = "openrouter/free"
MAX_ITERATIONS = 5
RESULTS_PER_SEARCH = 5


SYSTEM_PROMPT = """You are a research agent answering questions about the Ashen \
Era Archive, a fictional fantasy corpus. You can only use facts from the search \
results provided to you -- never use outside/general knowledge, since this world \
is entirely invented.

You have ONE tool: search the corpus with a text query (it searches both by \
meaning and by exact name match). Each result comes tagged with its source \
type and a reliability score (0.0-1.0):
  codex (0.9)      = official record, most trustworthy by default
  wiki (0.7)       = community-compiled, generally reliable
  chronicle (0.5)  = in-story narrative, may reflect a character's bias
  ephemera (0.3)   = in-world letters/ledgers/etc, least reliable by default

BE HONEST ABOUT UNCERTAINTY. If, after searching, you genuinely cannot find \
the answer in the evidence, say so clearly rather than guessing -- an honest \
"insufficient evidence" is far better than a confident wrong answer.

Each turn, respond with ONLY a JSON object, no other text, in one of these shapes:

To search for more information:
{"thought": "<reasoning about what you have and what's missing>", "action": "search", "query": "<search text>"}

To give a final answer:
{"thought": "<reasoning>", "action": "answer", "answer": "<answer, or 'Insufficient evidence to determine this.' if you truly don't know>", "confidence": "high"/"low", "sources": ["<doc titles relied on>"]}
"""


def _call_llm(messages: list[dict], max_retries: int = 2) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set.")
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(model=AGENT_MODEL, messages=messages)
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < max_retries:
                continue
            return {"thought": "PARSE_ERROR", "action": "answer",
                     "answer": f"[Could not parse model output after {max_retries+1} attempts: {raw[:300]}]",
                     "confidence": "low", "sources": []}


def _format_evidence(results: list[SearchResult]) -> str:
    if not results:
        return "(no evidence gathered yet)"
    lines = []
    for r in results:
        via = "+".join(r.found_by)
        lines.append(
            f"[{r.source_type}, reliability={r.reliability_prior}, found via {via}] "
            f"{r.title}:\n{r.text}\n"
        )
    return "\n---\n".join(lines)


def answer_question(question: str, verbose: bool = True) -> dict:
    gathered: list[SearchResult] = []
    seen_chunk_ids = set()
    trace = []

    for iteration in range(MAX_ITERATIONS):
        user_message = (
            f"Question: {question}\n\n"
            f"Evidence gathered so far:\n{_format_evidence(gathered)}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        decision = _call_llm(messages)
        trace.append({"iteration": iteration, "decision": decision})

        if verbose:
            print(f"\n--- Iteration {iteration} ---")
            print(f"Thought: {decision.get('thought', '')}")
            print(f"Action: {decision.get('action', '')}")

        if decision.get("action") == "answer":
            draft_answer = decision.get("answer", "")
            if verbose:
                print(f"Draft answer: {draft_answer}")
                print("Checking for source conflicts...")

            conflict_check = check_for_conflicts(question, draft_answer, gathered)
            trace.append({"conflict_check": conflict_check})

            if verbose and conflict_check["conflict_found"]:
                print(f"CONFLICT FOUND: {conflict_check['reasoning']}")

            return {
                "answer": conflict_check["final_answer"],
                "confidence": decision.get("confidence", "unknown"),
                "conflict_found": conflict_check["conflict_found"],
                "conflict_reasoning": conflict_check["reasoning"],
                "trace": trace,
            }

        query = decision.get("query", question)
        if verbose:
            print(f"Searching: {query}")
        results = search_corpus(query, n_results=RESULTS_PER_SEARCH)

        new_results = [r for r in results if r.chunk_id not in seen_chunk_ids]
        for r in new_results:
            seen_chunk_ids.add(r.chunk_id)
        gathered.extend(new_results)

    # Ran out of iterations -- be honest about it rather than forcing a guess.
    if verbose:
        print("\n[Max iterations reached]")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Question: {question}\n\nEvidence gathered so far:\n{_format_evidence(gathered)}\n\n"
            "You must give a final answer now. If the evidence is genuinely "
            "insufficient, say so honestly rather than guessing."
        )},
    ]
    decision = _call_llm(messages)
    trace.append({"iteration": MAX_ITERATIONS, "decision": decision, "forced": True})

    conflict_check = check_for_conflicts(question, decision.get("answer", ""), gathered)
    return {
        "answer": conflict_check["final_answer"],
        "confidence": decision.get("confidence", "low"),
        "conflict_found": conflict_check["conflict_found"],
        "conflict_reasoning": conflict_check["reasoning"],
        "trace": trace,
    }


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "In which year was the 'Gauntlet of Sorrowfell' actually forged?"
    result = answer_question(q)
    print(f"\n=== FINAL ANSWER (confidence: {result['confidence']}) ===")
    print(result["answer"])
    if result["conflict_found"]:
        print(f"\n[Conflict detected and resolved: {result['conflict_reasoning']}]")