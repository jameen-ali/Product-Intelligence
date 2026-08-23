# Industrial Product Truth Engine
# System Architecture Document

**Companion to:** `01_PRD.md`
**Status:** Implementation-ready — authoritative technical blueprint
**Architectural style:** Modular monolith, local-first AI, graph-first provenance, evidence-first decision making

---

## 1. Architecture Overview

The Industrial Product Truth Engine (IPTE) is not a document-to-JSON pipeline and not a RAG chatbot. It is a **decision system**: every attribute value that reaches a user or an export must be traceable through an unbroken chain of claim → evidence → normalization → cross-source comparison → canonical decision → confidence → trust status.

The system is built as a **modular monolith** FastAPI backend with clearly bounded internal modules (ingestion, extraction, normalization, evidence, conflict, truth, graph, versioning, change detection, impact, review, export), a React/TypeScript frontend, and four persistence systems each with a distinct, non-overlapping responsibility:

- **PostgreSQL** — operational system of record (jobs, sources, documents, claims, decisions, reviews — relational state).
- **Neo4j** — the Product Truth Graph (relationship-rich provenance, conflicts, versions, changes, impact).
- **Qdrant** — vector retrieval infrastructure for evidence/document semantic search (not authoritative truth).
- **File/object storage** — original, unmodified source documents.

AI (LLMs/VLMs via Ollama, with an optional OpenRouter fallback) is used strictly for **semantic interpretation** (extraction, semantic equivalence, explanation generation). All arithmetic, provenance, persistence, and truth-state transitions are handled by deterministic code.

---

## 2. Architectural Principles

1. **Extraction is not truth.** A claim is never written directly into a "final" attribute field.
2. **Evidence is first-class.** Every claim persists a verbatim, located evidence record.
3. **Deterministic arithmetic, semantic AI.** Unit conversion, scoring, and status transitions are code, not LLM output.
4. **No silent hallucination.** Absent evidence yields UNKNOWN, never a fabricated value.
5. **No silent conflict resolution.** Conflicting claims are preserved and exposed, never discarded or majority-voted away.
6. **Immutable history.** Historical product versions and evidence are never overwritten.
7. **Local-first AI, cloud-optional.** The system must run fully offline; cloud inference is an explicit, swappable fallback.
8. **Graph-first provenance.** Neo4j is the mechanism by which "why do you believe this?" is answered, not a decorative add-on.
9. **Explainability over opacity.** Confidence and canonical decisions always expose their contributing factors.
10. **One architecture, no ambiguity.** Every technology choice below is final for this build; alternatives are documented for context, not left open.

---

## 3. System Context

```mermaid
C4Context
    title System Context — Industrial Product Truth Engine

    Person(user, "Product Data Manager / Reviewer", "Uploads sources, reviews conflicts, exports product truth")
    System(ipte, "Industrial Product Truth Engine", "Converts fragmented industrial product data into evidence-backed product truth")
    System_Ext(manuf_site, "Manufacturer Website", "Public product page")
    System_Ext(ollama, "Ollama (local)", "Local LLM/VLM inference")
    System_Ext(openrouter, "OpenRouter (optional)", "Cloud LLM fallback")

    Rel(user, ipte, "Uploads PDFs, Excel, images; reviews conflicts; exports JSON/CSV")
    Rel(ipte, manuf_site, "Fetches product page (Crawl4AI/Playwright)")
    Rel(ipte, ollama, "Primary inference path")
    Rel(ipte, openrouter, "Fallback inference path (optional)")
```

The system's only external dependencies are: the user's uploaded files, an optionally-fetched manufacturer URL, and the AI inference provider. No other third-party system is required for the MVP to function.

---

## 4. High-Level Architecture

```mermaid
flowchart TD
    U[User] --> FE[React Web App]
    FE --> API[FastAPI Backend]
    API --> ING[Ingestion Layer]

    ING --> PDFP[Docling: PDF/Manual Parser]
    ING --> URLP[Crawl4AI / Playwright: URL Parser]
    ING --> TABP[Tabular Parser: Excel/CSV]
    ING --> IMGP[OCR + VLM: Image Pipeline]

    PDFP --> CLAIM[Claim Extraction]
    URLP --> CLAIM
    TABP --> CLAIM
    IMGP --> CLAIM

    CLAIM --> ENTRES[Product Entity Resolution]
    ENTRES --> NORM[Industrial Normalization Engine]
    NORM --> EVID[Evidence Engine]
    EVID --> AUTH[Source Authority Engine]
    AUTH --> CMP[Cross-Source Comparison]
    CMP --> CONF[Conflict Engine]
    CONF --> CANON[Canonical Value Engine]
    CANON --> TRUST[Confidence / Trust Engine]

    TRUST --> VERIFIED[VERIFIED]
    TRUST --> INFERRED[INFERRED]
    TRUST --> CONFLICT[CONFLICT]
    TRUST --> UNKNOWN[UNKNOWN]

    CONFLICT --> REVIEW[Human Review Layer]
    INFERRED --> REVIEW

    TRUST --> QD[(Qdrant: Evidence Retrieval)]
    TRUST --> NEO[(Neo4j: Product Truth Graph)]
    REVIEW --> NEO

    NEO --> VER[Version Engine]
    VER --> CHG[Change Detection]
    CHG --> IMPACT[Change Impact Engine]
    IMPACT --> OUT[Commerce-Ready Output]

    OUT --> JSON[JSON Export]
    OUT --> CSV[CSV Export]
    OUT --> RESTAPI[REST API]
```

---

## 5. Component Architecture

The backend is a single deployable service with strict internal module boundaries, so any module can later be extracted into its own service without a data-model rewrite.

```mermaid
flowchart LR
    subgraph backend/app
        api[api]
        core[core]
        ingestion[ingestion]
        extraction[extraction]
        normalization[normalization]
        evidence[evidence]
        validation[validation]
        conflict[conflict]
        truth[truth]
        graph[graph]
        retrieval[retrieval]
        versioning[versioning]
        change_detection[change_detection]
        impact[impact]
        review[review]
        export[export]
        models[models]
        schemas[schemas]
        services[services]
        repositories[repositories]
    end
    api --> services
    services --> ingestion
    services --> extraction
    services --> normalization
    services --> evidence
    services --> validation
    services --> conflict
    services --> truth
    services --> versioning
    services --> change_detection
    services --> impact
    services --> review
    services --> export
    services --> retrieval
    services --> graph
    repositories --> models
    services --> repositories
```

**Module responsibility table**

| Module | Responsibility | Depends on |
|---|---|---|
| `ingestion` | File/URL intake, hashing, type detection, dispatch to parsers | `core`, `repositories` |
| `extraction` | Claim creation from parsed documents via AI provider | `ingestion`, AI Provider |
| `normalization` | Deterministic unit conversion | `extraction` |
| `evidence` | Evidence record creation/retrieval | `extraction` |
| `validation` | Schema/dimensional-compatibility checks, standards hook | `normalization` |
| `conflict` | Cross-source comparison and conflict scoring | `normalization`, `evidence` |
| `truth` | Canonical value + confidence + trust status | `conflict`, `evidence` |
| `graph` | Neo4j writes/reads for the Product Truth Graph | `truth` |
| `retrieval` | Qdrant embedding storage/query | `evidence` |
| `versioning` | ProductVersion creation | `truth` |
| `change_detection` | Diff canonical vs new claims | `versioning` |
| `impact` | Logical asset impact mapping | `change_detection` |
| `review` | Human review queue and decision logging | `truth`, `graph` |
| `export` | JSON/CSV serialization | `truth`, `versioning`, `change_detection` |

---

## 6. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | React + Vite + TypeScript + Tailwind CSS | Fast iteration, typed UI, utility styling suited to a data-dense dashboard |
| Backend | Python + FastAPI + Pydantic | Async-capable, schema-validated, ideal for AI-integrated services |
| ORM | SQLAlchemy | Explicit control over PostgreSQL schema/migrations |
| Document intelligence | Docling | Layout-aware parsing with page/table/bbox provenance (Section 14) |
| Web ingestion | Crawl4AI (primary), Playwright (fallback) | Crawl4AI handles most product pages; Playwright covers JS-heavy pages |
| OCR | Docling-integrated OCR, RapidOCR fallback | Local, no API dependency |
| Local LLM/VLM | Ollama | Local-first inference, no per-request cost, offline-capable |
| Cloud fallback | OpenRouter | Optional, environment-gated, never mandatory |
| Structured output | Pydantic schemas | Enforced claim/decision shapes from both deterministic code and LLM output |
| Vector database | Qdrant | Local-runnable, filterable payload search for evidence retrieval |
| Knowledge graph | Neo4j Community Edition | Required system of record for provenance and multi-hop reasoning |
| Relational database | PostgreSQL (or Supabase Postgres) | Operational state, job tracking, primary relational entities |
| Orchestration | Explicit Python services; LangGraph only for the multi-stage pipeline state machine | Avoids opaque agent behavior; keeps the truth pipeline auditable |

