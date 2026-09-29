from src.features.answer.model.layers import BasisLayer, layer_of, split_passages
from src.features.cite.model.passage import Passage


def _passage(policy_type: str, code: str, name: str) -> Passage:
    from uuid import uuid4

    return Passage(
        chunk_id=uuid4(),
        policy_version_id=uuid4(),
        content="đoạn",
        article="125",
        clause="1",
        point=None,
        score=1.0,
        policy_type=policy_type,
        policy_code=code,
        policy_name=name,
    )


def test_law_and_guiding_decree_are_legal_basis():
    assert layer_of("LAW", "BLLD-2019", "Bộ luật Lao động") is BasisLayer.LEGAL_BASIS
    decree = layer_of("DECREE", "145/2020/ND-CP", "Nghị định 145/2020 hướng dẫn Bộ luật Lao động")
    assert decree is BasisLayer.LEGAL_BASIS


def test_internal_rule_and_precedent_keep_their_layers():
    assert layer_of("INTERNAL_RULE", "NQ-2024", "Nội quy lao động") is BasisLayer.INTERNAL_RULE
    assert layer_of("PRECEDENT", "QD-01", "Quyết định đã ban hành") is BasisLayer.PRECEDENT


def test_decree_283_is_inspection_risk_not_a_sanction_menu():
    by_code = layer_of("DECREE", "283/2026/ND-CP", "Nghị định 283/2026/NĐ-CP")
    by_name = layer_of("DECREE", "ND-KHAC", "Quy định xử phạt vi phạm hành chính")
    assert by_code is BasisLayer.INSPECTION_RISK
    assert by_name is BasisLayer.INSPECTION_RISK


def test_split_keeps_283_out_of_the_legal_basis():
    layered = split_passages(
        [
            _passage("LAW", "BLLD-2019", "Bộ luật Lao động"),
            _passage("DECREE", "283/2026/ND-CP", "Nghị định xử phạt vi phạm hành chính"),
            _passage("INTERNAL_RULE", "NQ", "Nội quy"),
        ]
    )
    assert len(layered.legal_basis) == 1
    assert len(layered.inspection_risk) == 1
    assert len(layered.internal_rule) == 1
    assert layered.legal_basis[0].policy_code == "BLLD-2019"
