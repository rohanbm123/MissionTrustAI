# CaseBrief

**Evidence-Backed AI Case Briefs for Human Adjudicators**
*From completed investigation to decision-ready evidence.*

CaseBrief is an evidence-backed AI case-briefing prototype that converts completed synthetic
investigation packages into decision-ready recommendations for human adjudicators.

**The system reduces document-review burden without replacing human adjudicative authority.**

It uses entirely synthetic data about fictional applicants. It produces no adjudicative
determination, and it does not grant or deny clearance, eligibility, employment or legal status of
any kind.

---

## Table of contents

- [The problem](#the-problem)
- [The product](#the-product)
- [The workflow](#the-workflow)
- [Recommendation states](#recommendation-states)
- [Architecture](#architecture)
- [The recommendation engine](#the-recommendation-engine)
- [Recommendation → reason → evidence](#recommendation--reason--evidence)
- [Evidence navigation](#evidence-navigation)
- [Human-in-the-loop design](#human-in-the-loop-design)
- [RAG pipeline](#rag-pipeline)
- [AI assurance methodology](#ai-assurance-methodology)
- [Contradiction detection](#contradiction-detection)
- [Evaluation framework](#evaluation-framework)
- [Audit trail](#audit-trail)
- [Database architecture](#database-architecture)
- [Synthetic dataset](#synthetic-dataset)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [Running locally](#running-locally)
- [Docker](#docker)
- [Demo script](#demo-script)
- [Testing](#testing)
- [Engineering decisions](#engineering-decisions)
- [Known limitations](#known-limitations)
- [Ethical considerations](#ethical-considerations)
- [Security and privacy design](#security-and-privacy-design)
- [Future improvements](#future-improvements)
- [Screenshots](#screenshots)
- [Disclaimer](#disclaimer)

---

## The problem

An adjudicator receives a completed investigation package: a dozen documents produced by different
sources at different times, in different formats, saying overlapping and occasionally conflicting
things. Before deciding anything, they must read all of it — because the one paragraph that
matters could be in any of them.

An LLM can summarise that package in seconds. The summary is fluent, plausible and impossible to
act on, because the adjudicator cannot tell which sentence came from which document, which came
from no document at all, where two sources disagree, or what the package is missing. An
unverifiable summary does not save work; it moves the work from reading the file to auditing the
model.

The question an adjudicator actually needs answered is not "what does this file say?" It is:

> **Based on the completed investigation package, what is the recommended next step, why, and what
> evidence supports that recommendation?**

## The product

CaseBrief answers exactly that question on one screen. Opening a case shows:

| | |
| --- | --- |
| **Overall recommendation** | One of three decision-support states, shown first |
| **Overall concern level** | NONE / LOW / MODERATE / HIGH |
| **Recommendation confidence** | Confidence in the *recommendation*, not in any single sentence |
| **Material unresolved issues** | The count that decides whether this is quick or slow |
| **Executive case assessment** | 120–200 words; the case understood in 30–60 seconds |
| **Why this recommendation** | 3–7 evidence-backed reasons, each expandable to its source passage |
| **Mitigating factors** | Each linked to the evidence that establishes it |
| **Remaining concerns** | Adverse items, with mitigation and what the human should confirm |
| **What could change this recommendation** | The real evidence dependencies |
| **Category assessments** | Financial, employment, travel, identity, monitoring, legal, documentation |
| **Every citation** | Clickable through to its exact location in the full case record |
| **Adjudicator decision** | Proceed · Request More Information · Escalate · View Full Investigation |
| **AI assurance metrics** | Supporting information, deliberately last |

The value chain the whole product is built around:

**Recommendation → Reason → Evidence → Original source → Human decision.**

## The workflow

```
Completed investigation package
  → AI evidence synthesis
  → Overall recommendation
  → Evidence-backed reasoning
  → Unresolved concerns
  → Human adjudicator decision
```

## Recommendation states

Only three states exist, and they are decision *support*, not decisions:

| State | Shown as | Meaning |
| --- | --- | --- |
| `PROCEED_TO_STANDARD_REVIEW` | 🟢 Proceed to Standard Review | Every identified concern has verifiable mitigating evidence and no material conflict remains |
| `REQUEST_ADDITIONAL_INFORMATION` | 🟡 Request Additional Information | The package lacks evidence needed to close a concern, or an asserted mitigation cannot be verified |
| `ESCALATE_FOR_ENHANCED_REVIEW` | 🔴 Escalate for Enhanced Review | Two independent records disagree on a material fact, or an adverse finding has no mitigation |

`APPROVE`, `DENY`, `GRANT` and `REJECT` do not exist in the schema, the prompt or the UI. A test
asserts the enumeration contains nothing resembling them, and `requires_human_decision` is forced
`true` by a Pydantic validator that the model cannot override.

## Architecture

```mermaid
flowchart TD
    A[Completed Synthetic Investigation Package] --> B[Document Ingestion]
    B --> C[Chunking]
    C --> D[Embeddings]
    D --> E[(PostgreSQL + pgvector<br/>or SQLite + NumPy)]
    E --> F[Retriever<br/>multi-facet fan-out]
    F --> G[LLM Provider<br/>Anthropic / OpenAI / Demo]
    G --> H[Structured Draft Brief<br/>FINAL_CASE_ASSESSMENT_V1]
    H --> I[Claim Extraction]
    I --> J[Evidence Validation<br/>semantic + retrieval + entailment]
    J --> K[Contradiction Detection]
    K --> L[Category Assessment<br/>7 evidence categories]
    L --> M[Recommendation Engine<br/>deterministic evidence rules]
    M --> N[Decision-Ready Brief<br/>recommendation · reasons · concerns · sensitivities]
    N --> O[Human Adjudicator<br/>proceed / request / escalate]
    O --> P[Audit Trail<br/>append-only]
    N --> Q[AI Assurance + Eval Metrics]
```

Layering is strict: Streamlit pages call **services**, services call **repositories**, repositories
own the database. No page builds SQL, calls an LLM, or scores a claim.

## The recommendation engine

The model drafts the narrative. `src/assurance/recommendation_engine.py` decides the recommendation
*state*, deterministically, from what the assurance pipeline actually established.

**Why a deterministic policy layer over a probabilistic one:**

- **Evidence sensitivity.** The recommendation must move when material evidence moves. Rules fed by
  validated claims, contradiction flags and missing-evidence findings do that reliably.
- **Auditability.** Every state carries named triggers and the source IDs behind them, so an
  adjudicator can see exactly why the system escalated.
- **Conservatism.** Where the model and the engine disagree, the more escalated of the two ships,
  and the divergence is surfaced in the UI and written to the audit trail.

### Category assessment

Each claim, finding, contradiction and missing-evidence item is routed to one of seven categories —
financial, employment, foreign travel, identity/background, monitoring, legal/conduct, documentation
completeness — by longest-keyword match, with documentation as a fallback only, so a substantive
finding phrased in absence vocabulary ("nine months of residence history is unverified") is not
filed as paperwork.

Per category the engine derives concern level, whether verifiable mitigating evidence exists,
evidence completeness, unresolved items, contradiction count and unsupported-statement count.

### Rules

Rules are evaluated independently; each firing rule proposes a state and **the most escalated
proposal wins**. There is no averaging — one material trigger is enough.

| Rule | Fires when | Proposes |
| --- | --- | --- |
| `material_contradiction` | Two **different** records disagree (confidence ≥ 0.70) in a category with a concern | 🔴 Escalate |
| `unmitigated_high_concern` | A high-concern category has adverse findings and no verifiable mitigation | 🔴 Escalate |
| `multiple_unmitigated_concerns` | Two or more categories carry unmitigated adverse findings | 🔴 Escalate |
| `contradicted_claim` | A statement is contradicted by the very evidence retrieved to support it | 🔴 Escalate |
| `high_concern_pending_evidence` | A high concern is built entirely from gaps, not adverse findings | 🟡 Request |
| `unverifiable_mitigation` | Mitigation is asserted but its document is not in the package | 🟡 Request |
| `unresolved_moderate_concern` | A moderate concern has no mitigating evidence at all | 🟡 Request |
| `disclosed_discrepancy` | One record documents a reported-vs-confirmed discrepancy | 🟡 Request |
| `material_missing_information` | Evidence needed to close an unmitigated concern is absent | 🟡 Request |
| `unsupported_material_statements` | >34% of a material category's statements are untraceable | 🟡 Request |
| `possible_conflict` | A sub-threshold conflict sits in an unmitigated category | 🟡 Request |
| `evidence_gap_in_assessed_category` | The category the case turns on lost its evidential basis | 🟡 Request |
| *(none fired)* | Every concern is mitigated and verified | 🟢 Proceed |

Two distinctions do most of the work, and both are deliberate:

- **Escalate on what the file says; request on what the file lacks.** A high concern built from
  adverse findings escalates. A high concern built from missing documents asks for the documents.
- **Two records disagreeing ≠ one record noting a discrepancy.** A conflict whose two sides come
  from the same passage ("title as reported by subject" vs "title confirmed by employer") is the
  investigation documenting a known discrepancy, not two sources secretly disagreeing. It requests;
  it does not escalate.

### Confidence

Recommendation confidence starts at 0.95 and is reduced by unsupported claims (0.30 × rate), weak
claims (0.10 × rate), each contradiction flag (0.04), each material missing-evidence item (0.03),
and model/engine divergence (0.05), then clamped to [0.10, 0.99].

### What could change this recommendation

Generated from real dependencies, not boilerplate: every load-bearing verifiable mitigation in a
material category ("if this could not be verified: …"), every unresolved conflict, every material
gap, plus whatever the model drafted.

## Recommendation → reason → evidence

Every reason in *Why this recommendation* expands to the passages behind it. Each shows:

```
Payment Plan Document · DOC-4-CHUNK-0 · March 14, 2026 · payment plan · relevance 0.91 · cited by model
    STRUCTURED REPAYMENT AGREEMENT Plan effective date: March 14, 2026

Case Notes · DOC-8-CHUNK-0 · May 6, 2026 · case notes · relevance 0.83
    The servicer confirmed a plan effective date of March 14, 2026 and two payments received on schedule.

Verification status: Supported · assurance score 0.91.
Scores come from the claim-level validation pipeline, not from the model's own self-report.
```

A drafted reason whose evidence no longer holds is **dropped from the brief** rather than shown with
a stale justification — which is what keeps the brief coherent when documents change underneath a
cached narrative.

Every citation is also **clickable**: `Open source →` next to the preview takes the adjudicator to
that exact passage in the full case record.

## Evidence navigation

The preview answers "what does the evidence say". The link answers "what surrounds it".

```
AI Recommendation → Reason → Evidence citation → Open source
    → Case Details, correct case
    → correct section (Documents or Case History)
    → correct document or event, auto-selected
    → exact passage highlighted, scrolled into view
    → surrounding context readable
    → ← Back to AI Case Brief, returning to the reason you left
```

### One source of truth

The passages rendered in Case Details **are** the `document_chunks` rows the retriever searches.
The document viewer breaks each document into the same addressable sections the RAG pipeline
indexes, under the same identifiers the AI cites — `DOC-4-CHUNK-0` in the brief is
`DOC-4-CHUNK-0` on the page. Nothing is duplicated for the AI view, and a test asserts the
content the adjudicator reads is byte-identical to the content the retriever holds.

### Evidence is not only documents

Monitoring alerts, applicant statements, status changes and investigative entries are citable
evidence, so `case_history_events` are indexed in the same table as document passages under stable
`EVT-YYYY-MM-DD-NNN` identifiers, used identically by the retrieval index, the AI citations, the
navigation layer and the audit trail. A citation of `EVT-2026-05-02-001` lands on the Case History
section with that event highlighted.

### Resolution is structural, never string parsing

`EvidenceLink` carries its own destination:

```json
{ "source_id": "DOC-4-CHUNK-0", "source_type": "document", "case_id": "PS-2026-00182",
  "document_id": "DOC-4", "chunk_id": "…", "document_name": "Payment Plan Document",
  "document_date": "2026-03-14", "evidence_text": "…", "relevance_score": 0.91 }

{ "source_id": "EVT-2026-05-06-001", "source_type": "case_history", "case_id": "PS-2026-00182",
  "event_id": "EVT-2026-05-06-001", "event_date": "2026-05-06",
  "event_type": "monitoring_alert", "evidence_text": "…" }
```

`resolve_source(case_id, source_id)` is a database lookup on `(case_id, source_id)` that follows
the row to its document or event. The identifier is an opaque handle; the stored `source_type`
decides the destination. Resolution is case-scoped, so a source ID from another case does not
resolve. A citation that cannot be resolved shows **"Source could not be located in the case
record."** and the adjudicator keeps browsing — it never crashes the page.

### Deep links

Navigation state travels as session state and as query parameters, so any location is linkable:

```
/Case_Details?case=PS-2026-00182&document=DOC-4&source=DOC-4-CHUNK-0&reason=reason-1
/Case_Details?case=PS-2026-00182&event=EVT-2026-05-02-001&source=EVT-2026-05-02-001&reason=reason-6
```

`reason_id` is stable within an analysis (`reason-1` … `reason-7`), which is what lets the return
trip land on the reason the adjudicator left rather than the top of the brief.

### Landing on the passage

The referenced passage is highlighted inline **and** lifted into a *Referenced by AI
recommendation — reason-1* callout at the top of the section, with the anchor scrolled into view
by a small component script. The callout is the guarantee: if a browser blocks the scroll, the
adjudicator still sees the exact passage immediately. Only the referenced passage is highlighted,
never the whole document; passages cited elsewhere in the brief get a quieter marker.

### Traceability runs both ways

Standing on a passage in the record, *Used in AI recommendation* names the reasons, mitigating
factors and remaining concerns that rest on it, with **Return to reason in the AI brief**. Opening
a citation writes an `evidence_source_opened` audit event carrying the case, reason, source,
document or event identifier and whether it resolved.

## Human-in-the-loop design

The adjudicator is the decision-maker. Four controls sit at the bottom of the brief: **Proceed**,
**Request More Information**, **Escalate**, and **View Full Investigation**.

Recording a decision writes an `adjudicator_actions` row that **copies** the AI recommendation, its
confidence and the evidence source IDs onto the row, so the record of what the human was shown
survives any later re-analysis. Whether the human agreed is *derived* from the action, never
self-reported. The AI recommendation is never overwritten.

The narrative-level workflow from the previous version is retained under *View Full Investigation*:
accept, accept-with-edits (stored with a unified diff), reject, or require additional evidence,
with the original AI draft preserved verbatim.

## RAG pipeline

1. **Load** — `data/synthetic_cases/<slug>/` validated against `CaseMetadata`.
2. **Clean** — whitespace normalised, banner and rule lines stripped so document furniture never
   becomes retrievable "evidence".
3. **Chunk** — paragraph-aware packing to ~700 characters with 120 characters of overlap.
4. **Embed** — unit-norm vectors; chunks addressed as `DOC-{n}-CHUNK-{i}`, the same identifier that
   appears in citations, evidence panels and the audit trail.
5. **Store** — `pgvector` on PostgreSQL, JSON text on SQLite.
6. **Retrieve** — multi-facet fan-out across ten standing adjudication facets, merged by best score.
7. **Generate** — `FINAL_CASE_ASSESSMENT_V1` over the retrieved passages only.
8. **Validate** — parsed into `CaseAnalysisOutput`; citations pointing at no passage in the package
   are stripped before scoring.

The system prompt (`MT_SYSTEM_V2`) instructs the model that it supports a human adjudicator, must
use only supplied evidence, must not speculate, **must not hide adverse information**, must
distinguish verified facts from concerns from mitigating evidence from unresolved issues from
missing information from contradictions, must reference source IDs for every material reason, must
use `REQUEST_ADDITIONAL_INFORMATION` when critical information is missing and
`ESCALATE_FOR_ENHANCED_REVIEW` when material unresolved contradictions exist, must always state what
could change the recommendation, and that the final decision belongs to the adjudicator.

## AI assurance methodology

> **Prototype AI assurance metrics.** Demonstration measures for a prototype. Not regulatory,
> safety or compliance metrics, and not validated against human-labelled ground truth.

Each claim is scored against its own targeted evidence pool. Within each candidate passage the
validator scores **sentence spans** rather than whole chunks, so the reviewer gets the line that
settles the claim rather than a wall of text.

| Signal | Weight | Measures |
| --- | --- | --- |
| `semantic` | 0.40 | Calibrated cosine between the claim and the best passage span |
| `retrieval` | 0.20 | Rank within the claim's evidence pool, plus a bonus if the model cited it |
| `entailment` | 0.40 | Whether the passage asserts the claim. Offline: lexical containment weighted 55/45 between content-word overlap and **exact numeric and date agreement**. Live: an LLM entailment verdict mapped to 1.0 / 0.6 / 0.1 / 0.0 |

```
total ≥ 0.75 → SUPPORTED     total ≥ 0.55 → WEAK_SUPPORT     total < 0.55 → UNSUPPORTED
```

`CONTRADICTED` overrides when the claim asserts a value its own best evidence contradicts.

**Why not LLM-as-judge?** An LLM grading its own output shares the failure mode that produced the
error. Two of three signals are computed independently of any model.

Narrative metrics — groundedness `(supported + 0.5 × weak) / total`, evidence coverage, unsupported
claim rate, contradiction rate, source diversity — are retained and shown on the assurance
dashboard, below the recommendation metrics.

## Contradiction detection

Typed field/value pairs (dates, amounts, percentages, counts, labelled record lines) are extracted
from every passage, normalised (`September 2023` → `2023-09`), and compared. Three guards keep it
honest:

- **Entity scoping.** Two values only conflict when they describe the same thing. An employment end
  date for Fairmont Logistics and one for a Vantage assignment are two facts, not a contradiction.
- **Reconciliation language.** A sentence that explicitly reconciles two records ("the third-party
  record and the subject's account can both be true") is not evidence of a conflict between them.
- **Range awareness.** A stated range ("June 2019 to November 2021") is never read as two competing
  values for the same field.

Claim-level contradiction requires the claim's asserted value to be **absent** from the evidence
while a different value for the same field is present — without which a passage stating both figures
("records identify five trips; four correspond to the disclosure") would read as contradicting a
claim that faithfully reports one of them.

On the shipped corpus this finds every planted conflict and produces no flags on the clean cases.
It remains a heuristic, and the UI, the stored description and this README all describe its output
as a **potential contradiction requiring human review**.

## Evaluation framework

```bash
python evals/run_evals.py                    # both suites
python evals/run_evals.py --label prompt-v2  # label the run
python evals/compare_runs.py                 # diff the two most recent runs
python evals/compare_runs.py --list
```

Two suites:

**Golden cases** — all ten synthetic cases, compared against
`evals/expected_recommendations.json`. Ground truth lives only in `evals/`; the inference pipeline
reads `data/synthetic_cases/` and has no path to it. A test asserts no expected answer appears in
any case package.

**Evidence mutations** — controlled variants that add or remove documents from a package. Each
variant is ingested as a separate case (`<slug>__<mutation_id>`) in a scratch corpus, analysed, and
purged; the demonstration caseload is never modified. In DEMO_MODE a variant reuses the base case's
generated narrative *on purpose*: holding the prose fixed isolates whether the **recommendation**
reacts to the evidence.

| Mutation | Change | Expected |
| --- | --- | --- |
| `alex_m1_remove_repayment_evidence` | Remove both documents evidencing the repayment plan | 🟡 Request |
| `alex_m2_add_contradictory_financial_record` | Add a second credit pull with a different balance and date | 🔴 Escalate |
| `alex_m3_remove_irrelevant_travel_document` | Remove a document no material reason depends on | 🟢 Proceed (unchanged) |
| `alex_m4_add_benign_document` | Add an unrelated clean record | 🟢 Proceed (unchanged) |
| `elena_m1_remove_conflicting_reference` | Remove one of several records attesting a conflict | 🔴 Escalate (unchanged) |
| `priya_m1_remove_amended_disclosure` | Remove all evidence of the corrective filing | 🟡 Request |
| `hannah_m1_add_benign_document` | Add a clean record to a clean package | 🟢 Proceed (unchanged) |
| `marcus_m1_remove_clean_employment_record` | Remove an unrelated clean record | 🔴 Escalate (unchanged) |

### Metric definitions

| Metric | Definition |
| --- | --- |
| **Recommendation accuracy** | Golden cases reaching the expected state |
| **Concern level accuracy** | Golden cases reaching the expected concern level |
| **Recommendation groundedness** | Share of stated reasons backed by verified evidence with ≥1 source |
| **Unsupported recommendation rate** | Briefs with no reasons, or with <50% of reasons verified |
| **Critical evidence recall** | Share of decision-critical documents the brief actually cited |
| **Citation precision** | Cited passages that resolve and score ≥ 0.30 relevance |
| **Citation recall** | Decisive facts (ground-truth terms) appearing in cited evidence |
| **Reason coverage** | Expected reason topics addressed by the brief |
| **Contradiction sensitivity** | Contradiction mutations reaching the expected state |
| **Missing-information sensitivity** | Removal mutations reaching the expected state |
| **Recommendation stability** | Immaterial mutations whose recommendation is **unchanged** from base |
| **Material evidence sensitivity** | Material mutations that both **moved** from base **and** landed on the expected state — moving for the wrong reason is instability, not sensitivity |
| **Human agreement rate** | Recorded adjudicator actions matching the AI recommendation |

Current results in DEMO_MODE: recommendation accuracy 100%, concern level accuracy 100%,
groundedness 100%, unsupported rate 0%, critical evidence recall 93%, citation precision 100%,
citation recall 73%, reason coverage 95%, stability 100%, material sensitivity 100%.

## Audit trail

```
04:38:01  human   case_opened                       Case PS-2026-00182 opened for adjudication
04:38:02  ai      analysis_requested                AI analysis requested for PS-2026-00182
04:38:02  ai      evidence_retrieved                16 evidence chunks retrieved
04:38:02  ai      summary_generated                 Summary generated by demo-fixture-v1
04:38:02  ai      claims_extracted                  14 claims extracted
04:38:03  ai      claims_validated                  10 supported, 3 weakly supported, 1 unsupported
04:38:03  ai      unsupported_claim_detected        1 unsupported claim flagged for human verification
04:38:03  ai      overall_recommendation_generated  Proceed to Standard Review (82% confidence, 0 material unresolved issues)
04:38:03  ai      metrics_computed                  Groundedness 86%, coverage 93%
04:41:17  human   case_proceeded                    Proceeded to standard review for a1646316
04:41:17  human   adjudicator_agreed_with_ai        Adjudicator agreed with the AI recommendation
```

New event types: `evidence_source_opened`, `overall_recommendation_generated`,
`recommendation_changed_after_evidence_update`, `adjudicator_agreed_with_ai`,
`adjudicator_disagreed_with_ai`, `additional_information_requested`, `case_escalated`,
`case_proceeded`.

Recommendation events carry the model, prompt version, recommendation, the model's own proposal and
whether it agreed with the engine, confidence, concern level, material unresolved issues, the
evidence source IDs used, and the full engine rationale. Adjudicator events carry the action, the AI
recommendation at the time of decision, agreement, and evidence used.

Metadata is scrubbed of anything key-like and truncated before storage. `AuditRepository` exposes
only `append`, `list_for_case`, `list_recent` and `count` — no update or delete path exists, and a
test asserts that.

## Database architecture

Eleven tables, string UUID keys, dialect-agnostic:

| Table | Purpose |
| --- | --- |
| `cases` | Case number, applicant, status, scenario, timeline |
| `documents` | Raw document text with its `DOC-n` reference |
| `document_chunks` | Every citable passage — a document slice **or** a history event — with `source_type`, source ID, metadata and embedding |
| `case_history_events` | Dated investigation events with stable `EVT-…` references |
| `ai_analysis` | One brief: model, prompt version, raw output, **assessment JSON, recommendation, confidence, concern level, material unresolved issues** |
| `claims` | Extracted claim with assurance status and full score breakdown |
| `claim_evidence` | Claim → passage links with relevance **and the structured navigation destination** |
| `contradictions` | Flagged conflicts with both sides quoted |
| `human_reviews` | Narrative decision, original text, edited text, diff |
| `adjudicator_actions` | **Human decision, AI recommendation copied onto the row, agreement, evidence used** |
| `audit_events` | Append-only event log |
| `assurance_metrics` | Per-analysis narrative metric snapshot |

The embedding column resolves to `pgvector.Vector(dim)` on PostgreSQL and to a JSON text column
elsewhere, so the same models back both deployment modes.

## Synthetic dataset

The prototype ships a focused **five-case** demonstration set — 32 documents — covering every
recommendation state:

| Expected | Case | Why it is in the set |
| --- | --- | --- |
| 🟢 Proceed | **Alex Morgan** | A financial concern with independently verified mitigation |
| 🟢 Proceed | **Hannah Ostrowski** | The clean control: proof the system will say "nothing here" |
| 🟡 Request | **Jordan Reyes** | A discrepancy documented *inside one record*, one month unverified |
| 🔴 Escalate | **Elena Vasquez** | Two *independent* records disagree, and nothing resolves it |
| 🔴 Escalate | **Marcus Dell** | Unreported foreign travel and contact; also the model/engine divergence demo |

Two contrasts carry the design, and they are why these five:

- **Alex Morgan vs Marcus Dell** — a concern the applicant disclosed and documented, versus one
  found only by record check with an explanation the employer does not support.
- **Jordan Reyes vs Elena Vasquez** — a discrepancy one record documents about itself, versus two
  sources that genuinely disagree. The first requests information; the second escalates.

Five more cases stay defined in `scripts/case_corpus.py` and are one line from being re-enabled —
Priya Nandakumar (reporting omission, corrected), Sofia Lindqvist (minor legal matter, closed),
Thomas Achebe (nine-month evidence gap), Victor Ramachandran (three moderate indicators),
Daniel Okonjo (substantial delinquency, no mitigation). Move a slug from `RESERVE_SLUGS` to
`ACTIVE_SLUGS` and re-seed, or run `python scripts/seed_database.py --demo --all-cases` for all ten.
Mutations whose base case is not loaded are skipped with a notice rather than failing.

Every applicant, employer, creditor, account, address, document and event is invented.

## Project structure

```
missiontrust/
├── app.py
├── pages/
│   ├── 1_Case_Dashboard.py       # queue, ordered by what needs attention
│   ├── 2_Case_Review.py          # the decision-ready brief
│   ├── 3_Case_Details.py         # the full case record + evidence landing target
│   ├── 4_Case_Documents.py       # plain reading view of the source documents as filed
│   ├── 5_AI_Assurance.py         # recommendation quality, then narrative assurance
│   └── 6_Audit_Trail.py
├── src/
│   ├── config/settings.py
│   ├── database/                 # models.py, db.py, repositories.py
│   ├── ingestion/                # document_loader.py, chunker.py, embedding_service.py
│   ├── retrieval/                # vector_store.py, retriever.py
│   ├── llm/                      # provider.py, prompts.py, summarizer.py
│   ├── assurance/                # claim_extractor.py, evidence_validator.py,
│   │                             # contradiction_detector.py, recommendation_engine.py,
│   │                             # metrics.py
│   ├── audit/logger.py
│   ├── services/                 # case_service.py, analysis_service.py,
│   │                             # review_service.py, evidence_service.py, bootstrap.py
│   ├── models/schemas.py
│   └── ui/                       # theme.py, components.py
├── data/
│   ├── synthetic_cases/<slug>/   # case_metadata.json + documents (no ground truth)
│   └── demo_analyses/<slug>.json # curated DEMO_MODE generation fixtures
├── evals/
│   ├── golden_cases.json             # generated
│   ├── expected_recommendations.json # generated
│   ├── evidence_mutation_cases.json
│   ├── run_evals.py
│   ├── metrics.py
│   ├── compare_runs.py
│   └── results/                      # run_<timestamp>.json
├── scripts/
│   ├── case_corpus.py            # the documents
│   ├── case_assessments.py       # brief fixtures + eval ground truth
│   ├── generate_synthetic_cases.py
│   ├── ingest_documents.py
│   └── seed_database.py
├── tests/                        # 147 tests, no network required
├── Dockerfile
└── docker-compose.yml
```

## Setup

Requires **Python 3.9 or newer**. No database server and no API key are needed.

```bash
cd missiontrust
python -m venv .venv && source .venv/bin/activate      # optional
pip install -r requirements.txt
cp .env.example .env                                    # optional; defaults work as-is
python scripts/seed_database.py --demo
streamlit run app.py
```

`--demo` resets the database, regenerates the corpus and eval ground truth, ingests everything,
generates a brief for all ten cases and records sample reviewer decisions. Seeding also happens
automatically if the app starts against an empty database.

## Environment variables

Every setting is read from the environment (optionally seeded from `.env`). **No credential is ever
hard-coded, logged, or written to an audit event.**

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEMO_MODE` | `true` | Run without any API key using curated generation fixtures |
| `DATABASE_URL` | SQLite at `~/.missiontrust/missiontrust.db` | e.g. `postgresql+psycopg://missiontrust:missiontrust@localhost:5433/missiontrust` |
| `LLM_PROVIDER` | `demo` | `demo`, `anthropic`, `openai`, or `groq` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | — / `claude-sonnet-5` | Anthropic credentials |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | — / `gpt-4o-mini` / — | OpenAI-compatible endpoint |
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_BASE_URL` | — / `llama-3.3-70b-versatile` / Groq's API | Groq, via the same OpenAI-compatible client |
| `EMBEDDING_PROVIDER` / `EMBEDDING_DIM` | `local` / `512` | Embedding backend |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `700` / `120` | Chunking |
| `RETRIEVAL_TOP_K` / `EVIDENCE_TOP_K` | `16` / `4` | Retrieval breadth |
| `WEIGHT_SEMANTIC` / `WEIGHT_RETRIEVAL` / `WEIGHT_ENTAILMENT` | `0.40` / `0.20` / `0.40` | Claim scoring weights |
| `THRESHOLD_SUPPORTED` / `THRESHOLD_WEAK` | `0.75` / `0.55` | Claim status thresholds |
| `SEMANTIC_FLOOR` / `SEMANTIC_CEILING` | `0.08` / `0.45` | Cosine calibration band |
| `REVIEWER_NAME` / `REVIEWER_ROLE` | `Demo Reviewer` / `Adjudication Analyst` | Adjudicator identity placeholder for real IAM |

Demo mode is *forced on* whenever the selected provider has no credential, so a missing key degrades
to a working demo rather than a stack trace.

## Running locally

```bash
streamlit run app.py                       # http://localhost:8501
python scripts/seed_database.py --demo     # full demo state
python scripts/ingest_documents.py         # re-chunk and re-embed only
python evals/run_evals.py                  # evaluation suite
python -m pytest -q                        # tests
```

To use a live model:

```bash
export DEMO_MODE=false
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...        # never commit this
streamlit run app.py
```

### Switching between fixture and live generation

`DEMO_MODE` sets the default, but the **Case Review page carries a generation-source control**, so
the two can be compared without editing configuration or restarting:

```
Generation source
  ( ) Curated fixture — instant
  (•) Live model — openai/gpt-oss-120b
```

The option only appears when a provider credential is actually configured. Everything downstream —
retrieval, claim validation, contradiction detection, the rules — runs identically either way; only
who writes the draft changes, and the brief's provenance line records which was used.

Groq speaks the OpenAI chat-completions API, so it runs through the same client:

```bash
export DEMO_MODE=false
export LLM_PROVIDER=groq
export GROQ_API_KEY=...
export GROQ_MODEL=llama-3.3-70b-versatile   # check Groq's current model list
streamlit run app.py
```

**The eval suite is the reason to bother.** Against fixtures it measures the rule engine; against a
live model it measures the whole system, generation included:

```bash
DEMO_MODE=false LLM_PROVIDER=groq python evals/run_evals.py --label groq-llama-3.3-70b
python evals/compare_runs.py            # diff it against the fixture baseline
```

With a live provider the LLM entailment verifier and the LLM contradiction pass also activate. The
recommendation engine is unchanged — the model's proposal is recorded and reconciled, never trusted
blindly.

## Docker

```bash
docker compose up --build           # http://localhost:8501
```

Compose starts `pgvector/pgvector:pg16` on host port **5433** and the app on **8501**. The
entrypoint waits for the database, seeds it and starts Streamlit.

## Demo script

1. **Case Dashboard** — ten completed packages, sorted with escalations first. The queue is
   recommendation-led: 3 escalate, 3 request information, 4 proceed.
2. **Open `PS-2026-00182` (Alex Morgan)** — the recommendation is the first thing on screen:
   🟢 *Proceed to Standard Review*, LOW concern, 82% confidence, 0 material unresolved issues.
3. **Read the executive assessment** — the case in one paragraph.
4. **Expand Reason 1** — *"The single financial concern has documented, independently verified
   mitigation."* → Payment Plan Document, DOC-4-CHUNK-0, March 14 2026, relevance 0.91, cited by
   model, quoting *"Plan effective date: March 14, 2026"*, verification status **Supported**.
5. **Click `Open source →`** on that citation — the app moves to **Case Details**, opens the
   Documents section on `DOC-4 Payment Plan Document`, highlights `DOC-4-CHUNK-0` and scrolls to
   it. *Used in AI recommendation* names reason-1 as the consumer. Read the surrounding clauses,
   then press **← Back to AI Case Brief** and land back on reason 1 with its evidence open.
6. **Open a history citation** — reason 6 cites `EVT-2026-05-02-001`. The same click lands on
   Case History with the May 2 monitoring alert highlighted, because evidence is not only
   documents.
7. **Scroll to Remaining concerns** — the delinquency is still listed even though the
   recommendation is positive. The system never hides adverse evidence behind a good outcome.
8. **What could change this recommendation** — *"If this could not be verified: The applicant
   entered a structured repayment plan…"* — derived from the actual load-bearing evidence.
9. **Open `PS-2026-00225` (Elena Vasquez)** — 🔴 *Escalate*. Reason one: the employer's payroll
   record and the reference interview disagree on the separation date and nothing resolves it.
10. **Open `PS-2026-00217` (Marcus Dell)** — the reconciliation notice: the model proposed *request
    information*, the evidence rules escalated, and the more conservative state shipped.
   information*, the evidence rules escalated, and the more conservative state shipped.
11. **Press Escalate on a case the AI said proceed** — the decision history shows the AI
   recommendation preserved, the human action, and `agreed_with_ai: no`.
12. **`python evals/run_evals.py`** — the evidence-mutation suite: removing the repayment evidence
    moves Alex from proceed to request; adding a contradictory credit pull escalates him; removing
    an unrelated travel document changes nothing.
13. **AI Assurance** — recommendation accuracy, stability and sensitivity first; narrative
    assurance metrics below.
14. **Audit Trail** — the same sequence, AI and human, with model and prompt versions.

## Testing

```bash
python -m pytest -q          # 173 tests, ~3s, no network
```

Tests pin `DATABASE_URL` to a temporary SQLite file, the local embedder and demo mode *before* any
application module is imported. A `ScriptedProvider` mock stands in for the LLM.

Coverage includes: the recommendation schema's forbidden states, every rule in the engine
(including "one material contradiction escalates an otherwise clean case" and "seven clean
categories do not dilute one unresolved conflict"), category classification and the
documentation-fallback rule, model/engine reconciliation, adverse information surviving a positive
recommendation, sensitivity derivation, every eval metric, the mutation harness building variants
without touching the source corpus, end-to-end material sensitivity and immaterial stability, all
ten golden cases end to end, adjudicator action logging with derived agreement, and everything
retained from the previous version — ingestion, chunking, retrieval, structured-output parsing,
claim validation, contradiction detection, narrative metrics, audit append-only behaviour and
human-review persistence.

Navigation is covered end to end: reason → document mapping, reason → history-event mapping,
case-scoped resolution (a source ID from another case must not resolve), correct document and
passage selection, correct history-event highlight, deep-link query parameters, back-navigation
preserving the originating reason, reverse traceability from a passage to the reasons citing it,
the assertion that everything the brief cites resolves, that the passages the adjudicator reads are
byte-identical to the ones the retriever holds, and that a missing source reports
*"Source could not be located in the case record."* rather than raising.

## Engineering decisions

- **A deterministic engine decides the state; the model writes the prose.** The alternative — asking
  the model for a recommendation and trusting it — fails the evidence-mutation suite by
  construction, because a cached or confidently-wrong narrative does not react to a removed
  document. Splitting the two makes the product testable and the escalation logic auditable.
- **The more conservative state ships on disagreement.** Marcus Dell demonstrates it live: the model
  proposed *request information*, the rules escalated.
- **Reasons whose evidence no longer holds are dropped, not shown.** This is what keeps a mutated
  case from displaying "the concern is mitigated" next to a 🔴 escalation.
- **Dual database, one schema.** `docker compose up` gives real pgvector; `streamlit run app.py`
  gives a working demo in thirty seconds.
- **A purpose-built retrieval layer instead of LlamaIndex or LangChain**, to keep the part a
  reviewer most needs to interrogate legible. The interfaces mirror the frameworks' own.
- **Deterministic local embeddings by default** — no key, no network, byte-identical across runs.
- **Ground truth lives only in `evals/`**, and a test enforces it.
- **History events share the passage table with documents**, rather than living in a parallel
  index. One retriever, one scorer, one set of assurance metrics, and navigation that does not
  care which kind of evidence it is pointing at.
- **Contradiction detection runs over the whole case record, not the retrieved top-k.** Two
  documents disagreeing is a property of the file, not of what a retrieval pass happened to
  surface — and once history events share the index, a top-k pool can no longer be assumed to
  contain both sides of a conflict.
- **A radio, not `st.tabs`, for the Case Details sections.** Streamlit cannot select a tab
  programmatically, and a citation has to be able to open the section it belongs to.
- **Two views of the same document, one stored copy.** Case Details renders a document as the
  addressable passages the retrieval index uses, with citations highlighted — that answers "what
  did the AI rely on". Case Documents renders the filed text verbatim — that answers "what does
  the document say". Both read the same row; nothing is duplicated.
- **`st.html`, not `st.markdown`, for verbatim document text.** A document's own `=====` underline
  is a setext heading to a markdown parser, which swallowed it and reformatted the title. Passage
  and document views bypass markdown entirely.
- **The referenced passage is both highlighted inline and lifted into a callout.** Auto-scroll via
  a component script is best-effort; the callout is the guarantee that the adjudicator sees the
  exact passage on arrival.

## What running against a live model exposed

DEMO_MODE proves the rule engine. It cannot prove the system, because generation is held constant.
Running the same pipeline against **`openai/gpt-oss-120b` on Groq** surfaced six defects that
fixtures had masked — four crashes or validation failures, and two architectural:

| Defect | Why fixtures hid it | Fix |
| --- | --- | --- |
| Schema required `executive_summary`; the prompt asks for `executive_case_assessment` | Fixtures carried both fields | Either field now fills the other |
| LLM verifier crashed — star-unpacking bound `chunk` to the span string | That branch only runs with a live provider | Explicit tuple unpacking, plus a scripted-provider test |
| One stray enum value (`claim_type: "informational"`) invalidated all 14 claims | Fixtures only contain valid enum values | Unknown enum values coerce to a safe default; **the recommendation state never does** |
| **An LLM-declared conflict could escalate a case on its own** | The LLM contradiction pass never runs in DEMO_MODE | Only deterministic detectors escalate |
| **Mitigation was read only from model-supplied `claim_type` labels** | Fixtures hand-label mitigations correctly | Mitigation is also read from `factor_details` |
| A claim summarising several sentences scored unsupported | Fixture claims map to single sentences | Entailment is scored against the whole passage as well as the best span |

The two architectural ones are worth stating plainly.

**The model had a side door into the recommendation.** The design claim is *"rules decide, the model
writes"* — but LLM-declared contradictions fed straight into the escalation rule. A live run flagged
an **$18,500** February balance against a **$17,850** May balance as a contradiction at **0.95
confidence**. The difference was two $325 payments: the mitigation working exactly as documented.
That single false positive escalated a case that should proceed.

Conflicts asserted by a model are now **advisory**, exactly like the recommendation a model proposes:
surfaced to the adjudicator, able to trigger an information request, never able to escalate alone.
Only the deterministic field/value detector — which is unit-tested and reproducible — escalates.
An unrecognised detector is treated as advisory, because under-escalating on an unknown detector is
safer than reopening the door.

**A live model may never emit `claim_type: "mitigation"`.** One run typed every claim `fact` and put
the repayment plan in `factor_details` — precisely where the prompt asks for it. Reading only claim
types made a fully-mitigated case look unmitigated. Stated mitigating factors now count as
mitigation when they resolve to real, already-scored evidence.

### What remains, honestly

After the fixes, Alex Morgan no longer escalates under a live model — but lands on
**REQUEST_ADDITIONAL_INFORMATION** rather than PROCEED, because `gpt-oss-120b` raises the
monitoring-alert concern without extracting the investigator's note that correlates it to the
already-disclosed account. The engine then reasons correctly over an incomplete extraction: a
concern with no mitigating evidence *should* prompt a request.

That is a **model-quality finding, not an engine defect**, and it is exactly what a live evaluation
is for. The prompt now instructs the model to pair every concern it raises with any mitigation the
package contains; that change has not yet been measured across a full live run.

### Rate limits

Groq's free tier caps at **8,000 tokens per minute**. One case makes roughly fifteen calls —
generation, one entailment check per claim, and the contradiction pass — and took **115–190 seconds**
with 429 retries throughout. A full suite of twelve analyses is a 30–45 minute run on that tier.
Prefer `--golden-only` for a live check.

## Known limitations

- The recommendation engine is a **prototype rule set**, tuned on ten synthetic cases. The
  thresholds are documented and configurable, but they are not calibrated against real adjudicative
  outcomes and there is no such thing here as a validated decision policy.
- **Source authority is not modelled.** The assurance layer asks whether a statement is traceable to
  *a* document, not whether that document is authoritative. Building the mutation suite surfaced
  this directly: removing the court disposition record from Sofia Lindqvist's package left every
  fact still "supported" — by the applicant's own statement. A production system would weight a
  court record above a self-report.
- **Facts are multiply attested**, as in real case files, so removing a single document often does
  not remove the fact. Two mutations had to remove *all* documents evidencing a fact to move the
  recommendation. That is correct behaviour, and it means single-document sensitivity is weaker than
  it looks.
- Contradiction detection is a **heuristic over typed field/value pairs**; it will not find a
  semantic contradiction expressed only in prose.
- The offline entailment signal is **lexical, not logical**; it cannot detect a claim that reuses
  source vocabulary while inverting the meaning.
- Metrics are **unvalidated**: no human-labelled ground truth beyond the authored expectations, no
  inter-rater agreement, no calibration study.
- **The offline entailment signal remains lexical, not logical.** A claim summarising a negated list
  ("no delinquent accounts, collections, judgments or liens") still scores below the support
  threshold even though two sentences of the financial report say exactly that. Scoring the whole
  passage as well as the best span improved it from 0.42 to 0.52, not past 0.55. The error runs in
  the safe direction — a reviewer is asked to verify something that is in fact supported — but it is
  a false positive and it is not fixed.
- **Live recommendation accuracy is lower than fixture accuracy**, and the gap is model extraction
  quality rather than engine behaviour. See the section above.
- Auto-scroll to an anchored passage depends on the component script reaching the parent document;
  where a browser blocks that, the referenced passage still appears in the callout at the top of
  the section but the page will not move on its own.
- The audit trail is append-only **by application discipline**, not cryptographically tamper-evident.
- There is **no authentication**; `REVIEWER_NAME` is a placeholder for real identity.
- Ten cases and eight mutations are enough to demonstrate the evaluation method, not to evaluate a
  model.

## Ethical considerations

- **The adjudicator decides.** Three decision-support states, none of which approves or denies
  anything. `requires_human_decision` cannot be turned off.
- **A recommendation anchors harder than a summary.** That is exactly why every reason carries its
  evidence and verification status, why *what could change this recommendation* is a required
  section, and why the model/engine divergence is shown rather than hidden.
- **Adverse information is never suppressed by a positive outcome.** Remaining concerns are built
  from the evidence independently of the recommendation, and a test enforces it.
- **Absence of evidence is reported, not inferred.** Missing information is a first-class output and
  drives a distinct recommendation state.
- **No profiling.** No demographic inference, no biometrics, no surveillance features, no predictive
  modelling of people.
- **Synthetic data only.**

## Security and privacy design

Credentials only from environment variables; `.env` git-ignored; `Settings.redacted()` is the only
path configuration takes to the UI. Audit metadata is scrubbed of key-like fields and truncated. All
database access is parameterised. Every external and file input is validated with Pydantic. Database
URLs are stripped of credentials before display. Errors degrade to explanatory panels rather than
stack traces.

**For production this architecture would additionally require:** strong IAM and SSO with role-based
access control; encryption at rest and in transit; tamper-evident audit storage; secure secrets
management; network isolation and private model endpoints; retention and disposition policies;
per-record access logging; formal model evaluation and monitoring; documented human-review
procedures; and independent compliance and privacy review. **CaseBrief implements none of these
and makes no certification claim of any kind.**

## Future improvements

- Source-authority weighting so a court record outranks a self-report
- Reviewer decisions fed back as labels to calibrate the rule thresholds
- Side-by-side model comparison on recommendation accuracy, stability and sensitivity — the provider
  layer, prompt versioning and eval harness already support it
- Prompt A/B evaluation through `compare_runs.py`
- Temporal knowledge graph over case entities for cross-document reasoning
- Bias and drift monitoring across case categories and recommendation states
- Reranking and hybrid BM25 + dense retrieval
- OpenSearch or AWS Bedrock Knowledge Bases as alternative back ends

## Screenshots

Place images in `assets/` and they will render here.

| View | File |
| --- | --- |
| Decision-ready brief | `assets/screenshot-brief.png` |
| Reason → evidence drill-down | `assets/screenshot-evidence.png` |
| Landing on the cited passage in the record | `assets/screenshot-case-details.png` |
| Case dashboard queue | `assets/screenshot-dashboard.png` |
| Recommendation quality metrics | `assets/screenshot-assurance.png` |
| Audit trail | `assets/screenshot-audit.png` |

## Disclaimer

**CaseBrief is an independent educational prototype using entirely synthetic data. It is not
affiliated with, endorsed by, or integrated with any government agency or commercial
personnel-security platform.**

Every applicant, case, employer, creditor, account, address, document and event in this repository
is fictional and was invented for demonstration purposes. The workflow is a generic,
adjudication-*style* review process, not a model of any real agency process. The system produces no
determination, recommendation of approval or denial, or decision of any kind about a real person,
and it makes no claim of FedRAMP, ATO, NIST, or any other certification or accreditation.