---

## 7. Technology Decision Matrix

**Document intelligence**

| Tool | Layout-aware | Table extraction | Local | Notes |
|---|---|---|---|---|
| **Docling (chosen)** | Yes | Yes | Yes | Actively maintained, strong page/table provenance, integrates OCR |
| Unstructured | Partial | Partial | Yes | Broader format support but weaker table/bbox fidelity for engineering datasheets |
| Marker | Yes | Partial | Yes | Strong for scientific PDFs, less mature table structure API |
| MinerU | Yes | Yes | Yes | Comparable capability; smaller ecosystem/community support at time of writing |

Decision: **Docling**, for its explicit page/section/table/bbox provenance model, which directly satisfies the evidence-location requirement (Section 16 of the PRD).

**Model provider**

| Provider | Local | Cost | Notes |
|---|---|---|---|
| **Ollama (chosen, primary)** | Yes | Free | No per-request cost, offline, privacy-preserving |
| **OpenRouter (chosen, fallback)** | No | Free-tier models available, others paid | Optional; used only when Ollama unavailable and explicitly configured |
| Direct OpenAI/Anthropic/Gemini API | No | Paid | Not used in MVP; documented as future provider (Section 40) |

**Vector database**

| Tool | Local | Metadata filtering | Notes |
|---|---|---|---|
| **Qdrant (chosen)** | Yes | Rich payload filtering | Filter-then-search fits the "narrow by product/attribute/source_type" pattern required (Section 26) |
| Chroma | Yes | Basic | Simpler but weaker filtering ergonomics at scale |
| pgvector | Yes (in Postgres) | SQL-based | Would conflate vector search with the operational relational store; kept separate per Section 30 |

**Graph database**

| Tool | Local | Query language | Notes |
|---|---|---|---|
| **Neo4j Community Edition (chosen)** | Yes | Cypher | Mature tooling, required by product spec, strong multi-hop traversal ergonomics |
| Memgraph | Yes | Cypher-compatible | Viable alternative; Neo4j chosen for ecosystem maturity and driver support |
| Relational graph emulation | Yes | SQL joins | Rejected — multi-hop provenance and conflict traversal become unmanageable in pure SQL |

**Web ingestion**

| Tool | JS rendering | Notes |
|---|---|---|
| **Crawl4AI (chosen, primary)** | Partial | Purpose-built for LLM-ready content extraction |
| **Playwright (chosen, fallback)** | Full | Used when Crawl4AI cannot render a JS-heavy product page |

**Orchestration**

| Approach | Auditability | Notes |
|---|---|---|
| **Custom Python services (chosen, default)** | High | Each pipeline stage is a plain function/service call, fully logged |
| **LangGraph (chosen, for pipeline state machine only)** | High | Used to represent the fixed INGEST→...→CHANGE state graph (Section 29/39), not for open-ended agent autonomy |
| LlamaIndex | Medium | Not adopted; would abstract away the explicit evidence/claim model this product depends on. Documented as a possible future integration point for advanced retrieval only (Section 27). |

---

## 8. Free/Open-Source Strategy

The MVP is designed to run with **zero mandatory paid dependencies**.

| Component | Category |
|---|---|
| React, Vite, TypeScript, Tailwind | Open-source software |
| FastAPI, Pydantic, SQLAlchemy | Open-source software |
| Docling | Open-source software |
| Crawl4AI, Playwright | Open-source software |
| Ollama runtime | Free local software |
| Open-weight LLM/VLM (see Section 70) | Free local model (license varies by model — verify before commercial use) |
| Qdrant | Open-source software (self-hosted) |
| Neo4j Community Edition | Open-source software (GPLv3 — verify obligations for any distributed/hosted offering) |
| PostgreSQL | Open-source software |
| OpenRouter | Free-tier models available; paid models exist — treated strictly as optional fallback |

No component in the P0 critical path requires an API key. OpenRouter is the only optional component that may require one.

---

## 9. AI Model Architecture

```mermaid
flowchart TD
    APP[Application Services] --> GW[Model Gateway]
    GW --> ROUTE{Task Type}
    ROUTE -->|Document parsing| DOCLING[Docling - non-LLM]
    ROUTE -->|Structured extraction| SMALL[Small/Medium Local LLM]
    ROUTE -->|Conflict/canonical reasoning| STRONG[Stronger Reasoning Model]
    ROUTE -->|Vision| VLM[Vision-Language Model]
    ROUTE -->|Embeddings| EMB[Embedding Model]
    ROUTE -->|Reranking optional| RERANK[Reranker]

    SMALL --> PROV[AIProvider Interface]
    STRONG --> PROV
    VLM --> PROV
    EMB --> PROV
    RERANK --> PROV

    PROV --> OLLAMA[OllamaProvider]
    PROV --> OPENROUTER[OpenRouterProvider]
```

The Model Gateway is the single chokepoint through which every AI call passes. No module calls Ollama or OpenRouter directly.

---

## 10. Ollama Architecture

**Path:** `Application → Model Gateway → OllamaProvider → Ollama → Local LLM/VLM`

- `OllamaProvider` implements the `AIProvider` interface (Section 12/40) using Ollama's local HTTP API (`OLLAMA_BASE_URL`, default `http://localhost:11434`).
- Structured output is requested via Ollama's JSON-mode/schema-constrained generation where supported by the selected model; output is always re-validated against the target Pydantic schema regardless.
- Health check: the Model Gateway pings `OLLAMA_BASE_URL` at startup and before each request batch; failures trigger the fallback logic in Section 11.
- Vision calls route to `OLLAMA_VISION_MODEL` (a separate, VLM-capable model) rather than the general-purpose text model.

## 11. OpenRouter Fallback Architecture

```mermaid
flowchart TD
    REQ[Model Gateway Request] --> CHECK1{Ollama reachable?}
    CHECK1 -->|Yes| USEOLLAMA[Use OllamaProvider]
    CHECK1 -->|No| CHECK2{OPENROUTER_API_KEY set?}
    CHECK2 -->|Yes| USEOR[Use OpenRouterProvider]
    CHECK2 -->|No| FAIL[Fail gracefully: AI_PROVIDER_UNAVAILABLE error, job marked FAILED with explanation]
```

Rules (non-negotiable, per PRD Section 7):
1. Ollama is always attempted first.
2. OpenRouter is used only if Ollama is unreachable **and** `OPENROUTER_API_KEY` is present in environment configuration.
3. If neither is available, the request fails with an explicit `AI_PROVIDER_UNAVAILABLE` error surfaced to the job status — the system never silently switches to a paid model, and never proceeds with a fabricated result.
4. Provider selection can be forced via `AI_PROVIDER=ollama|openrouter`, overriding the automatic fallback for testing/demo control.

## 12. Model Gateway

```python
# backend/app/core/ai_provider.py (conceptual interface)
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str: ...

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type[BaseModel], **kwargs) -> BaseModel: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def vision_generate(self, image_bytes: bytes, prompt: str, schema: type[BaseModel] | None = None) -> Any: ...

class OllamaProvider(AIProvider):
    ...

class OpenRouterProvider(AIProvider):
    ...
```

**Task → model routing table (default configuration):**

| Task | Model class | Example model family | Rationale |
|---|---|---|---|
| Document parsing | Non-LLM (Docling) | — | Deterministic layout parsing, not a generation task |
| Structured attribute extraction | Small/medium local LLM | Qwen2.5 7B-class / Llama 3.x 8B-class | Fast, cheap, sufficient for schema-constrained field extraction |
| Conflict/canonical reasoning explanation | Stronger local reasoning model (or same model with higher-effort prompting) | Qwen2.5 14B+/32B-class where hardware allows | Explaining trade-offs across sources benefits from stronger reasoning |
| Vision (label/image extraction) | VLM | Qwen2-VL / Qwen2.5-VL class | Local multimodal support via Ollama |
| Embeddings | Dedicated embedding model | `nomic-embed-text` or `bge-small/base` class | Purpose-built, small, fast |
| Reranking (optional) | Cross-encoder reranker | `bge-reranker` class | Only invoked if enabled; MVP functions without it |

The Gateway never uses the strongest/largest model for every call — this table is enforced in `core/model_router.py` and is data-driven (a config dict), so it can be retuned per hardware profile without code changes (see Section 70).

---

## 13. Document Ingestion Architecture

```mermaid
flowchart TD
    IN[Input: file or URL] --> DETECT[File Type Detection]
    DETECT --> VALID[Validation: size, type, malware-pattern checks]
    VALID --> HASH[Content Hash - SHA256]
    HASH --> DUPCHECK{Hash exists?}
    DUPCHECK -->|Yes| REUSE[Reuse existing Document record]
    DUPCHECK -->|No| META[Extract Metadata]
    META --> PARSE[Type-Specific Parsing]
    PARSE --> NORMDOC[Document Normalization]
    NORMDOC --> REPR[Document Representation - structured]
    REPR --> CHUNK[Chunking]
    CHUNK --> EVIDX[Evidence Indexing - Qdrant + Postgres]
```

