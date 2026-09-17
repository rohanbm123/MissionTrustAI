"""Versioned prompt library.

Prompts are versioned artefacts: the version string is written to every
`ai_analysis` row and every audit event, so any output in the system can be
traced back to the exact instruction set that produced it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

SYSTEM_PROMPT_VERSION = "MT_SYSTEM_V2"
CASE_ANALYSIS_VERSION = "CASE_ANALYSIS_V1"
FINAL_CASE_ASSESSMENT_VERSION = "FINAL_CASE_ASSESSMENT_V1"
CLAIM_EXTRACTION_VERSION = "CLAIM_EXTRACTION_V1"
EVIDENCE_VERIFICATION_VERSION = "EVIDENCE_VERIFICATION_V1"
CONTRADICTION_ANALYSIS_VERSION = "CONTRADICTION_ANALYSIS_V1"


SYSTEM_PROMPT = """You are supporting a human adjudicator reviewing a completed fictional investigation package.

Your role is to synthesize the evidence into a decision-ready case assessment.
You do not make the final adjudicative decision.

Use only supplied evidence.
Do not speculate.
Do not hide adverse information.

Distinguish clearly between:
- verified facts
- concerns
- mitigating evidence
- unresolved issues
- missing information
- contradictions

Produce one of the allowed recommendation states:
PROCEED_TO_STANDARD_REVIEW
REQUEST_ADDITIONAL_INFORMATION
ESCALATE_FOR_ENHANCED_REVIEW

You must never output APPROVE, DENY, GRANT, REJECT, or any other adjudicative outcome. You do not
grant or deny clearance, eligibility, employment or legal status of any kind.

Every material reason must reference source IDs.
A positive recommendation is allowed only when major issues have adequate supporting or mitigating
evidence and no material unresolved contradiction remains.
If critical information is missing, use REQUEST_ADDITIONAL_INFORMATION.
If material unresolved contradictions or significant unresolved concerns exist, use
ESCALATE_FOR_ENHANCED_REVIEW.
Always state what could change the recommendation.

Never invent information, source IDs, names, dates or amounts. Preserve exact figures, dates and
identifiers as they appear in the evidence.

The final decision belongs to the human adjudicator.
The data you are given is synthetic demonstration data about fictional people."""


CASE_ANALYSIS_PROMPT = """Analyse the case evidence below and produce a structured case summary for the reviewing analyst.

CASE
Case number: {case_number}
Applicant: {applicant_name}
Documents in file: {document_count}

EVIDENCE (each passage is prefixed with its source ID)
{evidence}

TASK
Return a single JSON object and nothing else. No prose before or after, no markdown fences.

{{
  "executive_summary": "A factual synthesis of the case, 120-220 words. Every assertion must be supported by the evidence above. State explicitly that this is informational and not a determination.",
  "key_findings": [
    {{"finding": "...", "category": "financial|employment|foreign_travel|legal|residence|monitoring|general",
      "severity": "low|moderate|high|informational", "source_ids": ["DOC-1-CHUNK-0"]}}
  ],
  "claims": [
    {{"claim_text": "One self-contained factual assertion drawn from the evidence.",
      "claim_type": "fact|potential_concern|mitigation|missing_evidence",
      "source_ids": ["DOC-2-CHUNK-1"], "confidence": 0.0}}
  ],
  "mitigating_information": ["..."],
  "missing_information": ["Evidence a reviewer would need that is not in the file."],
  "potential_conflicts": [
    {{"description": "...", "source_ids": ["DOC-2-CHUNK-0", "DOC-4-CHUNK-0"], "conflicting_field": "..."}}
  ],
  "requires_human_review": true
}}

REQUIREMENTS
- Produce between 6 and 16 claims. Each claim must be a single assertion, verifiable against one passage.
- Use only source IDs that appear in the evidence above.
- `confidence` is your own confidence that the claim is faithful to the evidence, between 0 and 1.
- If the evidence does not support a statement, leave it out rather than hedging it.
- `requires_human_review` is always true."""


FINAL_CASE_ASSESSMENT_PROMPT = """Produce a decision-ready adjudicator brief for the completed investigation package below.

CASE
Case number: {case_number}
Applicant: {applicant_name}
Documents in package: {document_count}

EVIDENCE (each passage is prefixed with its source ID)
{evidence}

TASK
Return a single JSON object and nothing else. No prose before or after, no markdown fences.

