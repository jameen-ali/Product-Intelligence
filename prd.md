# Industrial Product Truth Engine
## Product Requirements Document

**Version:** 1.0 (Hackathon Final)
**Event:** UniHack 2026 — "AI-Powered Product Intelligence for Industrial Commerce"
**Status:** Implementation-ready

---

### 1. Executive Summary

Industrial Product Truth Engine (IPTE) is an evidence-first AI system that converts fragmented industrial product information — PDF datasheets, manufacturer websites, technical manuals, supplier spreadsheets, and product images — into a structured, explainable, and commerce-ready product profile.

Rather than asking an LLM to generate or guess a product's specifications, IPTE requires every attribute value to be backed by traceable evidence. It extracts claims from each source, normalizes engineering units, evaluates source authority, detects cross-source contradictions, computes an explainable confidence score, and assigns one of four trust states (VERIFIED, INFERRED, CONFLICT, UNKNOWN) to every attribute. Uncertain attributes are routed to a human reviewer rather than silently resolved by the model.

The system stores all of this — sources, documents, claims, evidence, decisions, versions, and changes — in a Neo4j Product Truth Graph, giving every output full provenance back to its origin. The MVP is scoped to be buildable overnight while preserving the full "truth pipeline" end to end, using a single demonstration product (an industrial hydraulic pump) with five real input types.

Core positioning: **"From Product Data to Product Truth."**

---

### 2. Hackathon Problem Statement

UniHack 2026 problem statement: *"AI-Powered Product Intelligence for Industrial Commerce."*

Manufacturers manage product information across manufacturer websites, product pages, catalogs, PDF datasheets, technical manuals, supplier spreadsheets, CSV/Excel files, product images, and other digital assets. Converting this fragmented information into accurate, structured, validated, enriched, explainable, traceable, and commerce-ready product intelligence is complex and time-consuming.

Expected participant capabilities:

| # | Expected Capability | IPTE Coverage |
|---|---|---|
| 1 | Generate structured product intelligence from limited inputs | Feature 5 — Attribute Extraction |
| 2 | Improve product data quality and consistency | Features 7, 10, 11 |
| 3 | Validate and enrich product information with traceable outputs | Features 6, 9, 13 |
| 4 | Scale efficiently across large product catalogs | Section 33 — Scalability |

Permitted approaches (AI agents, RAG, knowledge graphs, document intelligence, VLMs, human-in-the-loop, multimodal AI) are all present in the IPTE architecture, applied specifically to the problem of **establishing product truth**, not merely extracting text.

---

### 3. Problem Definition

Industrial product specifications frequently disagree across sources even for the same product. Example — a hydraulic pump's rated voltage:

| Source | Claimed Voltage |
|---|---|
| Manufacturer PDF datasheet | 230V |
| Manufacturer website | 220V |
| Supplier Excel | 220V |
| Technical manual | 230V |
| Product image/label | 230V |

A naive extraction pipeline (PDF → OCR → LLM → JSON) picks one value — often the last one seen or the most frequent one — with no explanation, no audit trail, and no way to detect that a real contradiction exists. This is unacceptable for industrial commerce, where an incorrect voltage, pressure rating, or certification can cause equipment damage, safety incidents, or compliance failures.

IPTE treats every extracted value as a **claim**, not a fact, and only promotes a claim to a canonical, commerce-ready value after evidence, authority, and cross-source agreement have been reasoned about explicitly. Where reliable evidence does not exist, the system reports **UNKNOWN** rather than fabricating a value.

---

### 4. Existing Industry Pain Points

- **Manual reconciliation.** Data teams manually cross-check PDFs, spreadsheets, and web pages to resolve spec discrepancies, which does not scale past a few hundred SKUs.
- **Opaque AI extraction.** Many AI extraction tools return a final value without indicating which source it came from or why it was chosen over a conflicting value.
- **No unit-normalization discipline.** Values expressed as 5 HP, 3.73 kW, and 3730 W are treated as three different attributes rather than one normalized fact, fragmenting comparisons and search.
- **Silent staleness.** When a manufacturer updates a datasheet, downstream catalog/PIM/ERP records are not automatically flagged as out of date, and no one tracks what content needs to be revisited.
- **Binary trust.** Existing systems tend to treat data as either "present" or "missing," with no explicit representation of partial confidence, inference, or unresolved conflict.
- **PIM systems store; they do not decide.** Product Information Management platforms are built to store, manage, and distribute product records — they assume the values entering them are already correct.

---

### 5. Target Users

**Primary users**

| Persona Group | Representative Roles |
|---|---|
| Industrial product data managers | Own SKU data accuracy across systems |
| Catalog managers | Prepare products for online/offline catalogs |
| Product information managers | Manage PIM records and attribute schemas |
| Procurement teams | Evaluate supplier-submitted specifications |
| Manufacturing companies | Publish authoritative product specifications |
| Supplier onboarding teams | Validate incoming supplier data at intake |
| Engineering teams | Confirm technical specification accuracy |
| Technical documentation teams | Maintain manuals and datasheets |
| E-commerce / product-content teams | Publish commerce-ready listings |
| Enterprise data-quality teams | Monitor and audit data trust across catalogs |

**Secondary users**: compliance teams, maintenance teams, distributors, system integrators, digital commerce teams.

---

### 6. User Personas

**Persona 1 — Meera, Product Data Manager (Primary)**
Manages ~4,000 industrial SKUs across a legacy PIM. Spends significant time each week resolving spec mismatches flagged by procurement or customers. Needs to know *which* source is right and *why*, not just a merged value.

**Persona 2 — Arjun, Supplier Onboarding Analyst**
Reviews incoming supplier Excel sheets and datasheets for new vendors. Needs a fast way to see whether supplier-submitted specs match manufacturer-authoritative sources before approving a new supplier record.

**Persona 3 — Priya, E-commerce Content Lead**
Needs commerce-ready JSON/CSV attribute sets for product listings and cannot publish specifications she cannot defend to a customer or auditor.

**Persona 4 — Karthik, Compliance/Quality Reviewer**
Only engages when the system raises a CONFLICT or low-confidence VERIFIED attribute. Needs the evidence, not the raw documents, to make a fast decision.

---

### 7. Core User Journey

1. Meera creates a new product workspace for "Hydraulic Pump HP-4000."
2. She uploads a manufacturer PDF, pastes the manufacturer product URL, uploads a supplier Excel file, uploads a product label image, and uploads a technical manual PDF.
3. The system ingests, extracts, and normalizes attributes from all five sources, creating claims with evidence.
4. The Product Truth Workspace shows each attribute with its canonical value, trust status, and confidence.
5. Voltage shows **CONFLICT** (230V vs 220V). Meera opens the Evidence panel, reviews the exact sentences and page numbers behind each claim, and approves 230V.
6. Power shows **VERIFIED** with a normalized value (3.73 kW), sourced from three agreeing representations (5 HP, 3.73 kW, 3730 W).
7. Meera exports the commerce-ready JSON, which includes canonical values, original values, evidence references, confidence, and status for every attribute.
8. Three months later, a revised manufacturer PDF is uploaded. The system detects that Pressure changed from 250 bar to 280 bar, creates a new product version, and lists the catalog page and distributor feed as impacted assets pending review.

