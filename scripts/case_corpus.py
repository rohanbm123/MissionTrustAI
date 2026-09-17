"""Synthetic case corpus for CaseBrief.

FICTIONAL DEMONSTRATION DATA. Every applicant, employer, account, address and
event below is invented for this prototype. Nothing here is derived from, or
representative of, any real person, investigation, agency or commercial system.

Each entry supplies:
  * case metadata + a chronological timeline
  * 5-8 generic adjudication-style documents
  * a curated `demo_analysis` used when DEMO_MODE is on

The demo analysis only stands in for the *generation* step. Retrieval, evidence
linking, claim scoring, contradiction detection and metrics always run for real
against the ingested documents.
"""
from __future__ import annotations

from typing import Any, Dict, List

BANNER = "FICTIONAL DEMONSTRATION DATA — NOT A REAL CASE RECORD"


def doc(file: str, name: str, dtype: str, body: str) -> Dict[str, str]:
    return {
        "file": file,
        "document_name": name,
        "document_type": dtype,
        "text": f"{BANNER}\n\n{name.upper()}\n\n{body.strip()}\n",
    }


CASES: List[Dict[str, Any]] = []

# ===========================================================================
# CASE 1 — Alex Morgan: financial delinquency with mitigation (flagship demo)
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00182",
        "applicant_name": "Alex Morgan",
        "slug": "alex_morgan",
        "key_signal": "Financial delinquency with documented mitigation",
        "scenario": "financial_delinquency_with_mitigation",
        "opened_on": "2026-01-20",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-01-20", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-02-04", "label": "Financial delinquency reported", "detail": "Credit report shows an $18,500 delinquent account (Meridian Regional Health Services).", "category": "financial"},
            {"date": "2026-02-19", "label": "Applicant notified of financial issue", "detail": "Request for explanation issued to applicant.", "category": "administrative"},
            {"date": "2026-03-14", "label": "Repayment plan effective", "detail": "Structured repayment agreement begins; $325 monthly.", "category": "financial"},
            {"date": "2026-03-18", "label": "Applicant statement submitted", "detail": "Applicant attributes the debt to disputed medical billing.", "category": "statement"},
            {"date": "2026-04-02", "label": "Foreign travel disclosure filed", "detail": "Germany (Sept 2025) and Singapore (Nov 2025) reported.", "category": "travel"},
            {"date": "2026-05-02", "label": "Continuous monitoring alert", "detail": "Automated alert references the same Meridian account.", "category": "monitoring"},
            {"date": "2026-05-06", "label": "Investigator notes recorded", "detail": "Payment history verified against servicer records.", "category": "investigative"},
        ],
        "documents": [
            doc(
                "background_investigation_summary.txt",
                "Background Investigation Summary",
                "investigation_summary",
                """
Case Number: PS-2026-00182
Subject: Alex Morgan
Investigation Type: Periodic reinvestigation
Period Covered: January 2019 through January 2026

SCOPE
This summary consolidates record checks, employment verification, residence
verification, financial record review and the subject's own disclosures for the
period under review. It does not contain a recommendation or determination.

SUMMARY OF RECORD CHECKS
Employment history was verified with two employers of record. Residence history
was verified for three addresses over the seven-year period with no unexplained
gaps. Criminal history checks returned no records. Foreign travel disclosures
were received and cross-checked against the subject's submitted itinerary.

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Financial: One delinquent account in the amount of $18,500 appearing on the
   February 2026 consumer credit report, originating with Meridian Regional
   Health Services. The subject has submitted an explanation and supporting
   documentation.
2. Continuous monitoring: One automated alert generated in May 2026 referencing
   an account with the same originating creditor.

ITEMS WITH NO ADVERSE INFORMATION
Criminal history, employment verification, residence verification, education
verification, and foreign contact reporting returned no adverse information
during the period under review.

Prepared by: Investigative Support Unit 4 (fictional)
Date: 2026-05-08
""",
            ),
            doc(
                "financial_report.txt",
                "Financial Report",
                "financial_report",
                """
Report Date: 2026-02-04
Subject: Alex Morgan
Source: Consolidated consumer credit file (synthetic)

DELINQUENT ACCOUNT
Creditor: Meridian Regional Health Services
Account reference: MRH-4471-22
Balance reported delinquent: $18,500.00
Date first reported delinquent: February 4, 2026
Days past due at reporting: 121
Account status at reporting: Referred to third-party collection agent

ACCOUNT NOTES
The creditor's file annotation records that the account is "in dispute by the
consumer" and that the disputed amount relates to a series of billed services
rendered between March and July 2025. The consumer's dispute was filed with the
creditor on December 9, 2025.

OTHER ACCOUNTS
Six additional trade lines are reported. All are current with no history of
delinquency over the prior 24 months. Total non-mortgage revolving utilisation
is 19 percent. No bankruptcies, liens, judgments or civil filings appear in the
record. No repossession or foreclosure activity is recorded.

TOTALS
Total delinquent balance across all accounts: $18,500.00
Number of accounts 90+ days past due: 1
""",
            ),
            doc(
                "applicant_statement.txt",
                "Applicant Statement",
                "applicant_statement",
                """
Submitted: March 18, 2026
Subject: Alex Morgan
Regarding: Delinquent account reported February 2026

I am providing this statement to explain the delinquent balance that appeared on
my credit report in February 2026.

In 2025 I received treatment at a facility operated by Meridian Regional Health
Services. My insurer processed part of the claim and denied the remainder, and I
was billed for services I believed were covered under my plan. I filed a written
dispute with the billing office in December 2025 asking for an itemised
statement and a review of the denied portion. I did not receive a response
before the account was referred to collections.

Once I understood that the account had gone to collections, I contacted the
collection agent directly and entered a payment agreement. I entered a payment
agreement in March and I have made every scheduled payment since it began. I am
paying $325 per month.

I did not attempt to conceal this debt. I reported it on my security
questionnaire and I have provided the payment agreement and my payment receipts.
The dispute with the insurer is still open and I will provide the outcome when I
receive it.

Signed: Alex Morgan
""",
            ),
            doc(
                "payment_plan.txt",
                "Payment Plan Document",
                "payment_plan",
                """
Servicer: Cascade Recovery Services (fictional)
Consumer: Alex Morgan
Reference: MRH-4471-22

STRUCTURED REPAYMENT AGREEMENT
Plan effective date: March 14, 2026
Original balance placed: $18,500.00
Agreed monthly payment: $325.00
Payment method: Automatic debit, 14th of each month
Term: 60 months, subject to redetermination if the underlying dispute resolves

PAYMENT HISTORY AS OF MAY 1, 2026
March 14, 2026 — $325.00 — Received
April 14, 2026 — $325.00 — Received
Balance as of May 1, 2026: $17,850.00
Payments missed to date: 0

NOTES
The consumer's billing dispute with the originating creditor remains open. This
agreement does not waive the consumer's dispute rights. The servicer has
recorded the account as "paying as agreed" for the period covered.
""",
            ),
            doc(
                "employment_history.txt",
                "Employment History",
                "employment_history",
                """
Subject: Alex Morgan
Verification completed: 2026-02-27

POSITION 1
Employer: Northgate Systems Group (fictional)
Title: Senior Systems Analyst
Dates: June 2022 to present
Verified with: Employer records office
Separation reason: N/A — current employer

POSITION 2
Employer: Harbor Point Technologies (fictional)
Title: Systems Analyst
Dates: March 2019 to May 2022
Verified with: Employer records office
Separation reason: Voluntary resignation, accepted other employment

GAPS
No unexplained gaps in employment exceeding 30 days were identified for the
period under review. The dates reported by the subject on the security
questionnaire match the dates confirmed by both employers of record.
""",
            ),
            doc(
                "travel_disclosure.txt",
                "Foreign Travel Disclosure",
                "travel_disclosure",
                """
Submitted: April 2, 2026
Subject: Alex Morgan

REPORTED FOREIGN TRAVEL (rolling 24 months)

1. Germany
   Dates: September 8-16, 2025
   Purpose: Personal travel / vacation
   Sponsor or host: None
   Foreign national contacts of significance: None reported

2. Singapore
   Dates: November 3-9, 2025
   Purpose: Employer-sponsored technical conference
   Sponsor or host: Northgate Systems Group
   Foreign national contacts of significance: Conference attendees only;
   no continuing contact reported

CROSS-CHECK
Border-crossing record checks for the rolling 24-month period returned entries
consistent with the two trips reported above. No additional foreign travel was
identified during the period covered, and no undisclosed travel was identified.
""",
            ),
            doc(
                "monitoring_alert.txt",
                "Continuous Monitoring Alert",
                "monitoring_alert",
                """
Alert ID: CM-2026-77431
Generated: May 2, 2026, 03:14 UTC
Subject: Alex Morgan
Alert category: Financial — adverse account activity

ALERT DETAIL
An automated record refresh identified a collection account associated with the
subject. Creditor of record: Meridian Regional Health Services. Account
reference: MRH-4471-22. Reported balance at refresh: $17,850.00.

CORRELATION
This alert references the same originating creditor and account reference as the
delinquency reported in the February 4, 2026 financial report. The alerting
system does not evaluate mitigation and does not know whether a repayment
arrangement exists. Analyst correlation is required before this alert is treated
as a new or separate issue.

DISPOSITION
Routed to the assigned analyst for correlation with existing case material. No
automated action was taken. This alert is informational and is not a finding.
""",
            ),
            doc(
                "investigator_notes.txt",
                "Case Notes",
                "case_notes",
                """
Analyst: Investigator R. Ellery (fictional)
Entry date: May 6, 2026

Contacted Cascade Recovery Services and confirmed the structured repayment
agreement referenced by the subject. The servicer confirmed a plan effective
date of March 14, 2026 and two payments received on schedule. The servicer
confirmed no missed payments as of the date of contact.

Reviewed the May 2, 2026 continuous monitoring alert. The account reference in
the alert matches the account already documented in the February 2026 financial
report. In my assessment this alert reflects the same underlying account rather
than a second, separate delinquency, but this correlation should be confirmed by
the reviewing adjudicator.

The subject's billing dispute with the originating creditor is still open. The
outcome of that dispute is not in the record and is a documented gap.

No information developed during this period suggests concealment. The subject
self-reported the debt on the security questionnaire before it was identified
through record checks.

This entry contains no recommendation or determination.
""",
            ),
        ],
        "known_contradictions": [],
        "demo_analysis": {
            "executive_summary": (
                "The case file documents one financial issue and one related continuous-monitoring "
                "alert, both traceable to a single originating account. An $18,500 delinquent account "
                "with Meridian Regional Health Services was first reported delinquent on February 4, "
                "2026. The applicant states the balance arose from disputed medical billing following "
                "a partial insurance denial, and the file contains a structured repayment agreement "
                "with an effective date of March 14, 2026 at $325 per month, with two payments "
                "received and none missed as of May 1, 2026. A continuous-monitoring alert generated "
                "May 2, 2026 references the same creditor and account reference as the February "
                "report; investigator notes assess it as the same underlying account rather than a "
                "separate delinquency. Foreign travel to Germany and Singapore was disclosed and is "
                "consistent with border-crossing record checks. The outcome of the applicant's billing "
                "dispute is not in the record. This summary is informational and is not a determination; "
                "all findings require human verification."
            ),
            "key_findings": [
                {"finding": "A single delinquent account of $18,500 with Meridian Regional Health Services was first reported delinquent on February 4, 2026.", "category": "financial", "severity": "high", "source_ids": ["DOC-2-CHUNK-0"]},
                {"finding": "A structured repayment agreement effective March 14, 2026 is documented, with two scheduled payments received and no missed payments as of May 1, 2026.", "category": "financial_mitigation", "severity": "low", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "The May 2, 2026 continuous-monitoring alert references the same creditor and account reference as the February 2026 financial report and may not represent a separate issue.", "category": "monitoring", "severity": "moderate", "source_ids": ["DOC-7-CHUNK-0"]},
                {"finding": "No adverse information was developed for criminal history, employment verification, residence verification or foreign contact reporting during the period under review.", "category": "general", "severity": "informational", "source_ids": ["DOC-1-CHUNK-1"]},
            ],
            "claims": [
                {"claim_text": "A delinquent account of $18,500 with Meridian Regional Health Services was first reported delinquent on February 4, 2026.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.96},
                {"claim_text": "The account was 121 days past due at the time of reporting and had been referred to a third-party collection agent.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant states the debt resulted from disputed medical billing after an insurer denied part of a 2025 claim.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The applicant filed a written billing dispute with the creditor in December 2025.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0", "DOC-2-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "The applicant entered a structured repayment plan with an effective date of March 14, 2026.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0", "DOC-3-CHUNK-0"], "confidence": 0.96},
                {"claim_text": "The agreed monthly payment under the repayment plan is $325.00, paid by automatic debit.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Two scheduled payments were received in March and April 2026 and no payments have been missed as of May 1, 2026.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0", "DOC-8-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Six additional trade lines are reported as current with no delinquency over the prior 24 months.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-1"], "confidence": 0.9},
                {"claim_text": "A continuous-monitoring alert generated on May 2, 2026 references the same creditor and account reference as the February 2026 financial report.", "claim_type": "potential_concern", "source_ids": ["DOC-7-CHUNK-0"], "confidence": 0.91},
                {"claim_text": "The investigator assessed the monitoring alert as reflecting the same underlying account rather than a second, separate delinquency.", "claim_type": "mitigation", "source_ids": ["DOC-8-CHUNK-0"], "confidence": 0.88},
                {"claim_text": "The applicant disclosed foreign travel to Germany in September 2025 and to Singapore in November 2025.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Border-crossing record checks identified no foreign travel beyond the two disclosed trips during the rolling 24-month period.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "Employment dates reported by the applicant match the dates confirmed by both employers of record, with no unexplained gaps.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The applicant's insurer has since reversed the denial and reimbursed the disputed medical charges in full.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.55},
            ],
            "mitigating_information": [
                "The debt was self-reported by the applicant on the security questionnaire before it was identified through record checks (Case Notes).",
                "A structured repayment agreement is in place and is being paid as agreed, with zero missed payments recorded (Payment Plan Document).",
                "The balance originates from a single disputed medical account rather than a pattern of financial irresponsibility; all other trade lines are current (Financial Report).",
            ],
            "missing_information": [
                "The outcome of the applicant's billing dispute with the originating creditor is not in the record.",
                "No itemised statement from the creditor substantiating the disputed service charges is present in the file.",
                "Payment history after May 1, 2026 has not been refreshed in the case material.",
            ],
            "potential_conflicts": [],
            "requires_human_review": True,
        },
    }
)


