# Ashen Era Archive Assistant — Sub-track 1C

An AI research agent that answers questions about the Ashen Era Archive by
searching, reading, and deciding whether it has enough information — repeating
until confident, and explicitly resolving disagreements between sources of
different reliability. Built for SLIIT Codefest 2026, AI Competition, sub-track
1C ("Searching the Way a Human Does").

**Note:** while built and submitted for 1C, this system's search-read-decide loop
was also validated against 1B-style multi-hop questions (7/7 correctly answered
via multi-step reasoning chains — see `docs/decisions.md`), since 1B's
"no single document answers on its own" requirement is functionally a special
case of 1C's iterative search. No separate 1B-specific engineering was built.

See `docs/architecture.md` for how it works, `docs/decisions.md` for why it's
built this way, and `docs/limitations.md` for known gaps.

## Prerequisites
- Python 3.10+
- An OpenRouter account (free, no card required) — [openrouter.ai](https://openrouter.ai)
- `tesseract-ocr` (optional — only needed if you enable OCR, see Limitations)

## Setup

\`\`\`bash
git clone <this-repo-url>
cd ashen-agent-part1

pip install pdfplumber python-docx pytesseract pillow pymupdf openai chromadb python-dotenv flask colorama
\`\`\`

Create a file named `.env` in the project root:
\`\`\`
OPENROUTER_API_KEY=your-key-here
\`\`\`
Get a key from your OpenRouter dashboard (Settings → API Keys). No payment method required for the free tier used here.

## Corpus setup

Place the competition corpus into `data/raw/`, matching this structure:
\`\`\`
data/raw/
├── wiki/
├── codex/
├── chronicles/
├── ephemera/
└── images/          (optional — OCR disabled by default, see limitations.md)
\`\`\`

Place the question set at `data/sample_questions.json`.

## Running the full pipeline

Run these in order, once, to build the searchable index:

\`\`\`bash
# 1. Read and normalize every file in data/raw/
python -m src.ingest.parse_corpus

# 2. Chunk, embed, and store in the local vector database
python -m src.embed.embed_and_store
\`\`\`

Then use the system:

\`\`\`bash
# Ask a single question, see the full reasoning trace live
python -m src.agent.agent_loop "your question here"

# Run every 1C-tagged question in sample_questions.json and save results
python -m src.agent.batch_test

# Run a different track's questions instead (e.g. to stress-test multi-hop)
python -m src.agent.batch_test --track 1B

## Notes on API usage limits
OpenRouter's free tier allows 50 requests/day without adding credit. Each agent
search iteration uses 2 calls (embedding + decision), plus one conditional
conflict-check call. A handful of multi-hop questions can use the full daily
allowance — see `docs/limitations.md`.

## Project structure

\`\`\`
src/

├── models/    — the common data shape every document gets normalized into

├── ingest/    — reads .md/.docx/.pdf files, splits into entries, extracts tables

├── chunk/     — splits long documents into embedding-sized pieces

├── embed/     — embeds chunks and stores/searches them in ChromaDB

├── agent/     — the core search-read-decide loop + conflict-resolution agent


docs/          — architecture, decisions, and limitations documentation

ai_usage/      — AI usage disclosure and exported chat logs
\`\`\`