Every ingested item is assigned three identifiers at distinct levels:

| ID | Scope |
|---|---|
| `source_id` | The logical source (e.g., "this manufacturer PDF for Product X") |
| `document_id` | The parsed representation of that source |
| `ingestion_id` | This specific ingestion run/job (supports re-ingestion/reprocessing history) |

Content hashing (SHA-256 over raw bytes) is computed at ingestion time and checked against existing `documents.hash` before reparsing, avoiding duplicate processing of an identical re-uploaded file.

## 14. Docling Pipeline

Docling is the primary document-intelligence layer for PDF and technical manual ingestion.

```mermaid
flowchart TD
    PDF[PDF / Manual] --> DL[Docling Parser]
    DL --> LAYOUT[Layout Analysis: reading order]
    LAYOUT --> BLOCKS[Text Blocks with page numbers]
    LAYOUT --> TABLES[Tables with cell structure]
    LAYOUT --> HEAD[Headings / Sections]
    LAYOUT --> OCRSTEP[OCR pass for scanned pages]
    BLOCKS --> DOCREP[DocumentRepresentation object]
    TABLES --> DOCREP
    HEAD --> DOCREP
    OCRSTEP --> DOCREP
```

Docling output is mapped into an internal `DocumentRepresentation` Pydantic model preserving:

```python
class DocumentBlock(BaseModel):
    block_id: str
    document_id: str
    page: int | None
    section: str | None
    block_type: str  # "paragraph" | "heading" | "table" | "table_cell" | "caption"
    table_id: str | None
    row: int | None
    column: str | None
    bbox: tuple[float, float, float, float] | None
    text: str
```

This structure is never flattened to plain text before evidence indexing — flattening would destroy the page/table/row provenance evidence requires (PRD Section 15/16).

## 15. Web Ingestion

```mermaid
flowchart TD
    URL[Product URL] --> RULES[robots.txt + allow/deny rule check]
    RULES --> C4AI[Crawl4AI fetch]
    C4AI --> JSCHECK{Content sufficiently rendered?}
    JSCHECK -->|Yes| EXTRACT[HTML → structured content extraction]
    JSCHECK -->|No| PW[Playwright fallback render]
    PW --> EXTRACT
    EXTRACT --> SPEC[Specification-relevant content isolation]
    SPEC --> META2[Store URL, title, retrieved_at, content hash]
    META2 --> EVID2[Evidence records]
```

Constraints:
- Only the user-supplied product URL (and explicitly linked product documentation on the same domain) is fetched — no open-ended crawling.
- `robots.txt` is honored; disallowed pages are not fetched, and the failure is reported explicitly.
- An allow/deny domain list (Section 46) prevents SSRF via user-supplied URLs pointing at internal/private network ranges.

## 16. Multimodal Pipeline

```mermaid
flowchart TD
    IMG[Product Image] --> IMGVALID[Image Validation: format, size, resolution]
    IMGVALID --> OCR2[OCR Pass]
    OCR2 --> VLM2[VLM Structured Reading]
    VLM2 --> CLAIMEX[Structured Claim Extraction]
    CLAIMEX --> EVID3[Evidence: evidence_type = IMAGE]
    EVID3 --> TRUTHENGINE[→ Truth Engine]
```

Image-derived claims are tagged `evidence_type = IMAGE` and, in the default Source Authority configuration (Section 21), rank below direct manufacturer datasheet/manual text — a label photograph is corroborating evidence, not a substitute for documented specification text.

## 17. Product Entity Resolution

```mermaid
flowchart TD
    SRC1[Source A identifiers] --> COMPARE[Identifier Comparison]
    SRC2[Source B identifiers] --> COMPARE
    COMPARE --> STRONG{Strong ID match? model_number/SKU/part_number}
    STRONG -->|Exact match| MATCH[MATCH]
    STRONG -->|No strong ID| FUZZY[Fuzzy match: name + manufacturer + family]
    FUZZY --> SCORE{Similarity score}
    SCORE -->|High| POSSIBLE[POSSIBLE_MATCH → REVIEW_REQUIRED]
    SCORE -->|Low| NOMATCH[NO_MATCH]
```

Resolution never auto-merges on name similarity alone; only exact strong-identifier matches (`model_number`, `sku`, `part_number`) produce an automatic `MATCH`. Anything else results in `POSSIBLE_MATCH` (routed to review) or `NO_MATCH` (new product created).

## 18. Claim Extraction

```mermaid
flowchart TD
    DOCREP2[DocumentRepresentation / Parsed Row / Image Reading] --> PROMPT[Schema-constrained extraction prompt]
    PROMPT --> GATEWAY[Model Gateway → generate_structured]
    GATEWAY --> RAWCLAIM[Raw Claim candidate - Pydantic validated]
    RAWCLAIM --> LINKEVID[Link to source DocumentBlock as Evidence]
    LINKEVID --> PERSIST[Persist Claim - status = EXTRACTED]
```

Claim schema (matches PRD Section 15):

```python
class Claim(BaseModel):
    claim_id: str
    product_id: str
    attribute_id: str
    raw_value: str
    normalized_value: float | str | None
    unit: str | None
    source_id: str
    document_id: str
    evidence_id: str
    extraction_method: str          # "llm" | "vlm" | "rule" | "table_parse"
    extraction_model: str           # e.g. "ollama/qwen2.5:7b"
    extracted_at: datetime
    source_version: str | None
    confidence: float
    status: Literal["EXTRACTED","NORMALIZED","VERIFIED","INFERRED","CONFLICT","UNKNOWN","REJECTED"]
```

A claim is created with `status=EXTRACTED` and never bypasses the normalization/conflict/truth pipeline to reach `VERIFIED` directly — enforced at the repository layer (Section 61).

## 19. Evidence Architecture

Evidence schema (PRD Section 16):

```python
class Evidence(BaseModel):
    evidence_id: str
    source_id: str
    document_id: str
    page: int | None
    section: str | None
    table: str | None
    row: int | None
    column: str | None
    text: str | None
    image_reference: str | None
    bounding_box: tuple[float,float,float,float] | None
    retrieved_at: datetime
    hash: str
```

Not all fields are populated for every evidence type (e.g., a spreadsheet row has `row`/`column`, not `page`/`bbox`); the smallest useful location available is always preserved rather than left blank without explanation.

## 20. Industrial Normalization

```mermaid
flowchart TD
    CLAIMIN[Claim: raw_value + raw_unit] --> DETECTU[Unit Detection]
    DETECTU --> DIMCHECK{Dimensionally compatible with attribute type?}
    DIMCHECK -->|No| FLAGUNSUPP[Flag: normalization not attempted]
    DIMCHECK -->|Yes| SAFECONV[Deterministic Conversion Library]
    SAFECONV --> STORE2[Store normalized_value + normalized_unit + formula_used]
    STORE2 --> KEEPORIG[Original raw_value/raw_unit preserved unchanged]
```

Conversion is performed exclusively by a deterministic Python module (`normalization/units.py`), never by LLM arithmetic. Supported conversions and canonical units match PRD Section 17 (HP↔kW, W↔kW, bar↔psi, mm↔inch, kg↔lb, °C↔°F, L/min-family, plus native RPM/Nm/V/A). Each conversion factor is a named constant with a citation comment, so it is auditable rather than embedded inline as a magic number.

```python
# normalization/units.py (excerpt)
CONVERSIONS = {
    ("HP", "kW"): lambda v: v * 0.7457,
    ("W", "kW"): lambda v: v / 1000.0,
    ("bar", "psi"): lambda v: v * 14.5038,
    ("mm", "inch"): lambda v: v / 25.4,
    ("kg", "lb"): lambda v: v * 2.20462,
    ("F", "C"): lambda v: (v - 32) * 5.0/9.0,
}
```

## 21. Source Authority

```python
class SourceAuthority(BaseModel):
    source_type: str
    authority_score: float   # 0.0 - 1.0
    publisher: str | None
    domain: str | None
    retrieved_at: datetime
    version: str | None
    reliability: float       # historical reliability, adjustable
```

Default authority scores (configurable table, not hardcoded logic):

| Rank | Source type | Default score |
|---|---|---|
| 1 | Manufacturer technical datasheet | 1.00 |
| 2 | Manufacturer technical manual | 0.92 |
| 3 | Manufacturer official product page | 0.80 |
| 4 | Manufacturer label/image | 0.70 |
| 5 | Certified documentation | 0.65 |
| 6 | Authorized distributor | 0.50 |
| 7 | Supplier document | 0.40 |
| 8 | Third-party source | 0.25 |

This table lives in Postgres (`source_authority_config`) and is editable via an admin endpoint — authority is a weighted signal into Section 22/23, never a hard override.

## 22. Conflict Detection