---

### 8. Product Vision

To make **product truth** — not raw extraction — the deliverable of AI-powered product intelligence, so that industrial manufacturers and their commerce systems never publish a specification they cannot trace back to evidence.

---

### 9. Product Mission

Build a system that treats every AI-extracted specification as a claim requiring evidence, authority, and cross-source agreement before it can be trusted, and that is explicit — rather than silent — whenever it does not know the answer.

---

### 10. Product Principles

1. **Evidence before assertion.** No attribute value is presented as fact without linked evidence.
2. **Never silently hallucinate.** If evidence is insufficient, the status is UNKNOWN, never a guessed value.
3. **Preserve original values.** Source data is never overwritten, only annotated and normalized alongside the original.
4. **Separate extraction from truth decision.** An extracted claim and a canonical decision are distinct data objects.
5. **Separate inference from verification.** INFERRED and VERIFIED are never conflated in the data model or UI.
6. **Explain important decisions.** Canonical value selection and confidence scores must show their contributing factors.
7. **Flag contradictions, don't erase them.** Conflicting claims are preserved and surfaced, not discarded.
8. **Escalate uncertainty to humans.** Significant conflict or low confidence routes to human review rather than auto-resolving.
9. **UNKNOWN cannot become VERIFIED without new evidence.** Status transitions are evidence-driven only.
10. **Maintain full provenance.** Every canonical value must be traceable to the document, page/row, and source that produced it.

---

### 11. Product Scope

**In scope (MVP and near-term):** multi-source ingestion (PDF, URL, Excel/CSV, image, technical document), attribute/claim extraction, engineering unit normalization, source authority modeling, evidence capture, cross-source conflict detection, canonical value reasoning, explainable confidence scoring, VERIFIED/INFERRED/CONFLICT/UNKNOWN status, human review workflow, Neo4j product truth graph, product versioning, change detection, change impact analysis (logical, not integrated), and JSON/CSV export.

**Out of scope:** see Section 43.

---

### 12. Functional Requirements

Functional requirements are grouped by pipeline stage and numbered FR-001 through FR-024. Each is detailed in Section 13. Summary list:

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Multi-source ingestion | P0 |
| FR-002 | Document intelligence (PDF/manual parsing) | P0 |
| FR-003 | Excel/CSV ingestion | P0 |
| FR-004 | URL/website ingestion | P0 |
| FR-005 | Product image understanding | P1 |
| FR-006 | Product entity resolution | P0 |
| FR-007 | Attribute extraction to claims | P0 |
| FR-008 | Claim-level provenance record | P0 |
| FR-009 | Engineering unit normalization | P0 |
| FR-010 | Source authority ranking (configurable) | P0 |
| FR-011 | Evidence capture and retrieval | P0 |
| FR-012 | Cross-source consistency comparison | P0 |
| FR-013 | Conflict detection | P0 |
| FR-014 | Canonical value reasoning | P0 |
| FR-015 | Explainable confidence scoring | P0 |
| FR-016 | Trust status classification | P0 |
| FR-017 | Human-in-the-loop review queue | P0 |
| FR-018 | Product Truth Graph (Neo4j) | P0 |
| FR-019 | Product versioning | P1 |
| FR-020 | Change detection | P1 |
| FR-021 | Change impact analysis (logical) | P1 |
| FR-022 | Commerce-ready JSON/CSV export | P0 |
| FR-023 | Product Truth Workspace UI | P0 |
| FR-024 | Human review decision logging | P0 |

---

### 13. Detailed Feature Requirements

Each requirement follows: ID, Name, Priority, Description, User, Input, Processing, Output, Acceptance Criteria, Failure Conditions.

---

**FR-001 — Multi-Source Ingestion**
Priority: P0
Description: Allow a user to attach multiple sources (PDF, URL, Excel/CSV, image, technical document) to a single product workspace.
User: Product data manager
Input: Files and/or URLs provided through the Source Manager UI
Processing: File type detection, storage of raw source, association with a `Product` entity, creation of a `Source` and `Document` node
Output: A populated source list attached to a product workspace
Acceptance Criteria:
1. A user can attach at least 5 sources to one product.
2. Each source is stored with type, filename/URL, and upload timestamp.
3. Sources appear in the Source Manager before extraction begins.
Failure Conditions: Unsupported file type is rejected with a clear error rather than silently ignored.

---

**FR-002 — Document Intelligence (PDF / Manual Parsing)**
Priority: P0
Description: Extract paragraphs, tables, headings, and structured values from PDF datasheets and manuals, preserving page references.
User: System (automated), reviewed by data manager
Input: PDF file
Processing: Layout-aware parsing (e.g., Docling) into text blocks and tables with page numbers
Output: A structured document representation with page-tagged text segments
Acceptance Criteria:
1. Extracted text segments retain the source page number.
2. Tables are extracted as structured rows/columns, not flattened text.
3. At least one specification per demo PDF is correctly located.
Failure Conditions: If a PDF is image-only/scanned and cannot be parsed as text, the system flags it for OCR/image-based extraction rather than returning an empty result silently.

---

**FR-003 — Excel/CSV Ingestion**
Priority: P0
Description: Parse supplier spreadsheets into attribute/value pairs, preserving row and column reference.
User: Supplier onboarding analyst
Input: .xlsx or .csv file
Processing: Header detection, row-to-attribute mapping, row index retention
Output: Structured attribute claims tagged with row number
Acceptance Criteria:
1. Each parsed value records its originating row and column header.
2. Ambiguous or unmapped columns are surfaced for manual mapping rather than dropped.
Failure Conditions: Malformed spreadsheet (missing headers) triggers a mapping prompt, not a crash.

---

**FR-004 — URL / Website Ingestion**
Priority: P0
Description: Fetch and parse a manufacturer product page into structured claims.
User: Product data manager
Input: A product URL
Processing: Page fetch and content extraction (e.g., Crawl4AI/Playwright), extraction of specification tables/text
Output: Structured attribute claims tagged with the URL and, where possible, a text anchor/selector
Acceptance Criteria:
1. Specification values present in a rendered product page are extracted as claims.
2. The originating URL is stored with every claim from that source.
Failure Conditions: Pages requiring authentication or blocked by robots.txt fail explicitly with a reported reason.

---

**FR-005 — Product Image Understanding**
Priority: P1
Description: Extract visible text (labels, model numbers, specifications) from product images using a vision-language model.
User: Product data manager
Input: Product image (JPEG/PNG)
Processing: VLM-based text/label recognition
Output: Claims tagged with `evidence_type = image` and the source image reference
Acceptance Criteria:
1. Legible label text (e.g., "230V") is extracted as a claim.
2. Claims from images are visually distinguishable from document-derived claims in the UI.
Failure Conditions: Illegible or low-resolution images return no claim rather than a guessed value.

---

