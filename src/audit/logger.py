"""Application audit trail.

Events are append-only. There is deliberately no update or delete path: a
correction is recorded as a new event, never as a mutation of an existing one.

Metadata is filtered through `_scrub` so credentials and obviously sensitive
keys never reach the audit store.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.db import session_scope
from src.database.models import AuditEvent
from src.database.repositories import AuditRepository
from src.models.schemas import ActorType

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {"api_key", "apikey", "token", "password", "secret", "authorization"}


class EventType:
    CASE_OPENED = "case_opened"
    CASE_INGESTED = "case_ingested"
    ANALYSIS_REQUESTED = "analysis_requested"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    SUMMARY_GENERATED = "summary_generated"
    CLAIMS_EXTRACTED = "claims_extracted"
    CLAIMS_VALIDATED = "claims_validated"
    UNSUPPORTED_CLAIM_DETECTED = "unsupported_claim_detected"
    CONTRADICTION_DETECTED = "contradiction_detected"
    METRICS_COMPUTED = "metrics_computed"
    OVERALL_RECOMMENDATION_GENERATED = "overall_recommendation_generated"
    RECOMMENDATION_CHANGED = "recommendation_changed_after_evidence_update"
    ADJUDICATOR_AGREED_WITH_AI = "adjudicator_agreed_with_ai"
    ADJUDICATOR_DISAGREED_WITH_AI = "adjudicator_disagreed_with_ai"
    ADDITIONAL_INFORMATION_REQUESTED = "additional_information_requested"
    CASE_ESCALATED = "case_escalated"
    CASE_PROCEEDED = "case_proceeded"
    EVIDENCE_SOURCE_OPENED = "evidence_source_opened"
    REVIEW_DECISION = "review_decision"
    SUMMARY_EDITED = "summary_edited"
    EVIDENCE_REQUESTED = "additional_evidence_requested"
    ERROR = "error"


def _scrub(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    clean: Dict[str, Any] = {}
    for key, value in metadata.items():
        if any(marker in key.lower() for marker in _SENSITIVE_KEYS):
            clean[key] = "[redacted]"
        elif isinstance(value, str) and len(value) > 2000:
            clean[key] = value[:2000] + " …[truncated]"
        else:
            clean[key] = value
    return clean


def log_event(
    event_type: str,
    action: str,
    *,
    case_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    actor_type: str = ActorType.SYSTEM.value,
    actor_name: str = "system",
    metadata: Optional[Dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> Optional[str]:
    """Append one audit event. Never raises: audit failure must not break a demo."""
    payload = dict(
        case_id=case_id,
        analysis_id=analysis_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_name=actor_name,
        action=action,
        event_metadata=_scrub(metadata),
    )
    try:
        if session is not None:
            return AuditRepository.append(session, **payload).id
        with session_scope() as scoped:
            return AuditRepository.append(scoped, **payload).id
    except SQLAlchemyError as exc:  # pragma: no cover - environment dependent
        logger.error("Failed to write audit event %s: %s", event_type, exc)
        return None


def log_ai_event(event_type: str, action: str, **kwargs: Any) -> Optional[str]:
    kwargs.setdefault("actor_name", "CaseBrief AI")
    return log_event(event_type, action, actor_type=ActorType.AI.value, **kwargs)


def log_human_event(event_type: str, action: str, reviewer: str, **kwargs: Any) -> Optional[str]:
    return log_event(
        event_type, action, actor_type=ActorType.HUMAN.value, actor_name=reviewer, **kwargs
    )


def get_case_trail(case_id: str, limit: int = 500) -> List[AuditEvent]:
    with session_scope() as session:
        return AuditRepository.list_for_case(session, case_id, limit)


def get_recent_trail(limit: int = 500) -> List[AuditEvent]:
    with session_scope() as session:
        return AuditRepository.list_recent(session, limit)
