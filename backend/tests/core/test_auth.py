from __future__ import annotations


def test_local_auth_dependencies_return_configured_ids(monkeypatch) -> None:
    from chatmaster.core import auth

    class DummySettings:
        local_workspace_id = "workspace-test"
        local_user_id = "user-test"

    monkeypatch.setattr(auth, "get_settings", lambda: DummySettings())

    assert auth.get_current_workspace_id() == "workspace-test"
    assert auth.get_current_user_id() == "user-test"