**FR-006 — Product Entity Resolution**
Priority: P0
Description: Determine whether documents/sources refer to the same underlying product, using model number, manufacturer, SKU, and part number.
User: System (automated)
Input: Extracted identifiers from each source
Processing: Deterministic matching on strong identifiers (model number, SKU) supplemented by fuzzy name/manufacturer matching with a confidence threshold
Output: Sources linked to a single `Product` node, or flagged as a potential new product
Acceptance Criteria:
1. Two sources with the same model number are merged into one product.
2. Two sources with conflicting model numbers are NOT auto-merged; the system flags the discrepancy for manual confirmation.
Failure Conditions: The system must never silently merge two different products because their names are superficially similar.

---

**FR-007 — Attribute Extraction to Claims**
Priority: P0
Description: Extract structured attributes (voltage, power, RPM, pressure, flow rate, material, weight, dimensions, operating temperature, warranty, application, certification, standards, compatibility, etc.) as discrete claims, never as directly-trusted facts.
User: System (automated)
Input: Parsed document/page/row/image content
Processing: LLM/rule-based extraction constrained to a defined attribute schema, producing one `Claim` object per attribute per source
Output: Claim objects: attribute, raw value, unit, source, document, location, evidence text, extraction timestamp
Acceptance Criteria:
1. Every extracted value is stored as a `Claim`, never written directly to a "final" attribute field.
2. Each claim includes verbatim evidence text supporting it.
Failure Conditions: An attribute with no supporting text in the source is not created as a claim.

---

**FR-008 — Claim-Level Provenance**
Priority: P0
Description: Maintain full provenance for every claim: attribute, value, unit, source, document, page/section/row, extraction timestamp, evidence text, evidence type, confidence, and status.
User: All users (audit trail)
Input: Claim objects from FR-007
Processing: Persist provenance fields on claim creation; never mutate previous provenance fields, only append new versions
Output: A fully traceable claim record retrievable from the UI
Acceptance Criteria:
1. From any displayed attribute, a user can navigate to the exact source location supporting it.
2. Provenance fields are immutable once written; corrections create a new record.
Failure Conditions: Displaying a canonical value without a working link to at least one supporting claim is a defect.

---

**FR-009 — Engineering Unit Normalization**
Priority: P0
Description: Recognize equivalent engineering representations (e.g., 5 HP ≈ 3.73 kW ≈ 3730 W) and store a canonical normalized representation alongside the original value.
User: System (automated)
Input: Claims with numeric value + unit
Processing: Unit-conversion library applied per attribute type (power, pressure, torque, flow, temperature, length, mass, voltage, current, rotational speed), using a defined, auditable conversion factor table
Output: Each claim retains its original value/unit AND a normalized value/unit; a `normalization_confidence` reflecting rounding/conversion certainty
Acceptance Criteria:
1. 5 HP, 3.73 kW, and 3730 W from three different sources are recognized as consistent claims for the same attribute (Power).
2. The original value is never overwritten by the normalized value.
3. Supported conversions: HP↔kW, W↔kW, bar↔psi, mm↔inch, kg↔lb, °C↔°F, L/min↔other flow units, plus native handling of RPM, Nm, V, A.
Failure Conditions: Conversions outside the supported/safe list are not attempted; the system reports the value un-normalized rather than guessing a formula.

---

**FR-010 — Source Authority Ranking**
Priority: P0
Description: Maintain a configurable ranking of source-type reliability used as one input (not the sole input) to canonical value reasoning.
User: Data-quality administrator (configures), system (applies)
Input: Source type metadata
Processing: Lookup against a configurable authority table (default order: manufacturer datasheet > manufacturer manual > manufacturer website > product label/image > certified technical documentation > authorized distributor > supplier document > third-party source)
Output: An authority weight attached to each claim's source
Acceptance Criteria:
1. Administrators can reorder or edit the authority table without a code change.
2. A lower-ranked source's claim can still be selected as canonical when evidence/agreement strongly supports it — authority is a weighted factor, not an absolute override.
Failure Conditions: The system must not treat authority rank as a hard tie-breaker that ignores contrary strong evidence.

---

**FR-011 — Evidence Engine**
Priority: P0
Description: Collect and expose all supporting evidence snippets for a given claim/attribute, across all sources.
User: Product data manager, compliance reviewer
Input: Claims and their evidence text
Processing: Group evidence by attribute across sources
Output: An Evidence panel listing every snippet, its source, and its location
Acceptance Criteria:
1. For an attribute with 3 supporting sources, all 3 evidence snippets are visible in one panel.
2. Evidence snippets are exact excerpts from the source, not paraphrases.
Failure Conditions: Evidence panel must never fabricate or embellish a snippet beyond what appears in the source.

---

**FR-012 — Cross-Source Consistency Engine**
Priority: P0
Description: Compare claims for the same normalized attribute across sources to determine agreement or disagreement.
User: System (automated)
Input: Normalized claims grouped by attribute
Processing: Group-by-normalized-value comparison considering exactness of evidence, source authority, recency, and independence of sources (not simple majority vote)
Output: An agreement/disagreement map per attribute (e.g., "230V → 3 sources, 220V → 2 sources")
Acceptance Criteria:
1. The system displays claim counts and identities per distinct normalized value.
2. Majority count alone never overrides higher-authority, higher-quality contrary evidence.
Failure Conditions: Never silently drop a minority claim from the comparison record.

---

**FR-013 — Conflict Detection**
Priority: P0
Description: Flag an attribute as CONFLICT when multiple normalized values are each supported by credible, independent evidence.
User: System (automated)
Input: Output of FR-012
Processing: Threshold-based conflict rule (see Section 16) applied to agreement map
Output: A `Conflict` relationship between competing claims
Acceptance Criteria (concrete example):
Given: PDF = 230V, Website = 220V, Excel = 220V
When: the system processes all sources
Then:
1. Voltage is identified as conflicting.
2. All claims are preserved (none discarded).
3. Source evidence for both values is displayed.
4. A canonical candidate is generated with reasoning.
5. A confidence score is calculated.
6. Status is set to CONFLICT or VERIFIED per the rules in Section 16/18.
7. The user can inspect evidence for every claim.
8. No contradictory claim is silently discarded.
Failure Conditions: A true conflict must never be silently resolved without a status of CONFLICT and a review flag.

---

**FR-014 — Canonical Value Reasoning**
Priority: P0
Description: Select a canonical candidate value for each attribute using authority, evidence quality, recency, independent source count, and normalization certainty, and present the reasoning.
User: System (automated); reviewed by data manager
Input: Compared/conflicted claims (FR-012, FR-013)
Processing: Transparent weighted-scoring model (Section 19) producing a ranked candidate list
Output: A `Decision` record: selected value, contributing claims, and a human-readable reasoning string
Acceptance Criteria:
1. Every canonical value is accompanied by a reasoning explanation naming the supporting sources.
2. The decision record references the specific claims used, not just a summary sentence.
Failure Conditions: A canonical value must never appear in the UI without a reasoning trace behind it.

---

**FR-015 — Explainable Confidence Scoring**
Priority: P0
Description: Compute a 0–1 (or 0–100) confidence score per attribute, decomposed into visible contributing factors rather than a single opaque number.
User: All users
Input: Decision record and its supporting factors
Processing: Weighted scoring across: source authority, number of agreeing independent sources, evidence quality/exactness, recency, extraction certainty, cross-source agreement, normalization certainty (see Section 19 for the model)
Output: A composite confidence score plus a factor breakdown
Acceptance Criteria:
1. Hovering/expanding a confidence score shows at least 3 contributing factors and their individual weights/values.
2. Two attributes with the same score but different factor mixes show different breakdowns.
Failure Conditions: Displaying only "Confidence: 97%" without a breakdown is a defect.

