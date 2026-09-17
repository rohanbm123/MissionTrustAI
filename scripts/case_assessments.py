"""Decision-ready assessment fixtures and evaluation ground truth.

FICTIONAL DEMONSTRATION DATA.

`ASSESSMENTS` supplies the narrative half of the adjudicator brief for DEMO_MODE:
the executive assessment, the drafted reasons, factors, concerns and
sensitivities. It is what a live model would write.

The recommendation *state* in `proposed_recommendation` is only the model's
proposal. `src.assurance.recommendation_engine` derives the state that ships from
the validated evidence, so the brief still reacts when documents change under a
cached narrative.

`GROUND_TRUTH` is evaluation-only. It is written to `evals/` and is never loaded
by the inference pipeline.
"""
from __future__ import annotations

from typing import Any, Dict

ASSESSMENTS: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
ASSESSMENTS["alex_morgan"] = {
    "proposed_recommendation": "PROCEED_TO_STANDARD_REVIEW",
    "proposed_concern_level": "LOW",
    "executive_case_assessment": (
        "The completed investigation identified one material financial concern: an $18,500 "
        "delinquent account with Meridian Regional Health Services, first reported delinquent on "
        "February 4, 2026. The applicant disclosed the debt before record checks identified it, "
        "attributed it to disputed medical billing following a partial insurance denial, and the "
        "package contains a structured repayment agreement effective March 14, 2026 at $325 per "
        "month with two payments received and none missed as of May 1, 2026. Employment, foreign "
        "travel, residence and criminal-history records were consistent with the applicant's "
        "disclosures. The one continuous-monitoring alert in the package references the same "
        "creditor and account reference as the original finding and the investigator assessed it "
        "as the same underlying account. No unresolved contradictory information was identified. "
        "The evidence supports proceeding to standard review. The final decision belongs to the "
        "adjudicator."
    ),
    "why_this_recommendation": [
        {"reason": "The single financial concern has documented, independently verified mitigation.", "category": "financial", "importance": "high", "source_ids": ["DOC-4-CHUNK-0", "DOC-8-CHUNK-0"]},
        {"reason": "The applicant's explanation is consistent with the creditor's own file annotation recording the account as in dispute.", "category": "financial", "importance": "moderate", "source_ids": ["DOC-3-CHUNK-0", "DOC-2-CHUNK-0"]},
        {"reason": "The repayment plan is corroborated by the servicer, not only asserted by the applicant.", "category": "financial", "importance": "high", "source_ids": ["DOC-8-CHUNK-0"]},
        {"reason": "Employment dates reported by the applicant match the dates confirmed by both employers of record.", "category": "employment", "importance": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "Disclosed foreign travel matches border-crossing records with no undisclosed trips identified.", "category": "foreign_travel", "importance": "moderate", "source_ids": ["DOC-6-CHUNK-0"]},
        {"reason": "The later monitoring alert relates to the already-disclosed account rather than to new activity.", "category": "monitoring", "importance": "moderate", "source_ids": ["DOC-7-CHUNK-0", "DOC-8-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The applicant self-reported the debt on the security questionnaire before record checks identified it.", "category": "financial", "source_ids": ["DOC-8-CHUNK-0"]},
        {"factor": "The repayment agreement is being paid as agreed with zero missed payments recorded.", "category": "financial", "source_ids": ["DOC-4-CHUNK-0"]},
        {"factor": "All other trade lines are current, so the balance is a single disputed account rather than a pattern.", "category": "financial", "source_ids": ["DOC-2-CHUNK-1"]},
    ],
    "concern_details": [
        {"concern": "The delinquent account remains technically open pending completion of the repayment plan.", "category": "financial", "severity": "low", "mitigation": "A verified repayment plan is active and paying as agreed.", "human_review_consideration": "Confirm the repayment arrangement remains current at the time of adjudication.", "source_ids": ["DOC-4-CHUNK-0"]},
        {"concern": "The outcome of the applicant's billing dispute with the originating creditor is not in the record.", "category": "financial", "severity": "low", "mitigation": "The dispute does not affect the repayment arrangement already in force.", "human_review_consideration": "Consider whether the dispute outcome is needed before the file closes.", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If the repayment agreement cannot be verified with the servicer.",
        "If payments after May 1, 2026 were missed.",
        "If new unresolved financial activity appears in a later monitoring refresh.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["jordan_reyes"] = {
    "proposed_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
    "proposed_concern_level": "MODERATE",
    "executive_case_assessment": (
        "The completed investigation identified one employment discrepancy that is partially, but "
        "not fully, reconciled. The applicant reported a January 2021 start date with Vantage "
        "Analytics Partners; the employer's records office confirms a permanent start date of "
        "July 12, 2021. A staffing agency record shows a contract placement with the same client "
        "from February 8, 2021 to July 9, 2021, converting to direct employment on July 12, 2021, "
        "which corroborates the applicant's explanation that the reported date reflected when the "
        "work began rather than when employment status changed. Approximately one month between "
        "the reported January start and the February 8 assignment start is accounted for by no "
        "record in the package, and the agency states it holds no placement for that month. "
        "Financial, criminal-history, residence and travel checks returned no adverse information. "
        "The residual gap is a documentation question rather than an adverse finding."
    ),
    "why_this_recommendation": [
        {"reason": "A third-party staffing record reconciles most of the reported discrepancy and corroborates the applicant's account.", "category": "employment", "importance": "high", "source_ids": ["DOC-4-CHUNK-0"]},
        {"reason": "One month of claimed employment is corroborated by no record in the package and the agency states it holds none.", "category": "employment", "importance": "high", "source_ids": ["DOC-4-CHUNK-0", "DOC-5-CHUNK-0"]},
        {"reason": "The investigator recorded that no information developed suggests a deliberate misstatement.", "category": "employment", "importance": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "No adverse information was developed in any other category.", "category": "documentation", "importance": "moderate", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The applicant volunteered the explanation before the agency record was obtained, and the record substantiates it.", "category": "employment", "source_ids": ["DOC-3-CHUNK-0", "DOC-4-CHUNK-0"]},
        {"factor": "Employment dates for the earlier employer match the dates that employer confirmed.", "category": "employment", "source_ids": ["DOC-2-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "Approximately one month of reported employment is unverified by any record in the package.", "category": "employment", "severity": "moderate", "mitigation": "The surrounding period is fully corroborated by the staffing agency record.", "human_review_consideration": "Request payroll or timesheet evidence for January 2021 before closing the discrepancy.", "source_ids": ["DOC-4-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If a January 2021 payroll or timesheet record is produced.",
        "If the staffing agency record could not be authenticated.",
        "If further unexplained employment gaps were identified.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["priya_nandakumar"] = {
    "proposed_recommendation": "PROCEED_TO_STANDARD_REVIEW",
    "proposed_concern_level": "LOW",
    "executive_case_assessment": (
        "The completed investigation identified one reporting omission. The applicant's disclosure "
        "of January 30, 2026 reported four foreign trips over the rolling 24-month period; a "
        "border-crossing cross-check completed February 14, 2026 identified five, including a "
        "Canada trip of October 3-5, 2025 that did not appear on the original filing. The "
        "applicant filed an amended disclosure on February 25, 2026 adding that trip and "
        "attributing the omission to a belief that short personal trips did not require reporting. "
        "No other unreported travel was identified. Two continuing foreign contacts are "
        "documented, both previously reported, with no foreign government affiliation and no "
        "foreign financial interest identified. Financial, employment, residence and "
        "criminal-history checks returned no adverse information. The omission was corrected "
        "promptly and is corroborated as complete."
    ),
    "why_this_recommendation": [
        {"reason": "The omitted trip was added by amended disclosure within eleven days of the cross-check.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-4-CHUNK-0"]},
        {"reason": "Border-crossing records confirm no unreported travel remains beyond the corrected trip.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-3-CHUNK-0"]},
        {"reason": "Both documented foreign contacts were disclosed on the security questionnaire before this review.", "category": "foreign_travel", "importance": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "No adverse information was developed in financial, employment, residence or criminal-history checks.", "category": "documentation", "importance": "moderate", "source_ids": ["DOC-1-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The applicant corrected the filing voluntarily and stated there is no other unreported travel.", "category": "foreign_travel", "source_ids": ["DOC-4-CHUNK-0"]},
        {"factor": "Neither foreign contact is indicated in the record as employed by a foreign government.", "category": "foreign_travel", "source_ids": ["DOC-5-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "The Canada trip was identified by record check rather than by the applicant's own disclosure.", "category": "foreign_travel", "severity": "low", "mitigation": "An amended disclosure was filed within eleven days and no further omission was found.", "human_review_consideration": "Consider whether a reporting-requirements briefing should be recorded.", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If further unreported foreign travel were identified in a later cross-check.",
        "If the amended disclosure could not be located in the filing system.",
        "If a foreign contact were later found to hold a foreign government position.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["marcus_dell"] = {
    # The model reads this as a reporting lapse and proposes an information
    # request. The evidence rules escalate. This is the divergence demo.
    "proposed_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
    "proposed_concern_level": "MODERATE",
    "executive_case_assessment": (
        "The completed investigation identified unreported foreign travel and an unreported "
        "foreign contact. Border-crossing records show five trips over the rolling 24-month "
        "period against two disclosed; the three undisclosed trips total 26 days, and two of them "
        "were to the same country within a four-month window. A continuing contact with a foreign "
        "national employed by a state-owned enterprise in that country, recorded on at least "
        "eleven occasions between July 2025 and January 2026, appears on no filing by the "
        "applicant and was identified through record review rather than disclosure. The applicant "
        "attributes the omissions to a belief that employer-arranged travel was reported on his "
        "behalf; the employer's records office has no record of arranging or reimbursing any "
        "travel for him in the period, so the explanation is uncorroborated. Financial, "
        "criminal-history, employment and residence checks returned no adverse information. The "
        "final decision belongs to the adjudicator."
    ),
    "why_this_recommendation": [
        {"reason": "Three foreign trips totalling 26 days were not reported, and were identified only by record check.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-3-CHUNK-0"]},
        {"reason": "A continuing contact with a foreign national employed by a state-owned enterprise was never reported by the applicant.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-4-CHUNK-0"]},
        {"reason": "The applicant's explanation that the travel was employer-arranged is contradicted by the employer's own records office.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-7-CHUNK-0"]},
        {"reason": "No mitigating documentation of any kind has been provided for either the travel or the contact.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-7-CHUNK-0"]},
        {"reason": "All other categories are clean: financial, criminal-history, employment and residence checks returned no adverse information.", "category": "documentation", "importance": "moderate", "source_ids": ["DOC-1-CHUNK-1"]},
    ],
    "factor_details": [
        {"factor": "The applicant responded to the questions put to him and offered to provide further detail.", "category": "documentation", "source_ids": ["DOC-5-CHUNK-0"]},
        {"factor": "Employment dates match the dates confirmed by both employers with no unexplained gaps.", "category": "employment", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "Three foreign trips totalling 26 days were not disclosed and surfaced only through record check.", "category": "foreign_travel", "severity": "high", "mitigation": "", "human_review_consideration": "Establish the purpose of each undisclosed trip and who arranged it.", "source_ids": ["DOC-3-CHUNK-0"]},
        {"concern": "A continuing foreign contact employed by a state-owned enterprise was never reported.", "category": "foreign_travel", "severity": "high", "mitigation": "", "human_review_consideration": "Establish the nature, duration and extent of the contact before adjudication.", "source_ids": ["DOC-4-CHUNK-0"]},
        {"concern": "The applicant's account of employer-arranged travel is not supported by the employer.", "category": "foreign_travel", "severity": "high", "mitigation": "", "human_review_consideration": "Ask the applicant to produce itineraries or reimbursement records.", "source_ids": ["DOC-7-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If employer travel records, itineraries or reimbursements supporting the applicant's account were produced.",
        "If the foreign contact were shown to have no state-enterprise employment.",
        "If the purpose of each undisclosed trip were documented and independently verified.",
    ],
}

ASSESSMENTS["elena_vasquez"] = {
    "proposed_recommendation": "ESCALATE_FOR_ENHANCED_REVIEW",
    "proposed_concern_level": "HIGH",
    "executive_case_assessment": (
        "The completed investigation contains an unresolved conflict about a single fact: when the "
        "applicant's employment with Sterling Grove Manufacturing ended. The employer's payroll "
        "system of record states June 2023, with the final payroll period ending June 30, 2023 and "
        "no payroll activity recorded afterwards. A former supervisor interviewed on March 19, "
        "2026 stated September 2023, based on recollection of a project timeline and without "
        "documentation. The applicant also reports September 2023 and has requested a separation "
        "letter and final pay statements, which are not in the package. The approximate "
        "three-month discrepancy is unresolved and no document in the package reconciles it. "
        "Financial, criminal-history, residence and travel checks returned no adverse information. "
        "Two independent records disagree on a material fact."
    ),
    "why_this_recommendation": [
        {"reason": "The employer's payroll system of record and the reference interview give different employment end dates for the same position.", "category": "employment", "importance": "high", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"]},
        {"reason": "No documentary evidence supporting the later date is present in the package.", "category": "employment", "importance": "high", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "The employer states no payroll activity is recorded after the June 2023 period, which the September account does not explain.", "category": "employment", "importance": "high", "source_ids": ["DOC-2-CHUNK-0"]},
        {"reason": "No adverse information was developed in any other category.", "category": "documentation", "importance": "moderate", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The applicant has requested the separation letter and final pay statements that would resolve the conflict.", "category": "employment", "source_ids": ["DOC-4-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "Three sources give two different employment end dates and the conflict is unresolved.", "category": "employment", "severity": "high", "mitigation": "", "human_review_consideration": "Determine which record governs and whether the discrepancy is material to the period under review.", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If the separation letter or final pay statements were produced.",
        "If the employer's payroll system were shown to have a recording error.",
        "If the reference could produce contemporaneous documentation.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["daniel_okonjo"] = {
    "proposed_recommendation": "ESCALATE_FOR_ENHANCED_REVIEW",
    "proposed_concern_level": "HIGH",
    "executive_case_assessment": (
        "The completed investigation identified three delinquent accounts totalling $31,400.00, "
        "all 90 or more days past due, with revolving utilisation at 97 percent. A civil judgment "
        "in favour of Halcyon Bank for $14,900.00 was entered in November 2025 and is recorded as "
        "unsatisfied. The applicant acknowledges the balances, attributes them to a period of "
        "reduced income in 2024 — corroborated by a confirmed three-month employment gap between "
        "February and May 2024 — and states that no repayment agreement is in place. No repayment "
        "agreement, settlement letter, counselling enrollment or payment receipt is present in the "
        "package for any account. Criminal-history, residence and travel checks returned no "
        "adverse information. The financial concerns are substantial, current and entirely "
        "unmitigated on the evidence available."
    ),
    "why_this_recommendation": [
        {"reason": "Three delinquent accounts totalling $31,400.00 are 90 or more days past due.", "category": "financial", "importance": "high", "source_ids": ["DOC-2-CHUNK-0"]},
        {"reason": "A civil judgment of $14,900.00 entered November 2025 remains unsatisfied in the record available.", "category": "financial", "importance": "high", "source_ids": ["DOC-2-CHUNK-0", "DOC-5-CHUNK-0"]},
        {"reason": "No repayment arrangement or mitigating documentation exists for any of the three accounts.", "category": "financial", "importance": "high", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "Revolving credit utilisation of 97 percent indicates continuing rather than resolved financial pressure.", "category": "financial", "importance": "high", "source_ids": ["DOC-2-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The applicant has been responsive to requests and has not disputed the accuracy of the reported balances.", "category": "financial", "source_ids": ["DOC-5-CHUNK-0"]},
        {"factor": "The employment record independently corroborates the stated period of reduced income.", "category": "employment", "source_ids": ["DOC-4-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "Three delinquent accounts totalling $31,400.00 remain unresolved with no repayment arrangement.", "category": "financial", "severity": "high", "mitigation": "", "human_review_consideration": "Establish the applicant's current position with each creditor before adjudication.", "source_ids": ["DOC-2-CHUNK-0"]},
        {"concern": "The November 2025 civil judgment is recorded as unsatisfied.", "category": "financial", "severity": "high", "mitigation": "", "human_review_consideration": "Verify the current status of the judgment against the public docket.", "source_ids": ["DOC-5-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If executed repayment or settlement agreements were produced for the accounts.",
        "If the civil judgment were shown to be satisfied.",
        "If credit counselling enrollment were documented and verified.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["sofia_lindqvist"] = {
    "proposed_recommendation": "PROCEED_TO_STANDARD_REVIEW",
    "proposed_concern_level": "LOW",
    "executive_case_assessment": (
        "The completed investigation identified one legal matter: a municipal noise ordinance "
        "citation from May 2023, disclosed by the applicant on the security questionnaire before "
        "record checks identified it. A court disposition record obtained March 25, 2026 confirms "
        "the matter was classified as a non-criminal infraction, resolved by a $250.00 fine paid "
        "in full, with the case closed and no arrest, probation or supervision associated. A "
        "criminal history check completed March 27, 2026 identified no felony records, misdemeanor "
        "convictions, arrests, protective orders or pending charges. Financial, employment, "
        "residence and travel checks returned no adverse information, and reported employment "
        "dates match the dates both employers confirmed. The disclosed matter is closed and fully "
        "corroborated."
    ),
    "why_this_recommendation": [
        {"reason": "The court record confirms the matter is closed as a non-criminal infraction with the fine paid in full.", "category": "legal_conduct", "importance": "high", "source_ids": ["DOC-3-CHUNK-0"]},
        {"reason": "The applicant disclosed the citation before record checks identified it, and the description matches the court record exactly.", "category": "legal_conduct", "importance": "high", "source_ids": ["DOC-6-CHUNK-0", "DOC-2-CHUNK-0"]},
        {"reason": "The criminal history check identified no other legal activity of any kind.", "category": "legal_conduct", "importance": "moderate", "source_ids": ["DOC-4-CHUNK-0"]},
        {"reason": "Employment dates match the dates confirmed by both employers with no unexplained gaps.", "category": "employment", "importance": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The matter was self-reported before discovery and the applicant's description matches the court record in every particular.", "category": "legal_conduct", "source_ids": ["DOC-6-CHUNK-0"]},
        {"factor": "The disposition involved no arrest, no probation and no continuing obligation.", "category": "legal_conduct", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "The underlying citation document itself is not in the package, only the disposition record.", "category": "legal_conduct", "severity": "low", "mitigation": "The disposition record independently establishes the charge, classification and outcome.", "human_review_consideration": "Confirm the disposition record is sufficient for the file.", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If the court disposition record could not be authenticated.",
        "If any further legal activity were identified in a repository not yet queried.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["thomas_achebe"] = {
    "proposed_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
    "proposed_concern_level": "MODERATE",
    "executive_case_assessment": (
        "The completed investigation verified two of three reported addresses. The address "
        "reported for November 2021 through August 2022 — approximately nine months — could not be "
        "verified through any lease, utility account, mail-forwarding record or landlord contact. "
        "The applicant states this was an informal cash sublet held in another person's name and "
        "that he continued using his prior mailing address during the period; a commercial data "
        "provider associates him with the earlier address through March 2022 and holds no entry "
        "for the unverified address. The investigator notes the applicant's explanation would "
        "reconcile both records but has not been verified, and two contact attempts to the named "
        "leaseholder went unanswered. Employment across the entire unverified period is fully "
        "verified, and financial, criminal-history and travel checks returned no adverse "
        "information. The gap is an absence of evidence rather than an adverse finding."
    ),
    "why_this_recommendation": [
        {"reason": "Approximately nine months of reported residence history is unverified by any source of record.", "category": "identity_background", "importance": "high", "source_ids": ["DOC-2-CHUNK-0"]},
        {"reason": "The named leaseholder has not responded to two contact attempts, leaving the applicant's explanation uncorroborated.", "category": "identity_background", "importance": "high", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "The applicant's explanation would reconcile the data-provider record, but the investigator records it as plausible rather than verified.", "category": "identity_background", "importance": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
        {"reason": "Verified continuous employment covers the entire unverified residence period.", "category": "employment", "importance": "moderate", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "Verified continuous employment covers the entire unverified residence period.", "category": "employment", "source_ids": ["DOC-6-CHUNK-0"]},
        {"factor": "The applicant supplied the leaseholder's contact information voluntarily.", "category": "identity_background", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "Nine months of residence history cannot be verified by any source in the package.", "category": "identity_background", "severity": "moderate", "mitigation": "Employment across the same period is fully verified.", "human_review_consideration": "Seek an alternative corroborating source before closing the residence history.", "source_ids": ["DOC-2-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If the named leaseholder responded and confirmed the sublet.",
        "If correspondence, payment records or references placed the applicant at the address.",
        "If the data provider produced an entry for the unverified address.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["hannah_ostrowski"] = {
    "proposed_recommendation": "PROCEED_TO_STANDARD_REVIEW",
    "proposed_concern_level": "NONE",
    "executive_case_assessment": (
        "The completed investigation identified no issue meeting the threshold for further review. "
        "The financial report dated April 2, 2026 shows no delinquent accounts, twelve current "
        "trade lines with no 30-day or greater delinquency in the prior 84 months, revolving "
        "utilisation at 6 percent, and no collections, judgments, liens or bankruptcies. "
        "Employment dates reported by the applicant match the dates confirmed by both employers of "
        "record with no unexplained gaps, and both reported addresses were verified through lease "
        "and utility records with no unverified periods. One foreign trip to Canada in July 2025 "
        "was disclosed and matches border-crossing records, with no undisclosed travel identified "
        "and no foreign contacts, financial interests or property reported. Two developed "
        "references corroborated the applicant's residence and employment history. Every reported "
        "item was corroborated by an independent source."
    ),
    "why_this_recommendation": [
        {"reason": "No issue meeting the threshold for further review was identified in any category.", "category": "documentation", "importance": "high", "source_ids": ["DOC-1-CHUNK-0"]},
        {"reason": "All reported information was corroborated by at least one independent source.", "category": "documentation", "importance": "high", "source_ids": ["DOC-6-CHUNK-0"]},
        {"reason": "The financial record shows no delinquency in the prior 84 months and 6 percent utilisation.", "category": "financial", "importance": "moderate", "source_ids": ["DOC-2-CHUNK-0"]},
        {"reason": "Residence history is continuous and fully verified with no unverified periods.", "category": "identity_background", "importance": "moderate", "source_ids": ["DOC-4-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "Two developed references corroborated the applicant's residence and employment history.", "category": "identity_background", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "concern_details": [],
    "what_could_change_recommendation": [
        "If the education verification record referenced in the summary could not be produced.",
        "If new adverse activity appeared in a later monitoring refresh.",
    ],
}

# ---------------------------------------------------------------------------
ASSESSMENTS["victor_ramachandran"] = {
    "proposed_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
    "proposed_concern_level": "MODERATE",
    "executive_case_assessment": (
        "The completed investigation identified three moderate indicators in separate categories. "
        "One installment account with Fernwood Savings reached 90 days past due in August 2025 and "
        "has been current since November 2025, with no other delinquency and no collections, "
        "judgments or liens. A September 2025 trip to Mexico was reported on January 30, 2026, "
        "approximately four months after return and outside the 30-day reporting window; "
        "border-crossing records identify no undisclosed travel. The applicant reported the title "
        "Senior Program Manager while the employer confirms Program Manager II for identical "
        "dates, and the employer confirms that internal working titles differ from payroll titles. "
        "The investigator records the financial and title items as resolved and the late travel "
        "filing as only partially resolved: whether the applicant had been briefed on the "
        "reporting window is not documented in the package."
    ),
    "why_this_recommendation": [
        {"reason": "The late foreign travel filing is established but the package does not record whether the applicant was briefed on the 30-day requirement.", "category": "foreign_travel", "importance": "high", "source_ids": ["DOC-6-CHUNK-0", "DOC-3-CHUNK-0"]},
        {"reason": "The financial item is resolved on the record: the account has been current since November 2025 with no other delinquency.", "category": "financial", "importance": "moderate", "source_ids": ["DOC-2-CHUNK-0"]},
        {"reason": "The title discrepancy is explained by the employer's confirmation that internal working titles differ from payroll titles, with dates matching exactly.", "category": "employment", "importance": "moderate", "source_ids": ["DOC-4-CHUNK-0", "DOC-6-CHUNK-0"]},
        {"reason": "The investigator framed the pattern across categories, rather than any single item, as the question for the adjudicator.", "category": "documentation", "importance": "moderate", "source_ids": ["DOC-6-CHUNK-0"]},
    ],
    "factor_details": [
        {"factor": "The delinquent account was brought current before the reinvestigation began and no other delinquency appears in the credit file.", "category": "financial", "source_ids": ["DOC-2-CHUNK-0"]},
        {"factor": "Employment dates match exactly for both positions; the discrepancy is confined to title.", "category": "employment", "source_ids": ["DOC-4-CHUNK-0"]},
        {"factor": "The applicant addressed all three items in a single statement and did not dispute any underlying record.", "category": "documentation", "source_ids": ["DOC-5-CHUNK-0"]},
    ],
    "concern_details": [
        {"concern": "A foreign trip was reported approximately four months after return, outside the 30-day window.", "category": "foreign_travel", "severity": "moderate", "mitigation": "Border-crossing records identify no undisclosed travel.", "human_review_consideration": "Establish whether the applicant received a reporting-requirements briefing.", "source_ids": ["DOC-3-CHUNK-0"]},
    ],
    "what_could_change_recommendation": [
        "If a record of a reporting-requirements briefing were produced.",
        "If further late or unreported travel were identified.",
        "If the account returned to delinquency after November 2025.",
    ],
}


# ---------------------------------------------------------------------------
# Evaluation-only ground truth. Written to evals/, never read by inference.
# ---------------------------------------------------------------------------
GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "alex_morgan": {
        "case_id": "PS-2026-00182",
        "expected_recommendation": "PROCEED_TO_STANDARD_REVIEW",
        "expected_concern_level": "LOW",
        "rationale": "A single financial concern with independently verified mitigation and no unresolved conflict.",
        "critical_evidence": ["payment_plan.txt", "financial_report.txt", "applicant_statement.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["March 14, 2026", "$18,500", "$325.00", "repayment"],
        "expected_reason_topics": ["financial", "monitoring", "employment", "foreign_travel"],
    },
    "jordan_reyes": {
        "case_id": "PS-2026-00194",
        "expected_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
        "expected_concern_level": "MODERATE",
        "rationale": "A documented discrepancy mostly reconciled by a third-party record, with one month corroborated by nothing.",
        "critical_evidence": ["staffing_agency_record.txt", "employment_history.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["February 8, 2021", "July 12, 2021", "January 2021"],
        "expected_reason_topics": ["employment"],
    },
    "priya_nandakumar": {
        "case_id": "PS-2026-00203",
        "expected_recommendation": "PROCEED_TO_STANDARD_REVIEW",
        "expected_concern_level": "LOW",
        "rationale": "A reporting omission corrected promptly by amended disclosure with no residual unreported travel.",
        "critical_evidence": ["amended_disclosure.txt", "travel_crosscheck.txt", "foreign_contact_review.txt"],
        "critical_evidence_terms": ["October 3-5, 2025", "amended disclosure", "five foreign trips"],
        "expected_reason_topics": ["foreign_travel"],
    },
    "marcus_dell": {
        "case_id": "PS-2026-00217",
        "expected_recommendation": "ESCALATE_FOR_ENHANCED_REVIEW",
        "expected_concern_level": "HIGH",
        "rationale": "Unreported foreign travel and an unreported foreign contact, with an explanation the employer does not support and no mitigating documentation.",
        "critical_evidence": ["travel_crosscheck.txt", "foreign_contact_review.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["five foreign trips", "state-owned enterprise", "no record of sponsoring"],
        "expected_reason_topics": ["foreign_travel", "documentation"],
    },
    "elena_vasquez": {
        "case_id": "PS-2026-00225",
        "expected_recommendation": "ESCALATE_FOR_ENHANCED_REVIEW",
        "expected_concern_level": "HIGH",
        "rationale": "Two independent records disagree on a material fact and nothing in the package resolves it.",
        "critical_evidence": ["employer_verification.txt", "reference_interview.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["June 2023", "September 2023", "final payroll"],
        "expected_reason_topics": ["employment"],
    },
    "daniel_okonjo": {
        "case_id": "PS-2026-00231",
        "expected_recommendation": "ESCALATE_FOR_ENHANCED_REVIEW",
        "expected_concern_level": "HIGH",
        "rationale": "Substantial current delinquency plus an unsatisfied civil judgment with no mitigation of any kind.",
        "critical_evidence": ["financial_report.txt", "investigator_notes.txt", "applicant_statement.txt"],
        "critical_evidence_terms": ["$31,400.00", "$14,900.00", "97 percent", "judgment"],
        "expected_reason_topics": ["financial"],
    },
    "sofia_lindqvist": {
        "case_id": "PS-2026-00240",
        "expected_recommendation": "PROCEED_TO_STANDARD_REVIEW",
        "expected_concern_level": "LOW",
        "rationale": "A single self-reported minor matter, closed and fully corroborated by a court record.",
        "critical_evidence": ["court_record.txt", "criminal_history_check.txt", "applicant_statement.txt"],
        "critical_evidence_terms": ["$250.00", "non-criminal infraction", "Closed"],
        "expected_reason_topics": ["legal_conduct"],
    },
    "thomas_achebe": {
        "case_id": "PS-2026-00248",
        "expected_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
        "expected_concern_level": "MODERATE",
        "rationale": "A nine-month evidence gap rather than an adverse finding; the package lacks corroboration.",
        "critical_evidence": ["residence_verification.txt", "third_party_address_record.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["nine months", "Not verified", "March 2022"],
        "expected_reason_topics": ["identity_background"],
    },
    "hannah_ostrowski": {
        "case_id": "PS-2026-00256",
        "expected_recommendation": "PROCEED_TO_STANDARD_REVIEW",
        "expected_concern_level": "NONE",
        "rationale": "No issue meeting the threshold for further review in any category.",
        "critical_evidence": ["financial_report.txt", "residence_verification.txt", "employment_history.txt"],
        "critical_evidence_terms": ["No delinquent accounts", "6 percent", "no unverified periods"],
        "expected_reason_topics": ["documentation", "financial", "identity_background"],
    },
    "victor_ramachandran": {
        "case_id": "PS-2026-00263",
        "expected_recommendation": "REQUEST_ADDITIONAL_INFORMATION",
        "expected_concern_level": "MODERATE",
        "rationale": "Two of three indicators are resolved; the late travel filing lacks the briefing record needed to close it.",
        "critical_evidence": ["travel_disclosure.txt", "employment_history.txt", "investigator_notes.txt"],
        "critical_evidence_terms": ["30 days", "January 30, 2026", "Program Manager II"],
        "expected_reason_topics": ["foreign_travel", "employment", "financial"],
    },
}
