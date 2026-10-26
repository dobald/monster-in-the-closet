"""Settings and provider routing.

Every model call goes through `client_for(provider)`, so moving a step from the
Meta Model API to Baseten-hosted Muse Spark Open is an .env change, not a code change.
"""

from __future__ import annotations

import os
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
TAG_MODEL = {
    "meta": os.environ.get("TAG_MODEL_META", "muse-spark-1.3"),
    "baseten": os.environ.get("TAG_MODEL_BASETEN", "meta-models/muse-spark-open-1026"),
}
