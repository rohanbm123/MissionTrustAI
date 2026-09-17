"""Prototype contradiction detection.

The detector extracts typed field/value pairs (dates, amounts, percentages,
counts, labelled values) from every pair of evidence passages and flags any
field where two passages assert incompatible values.

This is a heuristic. It does not "understand" the documents, and it is
deliberately framed everywhere in the product as a *potential* contradiction
requiring human review. When a live LLM is configured it can be layered on top
via `llm_contradiction_pass` for cases the heuristic cannot express.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from src.llm.prompts import get_prompt
from src.llm.provider import LLMError, LLMProvider
from src.models.schemas import ContradictionFlag, RetrievedChunk

logger = logging.getLogger(__name__)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

_MONTH_YEAR = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2},\s*)?(\d{4})\b", re.IGNORECASE
)
_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")
_PERCENT = re.compile(r"\b(\d{1,3})\s*percent\b", re.IGNORECASE)
_TRIP_COUNT = re.compile(
    r"\b(" + "|".join(NUMBER_WORDS) + r"|\d{1,2})\s+(?:foreign\s+)?trips\b", re.IGNORECASE
)

# Canonical field keys and the cue words that identify them in a sentence.
FIELD_CUES: Dict[str, Tuple[str, ...]] = {
    "employment_end_date": ("employment end", "employment ended", "separation date", "last day",
                            "end date", "final payroll", "assignment end"),
    "employment_start_date": ("employment start", "start date", "began working", "assignment start",
                              "started at", "employment began"),
    "repayment_plan_effective_date": ("plan effective", "payment agreement", "repayment plan",
                                      "entered a payment"),
    "delinquency_reported_date": ("first reported delinquent", "reported delinquent",
                                  "delinquency reported"),
    "residence_end_date": ("address", "residence", "resided", "moved"),
    "delinquent_amount": ("delinquent", "balance placed", "total delinquent", "collection account",
                          "balance reported"),
    "credit_utilisation": ("utilisation", "utilization"),
    "foreign_trip_count": ("trips", "foreign travel"),
    "position_title": ("title",),
}

# A field only applies when its own subject matter is actually present in the
# sentence; without this an "end date" cue would claim any date in the file.
FIELD_CONTEXT_GUARDS: Dict[str, Tuple[str, ...]] = {
    "employment_end_date": ("employment", "employer", "position", "assignment", "payroll",
                            "worked", "job", "separation", "resign"),
    "employment_start_date": ("employment", "employer", "position", "assignment", "payroll",
                              "worked", "job", "hired", "started"),
    "residence_end_date": ("address", "residence", "resided", "moved", "lease"),
}

_LABELLED_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z /'()-]{2,60}):\s*(.+?)\s*$", re.MULTILINE)

# Entity scoping. Two values only conflict when they describe the same thing: an
# employment end date for Fairmont Logistics and one for a Vantage assignment are
# two facts, not a contradiction. Entities are read from the record block each
# value sits in.
_PROPER_NOUN = re.compile(r"\b([A-Z][a-z]+(?:[ ]+[A-Z][a-z]+)+)\b")
_RECORD_REF = re.compile(r"\b([A-Z]{2,}[-\u2014]?[A-Z0-9-]{2,})\b")
_ORDINAL_RECORD = re.compile(r"\b(ADDRESS|POSITION|Address|Position)\s*(\d+)\b")

# Document furniture that is not an entity.
# Sentences that explicitly reconcile two records are not evidence of a conflict
# between them — most often they are an investigator writing down why the
# apparent discrepancy is not one.
_RECONCILING = (
    "can both be true", "without contradicting", "is consistent with",
    "are consistent with", "would explain", "consistent with the", "match the dates",
    "dates match", "no discrepancy",
)

_ENTITY_STOPWORDS = {
    "employment history", "financial report", "applicant statement", "payment plan",
    "case notes", "background investigation", "employment start", "employment end",
    "reported foreign travel", "assignment record", "payment history", "delinquent account",
    "account notes", "criminal history", "residence verification", "record produced",
    "structured repayment", "quality assurance lead", "investigation type", "period covered",
    "issues identified", "items with", "no adverse information", "summary of record",
    "days past", "total delinquent", "other accounts", "verification note", "separation reason",
}

LABEL_MAP = {
    "employment end date": "employment_end_date",
    "assignment end date": "employment_end_date",
    "employment start date": "employment_start_date",
    "assignment start date": "employment_start_date",
    "plan effective date": "repayment_plan_effective_date",
    "date first reported delinquent": "delinquency_reported_date",
    "balance reported delinquent": "delinquent_amount",
    "original balance placed": "delinquent_amount",
    "total delinquent balance": "delinquent_amount",
    "title as reported by subject": "position_title",
    "title confirmed by employer": "position_title",
    "dates as reported by subject": "employment_dates_range",
    "dates confirmed by employer": "employment_dates_range",
    "dates confirmed by employer:": "employment_dates_range",
}


def _blocks(text: str) -> List[str]:
    return [b for b in reflow(text).split("\n\n") if b.strip()]


def extract_entities(block: str) -> frozenset:
    """Named entities in one record block, normalised for comparison."""
    found = set()
    for phrase in _PROPER_NOUN.findall(block):
        normalised = phrase.strip().lower()
        if normalised in _ENTITY_STOPWORDS or len(normalised) < 6:
            continue
        found.add(normalised)
    for ref in _RECORD_REF.findall(block):
        if any(ch.isdigit() for ch in ref) and len(ref) > 4:
            found.add(ref.lower())
    for kind, number in _ORDINAL_RECORD.findall(block):
        found.add(f"{kind.lower()} {number}")
    return frozenset(found)


def _block_for(text: str, needle: str) -> str:
    """The record block a value's sentence came from."""
    probe = needle.strip()[:60]
    for block in _blocks(text):
        if probe and probe in block:
            return block
    return text


