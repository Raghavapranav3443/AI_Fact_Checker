# VERITAS — Trust Intelligence Platform

**AI-powered fact-checking engine for the hackathon.** Decomposes text into atomic claims, retrieves evidence from multiple authoritative sources in parallel, cross-validates with a dual-model jury, and produces an interactive accuracy report with conflict detection, AI-text scoring, deepfake image analysis, and PDF export.

---

## Quick Start (5 minutes)

### 1. Add API Keys

Edit `backend/.env`:

```env
GEMINI_API_KEY=your_key_here      # console.cloud.google.com
GROQ_API_KEY=your_key_here        # console.groq.com  (free)
TAVILY_API_KEY=your_key_here      # app.tavily.com    (free tier: 1000 req/mo)
HIVE_API_KEY=your_key_here        # thehive.ai        (free trial, bonus feature)
```

### 2. Verify Keys

```bash
cd backend
venv/bin/python utils/verify_keys.py
```

All green = ready. Fix any red before proceeding.

### 3. Run Backend

```bash
cd backend
bash start.sh
# → http://localhost:8000
# → http://localhost:8000/docs  (API explorer)
```

### 4. Run Frontend

```bash
cd frontend
bash start.sh
# → http://localhost:5173
```

---

## Architecture

```
User Input (text or URL)
        ↓
FastAPI /api/ingest
        ↓
LangGraph Pipeline (SSE streams progress to frontend)
        ├── Groq Llama 3.3 70B → Claim Extraction (typed, atomic)
        ├── Groq Llama 3.1 8B  → Query Generation (Direct + Adversarial + Contextual)
        ├── Tavily API         → Parallel web evidence retrieval
        ├── Wikidata/Wikipedia/WorldBank/OpenFDA → Structured KB facts (free)
        ├── Gemini 1.5 Pro     → Verification Agent 1 (strict evidence grounding)
        ├── Groq Llama 3.3 70B → Verification Agent 2 (independent jury)
        ├── Reflector          → Self-critique → re-search if strong
        ├── Conflict Detector  → Cross-source contradiction analysis
        ├── AI Text Detector   → Perplexity + burstiness + n-gram
        └── Hive API           → Deepfake / AI image analysis (URL inputs)
        ↓
Interactive Report (inline highlights, conflict panel, citations)
```

## Key Design Decisions

| Problem | Solution |
|---|---|
| LLM hallucination in verdicts | Strict evidence grounding: model must quote a specific passage or return UNVERIFIABLE |
| Single-model bias | Cross-model jury: Gemini + Groq independently, then compare |
| Stale/wrong verdicts | Self-reflection critique pass: if strength > 60, triggers re-search |
| Missing contradictions | Adversarial query generated for every claim specifically to find counter-evidence |
| Temporal claims ("current CEO") | Claim typed as Temporal, recency-weighted source scoring |
| API rate limits during demo | Demo cache mode: pre-run all 3 scenarios, serve instantly |

---

## Demo Preparation (MUST DO before presenting)

### Build the demo cache

```bash
cd backend
venv/bin/python utils/demo_cache.py --build
```

This runs the full live pipeline on all 3 scenarios and caches results. Takes ~3 minutes. Do this the night before.

### Verify cache

```bash
venv/bin/python utils/demo_cache.py --list
```

### Enable cache mode if APIs fail during demo

In `backend/.env`:
```env
DEMO_CACHE_MODE=true
```

Restart the backend. All submissions now return cached results instantly, full UI animation still plays.

---

## Demo Scenarios

| Scenario | Expected Result | Why |
|---|---|---|
| **Scenario 1** — WHO article | 75–90 trust score, mostly TRUE | Shows clean high-confidence pipeline |
| **Scenario 2** — AI industry blog | 40–65 trust score, mixed verdicts | Shows FALSE detection, partial truths |
| **Scenario 3** — Economic claims | Has CONTESTED verdicts + conflicts | Shows conflict surfacing — the judging differentiator |

Paste the text from `utils/demo_cache.py` → `DEMO_SCENARIOS` for the exact inputs.

---

## Scoring Map

