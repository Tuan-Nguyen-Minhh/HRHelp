"""The four product features.

Each feature keeps its own model, schema, and controller. ``src.main`` mounts
those controllers. Cite has no HTTP route: the case graph calls it.
Shared request helpers live in ``src.common``. The agent ledger lives in ``src.agents``.
"""
