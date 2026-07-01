# Suproc Local Agentic Search System

A local AI agent that matches natural language business requirements against a SQLite dataset of suppliers, professionals, and opportunities. Built on Ollama (Qwen3), with deterministic scoring, validation, and a mandatory human approval gate before any outreach is drafted.

## Overview

The agent takes a plain-English requirement, parses it with a local LLM, builds an execution plan, searches the dataset, scores and ranks candidates across five dimensions, validates every recommendation against nine deterministic checks, corrects failures automatically (up to 3 attempts), and returns a response that requires human sign-off before anything is sent.

**Key Features:**
- **Agentic Architecture**: LLM handles parsing only; all retrieval, scoring, and validation runs in deterministic Python
- **Transparent Scoring**: Five-dimension match scoring (30/20/25/15/10 points) with an evidence dict per dimension
- **Validation Engine**: Nine deterministic checks, no LLM involvement
- **Correction Loop**: Automatic retry with pool-based candidate replacement (max 3 attempts)
- **Prompt Injection Protection**: Keyword blocking on user input and dataset notes
- **Human Approval Gate**: Output is always `AWAITING_APPROVAL`; nothing executes automatically
- **Test Coverage**: 20 scenario tests covering normal flow, edge cases, and security
- **Graceful Degradation**: Regex-based fallback parser when Ollama is unreachable

## Installation

### Prerequisites
- Python 3.11+
- Ollama with `qwen3:4b` or `qwen3:1.7b` pulled
- SQLite 3

### Setup

1. Clone and enter the project directory.

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Seed the database:

```bash
PYTHONPATH=. python scripts/seed_database.py
```

Expected output:
```
Database seeded at data/suproc.db
  Entities:       35
  Professionals:  15
  Opportunities:  10
  Interactions:   6
```

5. Confirm Ollama is running:

```bash
ollama list
```

## Usage

### CLI

```bash
PYTHONPATH=. python cli.py --request "We need three food-grade biodegradable packaging suppliers in Bengaluru, min 10000 units, within 30 days."
```

**Flags:**
- `--request "<text>"`: The requirement (required)
- `--json`: Print raw JSON instead of the formatted terminal view

### Output Structure

1. **Parsed Requirement** - objective, entity type, hard constraints, preferences, result count
2. **Execution Plan** - ordered steps the agent followed
3. **Recommendations** - ranked candidates with score breakdown and justification
4. **Draft Outreach Messages** - templated emails, one per recommendation
5. **Approval Gate** - always `AWAITING_APPROVAL`; human must confirm before sending

### Testing

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

Test scenarios:
- `TestNormalRequest` - valid supplier search with evidence-backed scores
- `TestNoValidResults` - impossible location constraint returns empty
- `TestConflictingRequirements` - conflicting filters handled without crash
- `TestMissingRequestInfo` - vague request still returns candidates
- `TestMissingDatasetInfo` - incomplete records are flagged correctly
- `TestAmbiguousLocation` - "South India" maps to the correct states
- `TestDuplicateRecords` - validator catches duplicate entity IDs
- `TestUnavailableEntity` - busy entities are rejected
- `TestCorrectionLoop` - failed entities are replaced from the scored pool
- `TestPromptInjection` - injection attempts are redacted at input and dataset layers
- `TestHumanApproval` - response always carries `AWAITING_APPROVAL`
- `TestIgnoreValidationAttempt` - validation runs regardless of injected instructions
- `TestLargeResultSet` - requesting more results than available does not crash
- `TestParserErrorHandling` - fallback parser produces valid output when Ollama is down
- `TestUnexpectedEntityType` - entity type mismatch is caught by validator
- `TestMaximumQuantity` - capacity constraint of 1M units correctly eliminates all candidates
- `TestImpossibleRequest` - zero-day delivery constraint is handled gracefully

**All 20 tests pass in ~0.20s.**

## Architecture

### Module Breakdown

