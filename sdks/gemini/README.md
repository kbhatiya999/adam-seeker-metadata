# seeker-sdk-gemini

Runs the seeker-sdk-llm tools on Google Gemini: provider plugin `gemini` (`--provider gemini`).

- Sends a tool's instructions as the system instruction, its JSON input as the message, and asks for JSON matching the
  tool's `output_schema` (structured output), so strategies and prompts are the same as with the file queue.
- Key: `GEMINI_API_KEY` (`mise run local:apikey:gemini` saves it to fnox.local.toml). Model: `SEEKER_GEMINI_MODEL`
  (default `gemini-flash-latest`); every model has its own free daily quota.
- Free-tier friendly: requests are paced (`SEEKER_GEMINI_RPM`, default 10 a minute); a per-minute limit is waited out
  and retried; when the daily quota is used up every further request returns Pending, so a run stops cleanly and the
  next one continues from the cache (`data/llm/cache/gemini/<model>/`).

```python
from seeker_sdk_gemini import GeminiProvider
from seeker_sdk_llm import ToolRunner

runner = ToolRunner(GeminiProvider(model="gemini-2.5-flash-lite"))
```
