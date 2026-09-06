# Key Decisions — Ashen Era Archive Assistant

## 1. Single sub-track (1C), not combined with 1B
Initially considered combining 1C and 1B as a multi-agent system. Dropped this —
the challenge doc explicitly states a strong single-track solution beats a shallow
multi-track one. Discovered during testing that a well-built 1C loop generalizes
to 1B-style multi-hop questions as an emergent property (validated: 7/7 real
1B-tagged sample questions answered correctly via multi-step chaining), without
needing separate architecture.

## 2. Stack: OpenRouter + ChromaDB, not Voyage AI or Grok
Voyage AI requires a card for identity verification (even though free-tier usage
itself is free) — ruled out under a strict no-card constraint. Grok's API has no
genuine free tier (pay-per-token, plus an opt-in data-sharing free-credit program
we didn't want to depend on). OpenRouter's free embedding + free chat models
require no card at all and were sufficient for this project's scale.

## 3. Reliability tiering as a first-class design element
Source type determines a default trust prior (codex 0.9 > wiki 0.7 > chronicle
0.5 > ephemera 0.3), attached to every chunk at ingestion time. This was driven
directly by corpus evidence: the codex explicitly states things like "this is the
authoritative record, popular accounts wrongly claim otherwise" — a strong signal
that source trust needed to be reasoned over, not assumed uniform.

## 4. Format decoupled from topic folder
Early implementation assumed each topic folder (codex/chronicles/ephemera) used
one consistent file format. This was wrong — the real corpus mixes .docx and .pdf
within the same topic. Fixed by treating "which folder" (topic/reliability) and
"which file extension" (how to read it) as fully independent decisions.

## 5. OCR disabled by default
Standalone images and scanned PDFs require OCR (tesseract). This was tested and
technically works, but is slow on typical development hardware and low-value for
this specific track — 1C's fact-lookup questions are answerable from text sources
(the same facts on image figure-plates typically also appear in codex register
tables). Documented as a deliberate trade-off, not an oversight — see limitations.md.

## 6. Hybrid search (semantic + exact match)
Pure vector similarity search can miss exact named-entity queries when phrasing
differs from the source text. Added exact substring matching for capitalized
proper-noun candidates extracted from each query, merged with semantic results.

## 7. Honest uncertainty over forced answers
The agent can respond "insufficient evidence" instead of guessing. A wrong
confident answer is worse than an honest gap, especially for a system meant to
demonstrate calibrated reasoning rather than just producing text.

## 8. A separate conflict-resolution agent, invoked adaptively
Rather than folding conflict-checking into every single decision (expensive) or
never checking at all (risks confidently wrong answers on contested facts), a
second agent with a narrowly-scoped prompt runs only when 2+ distinct sources
were used to answer. Validated on two different conflict patterns: one where a
source explicitly claimed authority over a competing account, and one where no
explicit authority claim existed and the system correctly fell back to the
default reliability ranking.