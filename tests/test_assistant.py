from datetime import date, timedelta

import pytest

from fieldmate.assistant import Assistant, due_from_text


class FakeModel:
    def structured(self, *args, **kwargs):
        return {"action": "create_task", "text": "Invented task", "due_date": None}


def test_action_classifier_cannot_write_on_followup():
    assistant = Assistant(None, None, FakeModel())
    intent = assistant.classify("And what about that?", [{"role": "user", "content": "Explain fieldwork"}])
    assert intent.action == "question"


def test_explicit_capture_preserves_wording():
    assistant = Assistant(None, None, None)
    assert assistant.classify("Save a note: east gate locked", []).text == "east gate locked"
    assert assistant.classify("Add a task: revisit tomorrow", []).action == "create_task"
    assert assistant.classify("What should I include in a visit handover?", []).action == "question"


def test_task_dates():
    assert due_from_text("revisit tomorrow") == (date.today() + timedelta(days=1)).isoformat()
    assert due_from_text("no date given") is None
    with pytest.raises(ValueError, match="date wasn't valid"):
        due_from_text("2026-02-31")
