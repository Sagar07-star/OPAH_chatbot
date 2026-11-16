"""Conversation storage: one thread per scope, safe under concurrency."""
from __future__ import annotations

import threading

from app.assistant import memory


def test_conversation_creation_is_race_safe():
    ids: list[str] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            ids.append(memory.ensure_conversation("clt_003", None, "All projects")["id"])
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(set(ids)) == 1


def test_project_and_general_threads_stay_separate():
    general = memory.ensure_conversation("clt_001", None, "All projects")
    project = memory.ensure_conversation("clt_001", "prj_1002", "Spring Lookbook")
    assert general["id"] != project["id"]
    assert memory.ensure_conversation("clt_001", "prj_1002")["id"] == project["id"]
    assert memory.ensure_conversation("clt_002", "prj_1002", "Other")["id"] != project["id"]


def test_messages_survive_a_new_connection_and_keep_order():
    conversation = memory.ensure_conversation("clt_001", "prj_1004", "Product Launch Video")
    first = memory.append_message(conversation["id"], "user", "hello")
    second = memory.append_message(conversation["id"], "assistant", "hi", {"type": "text", "message": "hi"})
    rows = memory.messages_for(conversation["id"])
    assert [row["id"] for row in rows] == [first["id"], second["id"]]
    assert rows[1]["envelope"]["type"] == "text"


def test_working_memory_is_scoped_per_project():
    memory.wm_set("clt_001", "prj_1002", "priorities", ["style"])
    assert memory.wm_get("clt_001", "prj_1002", "priorities") == ["style"]
    assert memory.wm_get("clt_001", "prj_1004", "priorities") is None
    memory.wm_clear("clt_001", "prj_1002")
    assert memory.wm_get("clt_001", "prj_1002", "priorities") is None
