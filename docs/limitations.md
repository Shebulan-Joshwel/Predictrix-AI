# Limitations — Ashen Era Archive Assistant

## OCR is disabled by default
~87 of the corpus's 415 files (standalone images and `.scan.pdf` files) require
OCR to extract text. This was implemented (tesseract + pymupdf) and functions,
but is disabled by default (`SKIP_OCR = True` in `src/ingest/parse_corpus.py`)
because it is slow on typical development hardware and most of the affected
content (character portraits, faction heraldry, creature art) is more relevant
to sub-track 1A's image-embedding requirement than to 1C's fact-lookup nature.
Where figure plates encode numeric facts (attunement costs, garrison strength),
those same facts typically also exist in codex register tables already captured
as text. Risk of missing information is assessed as low but non-zero for our track.

## No dedicated 1B architecture
The system was not purpose-built for multi-document fact-linking. Its strong
performance on 1B-style sample questions (7/7 answered via correct multi-hop
chaining) is an emergent property of a well-built 1C search loop, not a
deliberately engineered second capability. No entity graph or explicit
multi-document synthesis logic exists.

## Ground-truth verification
Batch test results were verified for *mechanism* (did it search iteratively,
chain correctly, catch conflicts) on real, previously-unseen questions. A subset
of answers were also manually cross-checked against the actual source documents
[[UPDATE THIS LINE WITH YOUR RESULT — e.g. "5/5 matched" or note any discrepancy found]].
Time constraints (mid-semester exams during the build window) limited
verification depth beyond this subset.

## Free-tier API rate limits
OpenRouter's free tier caps at 50 requests/day without a credit top-up. Each
agent iteration costs 2 API calls (embedding + decision), plus a conditional
conflict-check call — meaning a single batch of ~7 multi-hop questions can
consume the entire daily allowance. This constrained how much large-scale
testing could be done per day during development.

## Approaches tried and abandoned
- **Combining 1B and 1C as a multi-agent system** — dropped in favor of a single
  well-built 1C loop, per explicit competition guidance rewarding depth over
  breadth.
- **Voyage AI and Grok for embeddings/LLM** — both required either a card
  (Voyage) or had no genuine free tier (Grok); replaced with OpenRouter.
- **Pandoc for .docx parsing** — required an external system dependency with
  Windows installation friction; replaced with native python-docx parsing.
- **A fixed heading-level assumption for document splitting** — an early version
  assumed one heading level marked entity boundaries across all files. Real
  corpus files use inconsistent heading depths (entity name at one level,
  sub-sections nested one level deeper in some files but not others). Fixed by
  detecting the shallowest heading level actually present per file, rather than
  hardcoding an assumption from a single sample file.