```mermaid
flowchart TD
    CLAIMS3[Normalized Claims for one Attribute] --> GROUP[Group by normalized_value]
    GROUP --> SCOREGROUP[Score each group: authority, independence, evidence exactness, recency, extraction_confidence]
    SCOREGROUP --> TOP2[Rank groups by score]
    TOP2 --> GAP{Score gap between top 2 groups < closeness_threshold?}
    GAP -->|Yes| CONFLICTSTATE[Status = CONFLICT]
    GAP -->|No| WINNER[Top group becomes canonical candidate]
```

Independence discount: two claims from the same publisher (e.g., manufacturer PDF + manufacturer manual) count with reduced combined independence weight versus two claims from genuinely distinct organizations, preventing one publisher's duplicated documents from appearing as "many independent sources."

## 23. Canonical Value Engine

```python
class Decision(BaseModel):
    decision_id: str
    attribute_id: str
    canonical_value: float | str
    canonical_unit: str | None
    decision_reason: str
    supporting_claims: list[str]
    contradicting_claims: list[str]
    confidence: float
    status: Literal["VERIFIED","INFERRED","CONFLICT","UNKNOWN"]
    created_at: datetime
    model_used: str | None   # which model generated the reasoning text, if any
```

The `decision_reason` field is generated by the Model Gateway (explanation task) from the deterministic score breakdown — the model explains a score it did not compute, ensuring the reasoning text cannot silently override the deterministic outcome.

## 24. Trust Status Engine

| Status | Rule (deterministic, evaluated in `truth/status.py`) |
|---|---|
| VERIFIED | ≥1 claim from a source with `authority_score ≥ 0.8`, OR ≥2 independent agreeing sources; no competing group within `closeness_threshold` |
| INFERRED | Only one low/medium authority source, or evidence is indirect/approximate |
| CONFLICT | ≥2 independent, credible normalized-value groups within `closeness_threshold` |
| UNKNOWN | Zero claims exist for the attribute |

UNKNOWN → any other status requires a **new claim** (new evidence); it cannot be changed by re-scoring existing data.

## 25. Confidence Engine

```python
def compute_confidence(factors: ConfidenceFactors, weights: ConfidenceWeights) -> ConfidenceResult:
    score = (
        weights.authority * factors.authority_score +
        weights.agreement * factors.agreement_score +
        weights.evidence_quality * factors.evidence_quality_score +
        weights.recency * factors.recency_score +
        weights.extraction_certainty * factors.extraction_certainty +
        weights.normalization_certainty * factors.normalization_certainty
    )
    return ConfidenceResult(score=score, breakdown=factors)
```

Default weights match PRD Section 19 (authority 0.25, agreement 0.25, evidence quality 0.20, recency 0.10, extraction certainty 0.10, normalization certainty 0.10). The API always returns `breakdown`, never a bare number — this is enforced in the `ExportSchema` and `AttributeResponseSchema` (Section 32).

This is an explainable **weighted scoring heuristic**, not a statistically calibrated probability; the document and UI must not claim calibration that has not been measured.

## 26. Human Review

```mermaid
flowchart TD
    TRIGGER{status == CONFLICT OR confidence < review_threshold} --> QUEUE[Add to Review Queue]
    QUEUE --> UIVIEW[UI: Attribute, candidates, evidence, reasoning, confidence]
    UIVIEW --> ACTION{Reviewer Action}
    ACTION -->|Approve A| APPROVEA[Set canonical = A, status = VERIFIED]
    ACTION -->|Approve B| APPROVEB[Set canonical = B, status = VERIFIED]
    ACTION -->|Reject| REJECT[status stays CONFLICT, request more evidence]
    ACTION -->|Mark Unknown| MARKUNK[status = UNKNOWN, note reason]
    APPROVEA --> LOG[Persist Review record + graph RESOLVED_BY]
    APPROVEB --> LOG
    REJECT --> LOG
    MARKUNK --> LOG
```

Every action persists a `Review` record (`reviewer_id`, `timestamp`, `chosen_value`, `rationale`) linked in Neo4j via `(Claim)-[:RESOLVED_BY]->(Decision)` and `(Review)-[:REVIEWS]->(Claim)`.

---

## 27. RAG Architecture

The system deliberately does **not** implement generic RAG-as-truth-engine. RAG is retrieval infrastructure feeding the deterministic Truth Engine, never a substitute for it.

```mermaid
flowchart TD
    QUERY[Internal Query: e.g., 'find evidence for voltage, product X'] --> FILTER[Metadata Filter Builder]
    FILTER --> QDR[Qdrant: filtered similarity search]
    QDR --> CANDIDATES[Evidence Candidates]
    CANDIDATES --> GCTX[Neo4j: Graph Context - related claims/sources/versions]
    GCTX --> AUTHW[Source Authority Weighting]
    AUTHW --> TE[Truth Engine]
    TE --> DECISION2[Decision]
```

This is labeled **evidence-grounded, graph-augmented retrieval**, distinct from the naive `question → vector search → LLM answer` pattern: retrieval never directly produces a user-facing answer; it only supplies candidates into the deterministic conflict/canonical pipeline.

## 28. Qdrant Architecture

Collections (one per content type, to keep payload schemas simple):

| Collection | Vector source | Payload fields |
|---|---|---|
| `document_chunks` | Embedded `DocumentBlock.text` | `product_id, source_id, document_id, page, section, content_type, timestamp` |
| `evidence` | Embedded `Evidence.text` | `product_id, source_id, document_id, claim_id, evidence_id, content_type, timestamp` |
| `claims` | Embedded `attribute + raw_value` string | `product_id, claim_id, attribute, source_id, timestamp` |

Query pattern: metadata filter first (`product_id`, `attribute`, `source_type`), vector similarity second — never unfiltered global similarity search. Qdrant is never queried as a source of authoritative state; a Qdrant outage degrades semantic search UX but does not corrupt Postgres/Neo4j truth data (Section 45).

## 29. Knowledge Graph RAG

Graph traversal is used whenever the question is inherently relational/multi-hop; vector search is used whenever the question is semantic/textual.

| Question type | Mechanism |
|---|---|
| "What is the exact wording that supports 230V?" | Qdrant semantic search over `evidence` |
| "Why do we believe 230V?" (full chain) | Neo4j traversal: Product→Attribute→Claim→Evidence→Document→Source |
| "What changed between versions?" | Neo4j traversal: ProductVersion→Change |
| "What assets are affected by this change?" | Neo4j traversal: Change→AFFECTS→Asset |
| "Find similar evidence text across the catalog" | Qdrant semantic search |

---

## 30. Neo4j Architecture

Neo4j Community Edition, accessed via the official Python driver (`neo4j` package), wrapped in a `graph/` repository module so no other module issues raw Cypher directly.

## 31. Neo4j Schema

**Nodes**

| Node | Key properties |
|---|---|
| `Product` | `product_id`, `name`, `manufacturer`, `category`, `created_at` |
| `ProductVersion` | `version_id`, `product_id`, `version_number`, `created_at` |
| `Attribute` | `attribute_id`, `name`, `data_type`, `unit_category` |
| `Claim` | `claim_id`, `raw_value`, `normalized_value`, `unit`, `status`, `confidence`, `extracted_at` |
| `Evidence` | `evidence_id`, `text`, `page`, `row`, `column`, `image_reference`, `hash` |
| `Source` | `source_id`, `source_type`, `authority_score`, `retrieved_at` |
| `Document` | `document_id`, `hash`, `format`, `parsed_at` |
| `Supplier` | `supplier_id`, `name` |
| `Change` | `change_id`, `attribute_id`, `old_value`, `new_value`, `detected_at`, `impact_level` |
| `Asset` | `asset_id`, `asset_type`, `name` |
| `Review` | `review_id`, `reviewer_id`, `decision`, `rationale`, `reviewed_at` |
| `Decision` | `decision_id`, `canonical_value`, `decision_reason`, `confidence`, `status`, `created_at` |
| `Standard` | `standard_id`, `body` (e.g. IEC/ISO/EN/ASTM/DIN/API), `code`, `description` |

**Relationships**

```
(Product)-[:HAS_VERSION]->(ProductVersion)
(Product)-[:HAS_ATTRIBUTE]->(Attribute)
(Attribute)-[:HAS_CLAIM]->(Claim)
(Claim)-[:SUPPORTED_BY]->(Evidence)
(Evidence)-[:EXTRACTED_FROM]->(Document)
(Document)-[:FROM_SOURCE]->(Source)
(Source)-[:SUPPLIED_BY]->(Supplier)
(Claim)-[:CONFLICTS_WITH]->(Claim)
(Claim)-[:RESOLVED_BY]->(Decision)
(Decision)-[:SELECTS]->(Claim)
(ProductVersion)-[:HAS_CHANGE]->(Change)
(Change)-[:AFFECTS]->(Asset)
(Claim)-[:VALIDATED_AGAINST]->(Standard)
(Review)-[:REVIEWS]->(Claim)
```