@dataclass(frozen=True)
class FieldValue:
    field: str
    value: str          # normalised, comparable
    display: str        # as it appeared
    sentence: str
    kind: str           # date | money | percent | count | text
    label: str = ""     # set when the value came from a "Label: value" record line
    line_no: int = -1   # position of that record line within the passage
    entities: frozenset = frozenset()  # named entities in this value's record block


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
_MONTH_NAMES = {n: name.title() for name, n in MONTHS.items()}


def _pretty(normalised: str) -> str:
    """Render a normalised YYYY-MM value back as 'Month YYYY' for display."""
    try:
        year, month = normalised.split("-")
        return f"{_MONTH_NAMES[int(month)]} {year}"
    except (ValueError, KeyError):
        return normalised


def normalise_month_year(match: re.Match) -> str:
    month = MONTHS[match.group(1).lower()]
    year = match.group(3)
    return f"{year}-{month:02d}"


def reflow(text: str) -> str:
    """Rejoin hard-wrapped prose while leaving record lines on their own line.

    Source documents are wrapped at ~78 columns, so a single sentence often spans
    three lines. Without this, cue words and the dates they qualify land in
    different fragments and the field guards never fire.
    """
    lines = text.splitlines()
    out: List[str] = []
    for line in lines:
        stripped = line.strip()
        if out and stripped and not out[-1].endswith((".", "!", "?", ":")) and stripped[:1].islower():
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(stripped)
    return "\n".join(out)


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n", reflow(text))
    return [p.strip() for p in parts if p.strip()]


