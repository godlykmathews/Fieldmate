import pytest
from fastapi.testclient import TestClient

from fieldmate.app import create_app
from fieldmate.config import Settings
from fieldmate.text import plain_text, speech_text

EXAMPLE = "**Engineering Mathematics**\nYou should study Discrete Mathematics and combinatorics [D1]."


def test_reported_formatting_is_removed_from_display_and_speech():
    assert (
        plain_text(EXAMPLE)
        == "Engineering Mathematics\nYou should study Discrete Mathematics and combinatorics."
    )
    assert (
        speech_text(EXAMPLE)
        == "Engineering Mathematics You should study Discrete Mathematics and combinatorics."
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("## Topics\n- **Logic**\n* _Graphs_\n> `Functions` [web-2]", "Topics\nLogic\nGraphs\nFunctions"),
        ("See [the guide](https://example.org/guide) [1].", "See the guide."),
        ("2 * 3 = 6; 2 ** 3 ** 4; x_y; A[1]", "2 * 3 = 6; 2 ** 3 ** 4; x_y; A[1]"),
    ],
)
def test_plain_text_keeps_content_and_math(raw, expected):
    assert plain_text(raw) == expected


def test_speech_uses_operator_words_instead_of_deleting_math():
    assert speech_text("2 * 3 = 6, 50% & 1/2") == "2 times 3 equals 6, 50 percent and 1 divided by 2"


def test_speech_endpoint_cleans_old_or_directly_submitted_markdown(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    captured = []
    app.state.voice.speak = lambda text: captured.append(text) or b"fake-wav"
    with TestClient(app) as client:
        assert client.post("/api/speak", json={"text": EXAMPLE}).status_code == 200
        assert client.post("/api/speak", json={"text": "[D1]"}).status_code == 400
    assert captured == [speech_text(EXAMPLE)]