```mermaid
graph TD
    Product -->|HAS_VERSION| ProductVersion
    Product -->|HAS_ATTRIBUTE| Attribute
    Attribute -->|HAS_CLAIM| Claim
    Claim -->|SUPPORTED_BY| Evidence
    Evidence -->|EXTRACTED_FROM| Document
    Document -->|FROM_SOURCE| Source
    Source -->|SUPPLIED_BY| Supplier
    Claim -->|CONFLICTS_WITH| Claim
    Claim -->|RESOLVED_BY| Decision
    Decision -->|SELECTS| Claim
    ProductVersion -->|HAS_CHANGE| Change
    Change -->|AFFECTS| Asset
    Claim -->|VALIDATED_AGAINST| Standard
    Review -->|REVIEWS| Claim
```

**Constraints and indexes** (`neo4j/constraints.cypher`, `neo4j/indexes.cypher`):

```cypher
CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE;
CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE;
CREATE CONSTRAINT source_id_unique IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE;
CREATE CONSTRAINT attribute_id_unique IF NOT EXISTS FOR (a:Attribute) REQUIRE a.attribute_id IS UNIQUE;
CREATE CONSTRAINT version_id_unique IF NOT EXISTS FOR (v:ProductVersion) REQUIRE v.version_id IS UNIQUE;
CREATE CONSTRAINT change_id_unique IF NOT EXISTS FOR (c:Change) REQUIRE c.change_id IS UNIQUE;

CREATE INDEX claim_attribute_idx IF NOT EXISTS FOR (c:Claim) ON (c.status);
CREATE INDEX source_type_idx IF NOT EXISTS FOR (s:Source) ON (s.source_type);
```

## 32. Cypher Examples

**Provenance traversal ("why 230V?")**

```cypher
MATCH (p:Product {product_id: $productId})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "voltage"})
      -[:HAS_CLAIM]->(c:Claim {normalized_value: 230})
      -[:SUPPORTED_BY]->(e:Evidence)-[:EXTRACTED_FROM]->(d:Document)-[:FROM_SOURCE]->(s:Source)
RETURN p.name, a.name, c.raw_value, e.text, d.format, s.source_type, s.authority_score;
```

**Conflict investigation**

```cypher
MATCH (a:Attribute {name: "voltage"})-[:HAS_CLAIM]->(c1:Claim)-[:CONFLICTS_WITH]->(c2:Claim)
RETURN c1.normalized_value, c1.confidence, c2.normalized_value, c2.confidence;
```

**Product version change history**

```cypher
MATCH (p:Product {product_id: $productId})-[:HAS_VERSION]->(v:ProductVersion)-[:HAS_CHANGE]->(ch:Change)
RETURN v.version_number, ch.attribute_id, ch.old_value, ch.new_value, ch.detected_at
ORDER BY v.version_number;
```

**Change impact query**

```cypher
MATCH (ch:Change {change_id: $changeId})-[:AFFECTS]->(asset:Asset)
RETURN asset.asset_type, asset.name;
```

**Review audit query**

```cypher
MATCH (r:Review)-[:REVIEWS]->(c:Claim)
WHERE c.claim_id = $claimId
RETURN r.reviewer_id, r.decision, r.rationale, r.reviewed_at;
```

---

## 33. PostgreSQL Architecture

PostgreSQL is the operational system of record. Tables:

| Table | Purpose |
|---|---|
| `products` | Product identity fields |
| `product_versions` | Version metadata (mirrors Neo4j `ProductVersion`) |
| `attributes` | Attribute schema definitions |
| `claims` | Full claim records (mirrors Neo4j `Claim` for relational querying) |
| `evidence` | Evidence records |
| `sources` | Source metadata + authority config reference |
| `documents` | Parsed document metadata + hash |
| `suppliers` | Supplier records |
| `decisions` | Canonical decisions |
| `reviews` | Human review records |
| `changes` | Detected changes |
| `assets` | Logical asset catalog |
| `ingestions` | Ingestion run records |
| `processing_jobs` | Background job status tracking |
| `source_authority_config` | Editable authority ranking table |

Each table has: a UUID primary key, relevant foreign keys, `created_at`/`updated_at` timestamps, a `status` field where applicable, and a `metadata JSONB` column for extensible attributes without schema churn. Postgres and Neo4j intentionally store overlapping core fields (claims, decisions) — Postgres for relational/operational querying and transactional job state, Neo4j for relationship traversal; Postgres is the transactional writer of record, and graph writes are issued in the same service-layer transaction boundary immediately after a successful Postgres commit (Section 65 — reliability).

## 34. File Storage

```
data/
    raw/          # original, unmodified uploaded files
    processed/    # Docling/parser intermediate output
    extracted/    # structured claim JSON per document
    evidence/     # evidence snippets/crops (e.g. image label crops)
    exports/      # generated JSON/CSV exports
```

Every original file is stored exactly as uploaded, referenced by `document_id`/`product_id`/hash, and never overwritten by any downstream processing artifact. Production deployments may swap this for S3-compatible object storage behind the same `StorageBackend` interface used locally.

---

## 35. Product Versioning

A `ProductVersion` is created when a new source causes a **material** change to a previously canonical value (see Section 36 for the materiality test). Each version stores: `previous_value`, `new_value`, `source`, `document`, `detected_at`, `evidence`, `impact` — matching PRD Section 35. Versions are immutable and linked via `SUPERSEDES` in Neo4j and a `previous_version_id` foreign key in Postgres.

## 36. Change Detection

```mermaid
flowchart TD
    OLD[Old canonical product truth] --> DIFF[Attribute-by-attribute diff]
    NEW[New extracted + normalized claims] --> DIFF
    DIFF --> TYPE{Change type}
    TYPE -->|Value changed post-normalization beyond tolerance| REALCHANGE[REAL CHANGE]
    TYPE -->|Same normalized value, different unit/representation| REPRCHANGE[REPRESENTATION CHANGE - not flagged]
    TYPE -->|Attribute newly present| ADDED[Added attribute]
    TYPE -->|Attribute no longer supported by any source| REMOVED[Removed attribute]
    REALCHANGE --> CHANGEEVENT[Create Change node/record]
    ADDED --> CHANGEEVENT
    REMOVED --> CHANGEEVENT
```

Example: 5 HP vs 3.73 kW is a **representation change** (same normalized value, ~0 delta) — not flagged. 250 bar vs 280 bar is a **real change** — flagged, versioned, and passed to the Impact Engine.

## 37. Change Impact Analysis

```python
IMPACT_MAP = {
    "voltage": ["product_page", "technical_description", "erp_record"],
    "pressure": ["product_page", "catalog", "distributor_feed", "comparison_table", "technical_description", "erp_record"],
    "certification": ["product_page", "catalog", "compliance_record"],
    # ... additional attribute -> logical asset mappings
}
```

Impact level (`LOW`/`MEDIUM`/`HIGH`) is derived from a simple rule: safety-critical attributes (Section 39) affecting ≥3 asset categories → `HIGH`; 1–2 categories → `MEDIUM`; non-safety-critical, ≤1 category → `LOW`. Every impact record includes a human-readable `reason` string (e.g., *"Pressure specification changed and affects technical product claims."*) and is clearly labeled in the UI as a **logical/representative** impact — no real ERP/PIM/e-commerce system is contacted.

## 38. Industrial Standards Layer

A `Standard` node type and `VALIDATED_AGAINST` relationship exist in the schema (Section 31) to support future standards-aware validation (IEC/ISO/EN/ASTM/DIN/API). For the MVP, this is backed by a small, explicitly curated ruleset (e.g., a handful of manually verified voltage/pressure range rules per standard) — not by AI-inferred standards knowledge. Where no verified rule exists for an attribute/standard pair, the system returns `STANDARD_CHECK = NOT_AVAILABLE` rather than fabricating a compliance judgment.

---

## 39. AI Agent/Workflow Architecture

The pipeline is implemented as a **fixed state graph**, not open-ended autonomous agents.

```mermaid
stateDiagram-v2
    [*] --> INGEST
    INGEST --> EXTRACT
    EXTRACT --> NORMALIZE
    NORMALIZE --> EVIDENCE
    EVIDENCE --> VALIDATE
    VALIDATE --> CONFLICT
    CONFLICT --> DECIDE
    DECIDE --> REVIEW
    REVIEW --> GRAPH
    GRAPH --> VERSION
    VERSION --> CHANGE
    CHANGE --> [*]
```

Each state corresponds to a deterministic Python service (`ingestion.run()`, `extraction.run()`, etc.). LangGraph is used only to encode this specific, fixed sequence (with conditional branches for REVIEW vs. auto-VERIFIED) — every node is a plain, logged, testable function, and no node is permitted open-ended tool selection or unbounded iteration. Logical "workers" (Ingestion, Extraction, Normalization, Evidence, Validation, Conflict, Truth Decision, Change Detection) map one-to-one to the modules in Section 5.

