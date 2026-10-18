"""The Gemini provider without the network: a fake client stands in for google-genai."""

import pytest

from seeker_sdk_core import ConfigError, SeekerError, plugins
from seeker_sdk_gemini import GeminiProvider, classify
from seeker_sdk_llm import Pending, Tool, ToolRunner

TOOL = Tool("capital", "v1", "Answer with the capital.",
            {"type": "object", "required": ["capital"], "properties": {"capital": {"type": "string"}}})


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Response:
    def __init__(self, text):
        self.text = text
        self.model_version = "gemini-x-001"
        self.usage_metadata = type("U", (), {"prompt_token_count": 11, "candidates_token_count": 3})()


class Client:
    """`script` is what each call returns (a Response) or raises (an exception)."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def provider(client, **kw):
    slept = []
    clock = iter(range(0, 10_000, 1)).__next__   # one second passes per clock reading
    p = GeminiProvider(api_key="test", model="gemini-test", client=client, sleep=slept.append,
                       clock=lambda: float(clock()), **kw)
    return p, slept


def test_sends_instructions_input_and_schema_and_parses_json(tmp_path):
    client = Client(Response('{"capital": "Islamabad"}'))
    p, _ = provider(client)
    assert ToolRunner(p, str(tmp_path)).call(TOOL, {"country": "Pakistan"}) == {"capital": "Islamabad"}
    call = client.calls[0]
    assert call["model"] == "gemini-test" and call["contents"] == '{"country": "Pakistan"}'
    assert call["config"].system_instruction == TOOL.instructions
    assert call["config"].response_json_schema == TOOL.output_schema and call["config"].response_mime_type == "application/json"
    assert p.usage == {"requests": 1, "input_tokens": 11, "output_tokens": 3} and p.served_by == "gemini-x-001"
    assert p.key == "gemini/gemini-test" and (tmp_path / "gemini" / "gemini-test" / "capital@v1").is_dir()


def test_requests_are_paced_to_the_per_minute_rate():
    p, slept = provider(Client(Response('{"capital": "a"}'), Response('{"capital": "b"}')), requests_per_minute=12)
    p.run(TOOL.request({"c": 1}))
    p.run(TOOL.request({"c": 2}))
    assert slept and abs(slept[0] - 4.0) < 1e-9   # 60/12 = 5 s apart, one second already passed on the clock


def test_a_per_minute_limit_is_waited_out_and_retried():
    p, slept = provider(Client(ApiError(429, "RESOURCE_EXHAUSTED ... Please retry in 7.5s."), Response('{"capital": "x"}')),
                        requests_per_minute=0)
    assert p.run(TOOL.request({"c": 1})) == {"capital": "x"} and slept == [7.5]


def test_the_daily_quota_stops_the_run_cleanly():
    client = Client(ApiError(429, "Quota exceeded for metric generate_content_free_tier_requests, limit PerDay"))
    p, _ = provider(client, requests_per_minute=0)
    first = p.run(TOOL.request({"c": 1}))
    second = p.run(TOOL.request({"c": 2}))   # not even sent
    assert isinstance(first, Pending) and "daily quota" in first.reason and isinstance(second, Pending)
    assert len(client.calls) == 1


def test_a_bad_key_is_a_clear_error_and_other_failures_are_reported():
    p, _ = provider(Client(ApiError(400, "API key not valid. API_KEY_INVALID")), requests_per_minute=0)
    with pytest.raises(ConfigError, match="refused the key"):
        p.run(TOOL.request({"c": 1}))
    p, _ = provider(Client(ApiError(400, "Invalid JSON schema")), requests_per_minute=0)
    with pytest.raises(SeekerError, match="rejected the request for capital@v1"):
        p.run(TOOL.request({"c": 1}))
    p, slept = provider(Client(ApiError(503, "unavailable"), ApiError(503, "x"), ApiError(503, "y")), requests_per_minute=0)
    assert isinstance(p.run(TOOL.request({"c": 1})), Pending) and slept == [5.0, 5.0]


def test_an_answer_that_is_not_json_fails_the_schema_check(tmp_path):
    p, _ = provider(Client(Response("Islamabad")), requests_per_minute=0)
    result = ToolRunner(p, str(tmp_path)).call(TOOL, {"country": "Pakistan"})
    assert isinstance(result, Pending) and "missing 'capital'" in result.reason


def test_classify_and_missing_key(monkeypatch):
    assert classify(ApiError(429, "limit PerDay"))[0] == "daily"
    assert classify(ApiError(429, "retryDelay: 12s")) == ("rate", 12.0)
    assert classify(ApiError(403, "PERMISSION_DENIED"))[0] == "auth"
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="local:apikey:gemini"):
        GeminiProvider()


def test_gemini_is_a_provider_plugin():
    assert "gemini" in plugins.names(plugins.LLM_PROVIDERS)
