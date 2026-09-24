import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings


class GroqUnavailable(RuntimeError):
    """Raised after every configured Groq model fails."""


@dataclass(frozen=True)
class GroqCompletion:
    data: dict
    model: str
    used_backup: bool
    attempted_models: tuple[str, ...]


def is_groq_enabled():
    return bool(getattr(settings, "GROQ_ENABLED", False) and getattr(settings, "GROQ_API_KEY", ""))


def _models():
    primary = str(getattr(settings, "GROQ_PRIMARY_MODEL", "llama-3.1-8b-instant") or "").strip()
    backup = str(getattr(settings, "GROQ_BACKUP_MODEL", "llama-3.3-70b-versatile") or "").strip()
    result = []
    for model in (primary, backup):
        if model and model not in result:
            result.append(model)
    return result


def _decode_json_content(payload):
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise ValueError("Groq returned no completion choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Groq returned an empty completion.")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Groq returned JSON that is not an object.")
    return parsed


def _request(model, messages, *, temperature, max_completion_tokens):
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        str(getattr(settings, "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RDC-NCR-Portal/1.0",
        },
    )
    timeout = int(getattr(settings, "GROQ_TIMEOUT_SECONDS", 30))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _decode_json_content(payload)


def complete_json(messages, *, temperature=0.1, max_completion_tokens=None, validate=None):
    """Request validated JSON, trying the configured primary model before the backup."""
    if not is_groq_enabled():
        raise GroqUnavailable("Groq is not configured.")
    models = _models()
    if not models:
        raise GroqUnavailable("No Groq model is configured.")
    limit = int(max_completion_tokens or getattr(settings, "GROQ_MAX_COMPLETION_TOKENS", 4096))
    attempted = []
    failures = []
    for index, model in enumerate(models):
        attempted.append(model)
        try:
            data = _request(
                model,
                messages,
                temperature=max(0.0, min(2.0, float(temperature))),
                max_completion_tokens=max(256, limit),
            )
            if validate is not None and not validate(data):
                raise ValueError("Groq response did not match the required application structure.")
            return GroqCompletion(
                data=data,
                model=model,
                used_backup=index > 0,
                attempted_models=tuple(attempted),
            )
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            failures.append(f"{model}: {type(exc).__name__}")
    raise GroqUnavailable("All configured Groq models failed (" + "; ".join(failures) + ").")