---

**FR-016 — Trust Status Classification**
Priority: P0
Description: Classify each attribute as VERIFIED, INFERRED, CONFLICT, or UNKNOWN according to the rules in Section 18.
User: System (automated)
Input: Decision record, confidence score, conflict flags
Processing: Rule-based classification (Section 18)
Output: A `status` field on each attribute
Acceptance Criteria:
1. Every attribute displayed in the workspace has exactly one of the four statuses.
2. UNKNOWN attributes display no numeric value, only the UNKNOWN label and the reason (no evidence found).
Failure Conditions: An attribute must never be marked VERIFIED without at least one qualifying evidence-backed claim (see Section 18 thresholds).

---

**FR-017 — Human-in-the-Loop Review Queue**
Priority: P0
Description: Route CONFLICT attributes and low-confidence INFERRED attributes to a review queue with explicit approve/reject actions.
User: Data manager, compliance reviewer
Input: Attributes flagged for review
Processing: Queue generation, presentation of competing candidate values with evidence
Output: A review action (approve value A / approve value B / request more evidence) recorded against the attribute
Acceptance Criteria:
1. A CONFLICT attribute appears in the review queue before it can be exported as commerce-ready.
2. Reviewer's chosen value and rationale are persisted and linked to their identity and timestamp.
Failure Conditions: A CONFLICT attribute must not be exportable as VERIFIED without a recorded human decision (or an explicit "export with conflict flag" override).

---

**FR-018 — Product Truth Graph (Neo4j)**
Priority: P0
Description: Persist products, versions, attributes, claims, evidence, sources, documents, suppliers, changes, assets, and reviews as a Neo4j graph with the relationships defined in Section 21.
User: System (automated); queried by data manager for traceability
Input: All entities generated by FR-001 through FR-017
Processing: Graph writes on ingestion, extraction, decision, review, and versioning events
Output: A queryable graph exposing full traceability paths from Product to Source
Acceptance Criteria:
1. Given a canonical value, a Cypher traversal from `Product` to `Source` via `HAS_ATTRIBUTE → HAS_CLAIM → SUPPORTED_BY → EXTRACTED_FROM → FROM_SOURCE` returns a complete path.
2. `CONFLICTS_WITH` relationships exist between claims flagged as conflicting.
Failure Conditions: Any canonical value not represented in the graph is a defect for demo purposes.

---

**FR-019 — Product Versioning**
Priority: P1
Description: Retain historical product state when new sources materially change an attribute value.
User: Data manager
Input: A new source that updates a previously VERIFIED attribute
Processing: Creation of a new `ProductVersion` node linked to the prior version via `SUPERSEDES`
Output: A version history viewable per product
Acceptance Criteria:
1. Given Version 1 (Pressure = 250 bar) and a new source stating 280 bar, a Version 2 is created without deleting Version 1's record.
2. Both versions remain independently queryable.
Failure Conditions: Historical truth must never be overwritten in place.

---

**FR-020 — Change Detection**
Priority: P1
Description: Compare a newly ingested source's claims against the current canonical values and flag material differences.
User: System (automated)
Input: New source claims, current product version
Processing: Attribute-by-attribute diff against canonical values (post-normalization)
Output: A `Change` node describing the attribute, old value, new value, and detecting source
Acceptance Criteria (concrete example):
Given: OLD Pressure = 250 bar, NEW source states 280 bar
When: the new source is processed
Then: a "PRODUCT SPECIFICATION CHANGE DETECTED" event is generated, referencing both values and both sources.
Failure Conditions: Non-material differences (e.g., unit-only formatting) must not be flagged as a specification change.

---

**FR-021 — Change Impact Analysis (Logical)**
Priority: P1
Description: List logical downstream assets that could be affected by a detected change (e.g., product page, catalog entry, distributor feed, comparison content, technical description, ERP record, PIM record, generated marketing content), without building real integrations.
User: Data manager, e-commerce content lead
Input: A `Change` node
Processing: Static mapping of attribute type → logical asset categories, represented as `Asset` nodes linked via `AFFECTS`
Output: A list of logically impacted asset categories tied to the change
Acceptance Criteria:
1. A pressure change lists at least 3 plausible impacted asset categories.
2. The UI clearly labels these as logical/representative impacts, not confirmed integrations.
Failure Conditions: The system must not claim to have updated any real external system.

---

**FR-022 — Commerce-Ready JSON/CSV Export**
Priority: P0
Description: Generate a structured export containing identity, category, attributes, canonical values, original values, evidence references, confidence, status, conflicts, version, changes, and review status.
User: E-commerce content lead
Input: Finalized/reviewed product record
Processing: Serialization of the product truth record to JSON and CSV
Output: Downloadable JSON and CSV files
Acceptance Criteria:
1. Exported JSON includes both canonical_values and original_values per attribute.
2. Every attribute in the export includes its status and confidence.
Failure Conditions: Export must not silently omit UNKNOWN or CONFLICT attributes; they are included with their status shown.

---

**FR-023 — Product Truth Workspace UI**
Priority: P0
Description: A single primary screen displaying product identity, data quality summary, attributes, canonical values, original values, confidence, status, evidence, conflicts, source list, review actions, version, and changes.
User: All primary personas
Input: Aggregated product truth record
Processing: UI rendering; see Section 29 for layout requirements
Output: Interactive workspace
Acceptance Criteria:
1. All fields listed above are present and navigable from one screen or a single-level drill-down.
2. Status badges use consistent color coding across the app (Section 18).
Failure Conditions: N/A (UI presence requirement).

---

**FR-024 — Human Review Decision Logging**
Priority: P0
Description: Persist every human review decision (who, when, what was approved, prior conflicting candidates) as part of the audit trail.
User: Compliance reviewer, data manager
Input: Review actions from FR-017
Processing: Append-only decision log linked to the relevant `Review` and `Claim` nodes
Output: A retrievable audit history per attribute
Acceptance Criteria:
1. Every approved CONFLICT resolution shows reviewer identity and timestamp.
2. Review history is never deleted or overwritten.
Failure Conditions: Missing reviewer attribution on a resolved conflict is a defect.

---

### 14. Product Truth Model

Core distinction: **SOURCE ≠ CLAIM ≠ EVIDENCE ≠ CANONICAL VALUE.**

| Concept | Definition | Example |
|---|---|---|
| Source | An input document/page/spreadsheet/image provided by the user | Manufacturer PDF datasheet |
| Document | The parsed representation of a source | Parsed PDF with page-tagged text |
| Claim | A specific attribute/value asserted by one source | Voltage = 230V (from PDF, page 4) |
| Evidence | The verbatim text/visual snippet supporting a claim | "Rated voltage: 230 V" |
| Decision | The system's selection of a canonical value from competing claims | 230V selected as canonical |
| Confidence | A weighted, explainable score attached to a decision | 0.96 |
| Status | One of VERIFIED / INFERRED / CONFLICT / UNKNOWN | VERIFIED |
| Review | A recorded human action on a flagged attribute | Reviewer approved 230V |
| Version | A time-bound snapshot of a product's canonical attribute set | ProductVersion 2 |
| Change | A detected material difference between versions | Pressure 250→280 bar |
| Asset | A logical downstream artifact potentially affected by a change | Distributor feed |

