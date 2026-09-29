"""Import disciplinary models so foreign keys resolve in one metadata."""

from src.models.agent_retrievals import AgentRetrieval
from src.models.agent_runs import AgentRun
from src.models.case_access import CaseAccess
from src.models.case_drafts import CaseDraft
from src.models.case_facts import CaseFact
from src.models.case_violations import CaseViolation
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.models.messages import Message
from src.models.policies import Policy
from src.models.policy_versions import PolicyVersion
from src.models.recommendation_citations import RecommendationCitation
from src.models.recommendations import Recommendation
from src.models.reviews import Review
from src.models.tool_calls import ToolCall
from src.models.users import User
from src.models.violation_types import ViolationType

__all__ = [
    "AgentRetrieval",
    "AgentRun",
    "Case",
    "CaseAccess",
    "CaseDraft",
    "CaseFact",
    "CaseViolation",
    "Conversation",
    "DisciplinaryDecision",
    "Document",
    "DocumentChunk",
    "Message",
    "Policy",
    "PolicyVersion",
    "Recommendation",
    "RecommendationCitation",
    "Review",
    "ToolCall",
    "User",
    "ViolationType",
]