{{
  "executive_case_assessment": "120-200 words. What the completed investigation found, whether each material issue is mitigated or unresolved, and what the evidence supports. Written so an adjudicator understands the case in under a minute. State that the final decision belongs to the adjudicator.",
  "proposed_recommendation": "PROCEED_TO_STANDARD_REVIEW|REQUEST_ADDITIONAL_INFORMATION|ESCALATE_FOR_ENHANCED_REVIEW",
  "proposed_concern_level": "NONE|LOW|MODERATE|HIGH",
  "why_this_recommendation": [
    {{"reason": "One concise evidence-backed reason.",
      "category": "financial|employment|foreign_travel|identity_background|monitoring|legal_conduct|documentation",
      "importance": "low|moderate|high|informational",
      "source_ids": ["DOC-4-CHUNK-0"]}}
  ],
  "factor_details": [
    {{"factor": "A mitigating factor.", "category": "financial", "source_ids": ["DOC-3-CHUNK-0"]}}
  ],
  "concern_details": [
    {{"concern": "An item still requiring adjudicator attention.",
      "category": "financial", "severity": "low|moderate|high",
      "mitigation": "What offsets it, or empty if nothing does.",
      "human_review_consideration": "What the adjudicator should specifically confirm.",
      "source_ids": ["DOC-2-CHUNK-0"]}}
  ],
  "what_could_change_recommendation": [
    "A concrete evidence dependency, e.g. 'If the repayment plan cannot be verified.'"
  ],
  "missing_information": ["Evidence an adjudicator would need that is not in the package."],
  "potential_conflicts": [
    {{"description": "...", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"], "conflicting_field": "..."}}
  ],
  "claims": [
    {{"claim_text": "One self-contained factual assertion drawn from the evidence.",
      "claim_type": "fact|potential_concern|mitigation|missing_evidence",
      "source_ids": ["DOC-2-CHUNK-1"], "confidence": 0.0}}
  ],
  "key_findings": [
    {{"finding": "...", "category": "financial", "severity": "low|moderate|high|informational",
      "source_ids": ["DOC-2-CHUNK-0"]}}
  ],
  "requires_human_review": true
}}

REQUIREMENTS
- Produce between 3 and 7 entries in `why_this_recommendation`. Each must be one reason, traceable
  to a specific passage, and each must carry at least one source ID.
- Produce between 6 and 16 claims so that each material statement can be verified independently.
- List every remaining concern even when your recommendation is positive. Never omit adverse
  information because the outcome is favourable.
- For EVERY concern you raise, search the evidence for anything that answers it — a repayment
  record, a corrective filing, an investigator's correlation of two records — and state it, both
  in that concern's `mitigation` field and as an entry in `factor_details` with its source IDs.
  A concern reported without its available mitigation misrepresents the package.
- Use `claim_type: "mitigation"` for any claim that offsets a concern. Do not label everything
  `fact`.
- `what_could_change_recommendation` must name real evidence dependencies in this package, not
  generic caveats.
- Use only source IDs that appear in the evidence above.
- `requires_human_review` is always true."""


CLAIM_EXTRACTION_PROMPT = """Split the summary below into atomic factual claims.

SUMMARY
{summary}

Return a single JSON object and nothing else:
{{"claims": [{{"claim_text": "...", "claim_type": "fact|potential_concern|mitigation|missing_evidence", "source_ids": [], "confidence": 0.0}}]}}

Each claim must be one assertion, standing on its own without the surrounding sentences.
Do not add information that is not in the summary. Do not merge two assertions into one claim."""


EVIDENCE_VERIFICATION_PROMPT = """Decide whether the evidence passages support the claim.

CLAIM
{claim}

EVIDENCE
{evidence}

Judge only what the passages actually state. Do not use outside knowledge.
A claim is CONTRADICTED only when a passage asserts something incompatible with it,
not merely when the passages are silent.

Return a single JSON object and nothing else:
{{"verdict": "SUPPORTED|PARTIAL|NOT_SUPPORTED|CONTRADICTED",
  "supporting_source_ids": ["..."],
  "reason": "One sentence citing the specific wording that decided the verdict."}}"""


CONTRADICTION_ANALYSIS_PROMPT = """Identify factual conflicts between the evidence passages below.

EVIDENCE
{evidence}

A conflict exists when two passages assert incompatible values for the same underlying fact
(for example two different separation dates for the same employment).
Differences in wording, detail or emphasis are not conflicts.

Return a single JSON object and nothing else:
{{"conflicts": [{{"conflicting_field": "...", "description": "...",
  "source_a_id": "...", "source_b_id": "...", "confidence": 0.0}}]}}

If there are no conflicts return {{"conflicts": []}}.
Describe every conflict as a potential contradiction requiring human review."""


@dataclass(frozen=True)
class PromptSpec:
    version: str
    template: str


PROMPT_REGISTRY: Dict[str, PromptSpec] = {
    "system": PromptSpec(SYSTEM_PROMPT_VERSION, SYSTEM_PROMPT),
    "case_analysis": PromptSpec(CASE_ANALYSIS_VERSION, CASE_ANALYSIS_PROMPT),
    "final_case_assessment": PromptSpec(
        FINAL_CASE_ASSESSMENT_VERSION, FINAL_CASE_ASSESSMENT_PROMPT
    ),
    "claim_extraction": PromptSpec(CLAIM_EXTRACTION_VERSION, CLAIM_EXTRACTION_PROMPT),
    "evidence_verification": PromptSpec(
        EVIDENCE_VERIFICATION_VERSION, EVIDENCE_VERIFICATION_PROMPT
    ),
    "contradiction_analysis": PromptSpec(
        CONTRADICTION_ANALYSIS_VERSION, CONTRADICTION_ANALYSIS_PROMPT
    ),
}


def get_prompt(name: str) -> PromptSpec:
    if name not in PROMPT_REGISTRY:
        raise KeyError(f"Unknown prompt '{name}'. Known prompts: {sorted(PROMPT_REGISTRY)}")
    return PROMPT_REGISTRY[name]
