"""Central configuration: LLM provider, models, rate limits.

Any OpenAI-compatible provider can be used. Select it with LLM_PROVIDER:

    openrouter  (default)  key: OPENROUTER_API_KEY
    mistral     free "Experiment" plan on La Plateforme   key: MISTRAL_API_KEY
    groq        free tier                                   key: GROQ_API_KEY
    gemini      free tier (OpenAI-compatible endpoint)      key: GEMINI_API_KEY
    custom      any endpoint: set LLM_BASE_URL + LLM_API_KEY + LLM_MODEL

For every provider other than openrouter, LLM_MODEL (or the provider default)
is applied to all agents, overriding MODEL_RELEVANCE / MODEL_RISK /
MODEL_SYNTHESIS, so OpenRouter model ids left in .env cannot leak through.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

# provider -> (api key env var, base url, default model, default max requests/minute, seed parameter)
PROVIDERS = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
                   "mistralai/mistral-small-3.2-24b-instruct", 0, "seed"),
    # Free "Experiment" plan (Nov 2026): mistral-small/medium = 0 req/min, ministral-8b = 2 req/min.
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1", "ministral-8b-latest", 2, "random_seed"),
    # Free plan (Nov 2026): 1,000 requests/day and 8,000 tokens/minute per model -> ~6 calls/minute.
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", 6, "seed"),
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/",
               "gemini-2.5-flash-lite", 12, "seed"),
    "custom": ("LLM_API_KEY", "", "", 0, "seed"),
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
if LLM_PROVIDER not in PROVIDERS:
    raise ValueError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Choose one of: {', '.join(PROVIDERS)}")
_key_env, _default_url, _default_model, _default_rpm, LLM_SEED_PARAM = PROVIDERS[LLM_PROVIDER]

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv(_key_env)
if LLM_PROVIDER == "openrouter":
    LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("OPENROUTER_BASE_URL") or _default_url
else:
    LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _default_url

LLM_MODEL = os.getenv("LLM_MODEL") or _default_model
if LLM_PROVIDER != "openrouter" and LLM_MODEL:
    # Optional per-role models (e.g. to spread free daily quotas over two models).
    for _name in ("MODEL_RELEVANCE", "MODEL_RISK", "MODEL_SYNTHESIS"):
        os.environ[_name] = os.getenv(f"LLM_{_name}") or LLM_MODEL

# Extra request parameters for every call, as JSON (e.g. {"reasoning_effort": "low"}).
# Default for gpt-oss on Groq: low reasoning effort, which keeps token usage inside free quotas.
_default_extra = '{"reasoning_effort": "low"}' if LLM_PROVIDER == "groq" else "{}"
LLM_EXTRA_PARAMS = json.loads(os.getenv("LLM_EXTRA_PARAMS", _default_extra))

# Client-side pacing for free tiers (0 = unlimited).
LLM_MAX_RPM = int(os.getenv("LLM_MAX_RPM", str(_default_rpm)))

MODEL_RELEVANCE = os.getenv("MODEL_RELEVANCE") or LLM_MODEL
MODEL_RISK = os.getenv("MODEL_RISK") or LLM_MODEL
MODEL_SYNTHESIS = os.getenv("MODEL_SYNTHESIS") or LLM_MODEL

# Backward-compatible names used by the original v0 agents.
OPENROUTER_API_KEY = LLM_API_KEY
OPENROUTER_BASE_URL = LLM_BASE_URL

# Agno's OpenAIChat sends the system prompt with the OpenAI-specific role
# "developer"; Mistral, Groq and Gemini reject it (HTTP 422). Use "system".
SYSTEM_ROLE_MAP = {"system": "system", "user": "user", "assistant": "assistant", "tool": "tool", "model": "assistant"}


def _apply_agno_provider_compat() -> None:
    if LLM_PROVIDER == "openrouter":
        return
    try:
        from agno.models.openai import OpenAIChat
    except ImportError:
        return
    OpenAIChat.default_role_map = {**OpenAIChat.default_role_map, **SYSTEM_ROLE_MAP}
    if LLM_EXTRA_PARAMS and not getattr(OpenAIChat, "_signalguard_extra", False):
        original = OpenAIChat.get_request_params

        def get_request_params(self, *args, **kwargs):
            params = original(self, *args, **kwargs)
            for key, value in LLM_EXTRA_PARAMS.items():
                params.setdefault(key, value)
            return params

        OpenAIChat.get_request_params = get_request_params
        OpenAIChat._signalguard_extra = True


_apply_agno_provider_compat()

# Shared relevance threshold used by the pipeline and the final digest.
HIGH_RELEVANCE_THRESHOLD = 70
