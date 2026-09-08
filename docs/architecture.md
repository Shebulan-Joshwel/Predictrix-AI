# Architecture — Ashen Era Archive Assistant (Sub-track 1C)

## Problem
Some questions in the Ashen Era Archive cannot be answered from a single passage — the
answer requires searching, reading, realizing something is missing, and searching again,
sometimes across sources that actively disagree. We built an agent that performs this
loop explicitly rather than doing a single retrieve-then-answer pass.

## Pipeline

```
Raw corpus (mixed formats, mixed topics)
        │
        ▼
Ingestion (src/ingest/) — format-agnostic readers (.md/.docx/.pdf), decoupled
        │                  from topic folder. Each document tagged with a
        │                  reliability prior based on source type.
        ▼
Chunking (src/chunk/) — long documents split with overlap; short entries
        │                kept whole.
        ▼
Embedding + Storage (src/embed/) — OpenRouter free embedding model,
        │                           stored in local ChromaDB.
        ▼
Agent Loop (src/agent/agent_loop.py) — search → read → decide (search
        │                               again / answer), up to 5 iterations.
        ▼
Conflict Resolution Specialist (src/agent/conflict_agent.py) — separate
        │                        agent role, invoked only when 2+ sources
        │                        were used, checks for disagreement.
        ▼
Final answer (with confidence level and conflict explanation if applicable)
```

## Key components

- **`src/models/document.py`** — the common data shape every format gets normalized
  into, including a reliability prior per source type (codex 0.9, wiki 0.7,
  chronicle 0.5, ephemera 0.3).
- **`src/ingest/`** — readers, heading-based document splitting, table extraction.
  Format (file extension) and topic (folder) are treated as independent variables.
- **`src/agent/search_tool.py`** — hybrid retrieval: semantic (embedding similarity)
  + exact entity/keyword match, merged.
- **`src/agent/agent_loop.py`** — the core iterative loop. System prompt instructs
  the model to search, read, and explicitly judge whether it has enough evidence
  before answering; allows honest "insufficient evidence" rather than forced guesses.
- **`src/agent/conflict_agent.py`** — a second, narrowly-scoped agent that checks
  specifically for source disagreement and resolves it using reliability priors
  plus any explicit authority claims found in the text.

## Why an agent loop instead of single-pass RAG
Single-pass retrieval returns whatever is most similar to the question, once.
It cannot recognize that a fact is contested, or that an answer requires chaining
through an intermediate entity (e.g., person → faction → war). The loop lets the
model treat each search as new evidence to reason over, matching the track's
"decides where to look, checks if it has enough, repeats" requirement directly.

## Validated generalization to 1B
Although built for 1C, the same loop correctly answered 7/7 real 1B-tagged
sample questions via multi-step chaining (e.g., person → faction → war-outcome),
without any 1B-specific engineering. This is treated as an emergent property of
the iterative design, not a deliberately built second capability — see
`decisions.md` and `limitations.md`.

See `docs/test-cases.md` for the full log of every test run, with exact commands