# Registration hook: importing this module makes every model in
# src.models attach to Base.metadata.
#
# Nothing imports it today -- alembic/env.py pulls Base from src.db.base and
# the models explicitly. Kept because the star import is the conventional
# way to register future models without editing env.py, and it is harmless.
from src.db.base import Base  # noqa: F401
from src.models import *  # noqa: F403
