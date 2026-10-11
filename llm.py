"""
Thin LLM client. Works with any OpenAI-compatible endpoint (Groq, Gemini, OpenAI).
If no API key is set, `available` is False and every agent falls back to its
rule-based logic (Demo mode), so the app always runs.
"""
import json
import os
import re
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-20b",
        "key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "ollama (local)": {
        "url": "http://localhost:11434/v1/chat/completions",
        "model": "llama3.2",
        "key_env": None,
        "local": True,
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
}


class LLM:
    def __init__(self, provider="groq", api_key=None, model=None):
        cfg = PROVIDERS.get(provider, PROVIDERS["groq"])
        self.provider = provider
        self.url = cfg["url"]
        self.model = model or os.getenv("LLM_MODEL") or cfg["model"]
        self.local = cfg.get("local", False)
        self.api_key = api_key or (os.getenv(cfg["key_env"], "") if cfg["key_env"] else "")
        self.local_ok = self._ping_local() if self.local else False
        self.calls = 0
        self.errors = 0
        self.consecutive_failures = 0
        self.disabled = False
        self.repairs = 0
        self.last_error = ""

    def _ping_local(self):
        """Ollama needs no key; check that the local server is running."""
        try:
            return requests.get("http://localhost:11434/api/tags", timeout=1.5).ok
        except requests.RequestException:
            return False

    @property
    def available(self):
        if self.disabled:
            return False
        return self.local_ok if self.local else bool(self.api_key)

    def chat(self, system, user, temperature=0.4, max_retries=3):
        if not self.available:
            return None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        for attempt in range(max_retries):
            try:
                r = requests.post(self.url, headers=headers, json=payload, timeout=120 if self.local else 60)
                if r.status_code == 429:  # free-tier rate limit: wait as long as the API asks, then retry
                    wait = r.headers.get("retry-after")
                    self.last_error = "HTTP 429 rate limit: " + r.text[:200]
                    time.sleep(min(float(wait), 30) if wait else 8 * (attempt + 1))
                    continue
                if r.status_code >= 400:  # 401 bad key, 400 bad model/request: retrying will not help
                    self.last_error = f"HTTP {r.status_code}: {r.text[:300]}"
                    break
                self.calls += 1
                self.consecutive_failures = 0
                return r.json()["choices"][0]["message"]["content"]
            except requests.ConnectionError as e:  # server unreachable: stop retrying
                self.last_error = f"Connection error: {e}"
                break
            except Exception as e:  # timeout or malformed response: retry
                self.last_error = str(e)
                time.sleep(2)
        self.errors += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:  # circuit breaker: stop calling a broken API
            self.disabled = True
        return None

    def test_connection(self):
        """Tiny call used by the 'Test connection' button. Returns (ok, message)."""
        if not self.available:
            return False, "No API key entered (or Ollama not running)."
        self.disabled = False
        text = self.chat("You are a test.", "Reply with the single word: OK", 0, max_retries=1)
        if text:
            return True, f"Connected to {self.model}. Reply: {text.strip()[:40]}"
        return False, self.last_error or "Unknown error"

    def chat_json(self, system, user, temperature=0.3):
        text = self.chat(
            system + "\nRespond with ONLY one valid JSON object. No markdown fences, no commentary.",
            user,
            temperature,
        )
        return parse_json(text)


    def chat_structured(self, system, user, schema, temperature=0.3):
        """Ask for JSON matching a Pydantic schema; validate; one repair attempt; else None."""
        from pydantic import ValidationError
        schema_hint = json.dumps(schema.model_json_schema().get("properties", {}))
        sys_prompt = (system + "\nRespond with ONLY one JSON object matching this schema "
                      f"(no markdown, no commentary): {schema_hint}")
        text = self.chat(sys_prompt, user, temperature)
        for attempt in range(2):
            data = parse_json(text)
            if data is not None:
                try:
                    return schema.model_validate(data)
                except ValidationError as e:
                    error = str(e)
            else:
                error = "Output was not valid JSON."
            if attempt == 0 and text is not None:
                self.repairs = getattr(self, "repairs", 0) + 1
                text = self.chat(sys_prompt, f"{user}\n\nYour previous answer failed validation: {error[:400]}\n"
                                             "Return corrected JSON only.", 0.1)
        return None


def parse_json(text):
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