Safety-critical attributes (voltage, pressure, temperature, load, certification, material compatibility, operating limits — PRD Section 39) use a **stricter** review threshold (lower `confidence_threshold`, tighter `closeness_threshold`), meaning they are more readily routed to REVIEW than non-safety attributes.

---

## 40. API Architecture

Base path: `/api/v1`

| Method | Path | Purpose |
|---|---|---|
| POST | `/products` | Create a product workspace |
| GET | `/products` | List products |
| GET | `/products/{id}` | Full product truth record |
| POST | `/products/{id}/sources` | Attach a source (file/URL) |
| POST | `/ingest/pdf` | Ingest a PDF |
| POST | `/ingest/url` | Ingest a URL |
| POST | `/ingest/excel` | Ingest Excel/CSV |
| POST | `/ingest/image` | Ingest a product image |
| POST | `/products/{id}/process` | Trigger the truth pipeline (async job) |
| GET | `/products/{id}/attributes` | List attributes with canonical values/status/confidence |
| GET | `/products/{id}/claims` | List raw claims |
| GET | `/products/{id}/evidence` | List/query evidence |
| GET | `/products/{id}/conflicts` | List CONFLICT attributes |
| GET | `/products/{id}/graph` | Graph traversal view for the product |
| GET | `/products/{id}/versions` | Version history |
| GET | `/products/{id}/changes` | Detected changes + impact |
| POST | `/reviews/{claim_id}` | Submit a review record |
| POST | `/reviews/{claim_id}/approve` | Approve a candidate value |
| POST | `/reviews/{claim_id}/reject` | Reject / request more evidence |
| GET | `/products/{id}/export/json` | JSON export |
| GET | `/products/{id}/export/csv` | CSV export |
| POST | `/products/{id}/reprocess` | Re-run the pipeline (e.g., after new source) |

**Example — `POST /products/{id}/process`**

- Request: `{}` (no body required; operates on all attached sources not yet processed)
- Response: `202 Accepted` `{ "job_id": "uuid", "status": "QUEUED" }`
- Errors: `404` product not found; `409` if a processing job is already running for this product
- Auth: Bearer token (auth-ready; see Section 46)
- Processing flow: creates a `processing_jobs` row → enqueues background task → returns immediately; job status pollable via `GET /jobs/{job_id}`

**Example — `POST /reviews/{claim_id}/approve`**

- Request: `{ "chosen_value": 230, "rationale": "Datasheet and manual both confirm 230V; supplier sheet is outdated." }`
- Response: `200 OK` `{ "claim_id": "...", "status": "VERIFIED", "decision_id": "..." }`
- Errors: `404` claim not found; `400` if claim is not currently in a reviewable state
- Auth: Bearer token, reviewer role
- Processing flow: writes `Review` row (Postgres) → writes `Decision`/`RESOLVED_BY` (Neo4j) → recalculates attribute status

All other endpoints follow the same documented shape (method, path, purpose, request, response, errors, auth, processing flow) using the schemas defined in `backend/app/schemas/`.

---

## 41. Event Architecture

Internal events (published in-process via a lightweight event dispatcher; no external message broker required for MVP):

```
SOURCE_UPLOADED → DOCUMENT_PARSED → CLAIMS_EXTRACTED → CLAIMS_NORMALIZED
→ CONFLICT_DETECTED → TRUTH_DECIDED → REVIEW_REQUIRED → REVIEW_COMPLETED
→ PRODUCT_VERSION_CREATED → CHANGE_DETECTED → IMPACT_ANALYZED
```

Each event carries a minimal payload (`product_id`, relevant entity id, timestamp) and is logged to structured application logs (Section 48). Events drive UI polling/refresh hints and the observability log; they are not (yet) exposed as a public webhook system.

## 42. Background Processing

```mermaid
flowchart TD
    UPLOAD[Upload / Process Request] --> CREATEJOB[Create processing_jobs row: QUEUED]
    CREATEJOB --> RETURN[Return job_id to client]
    RETURN --> WORKER[FastAPI BackgroundTasks / async worker picks up job]
    WORKER --> RUNPIPE[Run pipeline: Section 39 state graph]
    RUNPIPE --> UPDATESTATUS[Update job status: PROCESSING → COMPLETED/FAILED/REVIEW_REQUIRED]
    UPDATESTATUS --> POLL[Frontend polls GET /jobs/id or receives SSE update]
```

Job states: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `REVIEW_REQUIRED`. For the overnight MVP, FastAPI's `BackgroundTasks` (or a simple asyncio task queue) is sufficient — no Kafka or dedicated message broker is introduced. This is documented as a clean upgrade point for Section 64 (scalability).

---

## 43. Frontend Architecture

```
frontend/src/
    components/   # ProductHeader, ProductQualityScore, AttributeTable, ClaimCard,
                  # EvidencePanel, ConflictCard, SourceAuthorityBadge, TrustStatusBadge,
                  # ConfidenceIndicator, ReviewPanel, GraphViewer, ChangeTimeline,
                  # ImpactPanel, ExportPanel
    pages/        # Dashboard, ProductWorkspace, SourceManager, EvidenceExplorer,
                  # ConflictReview, TruthGraph, ChangeIntelligence, Export
    hooks/        # useProduct, useAttributes, useEvidence, useReviewQueue, useJobStatus
    services/     # apiClient.ts (typed fetch wrappers per endpoint in Section 40)
    types/        # Claim, Evidence, Attribute, Decision, Review, Change, Asset
    utils/        # formatting, status color mapping, confidence breakdown rendering
```

State is managed with React Query (server-cache) for all API-backed data, avoiding a global client-state store for data that Postgres/Neo4j already own.

## 44. Product Truth Workspace

The primary screen composes: `ProductHeader`, `ProductQualityScore`, `AttributeTable` (one row per attribute), and, per selected attribute, `ClaimCard` list + `EvidencePanel` + `ConflictCard` (when applicable) + `TrustStatusBadge` + `ConfidenceIndicator` (with expandable factor breakdown) + `ReviewPanel` (when review-required) + version/change indicators via `ChangeTimeline`.

Example rendering (Voltage):

```
VOLTAGE
Canonical: 230 V        Status: VERIFIED        Confidence: 96%
Evidence: 3 supporting sources · 2 conflicting sources
Reason: "Three higher-authority sources support 230V. Two supplier-level sources report 220V."
Actions: [View evidence] [View graph] [Review] [Compare sources]
```

## 45. Graph Visualization

`GraphViewer` renders exactly two focused traversal views (not a generic full-graph explorer):
1. **Provenance view:** `Product → Attribute → Claim → Evidence → Source`
2. **Change view:** `Product → Version → Change → Affected Asset`

Both are rendered from a bounded Cypher query (Section 32) returning a small subgraph (typically <30 nodes), keeping the visualization readable rather than attempting a full-graph force-layout.

---

## 46. Security

- All secrets (`DATABASE_URL`, `NEO4J_PASSWORD`, `OPENROUTER_API_KEY`, etc.) loaded from `.env`; never committed or hardcoded.
- Input validation on every endpoint via Pydantic request schemas.
- File type validation by content-sniffing (not just extension) plus an allow-list (`pdf`, `xlsx`, `csv`, `jpg`, `jpeg`, `png`).
- `MAX_FILE_SIZE` enforced at upload; oversized files rejected before parsing.
- Uploaded filenames are sanitized/re-generated (UUID-based storage names) to prevent path traversal.
- **SSRF protection** for URL ingestion: resolve and reject requests targeting private/internal IP ranges (RFC 1918, loopback, link-local); maintain an explicit allow/deny domain list for the crawler.
- Authentication-ready: all endpoints accept a Bearer token; MVP may run with a single default demo user, but the request/response contracts and DB schema already include `user_id`/`reviewer_id` fields for future multi-user RBAC.
- Audit logs: every review decision and every canonical-value change is logged with actor, timestamp, and reason (Sections 26, 48).

## 47. Privacy

- Fully local deployment mode (Ollama + local Postgres/Neo4j/Qdrant + local file storage) is a first-class, supported configuration, not an afterthought — this is the default `docker-compose.yml` profile.
- No document content is sent to OpenRouter unless the fallback path is actually invoked (Section 11), and this is logged explicitly so it is never a silent occurrence.
- Exported files contain only data belonging to the requesting product/organization context (relevant primarily once multi-tenancy is added).

---

## 48. Observability

Every AI decision logs: `model`, `prompt_version`, `timestamp`, `input_reference` (e.g., document_id/page), `output`, and `decision_metadata` (which factors contributed). Raw prompts are logged at a truncated/redacted level by default (`LOG_LEVEL` controls verbosity) to avoid unnecessarily persisting full sensitive document text in logs.

Tracked metrics: ingestion time, processing time, model used, model latency, token usage (where the provider reports it), documents processed, claims extracted, conflicts detected, review rate, and error counts — surfaced via structured JSON logs and a simple metrics summary endpoint for the demo (`GET /metrics/summary`).

