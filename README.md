# 🛡️ <span style="font-family: 'Syne', sans-serif; font-weight: 800;">VERITAS</span> — Truth Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232a?style=flat&logo=react)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-000?style=flat&logo=langchain)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/LLM-Llama_3.3_70B-orange)](https://groq.com/)

**Veritas** is a professional-grade fact-checking and claim verification system. It leverages a multi-tiered AI agent architecture orchestrated via **LangGraph** to autonomously ingest content, extract atomic claims, retrieve cross-referenced evidence, and deliver high-confidence verdicts with self-reflective critique.

---

## 🚀 Key Features

- **Automated Claim Extraction**: Shreds complex articles into verifiable atomic claims using Llama-3.3-70B.
- **Multi-Source Evidence Retrieval**: Parallel search across **Tavily**, **Wikidata**, **Wikipedia**, **World Bank**, and **OpenFDA**.
- **Dual-Model Jury Verification**: Cross-verification by independent agent observers to ensure unbiased accuracy.
- **Deepfake & AI Detection**: Integrated **Hive AI** imaging analysis and deterministic AI text origin scoring.
- **Self-Reflection Architecture**: Every verdict is scrutinized by an independent "Skeptical Reviewer" agent to identify potential bias or outdated evidence.
- **Real-Time Streaming**: Live pipeline visualization using Server-Sent Events (SSE).

---

## 🏗️ Technical Architecture

Veritas uses a directed acyclic graph (DAG) to manage state and logic across the intelligence pipeline.

```mermaid
graph TD
    A["Ingest: Text/URL"] --> B{"Classifier"}
    B -- "Not Suitable" --> C["Exit/Reject"]
    B -- "Suitable" --> D["Claim Extractor"]
    D --> E["Evidence Retrieval"]
    E --> F["Dual-Model Jury"]
    F --> G["Conflict Detection"]
    F --> H["Self-Reflection"]
    E --> I["Media Detection"]
    G & H & I --> J["Final Report Generation"]
```

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Orchestration**: LangGraph (for complex agent state management)
- **Primary LLM**: Llama-3.3-70B-Versatile (via Groq)
- **Secondary LLM**: Llama-3.1-8B-Instant (for classification & reflection)
- **Search Engine**: Tavily AI
- **Scraping**: Playwright, BeautifulSoup4, Trafilatura
- **Media Analysis**: Hive AI (Deepfake/AI detection)

### Frontend
- **Framework**: React 18
- **State Management**: Context API + Custom Hooks
- **Styling**: Vanilla CSS (Modern Design System)
- **Visualization**: SVG-based live indicators and confidence gauges

---

## Scoring Map

| Rubric Criterion | How Veritas Addresses It |
|---|---|
| Claim Extraction accuracy | Groq Llama 3.3 with typed extraction, CoT, 12-claim cap |
| Evidence Retrieval quality | Triple-query + Wikidata + Wikipedia + WorldBank + OpenFDA |
| Verification Logic | Cross-model jury + strict grounding + self-reflection |
| Explainability UI | Inline text annotation, collapsible reasoning chain, PDF export |
| User Flow / streaming | SSE live updates: Extracting → Searching → Verifying |
| Design quality | Dark precision-instrument aesthetic, Syne + JetBrains Mono |
| Architecture robustness | Partial-result tolerance, retry/backoff, never fatal on single failure |
| Handling ambiguity | CONTESTED verdicts, conflict panel, Unverifiable when no evidence |
| Prompt engineering | Chain-of-Thought, strict grounding constraints, self-critique |
| AI Text Detection | Perplexity + burstiness + n-gram, 0–100 probability score |
| AI Media Detection | Hive API on all images extracted from URL |

---

## 📂 Core Logic Pointers

For developers interested in the underlying verification logic, please refer to:
- **Pipeline Orchestration**: [graph.py](file:///c:/Users/Rupesh/Desktop/Pranav/GfG_Hackathon-Veritas/veritas/backend/pipeline/graph.py)
- **Verification Agents**: [verifier.py](file:///c:/Users/Rupesh/Desktop/Pranav/GfG_Hackathon-Veritas/veritas/backend/agents/verifier.py)
- **Claim Extraction**: [extractor.py](file:///c:/Users/Rupesh/Desktop/Pranav/GfG_Hackathon-Veritas/veritas/backend/agents/extractor.py)
- **Deepfake/Media Detection**: [media_detector.py](file:///c:/Users/Rupesh/Desktop/Pranav/GfG_Hackathon-Veritas/veritas/backend/agents/media_detector.py)
- **Evidence Retrieval**: [tavily_search.py](file:///c:/Users/Rupesh/Desktop/Pranav/GfG_Hackathon-Veritas/veritas/backend/utils/tavily_search.py)

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.
