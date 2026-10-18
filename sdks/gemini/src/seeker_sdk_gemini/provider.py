"""Gemini provider for seeker-sdk-llm tools (entry point `gemini` in `seeker.llm_providers`).

It sends a tool's instructions as the system instruction, the tool's JSON input as the message, and asks for JSON
matching the tool's `output_schema` (Gemini structured output), so tools and strategies are the same as with the
file queue. Free-tier friendly: requests are paced (SEEKER_GEMINI_RPM, default 10 a minute), a per-minute limit is
waited out and retried, and when the daily quota is used up the provider returns Pending for everything else, so a
run stops cleanly and the next one (tomorrow) continues from the cache.
"""

import json
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple, Union

from seeker_sdk_core import ConfigError, SeekerError
from seeker_sdk_llm import Pending, Provider, ToolRequest

API_KEY_ENV = "GEMINI_API_KEY"
MODEL_ENV = "SEEKER_GEMINI_MODEL"
RPM_ENV = "SEEKER_GEMINI_RPM"
DEFAULT_MODEL = "gemini-flash-latest"
KEY_HELP = "Set GEMINI_API_KEY (mise run local:apikey:gemini) and run through fnox (the mise tasks do)."


def classify(error: Exception) -> Tuple[str, float]:
    """(kind, seconds to wait): kind is daily | rate | auth | transient | fatal."""
    code = getattr(error, "code", None)
    text = str(error)
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        if re.search(r"per ?day|PerDay", text, re.I):
            return "daily", 0.0
        m = re.search(r"retry(?:Delay)?[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)\s*s", text, re.I)
        return "rate", float(m.group(1)) if m else 30.0
    if code in (401, 403) or "API_KEY_INVALID" in text or "PERMISSION_DENIED" in text:
        return "auth", 0.0
    if code is None or (isinstance(code, int) and code >= 500) or "timed out" in text.lower():
        return "transient", 0.0
    return "fatal", 0.0


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 requests_per_minute: Optional[float] = None, client: Any = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.api_key = (api_key or os.environ.get(API_KEY_ENV) or "").strip()
        if not self.api_key and client is None:
            raise ConfigError(f"No Gemini API key. {KEY_HELP}")
        self.model = (model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL).strip()
        rpm = float(requests_per_minute if requests_per_minute is not None else (os.environ.get(RPM_ENV) or 10))
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._client, self._sleep, self._clock = client, sleep, clock
        self._last: Optional[float] = None
        self.exhausted = ""          # set when the daily quota is used up: everything else waits
        self.usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
        self.served_by = ""          # the model version that answered (an alias such as *-latest moves over time)

    @property
    def key(self) -> str:
        return f"gemini/{self.model}"

    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _pace(self) -> None:
        if self._last is not None and self.interval:
            wait = self._last + self.interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def _config(self, request: ToolRequest):
        from google.genai import types
        return types.GenerateContentConfig(system_instruction=request.tool.instructions,
                                           response_mime_type="application/json",
                                           response_json_schema=request.tool.output_schema, temperature=0.2)

    def run(self, request: ToolRequest) -> Union[Dict[str, Any], Pending]:
        if self.exhausted:
            return Pending(request.id, self.exhausted)
        contents = json.dumps(request.input, ensure_ascii=False)
        for attempt in range(3):
            self._pace()
            try:
                response = self.client().models.generate_content(model=self.model, contents=contents,
                                                                  config=self._config(request))
            except Exception as e:  # the SDK's APIError carries .code and the server's message
                kind, wait = classify(e)
                if kind == "daily":
                    self.exhausted = f"Gemini's daily quota for {self.model} is used up; run again tomorrow"
                    return Pending(request.id, self.exhausted)
                if kind == "auth":
                    raise ConfigError(f"Gemini refused the key: {str(e)[:200]}. {KEY_HELP}") from e
                if kind in ("rate", "transient") and attempt < 2:
                    self._sleep(wait if kind == "rate" else 5.0)
                    continue
                if kind in ("rate", "transient"):
                    return Pending(request.id, f"Gemini is busy ({kind}); run again later")
                raise SeekerError(f"Gemini rejected the request for {request.tool.key}: {str(e)[:300]}") from e
            self.usage["requests"] += 1
            self.served_by = getattr(response, "model_version", None) or self.served_by
            meta = getattr(response, "usage_metadata", None)
            if meta is not None:
                self.usage["input_tokens"] += getattr(meta, "prompt_token_count", 0) or 0
                self.usage["output_tokens"] += getattr(meta, "candidates_token_count", 0) or 0
            text = (getattr(response, "text", None) or "").strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"_not_json": text[:500]}  # fails the schema check; the runner reports it and asks again later
        return Pending(request.id, "Gemini did not answer")