This observability directly supports the judge-facing question in Section 62 of the PRD: for any canonical value, the system can answer *which sources, what evidence, which claims, which conflicts, what normalization, what authority, what decision, what confidence, who approved it* — each of these maps to a stored, queryable field (Sections 15, 16, 21–26, 32).

## 49. Error Handling

| Failure | Behavior |
|---|---|
| Invalid/corrupt PDF | Reject at validation with explicit error; job not created |
| Scanned PDF (no extractable text layer) | Routed to Docling OCR path; if OCR also fails, flagged `NEEDS_MANUAL_REVIEW`, not silently empty |
| Malformed Excel (no headers) | Column-mapping prompt surfaced to user; job paused, not failed silently |
| URL unavailable / blocked | Ingestion job `FAILED` with the specific HTTP/robots reason recorded |
| OCR failure | Claim not created for that block; logged, not fabricated |
| Ollama unavailable | Fallback logic (Section 11); ultimately `AI_PROVIDER_UNAVAILABLE` if no provider works |
| OpenRouter unavailable | Falls through to explicit failure; never silently retries indefinitely |
| Neo4j unavailable | Truth pipeline halts before the GRAPH state; job marked `FAILED`, Postgres state remains consistent (no partial graph writes) |
| Qdrant unavailable | Semantic search degrades (deterministic Postgres/Neo4j lookups still function); flagged as a warning, not a hard failure |
| PostgreSQL unavailable | Entire API returns `503`; no writes are attempted anywhere else |
| Extraction failure (schema validation fails on model output) | Claim not persisted; retried once with a stricter prompt, then flagged for manual attention |
| Conflicting entity resolution | `POSSIBLE_MATCH` routed to review; never auto-merged |
| Unsupported unit | Value stored un-normalized with a `normalization_status = UNSUPPORTED` flag; never guessed |

No failure path is permitted to leave a previously VERIFIED attribute silently downgraded or corrupted (Section 65).

---

## 50. Testing Architecture

**Unit tests:** unit conversion correctness (`normalization/units.py`), source authority scoring, confidence calculation, claim normalization, conflict-group scoring.

**Integration tests:** Docling parsing against sample PDFs, Neo4j read/write round-trips, Qdrant upsert/query round-trips, PostgreSQL repository CRUD, Ollama connectivity/generation smoke tests.

**End-to-end tests:** full pipeline across PDF + URL + Excel + Image inputs producing a complete Product Truth record.

**Named scenario tests (mandatory, mirror the PRD demo):**
- `test_voltage_conflict`: 230V (PDF/manual/image) vs 220V (website/Excel) → status `CONFLICT`, both groups present, evidence intact.
- `test_power_normalization`: 5 HP / 3.73 kW / 3730 W → recognized as one normalized attribute, status `VERIFIED`.
- `test_pressure_change`: 250 bar → 280 bar across versions → `Change` created, new `ProductVersion`, impact list generated.
- `test_unknown_attribute`: attribute with zero supporting claims → status `UNKNOWN`, no value fabricated.

## 51. Security Testing

Explicit test cases: malicious/oversized file upload rejected; invalid/malformed URL rejected; SSRF attempt against a private IP rejected; path traversal filename rejected; missing `OPENROUTER_API_KEY` when Ollama is down produces graceful `AI_PROVIDER_UNAVAILABLE` (not a crash); database unavailable produces `503` (not an unhandled exception); malformed/non-schema-conforming model output is caught by Pydantic validation and triggers the retry/flag path (Section 49), not a silent bad write.

---

## 52. Deployment Architecture

```mermaid
flowchart TD
    subgraph Local Development
        FE1[React Dev Server] --> API1[FastAPI]
        API1 --> PG1[(PostgreSQL)]
        API1 --> NEO1[(Neo4j)]
        API1 --> QD1[(Qdrant)]
        API1 --> OLL1[Ollama - local]
    end

    subgraph Optional Cloud
        FE2[Vercel] --> API2[Render/Railway/Fly.io]
        API2 --> PG2[(Supabase Postgres)]
        API2 --> NEO2[(Neo4j - self-hosted or community-compatible host)]
        API2 --> QD2[(Qdrant - local or free-tier if available)]
        API2 -.optional.-> OR2[OpenRouter]
    end
```

The application must remain fully locally runnable at all times; any cloud profile is additive, not required. No assumption is made that a free cloud tier persists indefinitely — the local `docker-compose.yml` profile is the source of truth for "does this work."

## 53. Docker Architecture

`docker-compose.yml` services: `frontend`, `backend`, `postgres`, `neo4j`, `qdrant`, `ollama` (optional service — see native mode below).

```yaml
# docker-compose.yml (conceptual excerpt)
services:
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [postgres, neo4j, qdrant]
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ipte
    volumes: ["pgdata:/var/lib/postgresql/data"]
  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    volumes: ["neo4jdata:/data"]
  qdrant:
    image: qdrant/qdrant
    volumes: ["qdrantdata:/qdrant/storage"]
  ollama:
    image: ollama/ollama
    volumes: ["ollamadata:/root/.ollama"]
volumes:
  pgdata:
  neo4jdata:
  qdrantdata:
  ollamadata:
```

**Native Ollama mode:** when GPU acceleration is required, Ollama runs directly on host hardware (`OLLAMA_BASE_URL=http://host.docker.internal:11434`) instead of the containerized service — both modes are supported and selected purely via the `OLLAMA_BASE_URL` environment variable, with no code branching required.

## 54. Antigravity Development Architecture

Antigravity is expected to: create files, install dependencies, run commands, start services, run tests, inspect logs, modify code, connect to databases, run local AI, and iterate on the UI. To support this without unnecessary configuration friction, the repository provides: `.env` / `.env.example`, `docker-compose.yml`, `backend/pyproject.toml`, `frontend/package.json`, `README.md`, and a `Makefile`/`scripts/` directory with one-command targets (`make up`, `make test`, `make seed-demo`).

**Developer tooling vs. product runtime:** MCP (Neo4j MCP, GitHub MCP, filesystem MCP, database MCP) is optional developer tooling Antigravity may use during implementation; it is never a runtime dependency of the deployed application itself.

## 55. Project Folder Structure

```
industrial-product-truth-engine/
├── frontend/
│   ├── src/{components,pages,hooks,services,types,utils}/
│   └── package.json
├── backend/
│   ├── app/{api,core,models,schemas,ingestion,extraction,normalization,
│   │         evidence,validation,conflict,truth,retrieval,graph,
│   │         versioning,change_detection,impact,review,export,tests}/
│   └── pyproject.toml
├── data/{raw,processed,extracted,evidence,demo}/
├── neo4j/{constraints.cypher,indexes.cypher,seed.cypher,queries.cypher}
├── qdrant/config/
├── scripts/
├── tests/
├── docs/{01_PRD.md,02_SYSTEM_ARCHITECTURE.md,03_IMPLEMENTATION_PLAN.md}
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

## 56. Environment Variables

```env
APP_ENV=development

DATABASE_URL=postgresql://user:password@localhost:5432/ipte

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=
OLLAMA_VISION_MODEL=
EMBEDDING_MODEL=

AI_PROVIDER=ollama

OPENROUTER_API_KEY=
OPENROUTER_MODEL=

STORAGE_PATH=./data

MAX_FILE_SIZE=25000000

