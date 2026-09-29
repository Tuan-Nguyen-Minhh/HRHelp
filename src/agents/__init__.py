"""System-wide agent.

``graph`` is the template used by ``POST /chat``.
``case_graph`` is the case sub-agent: open a case, clarify facts, then run the
cite retrieval pipeline and emit ``handoff.CaseHandoff`` for the sanction agent.
``runs`` is the ledger every feature writes when it opens a turn or records a search.
"""
