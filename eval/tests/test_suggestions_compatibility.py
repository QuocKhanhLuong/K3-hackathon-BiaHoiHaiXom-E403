"""Tests for frontend compatibility, deduplication, and chip logic contract."""


def test_frontend_suggestions_contract():
    """Verify backend produces compatible default_suggestions and suggestions fields."""
    from backend.app.ai.result_mapper import suggestions

    res_completed = {
        "status": "completed",
        "followups": [
            {"label": "Chip A", "question": "Question A?"},
            {"label": "Chip B", "question": "Question B?"},
        ],
    }

    sug = suggestions(res_completed)
    assert sug == ["Question A?", "Question B?"]

    res_awaiting = {
        "status": "awaiting_check",
        "followups": [{"label": "Chip A", "question": "Question A?"}],
    }
    assert suggestions(res_awaiting) == []

    res_blocked = {
        "status": "blocked",
        "followups": [{"label": "Chip A", "question": "Question A?"}],
    }
    assert suggestions(res_blocked) == []
