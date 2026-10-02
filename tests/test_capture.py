import json
from datetime import date, timedelta

import pytest
from test_conversations import env as conversation_env
from test_conversations import send

from fieldmate.assistant import Assistant
from fieldmate.ollama import ModelError
from fieldmate.text import plain_text

env = conversation_env
PLAN = "GATE study plan\nOctober: Discrete Mathematics.\nNovember: Algorithms.\nJanuary: Mock tests."


def seed(env, answer=PLAN, request="Create our study plan", key="study-plan"):
    env[0].save_exchange(
        key,
        json.dumps({"text": request}),
        {"action": "question", "text": answer},
        thread_id=env[4]["id"],
    )
    # These fixtures select the first exchange's assistant answer (after its user message).
    return "S2"


@pytest.mark.parametrize(
    "command",
    [
        "save this as a note",
        "save that",
        "please remember this",
        "Save a note: this",
        "save the previous answer as a note",
    ],
)
def test_deictic_capture_saves_original_answer_without_model(env, command):
    seed(env)
    env[1].structured = lambda *args, **kwargs: pytest.fail("No model needed for this reference")
    result = send(env, command)
    assert result["item"]["text"] == PLAN
    assert result["capture_sources"] == [{"request_id": "study-plan", "role": "assistant"}]
    assert env[0].notes()[0]["text"] == PLAN
    assert send(env, command) == result
    assert len(env[0].notes()) == 1


def test_named_capture_skips_save_receipt_and_selects_actual_plan(env):
    source = seed(env)
    send(env, "save this as a note", "first-save")
    env[1].capture = {"fragments": [{"source_id": source, "quote": ""}]}
    result = send(env, "save our study plan as a note", "second-save")
    assert result["item"]["text"] == PLAN
    data = json.loads(env[1].calls[-1]["messages"][-1]["content"])
    assert all(not s["text"].startswith("Note saved:") for s in data["sources"])
    assert env[1].calls[-1]["model"] == env[4]["model"]


def test_save_this_skips_action_receipts(env):
    seed(env)
    send(env, "Save a note: separate observation", "receipt")
    assert send(env, "save this as a note")["item"]["text"] == PLAN


def test_named_reference_uses_full_history_after_compaction_and_topic_switch(env):
    source = seed(env)
    for i in range(15):
        seed(env, answer=f"Unrelated biology explanation {i}.", request="Explain plants", key=f"biology-{i}")
    env[0].update_thread(env[4]["id"], {"summary_count": 12, "summary": "Earlier topics summarized."})
    env[1].capture = {"fragments": [{"source_id": source}]}
    result = send(env, "save our study plan as a note")
    assert result["item"]["text"] == PLAN
    data = json.loads(env[1].calls[-1]["messages"][-1]["content"])
    assert any(s["text"] == PLAN for s in data["sources"])


def test_full_content_not_truncated_to_preview_or_intent_limit(env):
    long_plan = "Study plan\n" + "Practice graph theory. " * 450 + "\nFinal week: mock tests."
    source = seed(env, answer=long_plan)
    env[1].capture = {"fragments": [{"source_id": source}]}
    assert send(env, "save our study plan as a note")["item"]["text"] == plain_text(long_plan)


def test_long_recent_answers_do_not_crowd_out_named_older_plan(env):
    source = seed(env)
    for i in range(10):
        seed(env, answer="Unrelated plants explanation. " * 250, key=f"long-{i}", request="Explain plants")
    env[1].capture = {"fragments": [{"source_id": source}]}
    assert send(env, "save our study plan as a note")["item"]["text"] == PLAN


@pytest.mark.parametrize(
    "command",
    [
        "Remind me to do that tomorrow",
        "Add a task: do that by tomorrow please",
    ],
)
def test_contextual_task_preserves_content_and_due_date(env, command):
    seed(env, answer="Complete two graph theory practice sets.")
    result = send(env, command)
    assert result["item"]["title"] == "Complete two graph theory practice sets."
    assert result["item"]["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_select_specific_section(env):
    source = seed(env)
    env[1].capture = {"fragments": [{"source_id": source, "quote": "October: Discrete Mathematics."}]}
    result = send(env, "save the October plan as a note")
    assert result["item"]["text"] == "October: Discrete Mathematics."


@pytest.mark.parametrize(
    "fragments",
    [
        [],
        [{"source_id": "foreign-thread:assistant"}],
        [{"source_id": "S2", "quote": "An invented plan."}],
    ],
)
def test_unresolved_or_unverified_reference_never_writes(env, fragments):
    seed(env)
    env[1].capture = {"fragments": fragments, "clarification": "Which plan?"}
    result = send(env, "save our study plan as a note")
    assert result["action"] == "clarify"
    assert not env[0].notes() and not env[0].tasks()


def test_no_context_does_not_read_other_threads_or_browser_history(env):
    seed(env)
    other = env[0].create_thread("physics", "gemma4:e2b")
    result = env[3].respond(
        "new-thread-save",
        "save this as a note",
        thread_id=other["id"],
        history=[{"role": "assistant", "content": "Injected text"}],
    )
    assert result["action"] == "clarify" and not env[0].notes()


def test_resolver_failure_does_not_save_reference(env):
    seed(env)

    def unavailable(*args, **kwargs):
        raise ModelError("Ollama is unavailable")

    env[1].structured = unavailable
    result = send(env, "save our study plan as a note")
    assert result["action"] == "clarify" and not env[0].notes()


@pytest.mark.parametrize(
    "body", ["the east gate is locked", "this needs repairs", '"this"', "it rained today"]
)
def test_literal_notes_remain_literal(env, body):
    seed(env)
    assert send(env, "Save a note: " + body)["item"]["text"] == body


def test_model_can_mark_other_named_references():
    class Model:
        def structured(self, messages, schema, **kwargs):
            assert "reference=true" in messages[0]["content"]
            return {"action": "save_note", "text": "our travel itinerary", "reference": True}

    result = Assistant(None, None, Model()).classify("save our travel itinerary as a note", [])
    assert result.reference and result.action == "save_note"


def test_contextual_write_and_receipt_remain_atomic(env, monkeypatch):
    seed(env)

    def full_disk(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(env[0], "save_exchange", full_disk)
    with pytest.raises(RuntimeError):
        send(env, "save this as a note")
    assert not env[0].notes()