```
agent/
├── __init__.py       # Package exports
├── schemas.py        # Pydantic models (ParsedRequirement, Recommendation, etc.)
├── tools.py          # Deterministic tools: search, filter, score, outreach
├── parser.py         # LLM-based parsing with regex fallback
├── planner.py        # Builds the execution plan from parsed requirements
├── validator.py      # Nine-point validation, no LLM calls
├── corrector.py      # Retry loop, max 3 attempts
├── formatter.py      # Assembles FinalResponse and sets approval gate
├── loop.py           # Orchestration
└── prompts.py        # System prompts for LLM

cli.py                    # Entry point with Rich terminal formatting
scripts/seed_database.py  # Creates and populates the SQLite database
tests/test_scenarios.py   # 20 scenario tests
requirements.txt
data/suproc.db
```

### Data Flow

```
User Request
    |
    v
Parser  (LLM -> ParsedRequirement)
    |
    v
Planner (deterministic execution plan)
    |
    v
Loop    (search -> filter -> score)
    |
    v
Validator (9 checks, deterministic)
    |
    +-- failed? -> Corrector (replace from pool, retry up to 3x)
    |
    v
Formatter (draft outreach, set approval gate)
    |
    v
FinalResponse (approval_status = "AWAITING_APPROVAL")
```

### Scoring (5 Dimensions, 100 Points)

| Dimension | Points | Criteria |
|-----------|--------|----------|
| Product Relevance | 0-30 | Category and tag match |
| Location Suitability | 0-20 | Entity in required state(s) |
| Constraint Compliance | 0-25 | Hard constraints satisfied |
| Availability/Capacity | 0-15 | Capacity and availability status |
| Reputation | 0-10 | Rating and review count |

Every score dimension includes a plain-text `evidence` entry explaining the points awarded.

### Validation (9 Checks)

1. **Entity Exists** - record present in the database
2. **Correct Type** - supplier / professional / business
3. **Location Match** - entity in a required state
4. **Certifications** - all required certs present
5. **Capacity Adequacy** - meets minimum unit requirement
6. **Delivery Time** - within maximum day limit
7. **Availability** - not marked busy
8. **No Duplicates** - entity ID appears once per result set
9. **Non-Zero Score** - scoring ran and produced a value above 0

Zero LLM calls in the validation layer.

### Correction Loop

When validation fails:

1. Collect failed entity IDs
2. Pull next-best candidates from the pre-scored pool, excluding failed and already-included entities
3. Re-validate the combined set
4. Repeat up to 3 times, then return whatever passed

The scored pool is computed once; correction just picks the next candidates from it.

### Parser

- **Primary path**: Ollama structured JSON output, validated against the Pydantic schema
- **Fallback path**: Regex heuristics (location names, certification keywords, capacity numbers, delivery-day patterns)
- **Sanitization**: Injection keywords stripped from user input before it reaches the LLM

## Security

### Prompt Injection

- User input is filtered in `parser.py` before being sent to the model
- Dataset notes are checked in `tools.py`; injection markers are replaced with `[CONTENT REDACTED]`
- All 9 validation checks run in pure Python and are unaffected by model output

### Code-Level

- No `eval()`, `exec()`, `pickle`, unsafe YAML, or `shell=True`
- No hardcoded secrets, keys, or credentials
- All SQL queries use parameterized placeholders (`?`)
- No unsafe file handling or directory traversal

## Dataset

SQLite database at `data/suproc.db`:

### Entities (35 records)
- 30 suppliers across packaging, logistics, and textiles categories
- 5 businesses (D2C food brands, cloud kitchens, SaaS)

The dataset includes deliberate edge cases: duplicate records, a prompt-injection attempt in a notes field, busy/unavailable entities, missing certifications, and conflicting descriptions.

### Professionals (15 records)
Skills, hourly rates, certifications, and availability status.

### Opportunities (10 records)
Budget range, required quantity, deadline, open/closed status.

