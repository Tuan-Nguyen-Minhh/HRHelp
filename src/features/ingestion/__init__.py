"""Admin-only document ingestion: upload a source file, run the step2/step3
pipeline in memory, and write the result into the official corpus tables.

No new tables or columns: ``documents`` (its existing ``ingest_status``,
``source``, ``file_type``, ``content_hash`` columns) is the ingestion record,
``document_chunks``/``chunk_references`` hold the content, and ``audit_logs``
carries provenance and failures.
"""
