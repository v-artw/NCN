"""Shared fail-closed AI provider configuration and OpenAI-compatible transport."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

SCHEMA_VERSION = "ncn_ai_providers_v1"
CONFIG_ENV = "EDGE_SCOUT_AI_PROVIDERS_CONFIG"
_PROVIDER_FIELDS = {
    "enabled",
    "name",
    "base_url",
    "model",
    "key_file",
    "api_key_env",
    "api_key_file_env",
    "timeout_seconds",
    "extra_options",
}
_FORBIDDEN_BUSINESS_KEYS = {
    "ai",
    "providers",
    "backends",
    "provider",
    "aiprovider",
    "model",
    "aimodel",
    "baseurl",
    "aiurl",
    "aibaseurl",
    "keyfile",
    "aikeyfile",
    "apikey",
    "apikeyenv",
    "apikeyfileenv",
    "aitimeout",
    "temperature",
    "aitemperature",
    "seed",
    "responseformat",
    "airesponseformat",
    "enableai",
    "aienabled",
}


class AIProviderError(ValueError):
    """Raised when central AI provider configuration is invalid or unavailable."""


class AIRequestError(RuntimeError):
    """Redacted request error from an OpenAI-compatible provider."""

    def __init__(self, status: int | None, detail: object):
        self.status = status
        self.detail = redact_ai_error(detail)
        label = "connection_error" if status is None else f"http_{status}"
        super().__init__(f"{label}:{self.detail}")


@dataclass(frozen=True)
class ResolvedAIProvider:
    key: str
    name: str
    base_url: str
    model: str
    timeout_seconds: float
    api_key: str
    extra_options: Mapping[str, Any]


@dataclass(frozen=True)
class AIProviderConfig:
    enabled: bool
    provider: str
    timeout_seconds: float
    temperature: float
    seed: int | None
    response_format: Mapping[str, Any] | None
    providers: Mapping[str, Mapping[str, Any]]
    config_path: Path
    config_sha256: str
    project_root: Path
    schema_version: str = SCHEMA_VERSION

    def as_mapping(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "seed": self.seed,
            "response_format": dict(self.response_format) if self.response_format else None,
            "providers": {key: dict(value) for key, value in self.providers.items()},
            "provider_config_style": self.schema_version,
            "schema_version": self.schema_version,
            "config_path": str(self.config_path),
            "config_sha256": self.config_sha256,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def redact_ai_error(value: object) -> str:
    text = str(value)
    patterns = (
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,}\]]+",
        r"(?i)(bearer\s+)[^\s,}\]]+",
        r"(?i)((?:api[_ -]?key|token|secret)\s*[:=]\s*)[^\s,}\]]+",
    )
    for pattern in patterns:
        text = re.sub(pattern, r"\1[redacted]", text)
    return text[:500]


def forbid_business_ai_overrides(payload: Mapping[str, Any], *, source: Path) -> None:
    def visit(value: object, path: tuple[str, ...] = ()) -> None:
        if not isinstance(value, Mapping):
            return
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = _normalized_key(key)
            child_path = (*path, key)
            provider_context = not path or path[0] != "news"
            if normalized in _FORBIDDEN_BUSINESS_KEYS or (
                provider_context and normalized in {"timeout", "timeoutseconds"}
            ):
                raise AIProviderError(
                    f"business AI config {source} must not override central field: {'.'.join(child_path)}"
                )
            visit(child, child_path)

    visit(payload)


def resolve_ai_config_path(value: object, *, business_config_path: Path) -> Path:
    env_value = os.environ.get(CONFIG_ENV, "").strip()
    selected = env_value or str(value or "").strip()
    if not selected:
        raise AIProviderError(
            f"business AI config {business_config_path} requires ai_config or {CONFIG_ENV}"
        )
    path = Path(selected).expanduser()
    if path.is_absolute():
        return path.resolve()
    project_root = business_config_path.resolve().parents[1]
    return (project_root / path).resolve()


def _normalize_base_url(value: object, *, provider: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIProviderError(f"AI provider {provider!r} has invalid base_url")
    return base_url


def load_ai_provider_config(
    path: Path,
    *,
    project_root: Path | None = None,
    provider_override: str | None = None,
) -> AIProviderConfig:
    config_path = path.expanduser().resolve()
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AIProviderError(f"AI provider config does not exist: {config_path}") from exc
    if not isinstance(payload, Mapping):
        raise AIProviderError("AI provider config must be a mapping")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise AIProviderError(f"AI provider schema_version must be {SCHEMA_VERSION}")
    root = (project_root or config_path.parents[1]).expanduser().resolve()
    providers_raw = payload.get("providers")
    if not isinstance(providers_raw, Mapping) or not providers_raw:
        raise AIProviderError("AI provider config requires non-empty providers")
    providers: dict[str, dict[str, Any]] = {}
    for raw_name, raw_provider in providers_raw.items():
        name = str(raw_name).strip()
        if not name or not isinstance(raw_provider, Mapping):
            raise AIProviderError("each AI provider must be a named mapping")
        unknown = set(raw_provider) - _PROVIDER_FIELDS
        if unknown:
            raise AIProviderError(
                f"AI provider {name!r} has unsupported fields: {', '.join(sorted(map(str, unknown)))}"
            )
        if str(raw_provider.get("api_key", "")).strip():
            raise AIProviderError(f"AI provider {name!r} must not contain inline api_key")
        provider = dict(raw_provider)
        provider["enabled"] = bool(provider.get("enabled", False))
        provider["base_url"] = _normalize_base_url(provider.get("base_url"), provider=name)
        provider["model"] = str(provider.get("model", "")).strip()
        if not provider["model"]:
            raise AIProviderError(f"AI provider {name!r} requires model")
        provider["name"] = str(provider.get("name", name)).strip() or name
        provider["api_key_env"] = str(provider.get("api_key_env", "")).strip()
        provider["api_key_file_env"] = str(provider.get("api_key_file_env", "")).strip()
        key_file_value = str(provider.get("key_file", "")).strip()
        if key_file_value:
            key_file = Path(key_file_value).expanduser()
            if not key_file.is_absolute():
                key_file = root / key_file
            provider["key_file"] = str(key_file.resolve())
        else:
            provider["key_file"] = ""
        provider["timeout_seconds"] = float(
            provider.get("timeout_seconds", payload.get("timeout_seconds", 120))
        )
        extra = provider.get("extra_options") or {}
        if not isinstance(extra, Mapping):
            raise AIProviderError(f"AI provider {name!r} extra_options must be a mapping")
        provider["extra_options"] = dict(extra)
        providers[name] = provider
    selected = str(provider_override or payload.get("provider", "")).strip()
    enabled = bool(payload.get("enabled", True))
    if enabled:
        if selected not in providers:
            raise AIProviderError(f"unknown AI provider: {selected!r}")
        if not providers[selected]["enabled"]:
            raise AIProviderError(f"selected AI provider is disabled: {selected!r}")
    response_format = payload.get("response_format")
    if response_format is not None and not isinstance(response_format, Mapping):
        raise AIProviderError("response_format must be a mapping or null")
    seed = payload.get("seed")
    if seed is not None:
        seed = int(seed)
    return AIProviderConfig(
        enabled=enabled,
        provider=selected,
        timeout_seconds=float(payload.get("timeout_seconds", 120)),
        temperature=float(payload.get("temperature", 0)),
        seed=seed,
        response_format=dict(response_format) if response_format else None,
        providers=providers,
        config_path=config_path,
        config_sha256=_sha256(config_path),
        project_root=root,
    )


def _resolve_api_key(provider: Mapping[str, Any]) -> str:
    api_key_env = str(provider.get("api_key_env", "")).strip()
    if api_key_env:
        value = os.environ.get(api_key_env, "").strip()
        if value:
            return value
    key_file_env = str(provider.get("api_key_file_env", "")).strip()
    if key_file_env:
        env_path = os.environ.get(key_file_env, "").strip()
        if env_path:
            path = Path(env_path).expanduser()
            if not path.is_file():
                raise AIProviderError(f"AI API key file does not exist: {path}")
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
    key_file_value = str(provider.get("key_file", "")).strip()
    if key_file_value:
        path = Path(key_file_value).expanduser()
        if not path.is_file():
            raise AIProviderError(f"AI API key file does not exist: {path}")
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    raise AIProviderError("selected AI provider has no available credential")


class OpenAICompatibleClient:
    """Minimal shared transport; workflow modules own prompts and response parsing."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float = 0,
        seed: int | None = 42,
        response_format: Mapping[str, Any] | None = None,
        extra_options: Mapping[str, Any] | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.seed = seed
        self.response_format = dict(response_format) if response_format else None
        self.extra_options = dict(extra_options or {})

    def request_json(
        self,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        user_agent: str = "NCN-AI/1.0",
    ) -> Any:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": user_agent}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace").strip()
            raise AIRequestError(exc.code, detail or exc.reason) from exc
        except urllib.error.URLError as exc:
            raise AIRequestError(None, exc.reason) from exc
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            raise AIRequestError(None, type(exc).__name__) from exc

    def models(self, *, user_agent: str = "NCN-AI/1.0") -> Any:
        return self.request_json("/models", user_agent=user_agent)

    def resolved_model(self, *, user_agent: str = "NCN-AI/1.0") -> str:
        if self.model != "auto":
            return self.model
        payload = self.models(user_agent=user_agent)
        models = payload.get("data", []) if isinstance(payload, Mapping) else []
        if not models or not isinstance(models[0], Mapping) or not models[0].get("id"):
            raise AIProviderError("AI endpoint returned no model for model=auto")
        return str(models[0]["id"])

    def chat_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        user_agent: str,
        extra_payload: Mapping[str, Any] | None = None,
    ) -> tuple[Any, str]:
        model = self.resolved_model(user_agent=user_agent)
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": self.temperature,
            **self.extra_options,
            **dict(extra_payload or {}),
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.response_format:
            payload["response_format"] = dict(self.response_format)
        try:
            response = self.request_json(
                "/chat/completions", payload, user_agent=user_agent
            )
        except AIRequestError as exc:
            if exc.status not in {400, 422}:
                raise
            compatible = dict(payload)
            compatible.pop("response_format", None)
            compatible.pop("seed", None)
            response = self.request_json(
                "/chat/completions", compatible, user_agent=user_agent
            )
        return response, model


def build_ai_client(config: AIProviderConfig | Mapping[str, Any]) -> OpenAICompatibleClient | None:
    if isinstance(config, AIProviderConfig):
        normalized = config
    else:
        path_value = config.get("config_path") or config.get("ai_config_path")
        if not path_value:
            raise AIProviderError("normalized AI config is missing config_path")
        normalized = load_ai_provider_config(Path(str(path_value)))
    if not normalized.enabled:
        return None
    provider = normalized.providers[normalized.provider]
    api_key = _resolve_api_key(provider)
    return OpenAICompatibleClient(
        provider=normalized.provider,
        base_url=str(provider["base_url"]),
        api_key=api_key,
        model=str(provider["model"]),
        timeout_seconds=float(provider.get("timeout_seconds", normalized.timeout_seconds)),
        temperature=normalized.temperature,
        seed=normalized.seed,
        response_format=normalized.response_format,
        extra_options=provider.get("extra_options") or {},
    )
