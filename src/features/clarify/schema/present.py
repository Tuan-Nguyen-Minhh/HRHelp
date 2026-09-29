"""Fact rows for the confirmation form."""

from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.catalog import required_specs
from src.features.clarify.schema import FactView


def present_facts(family: str, merged: dict[str, StoredFact]) -> list[FactView]:
    """List every required fact, in the order the chat asks for them."""
    views = []
    for spec in required_specs(family):
        item = merged.get(spec.key)
        views.append(
            FactView(
                fact_key=spec.key,
                label=spec.label,
                fact_value=item.value if item else None,
                confirmed=bool(item and item.confirmed),
            )
        )
    return views
