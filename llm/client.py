import json
import os
import re

from dotenv import load_dotenv

load_dotenv()


def selected_provider() -> str:
    """Choose the active LLM provider from env. Groq is the project default."""
    configured = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if configured:
        return configured
    return "groq"


def default_model(provider: str = "groq") -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def groq_model_candidates(model: str | None = None) -> list[str]:
    """Try a small built-in model fallback list so .env can stay simple."""
    preferred = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    fallbacks = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    return [preferred] + [item for item in fallbacks if item != preferred]


def groq_configs() -> list[dict]:
    """Return configured Groq keys in priority order without logging secrets."""
    configs = []

    primary_key = os.getenv("GROQ_API_KEY")
    if primary_key and primary_key.strip().startswith("gsk_"):
        configs.append(
            {
                "label": "GROQ_API_KEY",
                "api_key": primary_key,
            }
        )

    secondary_key = os.getenv("GROQ_API_KEY_2")
    if secondary_key and secondary_key.strip().startswith("gsk_"):
        configs.append(
            {
                "label": "GROQ_API_KEY_2",
                "api_key": secondary_key,
            }
        )

    return configs


def is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retryable_markers = [
        "401",
        "invalid_api_key",
        "invalid api key",
        "unauthorized",
        "429",
        "rate_limit",
        "rate limit",
        "quota",
        "tokens per day",
        "resource_exhausted",
        "too many requests",
        "model_not_found",
        "model not found",
        "does not exist",
    ]
    return any(marker in text for marker in retryable_markers)


def strip_json_markdown(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    starts = [idx for idx in (text.find("{"), text.find("[")) if idx >= 0]
    if not starts:
        return text

    start = min(starts)
    end_object = text.rfind("}")
    end_array = text.rfind("]")
    end = max(end_object, end_array)
    if end >= start:
        return text[start : end + 1]
    return text


def llm_text(
    prompt: str,
    *,
    system: str = "",
    temperature: float = 0,
    model: str | None = None,
    json_mode: bool = False,
) -> str:
    provider = selected_provider()
    if provider == "groq":
        return _groq_text(prompt, system=system, temperature=temperature, model=model, json_mode=json_mode)
    raise ValueError("LLM_PROVIDER must be 'groq'.")


def llm_json(
    prompt: str,
    *,
    system: str = "Return only valid JSON.",
    temperature: float = 0,
    model: str | None = None,
) -> dict | list:
    raw = llm_text(prompt, system=system, temperature=temperature, model=model, json_mode=True)
    return json.loads(strip_json_markdown(raw))


def _groq_text(
    prompt: str,
    *,
    system: str = "",
    temperature: float = 0,
    model: str | None = None,
    json_mode: bool = False,
) -> str:
    from groq import Groq

    configs = groq_configs()
    if not configs:
        raise RuntimeError("No valid Groq API key found. Set GROQ_API_KEY or GROQ_API_KEY_2 to a key that starts with gsk_.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for config in configs:
        client = Groq(api_key=config["api_key"])
        for candidate_model in groq_model_candidates(model):
            try:
                kwargs = {
                    "model": candidate_model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as exc:
                last_error = exc
                if not is_retryable_provider_error(exc):
                    raise
                print(f"Groq provider {config['label']} could not use {candidate_model}; trying fallback.")

    raise last_error or RuntimeError("Groq request failed.")
