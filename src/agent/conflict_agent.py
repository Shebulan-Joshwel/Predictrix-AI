"""
A SEPARATE agent role from the main search loop -- deliberately, not just
for narrative. This one has ONE job: given a draft answer and the evidence
behind it, check specifically for disagreeing sources and decide which to
trust, with reasoning.

WHY THIS IS A REAL SECOND ROLE, NOT JUST RELABELING:
The main loop's job is breadth -- decide where to search next, across many
possible directions. This agent's job is depth on ONE narrow question:
"do these specific sources actually agree?" Different job, different
system prompt, and it's invoked ADAPTIVELY -- only right before finalizing
an answer, and only when there's more than one distinct source in the
evidence (skipped entirely for simple single-source lookups, so it doesn't
waste API calls on the easy majority of questions).
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os

from openai import OpenAI

from src.agent.search_tool import SearchResult


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CONFLICT_AGENT_MODEL = "openrouter/free"

CONFLICT_SYSTEM_PROMPT = """You are a Conflict Resolution Specialist for the \
Ashen Era Archive. You are given a question, a draft answer, and the exact \
evidence chunks that answer was based on. Your ONLY job: check whether the \
evidence chunks disagree with each other on the specific fact being asked about.

Each chunk is tagged with its source type and reliability score:
  codex (0.9) > wiki (0.7) > chronicle (0.5) > ephemera (0.3)

Rules for resolving disagreement:
1. If a source EXPLICITLY claims authority or corrects another account (e.g.
   "this is the authoritative record, popular accounts wrongly claim otherwise"),
   that explicit claim wins over the default reliability ranking.
2. Otherwise, prefer the higher-reliability source, but say so explicitly.
3. If sources don't actually conflict (they're just about different things),
   say so plainly -- don't invent a conflict that isn't there.

Respond with ONLY this JSON:
{"conflict_found": true/false, "summary": "<ONE short plain sentence, e.g. 'Codex overrides ephemera's competing claim of 360 AS.'>", "reasoning": "<your fuller analysis, for the record>", "final_answer": "<the answer, corrected if needed, or unchanged if no conflict>"}
"""


def _call_llm(messages: list[dict]) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
    response = client.chat.completions.create(model=CONFLICT_AGENT_MODEL, messages=messages)
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"conflict_found": False, "reasoning": "PARSE_ERROR", "final_answer": None}


def check_for_conflicts(question: str, draft_answer: str, evidence: list[SearchResult]) -> dict:
    """Returns the (possibly corrected) final answer plus reasoning about
    any conflict found. Call this right before returning a final answer
    from the main agent loop."""
    unique_doc_ids = set(r.doc_id for r in evidence)
    if len(unique_doc_ids) <= 1:
        # Only one source involved -- nothing to conflict with, skip the
        # extra API call entirely.
        return {"conflict_found": False, "summary": "", "reasoning": "Single source, no check needed.",
                 "final_answer": draft_answer}

    evidence_text = "\n---\n".join(
        f"[{r.source_type}, reliability={r.reliability_prior}] {r.title}:\n{r.text}"
        for r in evidence
    )
    messages = [
        {"role": "system", "content": CONFLICT_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Question: {question}\n\nDraft answer: {draft_answer}\n\n"
            f"Evidence used:\n{evidence_text}"
        )},
    ]
    result = _call_llm(messages)
    if not result.get("final_answer"):
        result["final_answer"] = draft_answer  # fail-safe: keep original if parse failed
    return result