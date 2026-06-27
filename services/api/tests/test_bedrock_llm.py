"""Unit tests for the Bedrock LLM adapter — no AWS, injected fake client."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.adapters.bedrock_llm import BedrockError, BedrockLLM
from app.settings import Settings


class _FakeBedrock:
    """Stands in for the boto3 ``bedrock-runtime`` client."""

    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("bedrock unavailable")
        return {"output": {"message": {"content": [{"text": self._text}]}}}


def _llm(
    text: str = "", *, raises: bool = False, model_id: str = "eu.anthropic.claude"
) -> tuple[BedrockLLM, _FakeBedrock]:
    client = _FakeBedrock(text, raises=raises)
    llm = BedrockLLM(client=client, model_id=model_id, accountable_human="Chair")
    return llm, client


def _user_text(client: _FakeBedrock) -> str:
    return str(client.calls[0]["messages"][0]["content"][0]["text"])


def test_draft_reply_returns_model_text_and_uses_model_id() -> None:
    llm, client = _llm("Dear Owner, ... Kind regards, Chair")
    out = llm.draft_reply(subject="Leak", body="My geyser leaks", party="Jane", context=[])
    assert "Kind regards" in out
    assert client.calls[0]["modelId"] == "eu.anthropic.claude"
    user = _user_text(client)
    assert "Jane" in user and "Leak" in user


def test_draft_reply_marks_context_as_do_not_quote_background() -> None:
    llm, client = _llm("ok")
    llm.draft_reply(subject="s", body="b", party="P", context=["secret owner note"])
    assert "DO NOT quote" in _user_text(client)


def test_answer_question_grounds_in_context() -> None:
    llm, client = _llm("Per the rules ... not formal legal advice.")
    out = llm.answer_question(question="Can I keep a dog?", context=["Pets need consent"])
    assert "legal advice" in out
    assert "Pets need consent" in _user_text(client)


def test_answer_question_without_context_short_circuits_without_call() -> None:
    llm, client = _llm("should not be used")
    out = llm.answer_question(question="x", context=[])
    assert "could not find" in out
    assert client.calls == []


def test_suggest_metadata_parses_strict_json() -> None:
    llm, _ = _llm(json.dumps({"title": "Conduct Rules", "category": "rules"}))
    assert llm.suggest_metadata(content="...", filename="rules.pdf") == {
        "title": "Conduct Rules",
        "category": "rules",
    }


def test_suggest_metadata_invalid_category_falls_back_to_general() -> None:
    llm, _ = _llm(json.dumps({"title": "T", "category": "banana"}))
    assert llm.suggest_metadata(content="...", filename="f.txt")["category"] == "general"


def test_suggest_metadata_non_json_degrades_to_heuristics() -> None:
    llm, _ = _llm("not json at all")
    meta = llm.suggest_metadata(content="# Levy Statement\nArrears outstanding", filename="x.md")
    assert meta["title"] == "Levy Statement"
    assert meta["category"] == "finance"


def test_converse_failure_raises_bedrock_error() -> None:
    llm, _ = _llm(raises=True)
    with pytest.raises(BedrockError):
        llm.draft_reply(subject="s", body="b", party="P", context=[])
    llm2, _ = _llm(raises=True)
    with pytest.raises(BedrockError):
        llm2.answer_question(question="q", context=["c"])


def test_settings_bedrock_model_id_applies_eu_geo_prefix() -> None:
    settings = Settings(bedrock_inference_region="eu-west-1")
    assert settings.bedrock_model_id("balanced").startswith("eu.anthropic.claude-sonnet-4-6")


def test_settings_bedrock_model_id_no_prefix_outside_geo() -> None:
    settings = Settings(bedrock_inference_region="", aws_region="af-south-1")
    assert settings.bedrock_model_id("fast") == "anthropic.claude-haiku-4-5-20251001-v1:0"


def test_build_llm_returns_bedrock_adapter_when_provider_is_bedrock() -> None:
    from app.bootstrap import build_llm

    llm = build_llm(Settings(llm_provider="bedrock", bedrock_inference_region="eu-west-1"))
    assert isinstance(llm, BedrockLLM)


def test_build_llm_defaults_to_stub() -> None:
    from app.adapters.stub_llm import StubLLM
    from app.bootstrap import build_llm

    assert isinstance(build_llm(Settings(llm_provider="stub")), StubLLM)