| Rubric Criterion | Points | How Veritas Addresses It |
|---|---|---|
| Claim Extraction accuracy | 40 | Groq Llama 3.3 with typed extraction, CoT, 12-claim cap |
| Evidence Retrieval quality | 40 | Triple-query + Wikidata + Wikipedia + WorldBank + OpenFDA |
| Verification Logic | 40 | Cross-model jury + strict grounding + self-reflection |
| Explainability UI | 30 | Inline text annotation, collapsible reasoning chain, PDF export |
| User Flow / streaming | 30 | SSE live updates: Extracting → Searching → Verifying |
| Design quality | 30 | Dark precision-instrument aesthetic, Syne + JetBrains Mono |
| Architecture robustness | 30 | Partial-result tolerance, retry/backoff, never fatal on single failure |
| Handling ambiguity | 30 | CONTESTED verdicts, conflict panel, Unverifiable when no evidence |
| Prompt engineering | 30 | Chain-of-Thought, strict grounding constraints, self-critique |
| AI Text Detection | +10 | Perplexity + burstiness + n-gram, 0–100 probability score |
| AI Media Detection | +20 | Hive API on all images extracted from URL |
| **Total possible** | **130** | |

---

## Project Structure

```
veritas/
├── backend/
│   ├── main.py                    FastAPI entry point
│   ├── .env                       API keys (never commit)
│   ├── start.sh                   One-command startup
│   ├── agents/
│   │   ├── extractor.py           Claim extraction (Groq)
│   │   ├── query_generator.py     3-query generation per claim
│   │   ├── verifier.py            Dual-model jury + grounding
│   │   ├── reflector.py           Self-critique loop
│   │   ├── conflict_detector.py   Cross-source contradiction
│   │   ├── ai_detector.py         AI text probability scoring
│   │   └── media_detector.py      Hive deepfake detection
│   ├── api/
│   │   └── routes.py              /api/ingest, /api/stream, /api/report
│   ├── pipeline/
│   │   ├── graph.py               Full pipeline orchestrator + SSE
│   │   └── state.py               TypedDict data contracts
│   └── utils/
│       ├── retry.py               Exponential backoff + JSON parser
│       ├── scraper.py             URL → clean text + images
│       ├── validator.py           Input validation
│       ├── authority.py           Domain tier scoring
│       ├── knowledge_apis.py      Wikidata/Wikipedia/WorldBank/OpenFDA
│       ├── tavily_search.py       Parallel search wrapper
│       ├── evidence_bundler.py    Source merge/dedup/format
│       ├── verify_keys.py         Pre-flight API checker
│       └── demo_cache.py          Demo scenario cache system
└── frontend/
    └── src/
        ├── App.jsx                Page router
        ├── index.css              Design system + CSS variables
        ├── utils.js               Verdict color helpers
        ├── context/
        │   └── PipelineContext.jsx Global state
        ├── hooks/
        │   └── usePipeline.js     SSE client + reconnection
        ├── pages/
        │   ├── InputPage.jsx      Text/URL input
        │   ├── PipelinePage.jsx   Live streaming view
        │   └── ReportPage.jsx     Interactive accuracy report
        └── components/
            ├── StageIndicator     4-step pipeline progress
            ├── LiveClaimCard      Real-time claim cards
            ├── TrustScore         Circular gauge + breakdown
            ├── TextAnnotator      Inline text highlighting
            ├── ClaimDetail        Full verdict panel
            ├── ConflictPanel      Side-by-side conflict view
            ├── AIDetectionPanel   AI text detection results
            └── MediaPanel         Deepfake image grid
```

---

## Agent Handoff

If continuing work on this codebase, read `Veritas_Complete_Documentation.docx` — specifically Document 04 (AI Agent Rules). Key invariants:

- Never change the verification prompt without prefix `PROMPT CHANGE — VERIFICATION`
- Never change the extraction prompt without prefix `PROMPT CHANGE — EXTRACTION`
- All LLM responses must go through `parse_llm_json()` — never `json.loads()` directly
- All claims processed concurrently with `asyncio.gather()` — never sequential for-await loops
- Pipeline never raises on single failure — partial results always returned
