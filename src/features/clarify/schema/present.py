"""Fact rows for the confirmation form."""

from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.catalog import FactSpec, required_specs
from src.features.clarify.schema import FactView


def present_facts(
    family: str,
    merged: dict[str, StoredFact],
    specs: tuple[FactSpec, ...] | None = None,
) -> list[FactView]:
    """List every required fact, in the order the chat asks for them."""
    views = []
    used = set()
    for spec in specs or required_specs(family):
        item = merged.get(spec.key)
        views.append(
            FactView(
                fact_key=spec.key,
                label=spec.label,
                fact_value=item.value if item else None,
                confirmed=bool(item and item.confirmed),
            )
        )
        used.add(spec.key)
    for key, item in sorted(merged.items()):
        if key in used:
            continue
        views.append(
            FactView(
                fact_key=key,
                label=key,
                fact_value=item.value,
                confirmed=bool(item.confirmed),
            )
        )
    return views