Data flow: **RAW SOURCE → EXTRACTED CLAIM → EVIDENCE → NORMALIZED VALUE → CROSS-SOURCE ANALYSIS → CANONICAL DECISION → VERIFIED PRODUCT TRUTH.** No stage may be skipped, and each stage's output is persisted independently — "extraction is not truth."

---

### 15. Evidence and Provenance Model

Every claim persists the following fields, all immutable once written:

| Field | Description |
|---|---|
| attribute | Normalized attribute name (e.g., `voltage`) |
| raw_value | Value exactly as it appeared in the source |
| raw_unit | Unit exactly as it appeared in the source |
| normalized_value | Converted value in the canonical unit for that attribute type |
| normalized_unit | Canonical unit |
| source_id | Reference to the `Source` node |
| document_id | Reference to the `Document` node |
| location | Page number, row/column, or image label region |
| evidence_text | Verbatim supporting excerpt |
| evidence_type | `text`, `table`, `image_label`, `diagram_text` |
| extraction_timestamp | When the claim was created |
| extraction_confidence | Model/rule certainty that the value was correctly read from the source |

Provenance is exposed in the UI as a drill-down from any canonical value: **Value → Decision → Contributing Claims → Evidence → Source/Document/Location.**

---

### 16. Conflict Resolution Model

**Conflict definition:** An attribute enters CONFLICT when at least two distinct normalized values are each supported by at least one claim from an independent source, and the values are not reconcilable as equivalent representations (post-normalization) or as legitimate version differences.

**Resolution process (not majority vote):**

