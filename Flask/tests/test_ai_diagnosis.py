from ai_diagnosis import is_ai_available


def test_ai_fallback_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert is_ai_available() is False