def _field_for(sentence: str, candidates: Sequence[str]) -> Optional[str]:
    """Pick the field whose cue matches and whose subject matter is present."""
    lowered = sentence.lower()
    best: Optional[Tuple[int, str]] = None
    for field in candidates:
        guards = FIELD_CONTEXT_GUARDS.get(field)
        if guards and not any(guard in lowered for guard in guards):
            continue
        for cue in FIELD_CUES.get(field, ()):
            if cue in lowered and (best is None or len(cue) > best[0]):
                best = (len(cue), field)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_field_values(text: str) -> List[FieldValue]:
    """Pull comparable field/value pairs out of one passage."""
    values: List[FieldValue] = []

    line_index = {line.strip(): n for n, line in enumerate(text.splitlines())}
    for label, raw_value in _LABELLED_LINE.findall(text):
        canonical = LABEL_MAP.get(label.strip().lower())
        if not canonical:
            continue
        line = f"{label}: {raw_value}"
        label_key = label.strip().lower()
        line_no = line_index.get(line.strip(), -1)
        if canonical == "employment_dates_range":
            dates = [normalise_month_year(m) for m in _MONTH_YEAR.finditer(raw_value)]
            if dates:
                values.append(
                    FieldValue("employment_start_date", dates[0], _pretty(dates[0]), line,
                               "date", label_key, line_no)
                )
            if len(dates) > 1:
                values.append(
                    FieldValue("employment_end_date", dates[-1], _pretty(dates[-1]), line,
                               "date", label_key, line_no)
                )
            continue
        date_match = _MONTH_YEAR.search(raw_value)
        money_match = _MONEY.search(raw_value)
        if canonical.endswith("_date") and date_match:
            values.append(
                FieldValue(canonical, normalise_month_year(date_match), date_match.group(0),
                           line, "date", label_key, line_no)
            )
        elif canonical.endswith("_amount") and money_match:
            values.append(
                FieldValue(
                    canonical, f"{float(money_match.group(1).replace(',', '')):.2f}",
                    money_match.group(0), line, "money", label_key, line_no,
                )
            )
        elif canonical == "position_title":
            values.append(
                FieldValue(canonical, raw_value.strip().lower(), raw_value, line, "text",
                           label_key, line_no)
            )

    date_fields = [f for f in FIELD_CUES if f.endswith("_date")]
    for sentence in split_sentences(text):
        matches = list(_MONTH_YEAR.finditer(sentence))
        field = _field_for(sentence, date_fields) if matches else None
        if field:
            # A sentence stating a range ("June 2019 to November 2021") must not be
            # read as two competing values for the same field.
            match = matches[-1] if field.endswith("_end_date") else matches[0]
            values.append(
                FieldValue(field, normalise_month_year(match), match.group(0), sentence, "date")
            )
        for match in _MONEY.finditer(sentence):
            field = _field_for(sentence, ["delinquent_amount"])
            if field:
                amount = float(match.group(1).replace(",", ""))
                values.append(
                    FieldValue(field, f"{amount:.2f}", match.group(0), sentence, "money")
                )
        for match in _PERCENT.finditer(sentence):
            if _field_for(sentence, ["credit_utilisation"]):
                values.append(
                    FieldValue(
                        "credit_utilisation", f"{float(match.group(1)):.1f}",
                        match.group(0), sentence, "percent",
                    )
                )
        for match in _TRIP_COUNT.finditer(sentence):
            token = match.group(1).lower()
            count = NUMBER_WORDS.get(token, token if token.isdigit() else None)
            if count is not None:
                values.append(
                    FieldValue(
                        "foreign_trip_count", str(int(count)), match.group(0), sentence, "count"
                    )
                )
    return [
        FieldValue(
            v.field, v.value, v.display, v.sentence, v.kind, v.label, v.line_no,
            extract_entities(_block_for(text, v.sentence)),
        )
        for v in values
        if not any(marker in v.sentence.lower() for marker in _RECONCILING)
    ]


