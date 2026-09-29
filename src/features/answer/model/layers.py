"""Split retrieved passages into the four layers a sanction may use."""

from dataclasses import dataclass
from enum import StrEnum

from src.features.cite.model.passage import Passage

_LABOUR_TYPES = frozenset({"DECREE", "CIRCULAR"})


class BasisLayer(StrEnum):
    """The four groups shown on the answer."""

    LEGAL_BASIS = "legal_basis"
    INTERNAL_RULE = "internal_rule"
    PRECEDENT = "precedent"
    INSPECTION_RISK = "inspection_risk"


@dataclass(frozen=True)
class LayeredBasis:
    """Passages split so a sanction cannot be read from the wrong layer."""

    legal_basis: list[Passage]
    internal_rule: list[Passage]
    precedent: list[Passage]
    inspection_risk: list[Passage]

    @property
    def missing_internal_rule(self) -> bool:
        return not self.internal_rule


def layer_of(policy_type: str | None, policy_code: str, policy_name: str) -> BasisLayer:
    """Map one policy to a layer.

    Decree 283 and any administrative-penalty instrument stay in the
    inspection layer. A guiding decree such as 145/2020 stays with the law.
    An unknown type is inspection as well, so it cannot feed a sanction.
    """
    if policy_type == "INTERNAL_RULE":
        return BasisLayer.INTERNAL_RULE
    if policy_type == "PRECEDENT":
        return BasisLayer.PRECEDENT
    if policy_type == "LAW":
        return BasisLayer.LEGAL_BASIS
    if _is_administrative_penalty(policy_type, policy_code, policy_name):
        return BasisLayer.INSPECTION_RISK
    if policy_type in _LABOUR_TYPES:
        return BasisLayer.LEGAL_BASIS
    return BasisLayer.INSPECTION_RISK


def split_passages(passages: list[Passage]) -> LayeredBasis:
    """Group passages. Order inside a layer follows the retrieval rank."""
    grouped: dict[BasisLayer, list[Passage]] = {layer: [] for layer in BasisLayer}
    for passage in passages:
        layer = layer_of(passage.policy_type, passage.policy_code, passage.policy_name)
        grouped[layer].append(passage)
    return LayeredBasis(
        legal_basis=grouped[BasisLayer.LEGAL_BASIS],
        internal_rule=grouped[BasisLayer.INTERNAL_RULE],
        precedent=grouped[BasisLayer.PRECEDENT],
        inspection_risk=grouped[BasisLayer.INSPECTION_RISK],
    )


def _is_administrative_penalty(policy_type: str | None, policy_code: str, policy_name: str) -> bool:
    if policy_type in {"LAW", "INTERNAL_RULE", "PRECEDENT"}:
        return False
    folded_code = policy_code.casefold().replace("đ", "d")
    if "283/2026" in folded_code or "283_2026" in folded_code or "nd-283" in folded_code:
        return True
    folded_name = policy_name.casefold()
    return "xử phạt" in folded_name and "hành chính" in folded_name