LOG_LEVEL=INFO
```

No actual secret values are included above; `.env.example` ships with empty/placeholder values only.

## 57. Antigravity Implementation Rules

1. Read `01_PRD.md` first, before any implementation work.
2. Read `02_SYSTEM_ARCHITECTURE.md` (this document) before making any architecture-level change.
3. Preserve the module boundaries defined in Section 5 — do not collapse modules together for convenience.
4. Never hardcode secrets; always read from environment configuration.
5. Never silently replace a selected technology (Section 7's decisions are final for this build).
6. Check package/version compatibility before adding a new dependency.
7. Keep `.env.example` up to date with every new configuration variable.
8. Create and maintain database migrations for every Postgres schema change.
9. Create/update Neo4j constraints and indexes (`neo4j/constraints.cypher`, `neo4j/indexes.cypher`) alongside any graph schema change.
10. Create/update Qdrant collection definitions alongside any retrieval schema change.
11. Keep API request/response Pydantic schemas in sync with the endpoint table (Section 40).
12. Write tests for all truth-logic changes (Section 50), especially the four named scenario tests.
13. Never remove or bypass evidence capture, even for "quick" extraction paths.
14. Never overwrite a `raw_value`/original source value.
15. Never let a claim skip from `EXTRACTED` directly to `VERIFIED` without passing through normalization/conflict/decision.
16. Never allow an unsupported/unconverted value to be marked `VERIFIED` — normalization failures stay flagged.
17. Always implement the Ollama→OpenRouter→explicit-failure fallback chain (Section 11) for any new AI call site.
18. Log every failure with enough context to debug without re-running the full pipeline.
19. Never fabricate a value for a missing attribute; use `UNKNOWN`.
20. Prefer deterministic code over LLM calls wherever the task is not genuinely semantic (Section 60).

## 58. What Must Not Happen

- Generic chatbot architecture standing in for the Truth Engine.
- Direct PDF → LLM → JSON extraction with no provenance layer.
- LLM-only unit conversion.
- LLM-only truth/status decisions.
- Silent conflict resolution or majority-vote-only resolution.
- Deleting or hiding conflicting source claims.
- Overwriting historical product versions in place.
- Fake ERP/PIM integrations presented as real.
- A decorative, unused Neo4j instance not actually queried by the application.
- Fabricated citations or evidence text not present in the source.
- Hardcoded API keys anywhere in source control.
- Treating any paid API as a mandatory dependency.
- Uncontrolled, open-ended autonomous agents replacing the fixed pipeline in Section 39.
- Unsupported safety-certification claims (Section 39/45 of the PRD).

---

## 59. Demo Data Architecture

Demo product: **Industrial Hydraulic Pump.**

| File | Type | Purpose |
|---|---|---|
| `manufacturer_datasheet.pdf` | PDF | High-authority source; contains 230V, 5 HP, 250 bar (v1) / 280 bar (v2) |
| `manufacturer_product_page.html` | URL/HTML | Manufacturer website; contains 220V (intentionally conflicting) |
| `product_label.jpg` | Image | Label photo; contains 230V, model number |
| `supplier_catalog.xlsx` | Excel | Supplier-submitted spreadsheet; contains 220V (intentionally conflicting), 3730 W |
| `technical_manual.pdf` | PDF | Manufacturer manual; contains 230V, 3.73 kW |

Located under `data/demo/` with a seed script (`scripts/seed_demo.py`) that ingests all five files into a fresh `Product` record, producing the voltage conflict, power-normalization agreement, and pressure version-change scenarios described in the PRD (Sections 3, 40).

## 60. End-to-End Demo Flow

1. Create product ("Hydraulic Pump HP-4000").
2. Upload the five demo sources.
3. Trigger `/products/{id}/process`.
4. Docling/Crawl4AI/tabular parser/OCR+VLM each produce parsed representations.
5. Claim Extraction produces claims for voltage, power, pressure, and other schema attributes.
6. Normalization converts 5 HP/3.73 kW/3730 W to one canonical Power value.
7. Evidence Engine stores exact snippets per claim.
8. Cross-Source Comparison groups voltage claims into 230V (3 sources) vs 220V (2 sources).
9. Conflict Engine flags Voltage as `CONFLICT`.
10. Canonical Value Engine proposes 230V with reasoning.
11. Confidence/Trust Engine computes the confidence breakdown and status.
12. Reviewer opens Conflict Review, inspects evidence, approves 230V → status becomes `VERIFIED`.
13. Product Truth Graph view shows the full Product→Attribute→Claim→Evidence→Source path.
14. A revised datasheet (Pressure 280 bar) is uploaded.
15. Change Detection flags a real change; a new `ProductVersion` is created.
16. Impact Engine lists logical affected assets.
17. Product JSON (and CSV) is exported, containing canonical values, originals, evidence, confidence, status, conflicts, version, and changes.

---

## 61. Performance

Measured (not assumed) for the demo dataset: ingestion time per source, parsing time per document, extraction time per claim batch, graph insertion time per product, retrieval latency per evidence query, and total end-to-end processing time. No benchmark numbers are asserted in this document prior to actual measurement.

Optimization strategies applied from the start: cache parsed documents keyed by content hash (Section 13); cache embeddings keyed by chunk hash; avoid re-embedding/re-extracting duplicate files; batch embedding calls where the provider supports it; route simple extraction tasks to the small model and reserve the stronger model for conflict/canonical reasoning explanations (Section 12).

## 62. Scalability

The modular monolith is designed so each module in Section 5 can become an independently deployed service without a data-model rewrite, since Postgres/Neo4j/Qdrant are already the shared systems of record rather than in-process state. The growth path (1 → 100 → 10,000 → 100,000+ products) is supported by: queue-based workers replacing `BackgroundTasks` (Section 42), object storage replacing local disk (Section 34), Neo4j read-replica/clustering options at scale, Qdrant sharding/collection partitioning, batch ingestion endpoints, and dedicated model-serving infrastructure for the extraction/vision models. None of these require a change to the claim/evidence/decision data model defined in Sections 18–25.

## 63. Reliability

Implemented from the start: idempotent ingestion (content-hash dedup, Section 13), per-job status tracking with `QUEUED/PROCESSING/COMPLETED/FAILED/REVIEW_REQUIRED` states (Section 42), retries with backoff for transient AI-provider/network failures, timeouts on all external calls (URL fetch, Ollama/OpenRouter), processing checkpoints so a failed late-stage step (e.g., graph write) does not require re-running extraction, and structured logging throughout (Section 48). A failed AI extraction attempt never overwrites or corrupts a previously `VERIFIED` claim — writes to canonical state only occur after the full deterministic pipeline (normalization → conflict → decision) succeeds.

## 64. Risks

| Risk | Impact |
|---|---|
| Overnight build timeline vs. full pipeline + Neo4j + UI scope | Incomplete P0 delivery |
| Local model quality variance across hackathon hardware | Inconsistent extraction accuracy in the live demo |
| Docling/Crawl4AI edge cases on unfamiliar demo documents | Parsing gaps requiring fallback handling |
| Neo4j setup/connection issues under time pressure | Missing traceability in the live demo |
| Judges perceiving the system as "just another RAG/PIM tool" | Weak differentiation score |

## Mitigation

| Risk | Mitigation |
|---|---|
| Timeline pressure | Strict P0/P1/P2/P3 discipline (Section 65); never trade P0 truth-pipeline components for polish |
| Model quality variance | Task-specific routing (Section 12) keeps simple extraction on smaller, more reliable models; OpenRouter fallback available if local hardware underperforms |
| Parsing edge cases | Explicit error handling paths (Section 49) surface failures instead of silent gaps; demo dataset is pre-validated (Section 59) |
| Neo4j setup risk | `docker-compose.yml` brings up Neo4j with one command; seed script (Section 59) pre-populates before the live demo |
| Differentiation perception | Demo explicitly narrates the CLAIM→EVIDENCE→AUTHORITY→AGREEMENT→NORMALIZATION→DECISION→CONFIDENCE→STATUS chain live (Section 60) |

---

## 65. Future Architecture

- Extract high-load modules (extraction, normalization) into independent services behind the same repository interfaces.
- Replace `BackgroundTasks` with a proper queue (e.g., Celery/RQ) and worker pool.
- Add a real Standards Knowledge Layer with vetted, sourced rule sets per certifying body.
- Add supplier-level quality scoring aggregated across the full catalog in Neo4j.
- Add ERP/PIM/e-commerce connectors behind an explicit, clearly-labeled "Integrations" module (currently out of scope, Section 43 of the PRD).
- Add enterprise authentication/RBAC using the `user_id`/`reviewer_id` fields already present in the schema.
- Evaluate calibration of the confidence model against real adjudicated outcomes before making any statistical-accuracy claims.

## 66. Definition of Done

The architecture is considered fully implemented when:

1. All P0 items in Section 67 are functional against the demo dataset (Section 59).
2. The four named scenario tests in Section 50 pass.
3. A Cypher query can traverse Product→Source for every demo attribute (Section 32).
4. The Ollama→OpenRouter→explicit-failure fallback chain (Section 11) is exercised and verified.
5. No canonical value in the exported JSON lacks linked evidence.
6. `docker-compose up` brings up all required services and the seed script populates the demo product successfully.
7. The end-to-end demo flow (Section 60) runs live within the timing described in the PRD.

---

## 67. One-Night Implementation Reality

| Priority | Scope |
|---|---|
| **P0 — must work tonight** | PDF, URL, Excel ingestion; product extraction; claim extraction; evidence; normalization; conflict detection; canonical decision; trust status; Neo4j; Qdrant; PostgreSQL; human review; dashboard; JSON export |
| **P1 — should work if time allows** | Image understanding; product versioning; change detection; change impact |
| **P2 — partial/demo-ready** | Advanced graph reasoning; standards layer; supplier scoring |
| **P3 — future architecture** | ERP integrations; PIM integrations; distributed catalog processing; autonomous supplier agents |

---

## 68. Final Architectural Principle

*"We don't just extract product data. We create an evidence-backed, graph-connected, versioned representation of product truth."*

*"Every important product attribute can be traced from canonical value → decision → claims → evidence → source."*

This document, together with `01_PRD.md`, is the authoritative technical blueprint for implementation. Any deviation from the technology decisions in Section 7 or the architectural principles in Section 2 requires updating this document first, per the Antigravity Implementation Rules in Section 57.