### Interactions (6 records)
Past enquiries, contracts, and reviews between entities.

## Example

**Request:**
```
We need three food-grade biodegradable packaging suppliers in South India,
minimum 10000 units, delivery within 30 days, prefer sustainable and startup-friendly.
```

**Terminal output:**
```
Suproc Agent - Final Response
Validation: PASSED (attempt 1/3)

Interpreted Requirement:
  Objective: We need three food-grade biodegradable packaging suppliers...
  Entity Type: supplier
  Locations: [Karnataka, Tamil Nadu, Kerala, Andhra Pradesh, Telangana]
  Certifications: [food-grade]
  Min Capacity: 10000
  Max Delivery: 30 days
  Preferences: sustainable=True, startup_friendly=True

Execution Plan:
  1. Search supplier records by category and location
  2. Retrieve full details for each candidate
  3. Verify certifications: [food-grade]
  ... (8 more steps)

Recommendations:
  #1: PalmLeaf Naturals (SUP-004) - 94.68/100
    Location: Madurai, Tamil Nadu
    Certifications: [food-grade, organic-certified]
    Capacity: 80000 units | Delivery: 14 days
    Why Suitable: strong category match; located in Tamil Nadu;
                  holds certifications; capacity sufficient; rated 4.8/5

  #2: AgriPack Vizag (SUP-018) - 91.44/100
  #3: CoroPack Thrissur (SUP-028) - 89.20/100

Draft Outreach Messages:
  [3 templated messages ready for review]

Approval Status: AWAITING_APPROVAL
Human approval required before sending outreach.
```

## Known Limitations

1. **Model size**: Smaller models (1.7B) can miss nuanced constraints; `qwen3:4b` is recommended
2. **Location mapping**: South India states are hardcoded; other regions require manual addition
3. **Fixed scoring weights**: Dimensions are weighted statically regardless of request type
4. **Stateless**: Each request is independent; no conversation history carried across runs
5. **Dataset scale**: 35 entities is synthetic; a production deployment would need a much larger corpus
6. **Fallback parser**: The regex fallback is intentionally simple; complex requests need the LLM path
7. **No fine-tuning**: Uses a base Qwen3 model with no domain-specific training
8. **Binary approval**: Approval is a single flag; no granular per-recommendation approval

## Roadmap

- Configurable scoring weights per request type
- Dynamic location mapping (geocoding or GeoJSON)
- Semantic search via local embeddings (`nomic-embed-text`)
- Multi-turn request refinement
- Persistent approval workflow with a lightweight UI
- Batch processing for multiple concurrent requirements
- Outreach integration (email, CRM)

## Performance

| Stage | Latency |
|-------|---------|
| Startup | < 100ms |
| LLM parse | 2-5s (Ollama, model-dependent) |
| SQLite search | < 10ms |
| Scoring + validation | < 20ms |
| End-to-end | ~3-6s |

Nearly all latency is in the LLM call. Everything else is negligible.

## Assignment Compliance

All required components are implemented:

- Agentic architecture (LLM + deterministic tools, separated)
- LLM-based requirement parsing (Ollama)
- Six tools: search, get details, filter by constraints, score, interaction history, draft outreach
- Dataset: 35 entities, 15 professionals, 10 opportunities
- Transparent scoring (5 dimensions, evidence-backed)
- Validation engine (9 checks, deterministic)
- Correction loop (max 3 attempts, pool-based)
- Human approval gate
- 20 scenario-based tests
- Draft outreach messages
- Structured Pydantic outputs
- This README

## Running from a Fresh Clone

```bash
git clone https://github.com/shamiquekhan/Suproc-Local-Agentic-Search-System.git
cd Suproc-Local-Agentic-Search-System

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Confirm Ollama has qwen3:4b
ollama list

PYTHONPATH=. python scripts/seed_database.py
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python cli.py --request "We need three suppliers..."
```

## License

Open source. See the repository for details.
