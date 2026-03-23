"""Multi-provider dataset generator — uses ALL available APIs in round-robin."""

import time
import os
import httpx
import random
from dataclasses import dataclass
from typing import Any

@dataclass
class Provider:
    name: str
    url: str
    key: str
    model: str
    format: str  # "openai" or "anthropic"
    rpm_limit: int = 60  # requests per minute
    last_call: float = 0
    errors: int = 0
    success: int = 0

def load_providers() -> list[Provider]:
    """Load all available providers from env."""
    providers = []

    # Anthropic Claude Sonnet
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and len(key) > 20:
        providers.append(Provider(
            name="claude-sonnet",
            url="https://api.anthropic.com/v1/messages",
            key=key,
            model="claude-sonnet-4-20250514",
            format="anthropic",
            rpm_limit=50,
        ))

    # Codestral
    key = os.environ.get("CODESTRAL_API_KEY", "")
    if key and len(key) > 10:
        providers.append(Provider(
            name="codestral",
            url="https://codestral.mistral.ai/v1/chat/completions",
            key=key,
            model="codestral-latest",
            format="openai",
            rpm_limit=120,
        ))

    # Mistral
    key = os.environ.get("MISTRAL_API_KEY", "")
    if key and len(key) > 10:
        providers.append(Provider(
            name="mistral",
            url="https://api.mistral.ai/v1/chat/completions",
            key=key,
            model="mistral-small-latest",
            format="openai",
            rpm_limit=60,
        ))

    # OpenAI
    key = os.environ.get("OPENAI_API_KEY", "")
    if key and len(key) > 20:
        providers.append(Provider(
            name="openai",
            url="https://api.openai.com/v1/chat/completions",
            key=key,
            model="gpt-4o-mini",
            format="openai",
            rpm_limit=60,
        ))

    # Google Gemini
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key and len(key) > 10:
        providers.append(Provider(
            name="gemini",
            url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            key=key,
            model="gemini-2.0-flash",
            format="google",
            rpm_limit=60,
        ))

    return providers


def call_provider(provider: Provider, system: str, prompt: str, temperature: float = 0.3, max_tokens: int = 700) -> str | None:
    """Call a provider and return the response text."""
    # Rate limit
    now = time.time()
    min_interval = 60.0 / provider.rpm_limit
    wait = min_interval - (now - provider.last_call)
    if wait > 0:
        time.sleep(wait)
    provider.last_call = time.time()

    try:
        with httpx.Client(timeout=60.0) as client:
            if provider.format == "anthropic":
                resp = client.post(provider.url, headers={
                    "x-api-key": provider.key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }, json={
                    "model": provider.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                })
                resp.raise_for_status()
                answer = resp.json()["content"][0]["text"]

            elif provider.format == "google":
                resp = client.post(provider.url, headers={
                    "content-type": "application/json",
                }, json={
                    "contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
                })
                resp.raise_for_status()
                answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

            else:  # openai format
                headers = {
                    "Authorization": f"Bearer {provider.key}",
                    "Content-Type": "application/json",
                }
                body: dict[str, Any] = {
                    "model": provider.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if provider.name == "codestral":
                    body["response_format"] = {"type": "json_object"}
                resp = client.post(provider.url, headers=headers, json=body)
                resp.raise_for_status()
                answer = resp.json()["choices"][0]["message"]["content"]

            provider.success += 1
            return answer

    except Exception:
        provider.errors += 1
        return None


def pick_provider(providers: list[Provider]) -> Provider:
    """Pick the best available provider (least errors, respecting rate limits)."""
    available = [p for p in providers if p.errors < 10]
    if not available:
        # Reset errors and try again
        for p in providers:
            p.errors = 0
        available = providers
    # Weighted by success rate
    return random.choice(available)


class MultiProviderGenerator:
    def __init__(self):
        self.providers = load_providers()
        print(f"Loaded {len(self.providers)} providers: {[p.name for p in self.providers]}")

    def generate(self, system: str, prompt: str, temperature: float = 0.3) -> tuple[str | None, str]:
        """Generate with best available provider. Returns (text, provider_name)."""
        provider = pick_provider(self.providers)
        result = call_provider(provider, system, prompt, temperature)
        return result, provider.name

    def stats(self) -> dict:
        return {p.name: {"success": p.success, "errors": p.errors} for p in self.providers}


if __name__ == "__main__":
    # Test all providers
    gen = MultiProviderGenerator()
    for p in gen.providers:
        result = call_provider(p, "You are a test.", "Say OK.", temperature=0.1, max_tokens=10)
        status = "OK" if result else "FAIL"
        print(f"  {p.name}: {status} -> {(result or '')[:50]}")
