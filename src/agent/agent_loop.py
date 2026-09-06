"""
THE MAIN AGENT LOOP -- searches, reads, decides if it has enough, repeats.

Verbose terminal output now goes through cli_theme.py for color, spacing,
and a pixel-block spinner during blocking API calls -- purely cosmetic,
doesn't change any actual logic, just makes a live demo/terminal session
readable instead of a wall of plain text.
"""
import warnings
warnings.filterwarnings("ignore")

import json
import os

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from src.agent.search_tool import search_corpus, SearchResult
from src.agent.conflict_agent import check_for_conflicts
from src.agent import cli_theme as ui


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

BE CONCISE, BUT SHOW YOUR REASONING. For "thought": briefly state what you've \
learned so far, and if you're searching again, specifically what's still \
missing that the next search should find. 2-3 short sentences is enough -- \
avoid quoting large chunks of evidence verbatim. Keep "answer" to just the \
final answer itself, not an explanation.

Each turn, respond with ONLY a JSON object, no other text, in one of these shapes:

To search for more information:
{"thought": "<what you know, what's missing>", "action": "search", "query": "<search text>"}

To give a final answer:
{"thought": "<brief reasoning>", "action": "answer", "answer": "<just the answer, or 'Insufficient evidence to determine this.' if you truly don't know>", "confidence": "high"/"low", "sources": ["<doc titles relied on>"]}
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

    if verbose:
        ui.header(question)

    for iteration in range(MAX_ITERATIONS):
        user_message = (
            f"Question: {question}\n\n"
            f"Evidence gathered so far:\n{_format_evidence(gathered)}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        if verbose:
            ui.iteration_label(iteration)
            with ui.Spinner("thinking..."):
                decision = _call_llm(messages)
        else:
            decision = _call_llm(messages)
        trace.append({"iteration": iteration, "decision": decision})

        if verbose:
            ui.thought(decision.get("thought", ""))

        if decision.get("action") == "answer":
            draft = decision.get("answer", "")
            if verbose:
                ui.draft_answer(draft)

            if verbose:
                with ui.Spinner("checking for source conflicts..."):
                    conflict_check = check_for_conflicts(question, draft, gathered)
            else:
                conflict_check = check_for_conflicts(question, draft, gathered)
            trace.append({"conflict_check": conflict_check})

            if verbose and conflict_check["conflict_found"]:
                ui.conflict(conflict_check.get("summary", conflict_check["reasoning"]))

            return {
                "answer": conflict_check["final_answer"],
                "confidence": decision.get("confidence", "unknown"),
                "conflict_found": conflict_check["conflict_found"],
                "conflict_summary": conflict_check.get("summary", ""),
                "conflict_reasoning": conflict_check["reasoning"],
                "trace": trace,
            }

        query = decision.get("query", question)
        if verbose:
            ui.search_query(query)
            with ui.Spinner("digging through the archive..."):
                results = search_corpus(query, n_results=RESULTS_PER_SEARCH)
        else:
            results = search_corpus(query, n_results=RESULTS_PER_SEARCH)

        new_results = [r for r in results if r.chunk_id not in seen_chunk_ids]
        for r in new_results:
            seen_chunk_ids.add(r.chunk_id)
        gathered.extend(new_results)

        if verbose:
            ui.evidence_found(new_results)

    if verbose:
        ui.info("\n[Max iterations reached]")
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

    final_text = decision.get("answer") or "Insufficient evidence to determine this."
    conflict_check = check_for_conflicts(question, final_text, gathered)
    return {
        "answer": conflict_check["final_answer"],
        "confidence": decision.get("confidence", "low"),
        "conflict_found": conflict_check["conflict_found"],
        "conflict_summary": conflict_check.get("summary", ""),
        "conflict_reasoning": conflict_check["reasoning"],
        "trace": trace,
    }


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "In which year was the 'Gauntlet of Sorrowfell' actually forged?"
    result = answer_question(q)
    ui.answer(result["answer"], result["confidence"])
    # (conflict message, if any, already printed live during the loop above --
    # no need to repeat it here)