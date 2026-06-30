"""Local auth boundary.

The local/small-team MVP has no login yet. These dependencies centralize the
current workspace/user so future authentication can replace this file without
touching business handlers.
"""

from __future__ import annotations

from chatmaster.config import get_settings


def get_current_workspace_id() -> str:
    return get_settings().local_workspace_id


def get_current_user_id() -> str:
    return get_settings().local_user_id
