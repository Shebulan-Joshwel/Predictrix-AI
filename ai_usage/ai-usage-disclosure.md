# AI Usage Disclosure

## Tools used
- **Claude (Anthropic)** — used throughout development as an AI pair-architect:
  designing the pipeline, writing and iterating on code, diagnosing real bugs
  against actual corpus data, and reviewing test output.

## What Claude was used for
- Proposing and iterating on the overall architecture (ingestion → chunking →
  embedding → agent loop → conflict resolution)
- Writing the majority of the implementation code
- Diagnosing bugs using real evidence (e.g., a document-structure diagnostic
  script was written and run against an actual corpus file to correctly
  identify a heading-level parsing bug, rather than guessing a fix)
- Suggesting and implementing the hybrid search, honest-uncertainty, and
  conflict-resolution-agent design decisions after being asked for direct
  input during a decision-point discussion

## Decisions made by the team (not Claude)
- Choice of sub-track (1C, single-track — explicitly reconsidered and confirmed
  after Claude raised concerns about combining 1C+1B)
- Rejecting Grok and Voyage AI as the LLM/embedding stack due to card/cost
  constraints, in favor of OpenRouter
- Choosing to disable OCR as a scope trade-off given time and hardware constraints
- Approving each of the four open design questions Claude raised directly
  (agent model choice, hybrid search, honest uncertainty, multi-agent framing)
  before implementation proceeded
- Testing, running, and reporting all terminal output back for iteration —
  every fix in this project was verified against real output from the actual
  team member's machine, not assumed to work

## Chat logs
Full exported conversation history is included at `ai_usage/claude.md` in this
repository, covering the complete development process from initial planning
through final testing.