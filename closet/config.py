"""Settings and provider routing.

Every model call goes through `client_for(provider)`, so moving a step from the
Meta Model API to Baseten-hosted Muse Spark Open is an .env change, not a code change.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: str

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise SystemExit(
                f"{self.api_key_env} is not set. Copy .env.example to .env and add it."
            )
        return key


PROVIDERS = {
    "meta": Provider(
        "meta",
        os.environ.get("MODEL_API_BASE_URL", "https://api.meta.ai/v1"),
        "MODEL_API_KEY",
    ),
    "baseten": Provider(
        "baseten",
        os.environ.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
        "BASETEN_API_KEY",
    ),
}


# Key shapes for the two providers (Baseten "b10_…", Meta "LLM|…"), in case one turns up other than as the exact value.
_KEY_SHAPES = re.compile(r"b10_[A-Za-z0-9_-]{8,}|LLM\|[A-Za-z0-9_|-]{8,}|LLM_[0-9][A-Za-z0-9_|-]{8,}")


def redact(text: str) -> str:
    """Error text with any API key taken out. Failure messages are stored and shown in the app (a plan's
    trace, a tag error, a try-on job), and a provider's error can echo the key it was sent."""
    for p in PROVIDERS.values():
        key = os.environ.get(p.api_key_env, "")
        if len(key) >= 8:
            text = text.replace(key, "[REDACTED]")
    return _KEY_SHAPES.sub("[REDACTED]", text)


def client_for(provider: str = "meta") -> OpenAI:
    p = PROVIDERS[provider]
    return OpenAI(base_url=p.base_url, api_key=p.api_key, max_retries=3)


def async_client_for(provider: str = "meta") -> AsyncOpenAI:
    p = PROVIDERS[provider]
    return AsyncOpenAI(base_url=p.base_url, api_key=p.api_key, max_retries=3)


SAM_MODEL = os.environ.get("SAM_MODEL", "sam-3.1")
REASON_MODEL = os.environ.get("REASON_MODEL", "muse-spark-1.3")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "muse-image-1.0")
TAG_PROVIDER = os.environ.get("TAG_PROVIDER", "meta")
# The oni's "brain" (morning planner, check-in learning) runs on open weights by default:
# Muse Spark Open via Baseten, falling back to Muse Spark 1.3 on Meta if Baseten fails.
PLAN_PROVIDER = os.environ.get("PLAN_PROVIDER", "baseten")
PLAN_MODEL = {
    "baseten": os.environ.get("PLAN_MODEL_BASETEN", os.environ.get("TAG_MODEL_BASETEN", "meta-models/muse-spark-open-1026")),
    "meta": os.environ.get("PLAN_MODEL_META", os.environ.get("REASON_MODEL", "muse-spark-1.3")),
}
TAG_MODEL = {
    "meta": os.environ.get("TAG_MODEL_META", "muse-spark-1.3"),
    "baseten": os.environ.get("TAG_MODEL_BASETEN", "meta-models/muse-spark-open-1026"),
}
