"""System-wide agent.

``graph`` is the template agent. ``http`` mounts it at ``POST /chat`` and ``GET /status``.
``case_graph`` is the case sub-agent: open a case, clarify facts, then run the
cite retrieval pipeline and emit ``handoff.CaseHandoff`` for the sanction agent.
The sanction agent stores a draft and the caller closes ``ProposalHandoff`` for
the dispatch agent, which holds the draft or submits a legal ticket.
``runs`` is the ledger every feature writes when it opens a turn or records a search.
"""
