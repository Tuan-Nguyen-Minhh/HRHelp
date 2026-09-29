"""Import disciplinary models from their modules, not from this package.

``src.models.legal`` and ``src.models.documents`` both map a table named
``documents`` for two different schemas. Importing both in one process
makes SQLAlchemy reject the second mapper, so this package stays empty.
"""