# ===========================================================================
# CASE 2 — Jordan Reyes: employment discrepancy
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00194",
        "applicant_name": "Jordan Reyes",
        "slug": "jordan_reyes",
        "key_signal": "Unresolved employment-history discrepancy",
        "scenario": "employment_discrepancy",
        "opened_on": "2026-02-02",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-02-02", "label": "Case opened", "detail": "Initial investigation initiated.", "category": "administrative"},
            {"date": "2026-02-21", "label": "Employment verification returned", "detail": "Employer record conflicts with the applicant's questionnaire entry.", "category": "employment"},
            {"date": "2026-03-05", "label": "Applicant statement submitted", "detail": "Applicant describes a contract-to-permanent conversion.", "category": "statement"},
            {"date": "2026-03-27", "label": "Staffing agency record received", "detail": "Agency confirms a contract assignment covering the disputed period.", "category": "employment"},
            {"date": "2026-04-08", "label": "Case notes recorded", "detail": "Discrepancy partially reconciled; one month remains unverified.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00194
Subject: Jordan Reyes
Investigation Type: Initial investigation
Period Covered: February 2019 through February 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Employment: The employment dates reported by the subject for one prior
   employer do not match the dates confirmed by that employer's records office.
2. Documentation: A third-party staffing agency record has been introduced to
   explain part of the discrepancy and requires analyst reconciliation.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, residence verification and
foreign travel reporting returned no adverse information for the period covered.
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Jordan Reyes
Verification completed: 2026-02-21

POSITION 1
Employer: Vantage Analytics Partners (fictional)
Title: Data Operations Specialist
Dates as reported by subject: January 2021 to present
Dates confirmed by employer: July 2021 to present
Verification note: The employer's records office states the subject's
permanent employment start date is July 12, 2021. The employer's records office
has no record of employment before that date.

POSITION 2
Employer: Fairmont Logistics Group (fictional)
Title: Operations Coordinator
Dates as reported by subject: April 2019 to December 2020
Dates confirmed by employer: April 2019 to December 2020
Verification note: Dates match. No discrepancy.

DISCREPANCY
A gap of approximately six months exists between the start date reported by the
subject for Position 1 and the start date confirmed by the employer.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: March 5, 2026
Subject: Jordan Reyes

I am writing to explain the difference between the employment start date I
reported and the date my employer confirmed.

I began working at Vantage Analytics Partners in January 2021 as a contractor
placed through a staffing agency. I worked on site, on the same team, doing the
same work. In July 2021 the company converted my role to a permanent position
and I was placed on their payroll directly. When I completed the questionnaire I
reported the date I actually started the work, which was January 2021, not the
date my employment status changed.

I did not intend to misstate anything. I have asked the staffing agency to
provide a record of my assignment dates and I will submit that record.

Signed: Jordan Reyes
"""),
            doc("staffing_agency_record.txt", "Staffing Agency Record", "third_party_record", """
Agency: Beacon Workforce Solutions (fictional)
Worker: Jordan Reyes
Record produced: March 27, 2026

ASSIGNMENT RECORD
Client of record: Vantage Analytics Partners
Assignment start date: February 8, 2021
Assignment end date: July 9, 2021
Assignment type: Full-time contract placement
Conversion: Worker converted to direct client employment effective July 12, 2021

NOTE
The agency's record shows the assignment beginning in February 2021. The agency
has no record of any placement of this worker with this client during January
2021.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator D. Kavanagh (fictional)
Entry date: April 8, 2026

The staffing agency record reconciles most of the discrepancy: the subject was
working at the client site from February 2021 under a contract placement and
converted to direct employment in July 2021. This is consistent with the
subject's explanation of the difference.

One month remains unreconciled. The subject reported a January 2021 start; the
agency record begins February 8, 2021 and the agency states it has no record of a
placement in January 2021. The reason for the one-month difference has not been
established and should be resolved by the reviewing adjudicator.

No information developed suggests a deliberate misstatement. This entry contains
no recommendation or determination.
"""),
            doc("financial_report.txt", "Financial Report", "financial_report", """
Report Date: 2026-02-18
Subject: Jordan Reyes
Source: Consolidated consumer credit file (synthetic)

No delinquent accounts are reported. Nine trade lines are reported, all current.
Non-mortgage revolving utilisation is 11 percent. No collections, judgments,
liens, bankruptcies or civil filings appear in the record for the period covered.
"""),
        ],
        "known_contradictions": [
            {
                "field": "employment_start_date",
                "note": "Applicant reports a January 2021 start; the staffing agency record begins February 8, 2021 and the employer confirms July 12, 2021.",
            }
        ],
        "demo_analysis": {
            "executive_summary": (
                "The case file documents an employment-history discrepancy that is partially, but not "
                "fully, reconciled. The applicant reported a January 2021 start date with Vantage "
                "Analytics Partners; the employer's records office confirms a permanent start date of "
                "July 12, 2021. A staffing agency record shows a contract placement with the same "
                "client running February 8, 2021 to July 9, 2021, converting to direct employment on "
                "July 12, 2021, which is consistent with the applicant's explanation that the reported "
                "date reflected when the work began rather than when employment status changed. "
                "Approximately one month between the reported January start and the February 8 "
                "assignment start remains unexplained in the record. No other adverse information was "
                "developed. This summary is informational and is not a determination."
            ),
            "key_findings": [
                {"finding": "Reported and employer-confirmed start dates for Vantage Analytics Partners differ by approximately six months.", "category": "employment", "severity": "moderate", "source_ids": ["DOC-2-CHUNK-0"]},
                {"finding": "A staffing agency record accounts for most of the difference through a contract-to-permanent conversion.", "category": "employment_mitigation", "severity": "low", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "Approximately one month of the reported period remains unverified by any record in the file.", "category": "employment", "severity": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "The applicant reported a start date of January 2021 for Vantage Analytics Partners.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The employer's records office confirmed a permanent employment start date of July 12, 2021.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "The applicant states the role began as a contract placement through a staffing agency and converted to permanent employment in July 2021.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The staffing agency record shows an assignment start date of February 8, 2021 and an end date of July 9, 2021.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "The staffing agency has no record of any placement of the applicant with this client during January 2021.", "claim_type": "potential_concern", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "The investigator recorded that one month of the reported period remains unreconciled.", "claim_type": "potential_concern", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.91},
                {"claim_text": "The financial record review identified no delinquent accounts, collections, judgments or liens.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Employment dates for Fairmont Logistics Group as reported by the applicant match the dates confirmed by that employer.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.9},
            ],
            "mitigating_information": [
                "The applicant volunteered an explanation before the agency record was obtained, and the record substantiates the substance of that explanation (Applicant Statement; Staffing Agency Record).",
                "The investigator recorded that no information developed suggests a deliberate misstatement (Case Notes).",
            ],
            "missing_information": [
                "No record accounts for the period between the reported January 2021 start and the February 8, 2021 assignment start.",
                "No payroll or timesheet record for January 2021 is present in the file.",
            ],
            "potential_conflicts": [
                {"description": "Three different start dates appear in the record for the same position: January 2021 (applicant), February 8, 2021 (staffing agency) and July 12, 2021 (employer).", "source_ids": ["DOC-2-CHUNK-0", "DOC-4-CHUNK-0"], "conflicting_field": "employment_start_date"}
            ],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 3 — Priya Nandakumar: foreign travel disclosure
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00203",
        "applicant_name": "Priya Nandakumar",
        "slug": "priya_nandakumar",
        "key_signal": "Foreign travel and contact reporting under review",
        "scenario": "foreign_travel_disclosure",
        "opened_on": "2026-01-09",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-01-09", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-01-30", "label": "Travel disclosure filed", "detail": "Four foreign trips reported over 24 months.", "category": "travel"},
            {"date": "2026-02-14", "label": "Border-crossing cross-check", "detail": "One trip identified that was not on the original disclosure.", "category": "travel"},
            {"date": "2026-02-25", "label": "Amended disclosure submitted", "detail": "Applicant files an amended disclosure adding the trip.", "category": "statement"},
            {"date": "2026-03-11", "label": "Foreign contact review", "detail": "Two continuing foreign contacts documented and assessed.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00203
Subject: Priya Nandakumar
Investigation Type: Periodic reinvestigation
Period Covered: January 2019 through January 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Foreign travel: One trip identified by record check that did not appear on
   the subject's original disclosure. The subject filed an amended disclosure.
2. Foreign contacts: Two continuing foreign national contacts are documented and
   require analyst assessment.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, employment verification and
residence verification returned no adverse information for the period covered.
"""),
            doc("travel_disclosure.txt", "Foreign Travel Disclosure", "travel_disclosure", """
Submitted: January 30, 2026
Subject: Priya Nandakumar

REPORTED FOREIGN TRAVEL (rolling 24 months)
1. India — March 2-19, 2025 — Family visit — No sponsor
2. United Kingdom — June 5-9, 2025 — Employer-sponsored conference
3. Japan — August 11-18, 2025 — Personal travel
4. India — December 20, 2025 to January 4, 2026 — Family visit — No sponsor

The subject reported no foreign financial interests and no foreign property.
"""),
            doc("travel_crosscheck.txt", "Travel Record Cross-Check", "record_check", """
Cross-check completed: February 14, 2026
Subject: Priya Nandakumar

Border-crossing records for the rolling 24-month period identify five foreign
trips. Four correspond to the trips reported on the disclosure filed January 30,
2026.

ADDITIONAL TRIP IDENTIFIED
Destination: Canada
Dates: October 3-5, 2025
This trip does not appear on the original disclosure filed January 30, 2026.

No other unreported foreign travel was identified during the period covered.
"""),
            doc("amended_disclosure.txt", "Amended Travel Disclosure", "applicant_statement", """
Submitted: February 25, 2026
Subject: Priya Nandakumar

I am filing an amended disclosure to add a trip I did not include on my original
form.

I travelled to Canada from October 3 to October 5, 2025 for a weekend to attend a
family wedding. I did not report it because I did not think a short personal trip
by car required reporting. I understand now that all foreign travel must be
reported regardless of duration or destination.

There was no sponsor and no foreign government contact associated with this trip.
I have no other unreported travel.

Signed: Priya Nandakumar
"""),
            doc("foreign_contact_review.txt", "Foreign Contact Review", "investigation_summary", """
Review date: March 11, 2026
Subject: Priya Nandakumar

CONTACT 1
Relationship: Immediate family member (parent), resident in India
Frequency: Weekly
Assessment: Reported on the security questionnaire. Familial relationship,
consistently disclosed across filings.

CONTACT 2
Relationship: Former university classmate, resident in the United Kingdom
Frequency: Several times per year, social
Assessment: Reported on the security questionnaire. No employment by a foreign
government is indicated in the record.

No foreign financial interest, foreign property or foreign government
affiliation was identified for either contact during the period covered.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator M. Okafor (fictional)
Entry date: March 14, 2026

The unreported Canada trip was identified through record check rather than by
the subject's own disclosure. The subject filed an amended disclosure eleven days
after the cross-check was completed and described the omission as a
misunderstanding of the reporting requirement.

Whether the omission reflects a reporting-standard misunderstanding or a broader
disclosure concern is a judgment for the reviewing adjudicator. The record
contains no evidence of any other unreported travel.

This entry contains no recommendation or determination.
"""),
        ],
        "known_contradictions": [
            {"field": "foreign_travel_count", "note": "Original disclosure lists four trips; border-crossing records identify five."}
        ],
        "demo_analysis": {
            "executive_summary": (
                "The applicant filed a foreign travel disclosure on January 30, 2026 reporting four "
                "trips over the rolling 24-month period. A border-crossing cross-check completed "
                "February 14, 2026 identified five trips, including a Canada trip of October 3-5, 2025 "
                "that did not appear on the original disclosure. The applicant filed an amended "
                "disclosure on February 25, 2026 adding that trip and describing the omission as a "
                "misunderstanding of the reporting requirement. No other unreported travel was "
                "identified. Two continuing foreign contacts are documented, both previously reported, "
                "with no foreign government affiliation or foreign financial interest identified. "
                "This summary is informational and is not a determination."
            ),
            "key_findings": [
                {"finding": "One foreign trip was identified by record check that did not appear on the original disclosure.", "category": "foreign_travel", "severity": "moderate", "source_ids": ["DOC-3-CHUNK-0"]},
                {"finding": "The applicant filed an amended disclosure adding the omitted trip within eleven days of the cross-check.", "category": "foreign_travel", "severity": "low", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "Two continuing foreign contacts are documented, both previously reported on the security questionnaire.", "category": "foreign_contacts", "severity": "informational", "source_ids": ["DOC-5-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "The original disclosure filed January 30, 2026 reported four foreign trips over the rolling 24-month period.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Border-crossing records identified five foreign trips during the same period.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "A trip to Canada from October 3 to October 5, 2025 did not appear on the original disclosure.", "claim_type": "potential_concern", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "The applicant filed an amended disclosure on February 25, 2026 adding the Canada trip.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The applicant attributed the omission to a belief that short personal trips did not require reporting.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "No unreported foreign travel other than the Canada trip was identified during the period covered.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "Neither documented foreign contact is indicated in the record as being employed by a foreign government.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.89},
                {"claim_text": "The applicant reported no foreign financial interests and no foreign property.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.9},
            ],
            "mitigating_information": [
                "The amended disclosure was filed within eleven days of the cross-check and the applicant stated there is no other unreported travel (Amended Travel Disclosure).",
                "Both foreign contacts were disclosed on the security questionnaire before this review (Foreign Contact Review).",
            ],
            "missing_information": [
                "The record does not establish whether the applicant was briefed on the reporting standard for short personal trips.",
                "No corroborating documentation for the purpose of the Canada trip is present in the file.",
            ],
            "potential_conflicts": [
                {"description": "The original disclosure reports four trips while border-crossing records identify five for the same period.", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"], "conflicting_field": "foreign_travel_count"}
            ],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 4 — Marcus Dell: undisclosed foreign travel and an unreported contact
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00217",
        "applicant_name": "Marcus Dell",
        "slug": "marcus_dell",
        "key_signal": "Undisclosed foreign travel and an unreported foreign contact",
        "scenario": "undisclosed_foreign_travel",
        "opened_on": "2026-01-15",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-01-15", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-02-06", "label": "Foreign travel disclosure filed", "detail": "Applicant reports two trips over the rolling 24 months.", "category": "travel"},
            {"date": "2026-03-01", "label": "Border-crossing cross-check", "detail": "Records identify five trips; three were not disclosed.", "category": "travel"},
            {"date": "2026-03-22", "label": "Foreign contact identified", "detail": "Record review identifies a continuing contact not reported by the applicant.", "category": "travel"},
            {"date": "2026-04-17", "label": "Applicant statement submitted", "detail": "Applicant attributes the omissions to a reporting misunderstanding.", "category": "statement"},
            {"date": "2026-05-04", "label": "Investigator notes recorded", "detail": "Explanation not corroborated by the employer or any record.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00217
Subject: Marcus Dell
Investigation Type: Periodic reinvestigation
Period Covered: January 2019 through January 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Foreign travel: Border-crossing records identify five foreign trips during the
   rolling 24-month period. The subject disclosed two. Three trips were not
   reported.
2. Foreign contacts: A continuing contact with a foreign national employed by a
   state-owned enterprise was identified through record review. The contact does
   not appear on any filing by the subject.
3. The subject's explanation for the omissions is not corroborated by the
   employer or by any record in the package.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, employment verification and
residence verification returned no adverse information for the period covered.
"""),
            doc("travel_disclosure.txt", "Foreign Travel Disclosure", "travel_disclosure", """
Submitted: February 6, 2026
Subject: Marcus Dell

REPORTED FOREIGN TRAVEL (rolling 24 months)

1. Ireland
   Dates: May 4-11, 2025
   Purpose: Personal travel / vacation
   Sponsor or host: None

2. Canada
   Dates: September 12-15, 2025
   Purpose: Personal travel / vacation
   Sponsor or host: None

The subject reported no foreign financial interests, no foreign property and no
continuing foreign national contacts.
"""),
            doc("travel_crosscheck.txt", "Travel Record Cross-Check", "record_check", """
Cross-check completed: March 1, 2026
Subject: Marcus Dell

Border-crossing records for the rolling 24-month period identify five foreign
trips. Two correspond to the disclosure filed February 6, 2026.

TRIPS NOT APPEARING ON THE DISCLOSURE

1. Destination withheld pending review (Country A)
   Dates: July 8-19, 2025
   Duration: 11 days

2. Destination withheld pending review (Country A)
   Dates: November 2-13, 2025
   Duration: 11 days

3. Destination withheld pending review (Country B)
   Dates: January 6-10, 2026
   Duration: 4 days

Two of the three undisclosed trips were to the same country within a four-month
period. The combined duration of the undisclosed travel is 26 days.
"""),
            doc("foreign_contact_review.txt", "Foreign Contact Review", "investigation_summary", """
Review date: March 22, 2026
Subject: Marcus Dell

CONTACT IDENTIFIED THROUGH RECORD REVIEW
Relationship: Continuing personal contact, first recorded July 2025
Residence: Country A
Employment: Employed by a state-owned enterprise (synthetic record)
Frequency: Contact recorded on at least eleven occasions between July 2025 and
January 2026

REPORTING STATUS
This contact does not appear on the subject's security questionnaire, on the
travel disclosure filed February 6, 2026, or on any subsequent filing. The
contact was identified through record review rather than by the subject.

No foreign financial interest or foreign property was identified for the subject.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: April 17, 2026
Subject: Marcus Dell

I want to respond to the questions about my travel.

The trips I did not list were work-related. I understood that travel arranged
through my employer was reported by the company on my behalf and did not need to
appear on my personal disclosure. I now understand that is not correct and I
should have listed every trip myself.

Regarding the contact, this is a personal friendship. I did not think a friend I
met while travelling needed to be reported. I was not aware of where they work.

I did not intend to withhold anything. I am willing to provide further detail if
required.

Signed: Marcus Dell
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Marcus Dell
Verification completed: 2026-02-24

POSITION 1
Employer: Ridgeline Freight Services (fictional)
Title: Operations Supervisor
Dates confirmed by employer: March 2021 to present

POSITION 2
Employer: Calder Distribution Company (fictional)
Title: Logistics Coordinator
Dates confirmed by employer: August 2017 to February 2021

Reported dates match confirmed dates for both positions. No unexplained gaps were
identified during the period under review.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator L. Prieto (fictional)
Entry date: May 4, 2026

I contacted the employer's travel office regarding the subject's account that the
undisclosed trips were arranged through the company. The employer's records
office states it has no record of sponsoring, arranging or reimbursing any travel
for this subject during the period covered. The subject's explanation is not
corroborated by the employer.

The subject stated he was unaware of the contact's employer. The record review
established the contact's employment through open sources available since 2024.

Three unreported trips totalling 26 days, two of them to the same country, sit
alongside an unreported continuing contact in that same country. Whether these
facts are connected has not been established and should not be assumed. They are
recorded here together because they concern the same period and the same country.

No mitigating documentation has been provided. This entry contains no
recommendation or determination.
"""),
        ],
        "known_contradictions": [],
        "demo_analysis": {
            "executive_summary": (
                "Border-crossing records identify five foreign trips over the rolling 24-month "
                "period; the applicant disclosed two. Three trips totalling 26 days were not "
                "reported, two of them to the same country within a four-month window. A continuing "
                "foreign contact employed by a state-owned enterprise in that country, recorded on at "
                "least eleven occasions, appears on no filing by the applicant and was identified "
                "through record review. The applicant states the trips were employer-arranged and "
                "reported on his behalf; the employer's records office has no record of arranging or "
                "reimbursing any travel for him in the period. Financial, criminal-history, "
                "employment and residence checks returned no adverse information. The reporting "
                "failures are established and no mitigating documentation has been provided."
            ),
            "key_findings": [
                {"finding": "Three foreign trips totalling 26 days were not disclosed by the applicant.", "category": "foreign_travel", "severity": "high", "source_ids": ["DOC-3-CHUNK-0"]},
                {"finding": "A continuing foreign contact employed by a state-owned enterprise was not reported and was identified through record review.", "category": "foreign_travel", "severity": "high", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "The applicant's explanation that the travel was employer-arranged is not corroborated by the employer.", "category": "foreign_travel", "severity": "high", "source_ids": ["DOC-7-CHUNK-0"]},
                {"finding": "Financial, criminal-history, employment and residence checks returned no adverse information.", "category": "general", "severity": "informational", "source_ids": ["DOC-1-CHUNK-1"]},
            ],
            "claims": [
                {"claim_text": "Border-crossing records identify five foreign trips during the rolling 24-month period while the applicant disclosed two.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Three foreign trips totalling 26 days were not disclosed by the applicant.", "claim_type": "potential_concern", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Two of the undisclosed trips were to the same country within a four-month period.", "claim_type": "potential_concern", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "A continuing foreign contact employed by a state-owned enterprise was identified through record review and appears on no filing by the applicant.", "claim_type": "potential_concern", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The contact was recorded on at least eleven occasions between July 2025 and January 2026.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The applicant states the undisclosed trips were arranged through his employer and reported on his behalf.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The employer's records office states it has no record of sponsoring, arranging or reimbursing any travel for the applicant during the period.", "claim_type": "potential_concern", "source_ids": ["DOC-7-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The investigator recorded that the applicant's explanation is not corroborated by the employer.", "claim_type": "potential_concern", "source_ids": ["DOC-7-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The applicant reported no continuing foreign national contacts on his travel disclosure.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "Employment dates reported by the applicant match the dates confirmed by both employers with no unexplained gaps.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Financial and criminal-history checks returned no adverse information for the period covered.", "claim_type": "fact", "source_ids": ["DOC-1-CHUNK-1"], "confidence": 0.9},
            ],
            "mitigating_information": [
                "The applicant responded to the questions and offered to provide further detail (Applicant Statement).",
                "No adverse information was developed in financial, criminal-history, employment or residence checks (Background Investigation Summary).",
            ],
            "missing_information": [
                "No employer travel record, itinerary or reimbursement record supporting the applicant's account has been provided.",
                "The nature and full extent of the contact with the foreign national has not been established.",
                "The purpose of the three undisclosed trips is not documented.",
            ],
            "potential_conflicts": [],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 5 — Elena Vasquez: conflicting employment dates (contradiction demo)
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00225",
        "applicant_name": "Elena Vasquez",
        "slug": "elena_vasquez",
        "key_signal": "Conflicting separation dates across source documents",
        "scenario": "conflicting_employment_dates",
        "opened_on": "2026-02-11",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-02-11", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-03-03", "label": "Employer verification returned", "detail": "Employer records office reports a June 2023 separation.", "category": "employment"},
            {"date": "2026-03-19", "label": "Reference interview conducted", "detail": "Former supervisor recalls a September 2023 departure.", "category": "employment"},
            {"date": "2026-04-01", "label": "Applicant statement submitted", "detail": "Applicant reports separation in September 2023.", "category": "statement"},
            {"date": "2026-04-15", "label": "Case notes recorded", "detail": "Conflict unresolved; documentary evidence requested.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00225
Subject: Elena Vasquez
Investigation Type: Periodic reinvestigation
Period Covered: February 2019 through February 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Employment: The separation date for one prior employer is reported
   differently by three sources in the record. The conflict is unresolved.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, residence verification and
foreign travel reporting returned no adverse information for the period covered.
"""),
            doc("employer_verification.txt", "Employer Verification Record", "employment_history", """
Subject: Elena Vasquez
Employer: Sterling Grove Manufacturing (fictional)
Verification returned: March 3, 2026
Source: Employer records office, payroll system of record

Position: Quality Assurance Lead
Employment start date: February 2020
Employment end date: Employment ended June 2023
Final payroll period processed: Pay period ending June 30, 2023
Separation type recorded: Voluntary resignation

The records office states that no payroll activity is recorded for this employee
after the June 2023 pay period.
"""),
            doc("reference_interview.txt", "Reference Interview Summary", "reference_interview", """
Interview date: March 19, 2026
Subject: Elena Vasquez
Reference: Former direct supervisor at Sterling Grove Manufacturing (fictional)

The reference stated that the subject worked on the production quality team and
that employment ended September 2023, following the close of a certification
project the subject had led. The reference recalled a departure lunch held in
the same month.

The reference was not able to produce documentation and stated the recollection
was based on memory of the project timeline.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: April 1, 2026
Subject: Elena Vasquez

My last day at Sterling Grove Manufacturing was in September 2023. I gave notice
in August and worked through the completion of a certification audit.

I am aware the questionnaire I submitted lists September 2023, which is the date
I remember. I have requested a copy of my separation letter and my final pay
statements from the employer and will provide them when I receive them.

Signed: Elena Vasquez
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator T. Bramwell (fictional)
Entry date: April 15, 2026

Three sources give three accounts of the same separation. The employer's payroll
system of record shows employment ending June 2023. The former supervisor recalls
September 2023 from memory. The subject reports September 2023.

I have requested the separation letter and final pay statements. Until
documentary evidence is received, the discrepancy of approximately three months
is unresolved. A payroll-system date and a recollection are not equivalent
evidence and the reviewing adjudicator should weigh them accordingly.

This entry contains no recommendation or determination.
"""),
            doc("financial_report.txt", "Financial Report", "financial_report", """
Report Date: 2026-03-06
Subject: Elena Vasquez
Source: Consolidated consumer credit file (synthetic)

No delinquent accounts are reported. Eleven trade lines are reported, all
current. Revolving utilisation is 8 percent. No collections, judgments, liens,
bankruptcies or civil filings appear in the record for the period covered.
"""),
        ],
        "known_contradictions": [
            {"field": "employment_end_date", "note": "Employer payroll record states June 2023; the reference interview and the applicant state September 2023."}
        ],
        "demo_analysis": {
            "executive_summary": (
                "The file contains an unresolved conflict about a single fact: the date the applicant's "
                "employment with Sterling Grove Manufacturing ended. The employer's payroll system of "
                "record states that employment ended June 2023, with the final payroll period ending "
                "June 30, 2023 and no payroll activity recorded afterwards. A former supervisor "
                "interviewed on March 19, 2026 stated that employment ended September 2023, based on "
                "recollection of a project timeline and without documentation. The applicant also "
                "reports September 2023 and has requested a separation letter and final pay statements, "
                "which are not yet in the record. The approximate three-month discrepancy is "
                "unresolved. No other adverse information was developed. This summary is informational "
                "and is not a determination."
            ),
            "key_findings": [
                {"finding": "Employment end date for Sterling Grove Manufacturing is reported differently by the employer's payroll record (June 2023) and by both the reference and the applicant (September 2023).", "category": "employment", "severity": "high", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"]},
                {"finding": "No documentary evidence supporting the September 2023 date is present in the file.", "category": "employment", "severity": "moderate", "source_ids": ["DOC-5-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "The employer's records office reported that employment ended June 2023, with the final payroll period ending June 30, 2023.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "The employer's records office states no payroll activity is recorded for the employee after the June 2023 pay period.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "A former supervisor stated in a March 19, 2026 interview that employment ended September 2023.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The reference could not produce documentation and stated the recollection was based on memory of a project timeline.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant reports a September 2023 separation and has requested a separation letter and final pay statements.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The approximately three-month discrepancy in the separation date is unresolved in the current record.", "claim_type": "potential_concern", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The financial record review identified no delinquent accounts and no collections, judgments or liens.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.91},
            ],
            "mitigating_information": [
                "The applicant has requested the documentary records that would resolve the conflict (Applicant Statement).",
                "No other adverse information was developed during the period under review (Background Investigation Summary).",
            ],
            "missing_information": [
                "The separation letter has not been received.",
                "Final pay statements have not been received.",
                "No record explains why the payroll system shows no activity after June 2023 if the applicant worked into September 2023.",
            ],
            "potential_conflicts": [
                {"description": "Employment end date is stated as June 2023 by the employer's payroll system of record and as September 2023 by both the reference interview and the applicant.", "source_ids": ["DOC-2-CHUNK-0", "DOC-3-CHUNK-0"], "conflicting_field": "employment_end_date"}
            ],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 6 — Daniel Okonjo: financial concern without mitigation
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00231",
        "applicant_name": "Daniel Okonjo",
        "slug": "daniel_okonjo",
        "key_signal": "Delinquent balance with no documented mitigation",
        "scenario": "financial_concern_without_mitigation",
        "opened_on": "2026-01-27",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-01-27", "label": "Case opened", "detail": "Initial investigation initiated.", "category": "administrative"},
            {"date": "2026-02-18", "label": "Financial report received", "detail": "Three delinquent accounts totalling $31,400.", "category": "financial"},
            {"date": "2026-03-06", "label": "Request for explanation issued", "detail": "Applicant asked to address the reported balances.", "category": "administrative"},
            {"date": "2026-03-30", "label": "Applicant response received", "detail": "Response acknowledges the debts; no plan documented.", "category": "statement"},
            {"date": "2026-04-21", "label": "Case notes recorded", "detail": "No repayment documentation received.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00231
Subject: Daniel Okonjo
Investigation Type: Initial investigation
Period Covered: January 2019 through January 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Financial: Three delinquent accounts totalling $31,400 appear on the February
   2026 financial report. No repayment arrangement is documented for any of them.

ITEMS WITH NO ADVERSE INFORMATION
Criminal history checks, employment verification, residence verification and
foreign travel reporting returned no adverse information for the period covered.
"""),
            doc("financial_report.txt", "Financial Report", "financial_report", """
Report Date: 2026-02-18
Subject: Daniel Okonjo
Source: Consolidated consumer credit file (synthetic)

DELINQUENT ACCOUNTS
1. Halcyon Bank, revolving — $14,900.00 — 180+ days past due — In collection
2. Larkspur Credit Union, installment — $11,200.00 — 150 days past due
3. Ardent Telecom Services — $5,300.00 — 210 days past due — In collection

Total delinquent balance: $31,400.00
Accounts 90+ days past due: 3
Revolving utilisation: 97 percent

No bankruptcy filing appears in the record. One civil judgment is reported:
Halcyon Bank, entered November 2025, in the amount of $14,900.00.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: March 30, 2026
Subject: Daniel Okonjo

I acknowledge the balances reported. I fell behind after a period of reduced
income in 2024 and I have not been able to catch up.

I have spoken with one of the creditors by phone but I have not signed any
agreement. I intend to consult a credit counselling service. I do not currently
have a repayment plan in place and I do not have documentation to provide at this
time.

I understand these balances are a concern and I am prepared to answer further
questions.

Signed: Daniel Okonjo
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Daniel Okonjo
Verification completed: 2026-03-12

POSITION 1
Employer: Arbor Grid Utilities (fictional)
Title: Field Technician
Dates confirmed by employer: May 2024 to present

POSITION 2
Employer: Winslow Mechanical Services (fictional)
Title: Technician
Dates confirmed by employer: June 2019 to February 2024
Separation reason confirmed by employer: Voluntary resignation

GAP
A gap of approximately three months is confirmed between February 2024 and May
2024. The subject reported reduced income during this period.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator S. Aldridge (fictional)
Entry date: April 21, 2026

No repayment agreement, settlement letter, credit counselling enrollment or
payment receipt has been received for any of the three delinquent accounts. The
subject's response acknowledges the balances and states that no agreement is in
place.

The civil judgment reported in November 2025 was confirmed against the public
docket index. The judgment remains unsatisfied in the record available.

The subject has been responsive to requests and has not disputed the accuracy of
the reported balances. This entry contains no recommendation or determination.
"""),
        ],
        "known_contradictions": [],
        "demo_analysis": {
            "executive_summary": (
                "The financial report dated February 18, 2026 shows three delinquent accounts "
                "totalling $31,400.00, all 90 or more days past due, with revolving utilisation at 97 "
                "percent. A civil judgment in favour of Halcyon Bank for $14,900.00 was entered in "
                "November 2025 and is recorded as unsatisfied. The applicant acknowledges the balances "
                "and attributes them to a period of reduced income in 2024, corroborated by a "
                "confirmed three-month employment gap between February and May 2024. No repayment "
                "agreement, settlement letter, counselling enrollment or payment receipt is present in "
                "the file for any account. Unlike other financial cases in the caseload, this record "
                "contains no documented mitigation. This summary is informational and is not a "
                "determination."
            ),
            "key_findings": [
                {"finding": "Three delinquent accounts totalling $31,400.00 are reported, all 90 or more days past due.", "category": "financial", "severity": "high", "source_ids": ["DOC-2-CHUNK-0"]},
                {"finding": "A civil judgment for $14,900.00 entered November 2025 is recorded and remains unsatisfied.", "category": "financial", "severity": "high", "source_ids": ["DOC-2-CHUNK-0", "DOC-5-CHUNK-0"]},
                {"finding": "No repayment arrangement or mitigation documentation is present in the file.", "category": "financial", "severity": "high", "source_ids": ["DOC-5-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "Three delinquent accounts totalling $31,400.00 are reported on the February 18, 2026 financial report.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.96},
                {"claim_text": "The largest delinquent account is a Halcyon Bank revolving balance of $14,900.00, reported 180 or more days past due.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Revolving credit utilisation is reported at 97 percent.", "claim_type": "potential_concern", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "A civil judgment in the amount of $14,900.00 was entered in November 2025.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The judgment remains unsatisfied in the record available to the investigator.", "claim_type": "potential_concern", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "The applicant acknowledges the balances and states that no repayment agreement is in place.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "A three-month employment gap between February and May 2024 is confirmed by employer records.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "No repayment agreement, settlement letter, counselling enrollment or payment receipt has been received for any of the three accounts.", "claim_type": "potential_concern", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant has enrolled in a nonprofit credit counselling program and made an initial payment.", "claim_type": "mitigation", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.6},
            ],
            "mitigating_information": [
                "The applicant has been responsive to requests and has not disputed the accuracy of the reported balances (Case Notes).",
                "The employment record independently corroborates the stated period of reduced income (Employment History).",
            ],
            "missing_information": [
                "No repayment plan, settlement agreement or payment history exists in the file for any of the three accounts.",
                "The current status of the November 2025 civil judgment beyond the investigator's April 2026 check is unknown.",
                "No credit counselling enrollment documentation has been received.",
            ],
            "potential_conflicts": [],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 7 — Sofia Lindqvist: minor legal incident, resolved
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00240",
        "applicant_name": "Sofia Lindqvist",
        "slug": "sofia_lindqvist",
        "key_signal": "Single resolved misdemeanor citation, self-reported",
        "scenario": "minor_legal_incident_resolved",
        "opened_on": "2026-02-24",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-02-24", "label": "Case opened", "detail": "Initial investigation initiated.", "category": "administrative"},
            {"date": "2026-03-10", "label": "Self-reported incident", "detail": "Applicant discloses a 2023 citation on the questionnaire.", "category": "statement"},
            {"date": "2026-03-25", "label": "Court record obtained", "detail": "Disposition confirmed; fine paid, case closed.", "category": "legal"},
            {"date": "2026-04-09", "label": "Case notes recorded", "detail": "No further legal activity identified.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00240
Subject: Sofia Lindqvist
Investigation Type: Initial investigation
Period Covered: February 2019 through February 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Legal: One misdemeanor citation from 2023, self-reported by the subject and
   confirmed as resolved by court record.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, employment verification, residence verification and
foreign travel reporting returned no adverse information for the period covered.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: March 10, 2026
Subject: Sofia Lindqvist

I am disclosing a citation I received in 2023.

In May 2023 I was cited for a municipal noise ordinance violation following a
neighbour complaint about a gathering at my residence. I appeared in municipal
court, the matter was resolved as a non-criminal infraction, and I paid a fine of
$250. There was no arrest, no probation and no further proceedings.

I have had no other legal involvement of any kind. I reported this on my
questionnaire.

Signed: Sofia Lindqvist
"""),
            doc("court_record.txt", "Court Disposition Record", "legal_record", """
Record obtained: March 25, 2026
Subject: Sofia Lindqvist
Jurisdiction: Municipal Court, Fictional County (synthetic record)

Citation date: May 2023
Charge: Municipal noise ordinance violation
Classification: Non-criminal infraction
Disposition: Fine imposed and paid in full, $250.00
Case status: Closed
Arrest record: None associated with this citation
Probation or supervision: None

No other filings involving this subject appear in the jurisdiction's index for
the period searched.
"""),
            doc("criminal_history_check.txt", "Criminal History Check", "record_check", """
Check completed: March 27, 2026
Subject: Sofia Lindqvist

National and state criminal history repositories were queried for the period
under review. One municipal infraction is reflected, consistent with the
disposition record obtained March 25, 2026.

No felony records, no misdemeanor convictions, no arrests, no protective orders
and no pending charges were identified.
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Sofia Lindqvist
Verification completed: 2026-03-18

POSITION 1
Employer: Kingsbridge Research Institute (fictional)
Title: Laboratory Coordinator
Dates confirmed by employer: September 2020 to present

POSITION 2
Employer: Alder Creek Diagnostics (fictional)
Title: Laboratory Technician
Dates confirmed by employer: July 2018 to August 2020

No unexplained gaps were identified. Reported dates match confirmed dates for
both positions.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator P. Chandra (fictional)
Entry date: April 9, 2026

The 2023 citation was disclosed by the subject before it was identified through
record checks. The court record confirms the disposition described by the
subject: a non-criminal infraction, fine paid, case closed, no arrest.

No other legal activity was identified in any repository queried. The remainder
of the case file returned no adverse information.

This entry contains no recommendation or determination.
"""),
        ],
        "known_contradictions": [],
        "demo_analysis": {
            "executive_summary": (
                "The file documents one legal matter: a municipal noise ordinance citation from May "
                "2023, self-reported by the applicant on the security questionnaire before it was "
                "identified through record checks. A court disposition record obtained March 25, 2026 "
                "confirms the matter was classified as a non-criminal infraction, resolved by a $250.00 "
                "fine paid in full, with the case closed and no arrest, probation or supervision "
                "associated. A criminal history check completed March 27, 2026 identified no felony "
                "records, misdemeanor convictions, arrests, protective orders or pending charges. The "
                "remainder of the file returned no adverse information. This summary is informational "
                "and is not a determination."
            ),
            "key_findings": [
                {"finding": "One municipal infraction from May 2023 is documented and confirmed resolved.", "category": "legal", "severity": "low", "source_ids": ["DOC-3-CHUNK-0"]},
                {"finding": "The incident was self-reported before it was identified through record checks.", "category": "legal_mitigation", "severity": "informational", "source_ids": ["DOC-6-CHUNK-0"]},
                {"finding": "No other legal activity was identified in any repository queried.", "category": "legal", "severity": "informational", "source_ids": ["DOC-4-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "The applicant received a municipal noise ordinance citation in May 2023.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0", "DOC-2-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "The court classified the matter as a non-criminal infraction.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "A fine of $250.00 was imposed and paid in full and the case is closed.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "No arrest, probation or supervision is associated with the citation.", "claim_type": "mitigation", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant disclosed the citation on the security questionnaire before it was identified through record checks.", "claim_type": "mitigation", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The criminal history check identified no felony records, misdemeanor convictions, arrests, protective orders or pending charges.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Employment dates reported by the applicant match the dates confirmed by both employers with no unexplained gaps.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.92},
            ],
            "mitigating_information": [
                "The matter was self-reported prior to discovery and the applicant's description matches the court record in every particular (Case Notes; Court Disposition Record).",
                "The disposition involved no arrest, no probation and no continuing obligation (Court Disposition Record).",
            ],
            "missing_information": [
                "The record does not include the underlying citation document itself, only the disposition record.",
            ],
            "potential_conflicts": [],
            "requires_human_review": True,
        },
    }
)


# ===========================================================================
# CASE 8 — Thomas Achebe: address-history discrepancy
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00248",
        "applicant_name": "Thomas Achebe",
        "slug": "thomas_achebe",
        "key_signal": "Unverified nine-month residence period",
        "scenario": "address_history_discrepancy",
        "opened_on": "2026-03-02",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-03-02", "label": "Case opened", "detail": "Initial investigation initiated.", "category": "administrative"},
            {"date": "2026-03-21", "label": "Residence verification returned", "detail": "One reported address could not be verified.", "category": "residence"},
            {"date": "2026-04-04", "label": "Applicant statement submitted", "detail": "Applicant describes an informal sublet.", "category": "statement"},
            {"date": "2026-04-23", "label": "Third-party record received", "detail": "Data provider shows a different address for part of the period.", "category": "residence"},
            {"date": "2026-05-05", "label": "Case notes recorded", "detail": "Nine months of residence history remain unverified.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00248
Subject: Thomas Achebe
Investigation Type: Initial investigation
Period Covered: March 2019 through March 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Residence: One reported address covering approximately nine months could not
   be verified through any source of record.
2. A third-party data provider places the subject at a different address for part
   of the same period.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, employment verification and
foreign travel reporting returned no adverse information for the period covered.
"""),
            doc("residence_verification.txt", "Residence Verification Record", "record_check", """
Verification completed: March 21, 2026
Subject: Thomas Achebe

ADDRESS 1 — Reported: August 2022 to present
Status: Verified through lease record and utility account.

ADDRESS 2 — Reported: November 2021 to August 2022
Status: Not verified. No lease, utility account, mail-forwarding record or
landlord contact could be located for this address during the period reported.

ADDRESS 3 — Reported: June 2019 to November 2021
Status: Verified through lease record and two developed references.

UNVERIFIED PERIOD
Approximately nine months of reported residence history is unverified.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: April 4, 2026
Subject: Thomas Achebe

The address that could not be verified was an informal sublet. I rented a room
from a friend who held the lease. There was no written agreement, I paid in cash
each month, and the utilities were in the leaseholder's name, so nothing was ever
in my name at that address.

I have given the leaseholder's contact information to the investigator. I also
continued to use my previous mailing address for some correspondence during that
period, which may be why records show me elsewhere.

Signed: Thomas Achebe
"""),
            doc("third_party_address_record.txt", "Third-Party Address Record", "third_party_record", """
Record produced: April 23, 2026
Subject: Thomas Achebe
Source: Commercial address data provider (synthetic)

The provider's file associates the subject with the Address 3 location through
March 2022, four months beyond the November 2021 end date the subject reported
for that address.

The provider's file contains no entry for the Address 2 location at any point.

Data-provider records reflect mail and account associations and are not
themselves proof of physical residence.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator J. Whitfield (fictional)
Entry date: May 5, 2026

Two contact attempts were made to the leaseholder identified by the subject. No
response has been received as of this entry.

The third-party record and the subject's account can both be true: the subject
states he continued using the prior mailing address, which would explain the
provider's association through March 2022 without contradicting a November 2021
physical move. This is a plausible reconciliation, not a verified one.

Approximately nine months of residence history remains unverified by any source.
This entry contains no recommendation or determination.
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Thomas Achebe
Verification completed: 2026-03-27

POSITION 1
Employer: Coastal Meridian Insurance (fictional)
Title: Claims Analyst
Dates confirmed by employer: March 2020 to present

POSITION 2
Employer: Brightwater Retail Group (fictional)
Title: Assistant Manager
Dates confirmed by employer: January 2018 to February 2020

Reported dates match confirmed dates. No unexplained gaps were identified. The
subject's employment record covers the entire unverified residence period.
"""),
        ],
        "known_contradictions": [
            {"field": "residence_end_date", "note": "Applicant reports leaving Address 3 in November 2021; the data provider associates him with that address through March 2022."}
        ],
        "demo_analysis": {
            "executive_summary": (
                "Residence verification completed March 21, 2026 verified two of three reported "
                "addresses. The address reported for November 2021 through August 2022 — approximately "
                "nine months — could not be verified through any lease, utility account, "
                "mail-forwarding record or landlord contact. The applicant states this was an informal "
                "cash sublet held in another person's name, and that he continued using his prior "
                "mailing address during the period. A commercial data provider associates the applicant "
                "with the earlier address through March 2022, four months past the reported move date, "
                "and holds no entry at all for the unverified address. The investigator notes that the "
                "applicant's explanation would reconcile both records but has not been verified; two "
                "contact attempts to the named leaseholder went unanswered. This summary is "
                "informational and is not a determination."
            ),
            "key_findings": [
                {"finding": "Approximately nine months of reported residence history is unverified by any source of record.", "category": "residence", "severity": "moderate", "source_ids": ["DOC-2-CHUNK-0"]},
                {"finding": "A third-party data provider places the applicant at the prior address four months beyond the reported move date.", "category": "residence", "severity": "moderate", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "The applicant's employment record is fully verified and covers the entire unverified residence period.", "category": "employment", "severity": "informational", "source_ids": ["DOC-6-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "The address reported for November 2021 to August 2022 could not be verified through any lease, utility account, mail-forwarding record or landlord contact.", "claim_type": "potential_concern", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Approximately nine months of reported residence history is unverified.", "claim_type": "potential_concern", "source_ids": ["DOC-2-CHUNK-0", "DOC-5-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant states the unverified address was an informal sublet paid in cash with utilities in the leaseholder's name.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "A commercial data provider associates the applicant with the prior address through March 2022.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The data provider's file contains no entry for the unverified address at any point.", "claim_type": "potential_concern", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Two contact attempts to the leaseholder identified by the applicant received no response.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "The investigator recorded that the applicant's explanation would reconcile both records but is not itself verified.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "Employment dates match confirmed dates with no unexplained gaps across the unverified residence period.", "claim_type": "mitigation", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.91},
            ],
            "mitigating_information": [
                "Verified continuous employment covers the entire unverified residence period (Employment History).",
                "The applicant supplied the leaseholder's contact information voluntarily (Applicant Statement).",
                "Data-provider records reflect mail and account associations rather than proof of physical residence (Third-Party Address Record).",
            ],
            "missing_information": [
                "No response has been received from the named leaseholder.",
                "No cash-payment records, correspondence or references place the applicant at the unverified address.",
            ],
            "potential_conflicts": [
                {"description": "The applicant reports leaving the prior address in November 2021 while a data provider associates him with it through March 2022.", "source_ids": ["DOC-2-CHUNK-0", "DOC-4-CHUNK-0"], "conflicting_field": "residence_end_date"}
            ],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 9 — Hannah Ostrowski: clean case, no major concerns
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00256",
        "applicant_name": "Hannah Ostrowski",
        "slug": "hannah_ostrowski",
        "key_signal": "No adverse information developed",
        "scenario": "clean_case",
        "opened_on": "2026-03-16",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-03-16", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-04-02", "label": "Record checks completed", "detail": "Financial, criminal and residence checks returned clear.", "category": "investigative"},
            {"date": "2026-04-18", "label": "Employment verified", "detail": "Both employers of record confirmed reported dates.", "category": "employment"},
            {"date": "2026-04-30", "label": "Case notes recorded", "detail": "No issues identified for further review.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00256
Subject: Hannah Ostrowski
Investigation Type: Periodic reinvestigation
Period Covered: March 2019 through March 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
None. No issue meeting the threshold for further review was identified during
the period covered.

ITEMS WITH NO ADVERSE INFORMATION
Financial record review, criminal history checks, employment verification,
residence verification, education verification, foreign travel reporting and
foreign contact reporting all returned no adverse information.
"""),
            doc("financial_report.txt", "Financial Report", "financial_report", """
Report Date: 2026-04-02
Subject: Hannah Ostrowski
Source: Consolidated consumer credit file (synthetic)

No delinquent accounts are reported. Twelve trade lines are reported, all
current, with no 30-day or greater delinquency in the prior 84 months. Revolving
utilisation is 6 percent. No collections, judgments, liens, bankruptcies, civil
filings or repossessions appear in the record for the period covered.
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Hannah Ostrowski
Verification completed: 2026-04-18

POSITION 1
Employer: Windward Civic Systems (fictional)
Title: Program Analyst
Dates confirmed by employer: February 2021 to present

POSITION 2
Employer: Lakeview Municipal Services (fictional)
Title: Administrative Analyst
Dates confirmed by employer: September 2017 to January 2021

Reported dates match confirmed dates for both positions. No unexplained gaps.
"""),
            doc("residence_verification.txt", "Residence Verification Record", "record_check", """
Verification completed: April 2, 2026
Subject: Hannah Ostrowski

ADDRESS 1 — Reported March 2021 to present — Verified through lease and utility
records.
ADDRESS 2 — Reported August 2017 to March 2021 — Verified through lease record
and two developed references.

No unverified periods. Reported residence history is continuous.
"""),
            doc("travel_disclosure.txt", "Foreign Travel Disclosure", "travel_disclosure", """
Submitted: March 28, 2026
Subject: Hannah Ostrowski

REPORTED FOREIGN TRAVEL (rolling 24 months)
1. Canada — July 12-19, 2025 — Personal travel

Border-crossing record checks for the period identify one trip, consistent with
the disclosure. No undisclosed foreign travel was identified. The subject
reported no foreign contacts, no foreign financial interests and no foreign
property.
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator K. Rasmussen (fictional)
Entry date: April 30, 2026

All record checks are complete and all reported information was corroborated by
an independent source. No discrepancy, alert or adverse record was developed
during the period covered.

Two developed references were interviewed and both corroborated the subject's
residence and employment history.

This entry contains no recommendation or determination.
"""),
        ],
        "known_contradictions": [],
        "demo_analysis": {
            "executive_summary": (
                "No issue meeting the threshold for further review was identified during the period "
                "covered. The financial report dated April 2, 2026 shows no delinquent accounts, "
                "twelve current trade lines, revolving utilisation at 6 percent, and no collections, "
                "judgments, liens or bankruptcies. Employment dates reported by the applicant match "
                "the dates confirmed by both employers of record with no unexplained gaps, and both "
                "reported addresses were verified through lease and utility records. One foreign trip "
                "to Canada in July 2025 was disclosed and matches border-crossing records, with no "
                "undisclosed travel identified. Two developed references corroborated the applicant's "
                "residence and employment history. This summary is informational and is not a "
                "determination."
            ),
            "key_findings": [
                {"finding": "No issue meeting the threshold for further review was identified.", "category": "general", "severity": "informational", "source_ids": ["DOC-1-CHUNK-0"]},
                {"finding": "All reported information was corroborated by at least one independent source.", "category": "general", "severity": "informational", "source_ids": ["DOC-6-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "No delinquent accounts are reported and twelve trade lines are current.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Revolving credit utilisation is reported at 6 percent.", "claim_type": "fact", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Employment dates reported by the applicant match the dates confirmed by both employers with no unexplained gaps.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "Both reported addresses were verified and residence history is continuous with no unverified periods.", "claim_type": "fact", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "One foreign trip to Canada in July 2025 was disclosed and is consistent with border-crossing records.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "No undisclosed foreign travel was identified during the rolling 24-month period.", "claim_type": "fact", "source_ids": ["DOC-5-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "Two developed references corroborated the applicant's residence and employment history.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.92},
            ],
            "mitigating_information": [],
            "missing_information": [
                "Education verification results are referenced in the investigation summary but the underlying verification record is not included in this file.",
            ],
            "potential_conflicts": [],
            "requires_human_review": True,
        },
    }
)

# ===========================================================================
# CASE 10 — Victor Ramachandran: multiple moderate-risk indicators
# ===========================================================================
CASES.append(
    {
        "case_number": "PS-2026-00263",
        "applicant_name": "Victor Ramachandran",
        "slug": "victor_ramachandran",
        "key_signal": "Three moderate indicators across separate categories",
        "scenario": "multiple_moderate_indicators",
        "opened_on": "2026-01-06",
        "status": "Awaiting AI Analysis",
        "timeline": [
            {"date": "2026-01-06", "label": "Case opened", "detail": "Periodic reinvestigation initiated.", "category": "administrative"},
            {"date": "2026-02-10", "label": "Financial report received", "detail": "One 90-day delinquency, since brought current.", "category": "financial"},
            {"date": "2026-02-28", "label": "Travel cross-check", "detail": "One late-filed travel report identified.", "category": "travel"},
            {"date": "2026-03-20", "label": "Employment verification", "detail": "Title discrepancy identified; dates match.", "category": "employment"},
            {"date": "2026-04-11", "label": "Applicant statement submitted", "detail": "Applicant addresses all three items.", "category": "statement"},
            {"date": "2026-04-28", "label": "Case notes recorded", "detail": "Two items resolved; one partially resolved.", "category": "investigative"},
        ],
        "documents": [
            doc("background_investigation_summary.txt", "Background Investigation Summary", "investigation_summary", """
Case Number: PS-2026-00263
Subject: Victor Ramachandran
Investigation Type: Periodic reinvestigation
Period Covered: January 2019 through January 2026

ISSUES IDENTIFIED FOR FURTHER REVIEW
1. Financial: One account reached 90 days past due in 2025 and has since been
   brought current.
2. Foreign travel: One trip was reported after the required filing window.
3. Employment: A position title reported by the subject differs from the title in
   the employer's record. Dates match.

Individually each item is moderate. The subject has provided an explanation for
each. Whether the items in combination warrant additional inquiry is a judgment
for the reviewing adjudicator.
"""),
            doc("financial_report.txt", "Financial Report", "financial_report", """
Report Date: 2026-02-10
Subject: Victor Ramachandran
Source: Consolidated consumer credit file (synthetic)

DELINQUENCY HISTORY
Account: Fernwood Savings, installment
Maximum delinquency: 90 days past due, reported August 2025
Current status: Current since November 2025
Balance: $6,410.00

Eight additional trade lines are reported, all current. Revolving utilisation is
23 percent. No collections, judgments, liens or bankruptcies appear in the
record. No account is currently past due.
"""),
            doc("travel_disclosure.txt", "Foreign Travel Disclosure", "travel_disclosure", """
Submitted: February 28, 2026
Subject: Victor Ramachandran

REPORTED FOREIGN TRAVEL (rolling 24 months)
1. Portugal — April 4-12, 2025 — Personal travel — Reported April 25, 2025
2. Mexico — September 19-22, 2025 — Personal travel — Reported January 30, 2026

FILING NOTE
The Mexico trip was reported approximately four months after return. The
applicable reporting window for this program is 30 days. The Portugal trip was
reported within the window.

Border-crossing records identify two trips for the period, consistent with the
two trips reported above. No undisclosed travel was identified.
"""),
            doc("employment_history.txt", "Employment History", "employment_history", """
Subject: Victor Ramachandran
Verification completed: 2026-03-20

POSITION 1
Employer: Halstead Analytics Corporation (fictional)
Title as reported by subject: Senior Program Manager
Title confirmed by employer: Program Manager II
Dates as reported by subject: May 2021 to present
Dates confirmed by employer: May 2021 to present

POSITION 2
Employer: Orion Public Sector Group (fictional)
Title: Business Analyst
Dates confirmed by employer: June 2017 to April 2021
Reported dates match confirmed dates.

NOTE
Employment dates match for both positions. Only the position title for Position 1
differs from the employer's record of title.
"""),
            doc("applicant_statement.txt", "Applicant Statement", "applicant_statement", """
Submitted: April 11, 2026
Subject: Victor Ramachandran

I want to address the three items raised.

Financial: I missed payments on an installment loan in mid-2025 after an
unexpected home repair. I brought the account current in November 2025 and it has
been current since.

Travel: I reported my September 2025 trip to Mexico late. I believed short trips
to neighbouring countries did not require a separate report. That was my error
and I reported it as soon as I understood the requirement.

Employment title: My internal working title on my team is Senior Program Manager
and that is the title used on my team's roster and in my email signature. I now
understand the official payroll title is Program Manager II. I reported the title
I use day to day, not the payroll title.

Signed: Victor Ramachandran
"""),
            doc("investigator_notes.txt", "Case Notes", "case_notes", """
Analyst: Investigator N. Doyle (fictional)
Entry date: April 28, 2026

Financial: Resolved on the record. The account has been current since November
2025 and the credit file shows no other delinquency.

Employment title: Resolved on the record. Dates match for both positions and the
difference is confined to title. The employer confirmed that internal working
titles are used on team rosters and differ from payroll titles.

Travel: Partially resolved. The late filing is established and the subject's
explanation is on the record, but whether the subject had been briefed on the
30-day reporting requirement is not documented in the file.

No single item in this case is severe. The reviewing adjudicator should consider
whether the pattern across categories warrants further inquiry. This entry
contains no recommendation or determination.
"""),
        ],
        "known_contradictions": [
            {"field": "position_title", "note": "Applicant reports Senior Program Manager; the employer confirms Program Manager II for the same dates."}
        ],
        "demo_analysis": {
            "executive_summary": (
                "Three moderate indicators appear across separate categories. Financially, one "
                "installment account with Fernwood Savings reached 90 days past due in August 2025 and "
                "has been current since November 2025, with no other delinquency and no collections, "
                "judgments or liens in the record. On travel, a September 2025 trip to Mexico was "
                "reported in January 2026, approximately four months after return and outside the "
                "30-day reporting window; border-crossing records identify no undisclosed travel. On "
                "employment, the applicant reported the title Senior Program Manager while the employer "
                "confirms Program Manager II for identical dates. The investigator records the "
                "financial and title items as resolved and the late travel filing as partially "
                "resolved, noting that whether the applicant had been briefed on the reporting window "
                "is not documented. This summary is informational and is not a determination."
            ),
            "key_findings": [
                {"finding": "One installment account reached 90 days past due in August 2025 and has been current since November 2025.", "category": "financial", "severity": "moderate", "source_ids": ["DOC-2-CHUNK-0"]},
                {"finding": "A September 2025 foreign trip was reported approximately four months after return, outside the 30-day window.", "category": "foreign_travel", "severity": "moderate", "source_ids": ["DOC-3-CHUNK-0"]},
                {"finding": "Reported position title differs from the employer's title of record while dates match exactly.", "category": "employment", "severity": "low", "source_ids": ["DOC-4-CHUNK-0"]},
                {"finding": "The investigator noted that no single item is severe and framed the pattern across categories as the question for the adjudicator.", "category": "general", "severity": "informational", "source_ids": ["DOC-6-CHUNK-0"]},
            ],
            "claims": [
                {"claim_text": "An installment account with Fernwood Savings reached 90 days past due, reported August 2025.", "claim_type": "potential_concern", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "That account has been current since November 2025 and no account is currently past due.", "claim_type": "mitigation", "source_ids": ["DOC-2-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The September 2025 trip to Mexico was reported on January 30, 2026, approximately four months after return.", "claim_type": "potential_concern", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The applicable reporting window for this program is 30 days.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Border-crossing records identify two trips for the period and no undisclosed travel.", "claim_type": "fact", "source_ids": ["DOC-3-CHUNK-0"], "confidence": 0.93},
                {"claim_text": "The applicant reported the title Senior Program Manager while the employer confirmed Program Manager II.", "claim_type": "potential_concern", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.95},
                {"claim_text": "Employment dates reported by the applicant match the dates confirmed by the employer for both positions.", "claim_type": "mitigation", "source_ids": ["DOC-4-CHUNK-0"], "confidence": 0.94},
                {"claim_text": "The employer confirmed that internal working titles are used on team rosters and differ from payroll titles.", "claim_type": "mitigation", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.9},
                {"claim_text": "The investigator recorded the financial item and the title item as resolved on the record.", "claim_type": "fact", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.92},
                {"claim_text": "Whether the applicant had been briefed on the 30-day travel reporting requirement is not documented in the file.", "claim_type": "missing_evidence", "source_ids": ["DOC-6-CHUNK-0"], "confidence": 0.9},
            ],
            "mitigating_information": [
                "The delinquent account was brought current before the reinvestigation began and no other delinquency appears in the credit file (Financial Report).",
                "Employment dates match exactly for both positions; the discrepancy is confined to title (Employment History).",
                "The applicant addressed all three items in a single statement and did not dispute any of the underlying records (Applicant Statement).",
            ],
            "missing_information": [
                "No record documents whether the applicant received a briefing on the 30-day foreign travel reporting requirement.",
                "No documentation of the home repair cited as the cause of the 2025 delinquency is present in the file.",
            ],
            "potential_conflicts": [
                {"description": "The applicant reports the position title Senior Program Manager while the employer's record confirms Program Manager II for the same dates.", "source_ids": ["DOC-4-CHUNK-0"], "conflicting_field": "position_title"}
            ],
            "requires_human_review": True,
        },
    }
)


# Merge the decision-ready assessment fixtures into each case's demo analysis.
# Kept in a separate module so this file stays the *documents*, not the briefs.
from case_assessments import ASSESSMENTS, GROUND_TRUTH  # noqa: E402

for _case in CASES:
    _assessment = ASSESSMENTS.get(_case["slug"])
    if _assessment:
        _case["demo_analysis"].update(_assessment)
    _case["ground_truth"] = GROUND_TRUTH.get(_case["slug"], {})


# ---------------------------------------------------------------------------
# Active caseload
# ---------------------------------------------------------------------------
# The prototype ships a focused five-case demonstration set. All ten cases stay
# defined here: switching one back on is a one-line edit, not a rewrite.
#
# The five were chosen to cover every recommendation state and to preserve the
# two contrasts that explain the engine without a word of documentation:
#
#   Alex Morgan  vs  Marcus Dell    a financial concern with, and without,
#                                   verifiable mitigation
#   Jordan Reyes vs  Elena Vasquez  a discrepancy documented inside one record,
#                                   versus two independent records that disagree
#
# Hannah Ostrowski is the clean control: proof the system will say "nothing here".
ACTIVE_SLUGS = {
    "alex_morgan",        # PROCEED  — concern with verified mitigation
    "hannah_ostrowski",   # PROCEED  — clean package
    "jordan_reyes",       # REQUEST  — disclosed discrepancy, one month unverified
    "elena_vasquez",      # ESCALATE — two records disagree on a material fact
    "marcus_dell",        # ESCALATE — undisclosed foreign travel; model/engine divergence
}

RESERVE_SLUGS = {
    "priya_nandakumar",   # PROCEED  — reporting omission, promptly corrected
    "sofia_lindqvist",    # PROCEED  — minor legal matter, closed
    "thomas_achebe",      # REQUEST  — nine-month evidence gap
    "victor_ramachandran",# REQUEST  — three moderate indicators at once
    "daniel_okonjo",      # ESCALATE — substantial delinquency, no mitigation
}


def active_cases(include_all: bool = False) -> List[Dict[str, Any]]:
    if include_all:
        return CASES
    return [case for case in CASES if case["slug"] in ACTIVE_SLUGS]


def case_by_slug(slug: str) -> Dict[str, Any]:
    for case in CASES:
        if case["slug"] == slug:
            return case
    raise KeyError(f"Unknown case slug: {slug}")