def _dedupe(values: Sequence[FieldValue]) -> List[FieldValue]:
    seen = set()
    unique: List[FieldValue] = []
    for value in values:
        key = (value.field, value.value)
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def detect_contradictions(
    chunks: Sequence[RetrievedChunk], max_flags: int = 3
) -> List[ContradictionFlag]:
    """Flag fields where two passages assert incompatible values."""
    extracted: Dict[str, List[FieldValue]] = {
        chunk.source_id: _dedupe(extract_field_values(chunk.content)) for chunk in chunks
    }
    by_source = {chunk.source_id: chunk for chunk in chunks}

    flags: List[ContradictionFlag] = []
    seen_pairs = set()

    # Within one passage, two *labelled* record lines disagreeing on the same field
    # is the classic "as reported by subject" vs "as confirmed by employer" pattern.
    for source_id, values in extracted.items():
        chunk = by_source[source_id]
        labelled = [v for v in values if v.label]
        for value_a, value_b in combinations(labelled, 2):
            if value_a.field != value_b.field or value_a.value == value_b.value:
                continue
            # Only compare adjacent record lines carrying *different* labels: a repeated
            # label ("Dates confirmed by employer") describes a different record, not a
            # competing value for the same one.
            if value_a.label == value_b.label:
                continue
            if abs(value_a.line_no - value_b.line_no) > 3:
                continue
            if not describes_same_entity(value_a, value_b):
                continue
            key = (value_a.field, *sorted([value_a.value, value_b.value]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            flags.append(
                ContradictionFlag(
                    conflicting_field=value_a.field,
                    description=(
                        f"Potential contradiction requiring human review: within "
                        f"'{chunk.document_name}', {value_a.field.replace('_', ' ')} is recorded "
                        f"both as {value_a.display} and as {value_b.display}."
                    ),
                    source_a_id=source_id,
                    source_a_document=chunk.document_name,
                    source_a_text=value_a.sentence[:400],
                    source_b_id=source_id,
                    source_b_document=chunk.document_name,
                    source_b_text=value_b.sentence[:400],
                    confidence=_confidence(value_a, value_b, same_passage=True),
                    detector="heuristic-field-value-v1",
                )
            )

    for a_id, b_id in combinations(extracted, 2):
        chunk_a, chunk_b = by_source[a_id], by_source[b_id]
        if chunk_a.document_id == chunk_b.document_id:
            continue  # within-document phrasing differences are not conflicts
        for value_a in extracted[a_id]:
            for value_b in extracted[b_id]:
                if value_a.field != value_b.field or value_a.value == value_b.value:
                    continue
                if not describes_same_entity(value_a, value_b):
                    continue
                key = (value_a.field, *sorted([value_a.value, value_b.value]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                flags.append(
                    ContradictionFlag(
                        conflicting_field=value_a.field,
                        description=(
                            f"Potential contradiction requiring human review: "
                            f"'{chunk_a.document_name}' indicates {value_a.field.replace('_', ' ')} "
                            f"of {value_a.display}, while '{chunk_b.document_name}' indicates "
                            f"{value_b.display}."
                        ),
                        source_a_id=a_id,
                        source_a_document=chunk_a.document_name,
                        source_a_text=value_a.sentence[:400],
                        source_b_id=b_id,
                        source_b_document=chunk_b.document_name,
                        source_b_text=value_b.sentence[:400],
                        confidence=_confidence(value_a, value_b),
                        detector="heuristic-field-value-v1",
                    )
                )

    # One flag per conflicting field: a reviewer needs "these sources disagree about
    # the separation date", not every pairwise permutation of the values.
    flags.sort(key=lambda f: f.confidence, reverse=True)
    best_per_field: Dict[str, ContradictionFlag] = {}
    extra_values: Dict[str, int] = {}
    for flag in flags:
        extra_values[flag.conflicting_field] = extra_values.get(flag.conflicting_field, 0) + 1
        best_per_field.setdefault(flag.conflicting_field, flag)

    deduped: List[ContradictionFlag] = []
    for field, flag in best_per_field.items():
        if extra_values[field] > 1:
            flag = flag.model_copy(
                update={
                    "description": (
                        f"{flag.description} A further {extra_values[field] - 1} value "
                        f"disagreement(s) on this field appear in the case file."
                    )
                }
            )
        deduped.append(flag)
    deduped.sort(key=lambda f: f.confidence, reverse=True)
    return deduped[:max_flags]


def describes_same_entity(a: FieldValue, b: FieldValue) -> bool:
    """False only when both sides name entities and none of them overlap."""
    if not a.entities or not b.entities:
        return True  # cannot disprove sameness; leave the pair to the other guards
    return bool(a.entities & b.entities)


def _confidence(a: FieldValue, b: FieldValue, same_passage: bool = False) -> float:
    """Structured, labelled values disagree more meaningfully than prose does."""
    base = 0.55
    if a.kind == b.kind == "date":
        base = 0.72
    if a.kind == b.kind in {"money", "count", "percent"}:
        base = 0.68
    if same_passage and a.label and b.label:
        # Two labelled lines side by side in one record ("as reported" vs "as
        # confirmed") are the strongest signal this heuristic can observe.
        base += 0.08
    return round(min(base, 0.9), 2)


def claim_conflicts_with_evidence(claim_text: str, evidence_text: str) -> Optional[str]:
    """Return the conflicting field when a claim contradicts its own best evidence.

    A claim is contradicted only when the value it asserts is **absent** from the
    evidence while a different value for the same field is present. Without that
    guard, a passage that states both figures — "records identify five trips;
    four correspond to the disclosure" — reads as a contradiction of a claim that
    faithfully reports one of them.
    """
    claim_values = {v.field: v for v in extract_field_values(claim_text)}
    if not claim_values:
        return None

    evidence_values = extract_field_values(evidence_text)
    present_by_field: Dict[str, set] = {}
    for value in evidence_values:
        present_by_field.setdefault(value.field, set()).add(value.value)

    for field, claimed in claim_values.items():
        present = present_by_field.get(field)
        if not present or claimed.value in present:
            continue
        if claimed.value in _raw_values(evidence_text, field):
            continue
        return field
    return None


def _raw_values(text: str, field: str) -> set:
    """Every value of `field` anywhere in the text, ignoring sentence scoping.

    The field guards deliberately pick one value per sentence; for the "is the
    claimed value present at all?" question we want them all.
    """
    values = set()
    if field.endswith("_date"):
        values.update(normalise_month_year(m) for m in _MONTH_YEAR.finditer(text))
    elif field.endswith("_amount"):
        values.update(
            f"{float(m.group(1).replace(',', '')):.2f}" for m in _MONEY.finditer(text)
        )
    elif field == "credit_utilisation":
        values.update(f"{float(m.group(1)):.1f}" for m in _PERCENT.finditer(text))
    elif field == "foreign_trip_count":
        for m in _TRIP_COUNT.finditer(text):
            token = m.group(1).lower()
            count = NUMBER_WORDS.get(token, token if token.isdigit() else None)
            if count is not None:
                values.add(str(int(count)))
        for word, number in NUMBER_WORDS.items():
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                values.add(str(number))
    return values


def llm_contradiction_pass(
    provider: LLMProvider, chunks: Sequence[RetrievedChunk]
) -> List[ContradictionFlag]:  # pragma: no cover - network path
    """Optional second opinion from a live model. Never raises."""
    if provider.is_demo or not chunks:
        return []
    by_source = {chunk.source_id: chunk for chunk in chunks}
    evidence = "\n\n---\n\n".join(f"[{c.source_id}] {c.content}" for c in chunks)
    try:
        payload = provider.complete_json(
            get_prompt("system").template,
            get_prompt("contradiction_analysis").template.format(evidence=evidence),
        )
    except LLMError as exc:
        logger.warning("LLM contradiction pass failed: %s", exc)
        return []

    flags: List[ContradictionFlag] = []
    for item in payload.get("conflicts", []):
        a = by_source.get(item.get("source_a_id", ""))
        b = by_source.get(item.get("source_b_id", ""))
        if not a or not b:
            continue
        flags.append(
            ContradictionFlag(
                conflicting_field=item.get("conflicting_field", "unspecified"),
                description=f"Potential contradiction requiring human review: {item.get('description', '')}",
                source_a_id=a.source_id,
                source_a_document=a.document_name,
                source_a_text=a.content[:400],
                source_b_id=b.source_id,
                source_b_document=b.document_name,
                source_b_text=b.content[:400],
                confidence=float(item.get("confidence", 0.6) or 0.6),
                detector="llm-verifier-v1",
            )
        )
    return flags
