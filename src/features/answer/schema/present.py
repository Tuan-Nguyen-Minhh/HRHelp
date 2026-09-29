"""Build the API answer from a recommendation row and its citations."""

from uuid import UUID

from src.common.text import clip_quote
from src.features.answer.model.layers import BasisLayer, layer_of
from src.features.answer.model.store import CitationRow
from src.features.answer.schema import AnswerView, CitationView, ProcessStep
from src.features.cite.model.passage import Passage
from src.models.recommendations import Recommendation


def to_answer_view(recommendation: Recommendation, citations: list[CitationView], case_status: str) -> AnswerView:
    """Group citations into the four layers the screen renders separately."""
    grouped: dict[BasisLayer, list[CitationView]] = {layer: [] for layer in BasisLayer}
    for item in citations:
        grouped[item.layer].append(item)
    return AnswerView(
        recommendation_id=recommendation.id,
        case_id=recommendation.case_id,
        case_status=case_status,
        agent_run_id=recommendation.agent_run_id,
        rationale=recommendation.rationale,
        sanction_type=recommendation.sanction_type,
        process_steps=_steps(recommendation.process_steps),
        risk_level=recommendation.risk_level,
        missing_internal_rule=not grouped[BasisLayer.INTERNAL_RULE],
        message=recommendation.recommendation,
        legal_basis=grouped[BasisLayer.LEGAL_BASIS],
        internal_rule=grouped[BasisLayer.INTERNAL_RULE],
        precedent=grouped[BasisLayer.PRECEDENT],
        inspection_risk=grouped[BasisLayer.INSPECTION_RISK],
    )


def view_from_row(row: CitationRow) -> CitationView:
    """Re-layer a stored citation from the policy it was taken from."""
    code = row.policy_code or ""
    name = row.policy_name or ""
    return CitationView(
        citation_id=row.citation_id,
        chunk_id=row.chunk_id,
        layer=layer_of(row.policy_type, code, name),
        policy_type=row.policy_type,
        policy_code=row.policy_code,
        policy_name=row.policy_name,
        quote=row.quote,
        article=row.article,
        clause=row.clause,
        point=row.point,
        score=row.score,
    )


def view_from_passage(citation_id: UUID, passage: Passage) -> CitationView:
    """Layer a passage that was just stored as a citation."""
    return CitationView(
        citation_id=citation_id,
        chunk_id=passage.chunk_id,
        layer=layer_of(passage.policy_type, passage.policy_code, passage.policy_name),
        policy_type=passage.policy_type,
        policy_code=passage.policy_code,
        policy_name=passage.policy_name,
        quote=clip_quote(passage.content),
        article=passage.article,
        clause=passage.clause,
        point=passage.point,
        score=passage.score,
    )


def _steps(raw: object) -> list[ProcessStep]:
    if not isinstance(raw, list):
        return []
    return [ProcessStep.model_validate(item) for item in raw]