1. Normalize all competing values to the same unit.
2. Group claims by resulting normalized value.
3. Score each group using: source authority weight, number of *independent* sources (same manufacturer's PDF and manual count with reduced independence versus manufacturer + third-party), evidence exactness (direct numeric statement vs. inferred), recency of source, and product/version match confidence (Section 6, FR-012).
4. The highest-scoring group becomes the canonical candidate; all groups and their scores are retained and shown.
5. If the top two groups' scores are within a configurable closeness threshold, status is forced to CONFLICT and routed to human review regardless of the winning score.
6. If a human reviewer approves a candidate, that becomes canonical and the decision is logged (FR-024); losing claims remain in the graph, linked via `CONFLICTS_WITH`, for audit purposes.

This process is intentionally not a simple vote count, per Feature 10: two sources agreeing does not automatically defeat one high-authority, high-exactness contrary source.

---

### 17. Industrial Normalization Model

| Attribute Type | Supported Units | Canonical Unit | Notes |
|---|---|---|---|
| Power | HP, kW, W | kW | 1 HP = 0.7457 kW |
| Voltage | V | V | No cross-unit conversion; equivalence check only |
| Current | A | A | No cross-unit conversion |
| Pressure | bar, psi | bar | 1 bar = 14.5038 psi |
| Length/Dimension | mm, inch | mm | 1 inch = 25.4 mm |
| Mass | kg, lb | kg | 1 lb = 0.453592 kg |
| Temperature | °C, °F | °C | °C = (°F − 32) × 5/9 |
| Flow rate | L/min and related volumetric units | L/min | Conversions limited to defined, verified factors |
| Rotational speed | RPM | RPM | No cross-unit conversion |
| Torque | Nm | Nm | No cross-unit conversion in MVP |

Rules:
1. The original value and unit are always preserved unchanged alongside the normalized value.
2. Only unit pairs in the supported table above are converted; anything else is left un-normalized and flagged rather than guessed.
3. Conversion factors are stored in a single auditable configuration, not hardcoded inline, so they can be reviewed and corrected.
4. Normalization confidence reflects rounding and source-value precision (e.g., a value given as "≈5 HP" yields lower normalization confidence than "5.0 HP").

---

### 18. Trust Status Model

| Status | Definition | Minimum Condition (MVP rule) |
|---|---|---|
| VERIFIED | Strong direct evidence exists and sources agree (post-normalization) | ≥1 high-authority source claim OR ≥2 independent agreeing sources, with no unresolved conflicting group above the closeness threshold |
| INFERRED | Reasonable inference exists, but direct evidence is insufficient for VERIFIED | Only a single low/medium-authority source, or evidence text is indirect/approximate rather than a direct statement |
| CONFLICT | Reliable sources disagree and the gap is not resolved | Two or more independent, credible normalized-value groups with scores within the closeness threshold, pending or absent human resolution |
| UNKNOWN | No reliable evidence exists for the attribute | Zero claims found for the attribute across all ingested sources |

Rules:
- UNKNOWN is a terminal state until new evidence (a new source) is ingested; it is never converted into a fabricated value.
- CONFLICT can only become VERIFIED through either a human review decision (FR-017) or the ingestion of new corroborating evidence that resolves the closeness threshold.
- Status is recalculated whenever new claims are added for that attribute.

---

### 19. Confidence Model

Confidence is a transparent, weighted score in the MVP (not a black-box model output). Suggested default weights, configurable by an administrator:

| Factor | Description | Default Weight |
|---|---|---|
| Source authority | Weighted average authority rank of supporting claims | 0.25 |
| Independent source agreement | Number of independent sources agreeing on the normalized value | 0.25 |
| Evidence quality/exactness | Whether the evidence is a direct numeric statement vs. an inferred/approximate mention | 0.20 |
| Recency | How recently the supporting source(s) were published/uploaded | 0.10 |
| Extraction certainty | Model/rule confidence that the value was read correctly from the source | 0.10 |
| Normalization certainty | Confidence in the unit conversion applied | 0.10 |

The final score is displayed with its factor breakdown (FR-015), not as a single number. Weights are stored in configuration and may be tuned without a code change. The exact mathematical formula for the MVP is a linear weighted sum of the normalized (0–1) factor scores; more advanced probabilistic models are a future consideration (Section 37).

---

### 20. Human Review Workflow

1. **Trigger:** An attribute is set to CONFLICT, or to INFERRED with confidence below a configurable threshold.
2. **Queue entry:** The attribute appears in the Conflict Review module with all competing values, their evidence, and their computed scores.
3. **Reviewer action:** Approve Value A, Approve Value B, request more evidence (leaves status as CONFLICT/INFERRED and notes the request), or mark as UNKNOWN if evidence is judged unreliable.
4. **Logging:** Reviewer identity, timestamp, chosen value, and rationale (optional free text) are recorded (FR-024) and linked in the graph via `RESOLVED_BY`.
5. **Propagation:** The approved value becomes canonical; losing claims remain stored and linked via `CONFLICTS_WITH` for audit.
6. **Re-trigger:** If a new source later contradicts a human-approved value, the attribute re-enters the review queue; prior human decisions are visible to the new reviewer.

---

### 21. Neo4j Product Truth Graph Requirements

Neo4j is a required, non-optional component of the MVP; it is the system of record for traceability, not a secondary cache.

**Node types:** `Product`, `ProductVersion`, `Attribute`, `Claim`, `Evidence`, `Source`, `Document`, `Supplier`, `Change`, `Asset`, `Review`.

**Relationship types and meaning:**

| Relationship | From → To | Meaning |
|---|---|---|
| HAS_ATTRIBUTE | Product → Attribute | Product declares this attribute |
| HAS_CLAIM | Attribute → Claim | A claim asserts a value for this attribute |
| SUPPORTED_BY | Claim → Evidence | Evidence backs this claim |
| EXTRACTED_FROM | Evidence → Document | Evidence originates from this document |
| FROM_SOURCE | Document → Source | Document belongs to this source |
| SUPPLIED_BY | Source → Supplier | Source was provided by this supplier |
| HAS_VERSION | Product → ProductVersion | Product has this version snapshot |
| SUPERSEDES | ProductVersion → ProductVersion | Newer version supersedes older |
| CONFLICTS_WITH | Claim → Claim | Two claims disagree on the same attribute |
| RESOLVED_BY | Claim → Review | A review resolved this claim's conflict |
| AFFECTS | Change → Asset | A change potentially impacts this logical asset |
| REQUIRES_REVIEW | Attribute → Review | Attribute is pending/has a review record |

Example traversal (conceptual):

```
(Product)-[:HAS_ATTRIBUTE]->(Attribute)-[:HAS_CLAIM]->(Claim)
  -[:SUPPORTED_BY]->(Evidence)-[:EXTRACTED_FROM]->(Document)-[:FROM_SOURCE]->(Source)

(Claim)-[:CONFLICTS_WITH]->(Claim)
(Product)-[:HAS_VERSION]->(ProductVersion)-[:HAS_CHANGE]->(Change)-[:AFFECTS]->(Asset)
```

Acceptance: for any canonical value shown in the UI, a single Cypher query must be able to return the full path from `Product` to `Source`.

---

### 22. Product Versioning

- A `ProductVersion` is created whenever a newly ingested source causes a material (post-normalization) change to a previously canonical value.
- Versions are immutable once created; corrections create a new version rather than editing history.
- `SUPERSEDES` links preserve the chronological chain of versions.
- The UI exposes a version timeline per product so a user can see what changed, when, and why (linked `Change` node).

---

### 23. Change Detection

- Triggered on ingestion of any new source for an already-processed product.
- Compares each newly claimed, normalized value against the current canonical value for that attribute.
- Material change = normalized value differs beyond a configurable tolerance (accounts for rounding/precision, not just unit-format differences).
- Produces a `Change` node: attribute, old value, new value, detecting source, timestamp.
- Non-material differences (e.g., "230V" vs "230.0V") are not flagged as changes.

---

### 24. Change Impact Analysis

- For each detected `Change`, the system maps the affected attribute type to a static, pre-defined list of logical asset categories (e.g., product page, catalog, distributor feed, product comparison, technical description, ERP record, PIM record, generated marketing content).
- These are represented honestly in the UI as **logical/representative impact categories**, not live integrations — the MVP does not connect to any real ERP, PIM, or e-commerce system.
- Each impacted asset entry can be marked "acknowledged" by a reviewer to track resolution, but no automatic external update occurs.

---

### 25. AI Requirements

The AI components must:
1. Treat every extracted value as a claim requiring evidence, never as final truth (Principle 1, 4).
2. Never fabricate a value when no supporting evidence exists; return UNKNOWN instead (Principle 2, 9).
3. Preserve original source values unmodified alongside any normalized/derived value (Principle 3).
4. Separate the extraction step (claim creation) from the decision step (canonical value selection) as distinct pipeline stages and distinct data objects (Principle 4, 5).
5. Produce a human-readable explanation for every canonical decision and confidence score (Principle 6).
6. Explicitly flag contradictions rather than resolving them silently (Principle 7).
7. Escalate attributes to human review per the rules in Section 18/20 (Principle 8).
8. Only assign VERIFIED when the Section 18 minimum condition is met (Principle 9).
9. Log which model/prompt/version produced each claim, to support debugging and provenance (Principle 10).

Recommended technical approach (non-binding — see Section 19 of source brief and Section 30 below): document intelligence via a layout-aware parser (e.g., Docling), structured extraction via an LLM constrained to a Pydantic schema, vision-language extraction for images, and a deterministic rules layer for unit normalization and conflict scoring (kept separate from the LLM to preserve auditability).

---

### 26. Data Requirements

- All raw source files must be retained in original form for the life of the product record.
- All claims, evidence, decisions, and reviews must be retained indefinitely (or per configurable retention policy) for audit purposes.
- Attribute schema (voltage, power, current, RPM, pressure, flow rate, material, weight, dimensions, operating temperature, warranty, application, certification, standards, compatibility, plus identity fields: product name, model number, manufacturer, category) is defined centrally and versionable.
- PostgreSQL/Supabase stores relational/operational data (users, jobs, file metadata, review queue state); Neo4j stores the truth graph; Qdrant stores embeddings for retrieval-augmented extraction and entity matching.

---

### 27. Input Requirements

**MVP-supported inputs:** PDF, product URL, Excel, CSV, product image, technical document (PDF/manual).

**Future extensibility (not built in MVP):** DOCX, additional image formats, supplier portals, ERP exports, PIM exports, direct API ingestion.

Each input type must, at minimum, produce: (a) a stored raw copy, (b) a parsed structured representation, (c) claims with location-level provenance where the format supports it.

---

### 28. Output Requirements

- **JSON export** containing: `product`, `identity`, `category`, `attributes` (each with `canonical_value`, `original_values`, `evidence`, `sources`, `confidence`, `status`), `conflicts`, `version`, `changes`, `review_status`.
- **CSV export** containing a flattened attribute-per-row view suitable for spreadsheet review, including canonical value, unit, confidence, and status columns.
- **Future outputs:** REST API, ERP integration, PIM integration, e-commerce platform integration (explicitly out of MVP scope; see Section 43).

---

### 29. User Interface Requirements

Primary modules:

1. **Product Intelligence Dashboard** — list of products, their overall data-quality summary, and counts of VERIFIED/INFERRED/CONFLICT/UNKNOWN attributes.
2. **Product Workspace** — the product-level container linking to all other modules for a given product.
3. **Source Manager** — add/view sources (PDF, URL, Excel/CSV, image, manual) and their ingestion status.
4. **Evidence/Claims View** — browse every claim and its evidence, filterable by source and attribute.
5. **Conflict Review** — the human-in-the-loop queue (FR-017) for CONFLICT and low-confidence attributes.
6. **Product Truth Graph** — a visual (or query-driven) view into the Neo4j relationships for a given product.
7. **Change Intelligence** — version history, detected changes, and logical impact analysis.
8. **Export** — JSON/CSV download.

**Product Truth Workspace (most important screen)** must display, on one screen or a single-level drill-down: product identity, data quality summary, attribute list, canonical value, original values, confidence (with breakdown), status badge, evidence access, conflict indicators, source list, review actions, version indicator, and recent changes.

Status color convention (must be applied consistently): VERIFIED = green, INFERRED = amber/yellow, CONFLICT = red, UNKNOWN = grey.

---

### 30. API-Level Requirements

The backend (FastAPI) must expose, at minimum:

| Endpoint (conceptual) | Purpose |
|---|---|
| `POST /products` | Create a product workspace |
| `POST /products/{id}/sources` | Attach a source (file upload or URL) |
| `POST /products/{id}/process` | Trigger the extraction/truth pipeline |
| `GET /products/{id}` | Retrieve the full Product Truth record |
| `GET /products/{id}/attributes/{attr}/evidence` | Retrieve all evidence for an attribute |
| `POST /products/{id}/attributes/{attr}/review` | Submit a human review decision |
| `GET /products/{id}/versions` | List product versions |
| `GET /products/{id}/changes` | List detected changes and impacted assets |
| `GET /products/{id}/export` | Export JSON/CSV |

All processing-heavy endpoints (`process`) should be asynchronous, returning a job ID that can be polled or subscribed to, to support future scaling (Section 33).

---

### 31. Security Requirements

- No secrets (API keys, DB credentials) hardcoded; all provided via environment configuration.
- External AI/API calls must be optional and swappable for local equivalents (local LLM via Ollama, local vector DB, local Neo4j, local PostgreSQL).
- Uploaded documents are stored with access control scoped to the owning organization/user in a multi-tenant future state; the MVP may use a single-tenant model but must not hardcode this assumption into the data model.
- All review actions are attributable to an authenticated identity (even if simplified for the hackathon demo).

---

### 32. Privacy Requirements

- Industrial documents may contain confidential specifications; the architecture must support fully local execution (local LLM, local document processing, local vector database, local Neo4j, local PostgreSQL) as a deployment option.
- No source document content should be sent to a third-party API unless explicitly configured by the deploying organization.
- Exported outputs contain only the data the requesting user is authorized to see (relevant primarily to the future multi-tenant state; noted here as a design constraint).

---

### 33. Scalability Requirements

The architecture must conceptually support growth from 1 product to 10, 1,000, and 100,000+ products without redesign:

- Ingestion and extraction are asynchronous/background jobs, not synchronous request-response calls, from the MVP onward.
- Attribute schema and normalization tables are data-driven (configuration), not hardcoded per product.
- The Neo4j graph model uses generic `Product`/`Attribute`/`Claim` structures rather than per-product-type schemas, so new product categories do not require a data-model change.
- Batch processing (bulk source upload, bulk re-processing) is an explicit future extension point, not precluded by MVP design choices.
- Vector search (Qdrant) is used for entity resolution and retrieval at a scale where naive in-memory comparison would not work.

---

### 34. Performance Requirements

- Single-product processing (5 sources: PDF, URL, Excel, image, manual) should complete within a demo-appropriate time window (target: under a few minutes end-to-end for the hackathon demo dataset).
- UI interactions (viewing evidence, switching tabs) should feel immediate (sub-second) since they operate on already-processed, persisted data rather than triggering new extraction.
- Exact production-scale performance targets (e.g., time per 1,000 products) are not committed in the MVP and are deferred to the architecture document with proper load testing.

---

### 35. Error Handling

| Scenario | Required Behavior |
|---|---|
| Unsupported file type uploaded | Reject with a clear, specific error; do not silently ignore |
| Scanned/image-only PDF | Route to image/VLM-based extraction path or flag as needing OCR; do not return an empty result silently |
| URL fetch blocked/authenticated | Report the failure reason explicitly to the user |
| Attribute with no evidence found | Status = UNKNOWN; never fabricate a value |
| Conflicting product identifiers across sources | Flag for manual entity-resolution confirmation; do not auto-merge |
| Unsupported unit conversion requested | Leave value un-normalized and flagged; do not attempt an unverified formula |
| Processing job failure | Job status marked failed with a retrievable error message; partial results are not presented as complete |

---

### 36. MVP Requirements

**P0 (must work for the demo):**
PDF ingestion; URL ingestion; Excel/CSV ingestion; product entity extraction; attribute extraction to claims; evidence extraction; unit normalization; cross-source comparison; conflict detection; canonical value selection; explainable confidence; VERIFIED/INFERRED/CONFLICT/UNKNOWN classification; human review; Neo4j graph; Product Truth Workspace dashboard; JSON export.

**P1:** Image understanding; product versioning; change detection; change impact analysis.

**P2:** Supplier quality scoring; advanced graph analytics; additional autonomous agent behaviors.

**P3 (explicitly future, not MVP):** ERP integration; full PIM integration; enterprise authentication; large-scale distributed processing; autonomous supplier agents; production-grade workflow orchestration.

The MVP must not trade away any P0 truth-pipeline functionality (evidence, conflict detection, canonical reasoning, status, Neo4j) for cosmetic UI polish.

---

### 37. Future Roadmap

- DOCX and additional image format ingestion.
- Direct ERP/PIM export connectors and supplier portal ingestion.
- API-first ingestion for programmatic bulk onboarding.
- Batch/bulk processing UI for catalog-scale operations.
- Probabilistic (rather than purely linear-weighted) confidence modeling.
- Supplier-level quality scoring aggregated across many products.
- Expanded graph analytics (e.g., identifying systematically unreliable sources across the catalog).
- Additional autonomous agent workflows for proactive re-verification of aging VERIFIED attributes.
- Multi-tenant enterprise authentication and role-based access control.

---

### 38. Success Metrics

| Metric | What It Measures | Evaluation Method |
|---|---|---|
| Attribute extraction accuracy | % of ground-truth attributes correctly extracted as claims | Manual comparison against a labeled demo dataset |
| Entity resolution accuracy | % of sources correctly linked to the right product (no false merges/splits) | Manual review of entity-resolution decisions on test sources |
| Unit normalization accuracy | % of unit conversions matching correct reference values | Comparison against known conversion factors |
| Conflict detection accuracy | % of true conflicts correctly flagged, and false-conflict rate | Manual review against a curated conflict test set (e.g., voltage scenario) |
| Canonical value accuracy | % of canonical decisions matching expert-adjudicated correct value | Manual expert review of a sample of decisions |
| Evidence attribution accuracy | % of evidence snippets that are verbatim and correctly sourced | Spot-check evidence text against original documents |
| Hallucination rate | % of displayed values with no corresponding evidence in the graph | Automated audit: every canonical value must trace to ≥1 claim/evidence node |
| Human review rate | % of attributes requiring human review | Count of CONFLICT/low-confidence attributes ÷ total attributes |
| Processing time | Time to fully process one product's sources | Instrumented timing on the demo dataset |
| Data completeness | % of schema attributes with a non-UNKNOWN status | Computed per product |
| Data consistency | % of attributes without unresolved CONFLICT after review | Computed per product |
| Change detection accuracy | % of injected test changes correctly detected | Manual test with old/new version pairs (e.g., pressure scenario) |

No specific numeric targets are asserted in this document; targets should be set after initial testing against the demo dataset and documented separately.

---

### 39. Competitive Differentiation

| Category | What It Does | Example | What It Does Not Do |
|---|---|---|---|
| Existing PIM (e.g., Akeneo, Inriver, Salsify, Pimcore) | Store, manage, and distribute product information | Central repository for approved product records | Does not itself decide which conflicting input value is correct, or maintain claim-level evidence for why a value is trusted |
| AI extraction tools (e.g., Parsio, Koncile) | Extract structured data from documents | Pull specifications out of a PDF | Typically stop at extraction; do not model cross-source conflict, authority, or trust status |
| Generic RAG / retrieval tools | Retrieve relevant information from a corpus | Answer a question by finding a relevant passage | Do not produce a persisted, versioned, evidence-linked canonical product record |
| Catalog enrichment tools (e.g., NVIDIA Retail Catalog Enrichment, Channel3, Deep Lake–based pipelines) | Enrich/generate product content and descriptions | Generate marketing copy or fill missing fields | Not built around an explicit evidence hierarchy, conflict resolution, or a VERIFIED/INFERRED/CONFLICT/UNKNOWN trust model for industrial specifications |

This is not a claim that these categories lack AI, RAG, agents, citations, confidence scoring, validation, or graph technology in general — several do use some of these techniques. IPTE's differentiation is the specific **combination**, applied to industrial specification truth:

1. Industrial engineering specification reasoning
2. Engineering-unit normalization
3. Evidence hierarchy
4. Claim-level provenance
5. Cross-source contradiction reasoning
6. Canonical specification decision-making
7. VERIFIED / INFERRED / CONFLICT / UNKNOWN states
8. Product temporal truth (versioning)
9. Specification change detection
10. Change-impact intelligence
11. Uncertainty-aware human review
12. Industrial standards awareness

Positioning: **"An industrial evidence-first product truth and decision layer"** — not a generic PIM, not a generic RAG chatbot, not a generic AI catalog generator.

---

### 40. Hackathon Demo Scenario

**Duration:** 3–5 minutes
**Demo product:** Industrial Hydraulic Pump
**Inputs:** PDF datasheet, manufacturer website, product image, supplier Excel, technical manual

**Script:**

1. Upload all five sources into a new product workspace.
2. Trigger extraction; show the product identity resolved from multiple sources.
3. Display the attribute list in the Product Truth Workspace.
4. Show normalized engineering values (5 HP / 3.73 kW / 3730 W recognized as one Power attribute).
5. Show Voltage flagged as CONFLICT (PDF=230V, Website=220V, Image=230V, Excel=220V, Manual=230V).
6. Open the Evidence panel for Voltage; show exact snippets and page/row references per source.
7. Show the canonical candidate (230V) with its reasoning (authority + independent agreement + evidence exactness).
8. Show the confidence score breakdown.
9. Show the current status (CONFLICT, pending review).
10. Reviewer approves 230V in the Conflict Review screen; status updates to VERIFIED; decision is logged.
11. Open the Product Truth Graph view; show the traversal from Product → Attribute → Claim → Evidence → Source.
12. Upload a revised manufacturer PDF with Pressure changed from 250 bar to 280 bar.
13. Show the change-detection alert ("PRODUCT SPECIFICATION CHANGE DETECTED") and the new Product Version created.
14. Show the logical impacted-asset list (catalog, distributor feed, product page, etc.), clearly labeled as representative, not live integrations.
15. Export the final product JSON and show its structure (canonical values, original values, evidence, confidence, status, conflicts, version, changes, review status).

---

### 41. Business Impact

By making trust and evidence first-class outputs rather than an afterthought, IPTE is positioned to reduce:

- Manual product data entry and re-keying across systems
- Supplier onboarding review effort, by surfacing spec mismatches automatically
- Catalog preparation time, by producing commerce-ready exports directly
- Effort required to respond to a product update (via change detection instead of manual re-checking)
- Data inconsistency across a catalog, by exposing conflicts explicitly instead of hiding them behind a single merged value
- Time spent tracing "why does this value say X" during audits or customer disputes

And to improve:

- Product data quality and internal trust in published specifications
- Traceability and auditability of every published attribute
- Speed and confidence of supplier onboarding decisions
- Commerce readiness of new products entering a catalog
- Visibility into a product's specification lifecycle over time

No specific percentage or dollar figures are asserted; these should be validated against pilot deployments rather than claimed here.

---

### 42. Risks and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Overnight build timeline is tight for a full pipeline + Neo4j graph + UI | Incomplete P0 scope | Strict adherence to Section 36 MVP prioritization; P1+ features deferred without hesitation |
| LLM extraction misreads a value (e.g., OCR/parsing error) | Incorrect claim entering the pipeline | Claims always carry extraction_confidence and verbatim evidence, enabling human detection of extraction errors even if not automatically caught |
| Source parsing failure (scanned PDF, blocked URL) | Missing data for a demo source | Explicit error handling and fallback paths per Section 35, rather than silent failure |
| Over-reliance on source authority ranking suppresses a correct lower-authority claim | Wrong canonical value | Authority is one weighted factor among several (Section 19), not an absolute rule; closeness threshold forces human review in ambiguous cases |
| Unit normalization applied incorrectly | Wrong normalized value shown as equivalent to original | Conversion factors are limited to a defined, auditable table (Section 17); unsupported conversions are not attempted |
| Neo4j integration complexity under time pressure | Missing traceability in the demo | Prioritize a minimal but complete graph schema (Section 21) covering the demo path end-to-end before adding graph analytics |
| Judges perceive the product as "just another PIM/RAG tool" | Weak differentiation score | Demo explicitly walks the CLAIM → EVIDENCE → AUTHORITY → AGREEMENT → NORMALIZATION → DECISION → CONFIDENCE → STATUS chain (Section 12) live |

---

### 43. Out-of-Scope

Explicitly excluded from this product and from the MVP:

- Building a complete ERP system
- Building a complete PIM system
- Replacing enterprise e-commerce platforms
- Full autonomous procurement workflows
- Full ERP integrations (MVP represents impact only logically, per Section 24)
- Real production supplier portals
- Fake/simulated integrations presented as real
- Unsupported AI-generated specifications (i.e., values without evidence)
- Large-scale distributed infrastructure within the MVP build

---

### 44. Definition of Done

The hackathon MVP is considered done when all of the following hold:

1. All P0 functional requirements (FR-001–FR-004, FR-006–FR-018, FR-022–FR-024) are implemented and demonstrable on the hydraulic pump dataset.
2. The five demo source types (PDF, URL, Excel, image, manual) can all be ingested for one product in a single workspace.
3. The voltage conflict scenario (Section 40, step 5–10) runs end-to-end, including human review and status update to VERIFIED.
4. The power normalization scenario (5 HP / 3.73 kW / 3730 W) is shown as one unified, normalized attribute.
5. The pressure change scenario (250 bar → 280 bar) triggers change detection, a new product version, and a logical impact list.
6. The Neo4j graph contains a traversable path from Product to Source for at least the demo product's attributes.
7. JSON export produces a schema-complete file containing canonical values, original values, evidence, confidence, status, conflicts, version, and changes.
8. No attribute in the demo is displayed with a fabricated value lacking linked evidence.
9. The Product Truth Workspace displays all fields specified in Section 29 for the demo product.
10. The demo can be run live within the 3–5 minute window described in Section 40.
