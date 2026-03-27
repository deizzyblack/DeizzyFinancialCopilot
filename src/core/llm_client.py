"""Thin LLM client for fallback mapping and period normalization.

Uses the Anthropic Messages API format. Designed for minimal cost:
- Small prompts with constrained output
- Haiku model by default
- Short timeout
- Returns None on any failure (caller falls through to default)
"""

import json
import logging
from dataclasses import dataclass

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

METRIC_NAMES = [
    "Revenue", "EBITDA", "Net Income", "Cash", "Assets", "Liabilities", "Equity"
]

PERIOD_TYPES = ["QUARTER", "HALF", "YTD", "FULL_YEAR"]


@dataclass
class LLMMappingResult:
    metric: str | None
    confidence: float


@dataclass
class LLMPeriodResult:
    period: str | None
    period_type: str | None
    confidence: float


class LLMClient:
    """Calls external LLM API for fallback only. Returns structured data or None."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
    ):
        self.api_url = api_url or settings.llm_api_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.enabled = enabled if enabled is not None else settings.llm_enabled

    def map_metric(self, raw_label: str) -> LLMMappingResult | None:
        """Ask LLM to map a financial label to a standard metric."""
        if not self.enabled:
            return None

        prompt = (
            f"Map this financial label to one of the standard metrics.\n\n"
            f"Label: \"{raw_label}\"\n"
            f"Valid metrics: {json.dumps(METRIC_NAMES)}\n\n"
            f"Respond with ONLY valid JSON, no other text:\n"
            f'{{"metric": "<metric or null>", "confidence": <0.0-1.0>}}'
        )

        raw = self._call(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            metric = data.get("metric")
            confidence = float(data.get("confidence", 0.0))

            if metric and metric not in METRIC_NAMES:
                return None

            return LLMMappingResult(
                metric=metric if metric else None,
                confidence=min(max(confidence, 0.0), 1.0),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("LLM mapping response not valid JSON: %s", raw[:200])
            return None

    def normalize_period(self, raw_period: str) -> LLMPeriodResult | None:
        """Ask LLM to parse a messy period string."""
        if not self.enabled:
            return None

        prompt = (
            f"Parse this financial period label into structured format.\n\n"
            f"Raw period: \"{raw_period}\"\n"
            f"Valid period_type values: {json.dumps(PERIOD_TYPES)}\n"
            f"Period format examples: Q1-2025, H2-2024, YTD-2025, FY-2024\n\n"
            f"Respond with ONLY valid JSON, no other text:\n"
            f'{{"period": "<formatted or null>", "period_type": "<type or null>", '
            f'"confidence": <0.0-1.0>}}'
        )

        raw = self._call(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            period = data.get("period")
            period_type = data.get("period_type")
            confidence = float(data.get("confidence", 0.0))

            if period_type and period_type not in PERIOD_TYPES:
                return None

            return LLMPeriodResult(
                period=period if period else None,
                period_type=period_type if period_type else None,
                confidence=min(max(confidence, 0.0), 1.0),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("LLM period response not valid JSON: %s", raw[:200])
            return None

    def _call(self, prompt: str) -> str | None:
        """Make a single LLM API call. Returns raw text or None on failure."""
        if not self.api_url or not self.api_key:
            logger.debug("LLM client not configured (missing url or key)")
            return None

        try:
            response = httpx.post(
                self.api_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return None

        except (httpx.HTTPError, KeyError, IndexError) as e:
            logger.warning("LLM API call failed: %s", e)
            return None
