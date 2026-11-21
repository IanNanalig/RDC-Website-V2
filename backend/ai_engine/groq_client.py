import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings


class GroqUnavailable(RuntimeError):
    """Raised after every configured Groq model fails."""

    def __init__(self, message, *, reason="provider_unavailable"):
        super().__init__(message)
        self.reason = reason


class InvalidGroqResponse(ValueError):
    pass


# Structured output is opt-in for callers and limited to the configured model
# families with strict JSON Schema support.
STRICT_OUTPUT_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}
CLASSIFICATION_ONLY_MODELS = {
    "meta-llama/llama-prompt-guard-2-86m",
    "meta-llama/llama-prompt-guard-2-22m",
}


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
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise InvalidGroqResponse("Groq returned no completion choices.")
    if choices[0].get("finish_reason") == "length":
        raise InvalidGroqResponse("Groq stopped at the completion token limit.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise InvalidGroqResponse("Groq returned an empty completion.")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise InvalidGroqResponse("Groq returned JSON that is not an object.")
    return parsed


def _request(model, messages, *, temperature, max_completion_tokens, response_schema=None):
    response_format = {"type": "json_object"}
    if response_schema is not None and model in STRICT_OUTPUT_MODELS:
        response_format = {"type": "json_schema", "json_schema": response_schema}
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "response_format": response_format,
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


def _http_failure(error):
    provider_code = ""
    try:
        payload = json.loads(error.read(8192))
        details = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(details, dict):
            code = details.get("code")
            if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code):
                provider_code = code
    except (OSError, ValueError):
        pass
    finally:
        error.close()

    status = error.code
    if status == 413 or provider_code == "context_length_exceeded":
        reason = "request_too_large"
    elif provider_code in {"json_validate_failed", "schema_validation_failed"}:
        reason = "invalid_response"
    elif status >= 500:
        reason = "provider_server_error"
    else:
        reason = {
            400: "provider_request_rejected", 401: "provider_auth", 403: "provider_auth",
            404: "provider_request_rejected", 429: "rate_limited",
        }.get(status, "provider_unavailable")
    return reason, f"HTTP {status}" + (f" ({provider_code})" if provider_code else "")


def complete_json(messages, *, temperature=0.1, max_completion_tokens=None, validate=None, response_schema=None):
    """Request validated JSON, trying the configured primary model before the backup."""
    if not is_groq_enabled():
        raise GroqUnavailable("Groq is not configured.")
    models = _models()
    if not models:
        raise GroqUnavailable("No Groq model is configured.")
    limit = int(max_completion_tokens or getattr(settings, "GROQ_MAX_COMPLETION_TOKENS", 4096))
    attempted = []
    failures = []
    reasons = set()
    for index, model in enumerate(models):
        attempted.append(model)
        if model in CLASSIFICATION_ONLY_MODELS:
            reasons.add("provider_model")
            failures.append(f"{model}: classification-only model cannot generate a scorecard")
            continue
        try:
            data = _request(
                model,
                messages,
                temperature=max(0.0, min(2.0, float(temperature))),
                max_completion_tokens=max(256, limit),
                response_schema=response_schema,
            )
            if validate is not None and not validate(data):
                raise InvalidGroqResponse("Groq response did not match the required application structure.")
            return GroqCompletion(
                data=data,
                model=model,
                used_backup=index > 0,
                attempted_models=tuple(attempted),
            )
        except urllib.error.HTTPError as exc:
            reason, detail = _http_failure(exc)
            reasons.add(reason)
            failures.append(f"{model}: {detail}")
        except (TimeoutError, socket.timeout):
            reasons.add("provider_timeout")
            failures.append(f"{model}: timed out")
        except urllib.error.URLError:
            reasons.add("provider_network")
            failures.append(f"{model}: connection failed")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            reasons.add("invalid_response")
            detail = str(exc) if isinstance(exc, InvalidGroqResponse) else type(exc).__name__
            failures.append(f"{model}: {detail}")
    # A compact retry can still succeed on the model that rejected the size
    # even if the other configured model failed for a different reason.
    reason = "request_too_large" if "request_too_large" in reasons else (
        next(iter(reasons)) if len(reasons) == 1 else "provider_unavailable"
    )
    raise GroqUnavailable("All configured Groq models failed (" + "; ".join(failures) + ").", reason=reason)
