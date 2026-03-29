"""
Feature Flag Service.

Wraps LaunchDarkly SDK to gate commerce intents.
Single responsibility: evaluate feature flags.

Rules:
  - Default to DISABLED when LaunchDarkly is unreachable (fail-safe)
  - Evaluate per-intent flags before routing any commerce intent
  - Log all flag evaluation failures

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

import os
from app.core.logging import get_logger

logger = get_logger(__name__)

# Commerce intents gated by feature flags
COMMERCE_INTENTS: frozenset[str] = frozenset({
    "checkout_initiate",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "order_status",
    "order_history",
    "cancel_order",
})

# Global flag key that gates all commerce intents
_COMMERCE_GLOBAL_FLAG = "commerce.enabled"

# Per-intent flag keys
_INTENT_FLAG_MAP: dict[str, str] = {
    "checkout_initiate":  "commerce.checkout_initiate",
    "add_to_cart":        "commerce.add_to_cart",
    "remove_from_cart":   "commerce.remove_from_cart",
    "view_cart":          "commerce.view_cart",
    "order_status":       "commerce.order_status",
    "order_history":      "commerce.order_history",
    "cancel_order":       "commerce.cancel_order",
}


class FeatureFlagService:
    """
    Evaluates LaunchDarkly feature flags for commerce intents.

    Fail-safe: if LaunchDarkly SDK is unavailable or not configured,
    all commerce intents default to DISABLED.
    """

    def __init__(self) -> None:
        self._client = None
        self._sdk_key = os.environ.get("LAUNCHDARKLY_SDK_KEY", "True")
        self._initialized = False
        self._init_client()

    def _init_client(self) -> None:
        """Attempt to initialise the LaunchDarkly client. Silently fails if SDK not available."""
        if not self._sdk_key:
            logger.warning(
                "feature_flag.sdk_key_missing",
                detail="LAUNCHDARKLY_SDK_KEY not set — all commerce flags default to disabled",
            )
            return
        try:
            import ldclient
            from ldclient.config import Config

            ldclient.set_config(Config(self._sdk_key))
            self._client = ldclient.get()
            if self._client.is_initialized():
                self._initialized = True
                logger.info("feature_flag.initialized")
            else:
                logger.warning(
                    "feature_flag.not_initialized",
                    detail="LaunchDarkly client failed to initialize — defaulting to disabled",
                )
                self._client = None
        except ImportError:
            logger.warning(
                "feature_flag.sdk_not_installed",
                detail="launchdarkly-server-sdk not installed — all commerce flags default to disabled",
            )
        except Exception as exc:
            logger.warning(
                "feature_flag.init_failed",
                error=str(exc),
                detail="LaunchDarkly init error — defaulting to disabled",
            )

    def is_commerce_enabled(self, customer_id: str | None = None) -> bool:
        """
        Evaluate the global commerce.enabled flag.
        Returns False if LaunchDarkly is unreachable.
        """
        return self._evaluate(_COMMERCE_GLOBAL_FLAG, customer_id, default=False)

    def is_intent_enabled(self, intent: str, customer_id: str | None = None) -> bool:
        """
        Evaluate the per-intent flag AND the global flag.
        Both must be enabled for the intent to be routed.
        Returns False if LaunchDarkly is unreachable.
        """
        # Local dev override — set FEATURE_FLAG_FORCE_ENABLE=true to bypass LaunchDarkly
        from app.core.config import get_settings
        if get_settings().FEATURE_FLAG_FORCE_ENABLE:
            return True
        if not self.is_commerce_enabled(customer_id):
            return False
        flag_key = _INTENT_FLAG_MAP.get(intent, f"commerce.{intent}")
        return self._evaluate(flag_key, customer_id, default=False)

    def _evaluate(self, flag_key: str, customer_id: str | None, default: bool) -> bool:
        """
        Core evaluation. Always returns `default` on any error.
        """
        if not self._initialized or self._client is None:
            logger.info(
                "feature_flag.evaluation_skipped",
                flag=flag_key,
                reason="client_not_initialized",
                result=default,
            )
            return default
        try:
            context = self._build_context(customer_id)
            result: bool = self._client.variation(flag_key, context, default)
            logger.info(
                "feature_flag.evaluated",
                flag=flag_key,
                customer_id=customer_id,
                result=result,
            )
            return bool(result)
        except Exception as exc:
            logger.warning(
                "feature_flag.evaluation_failed",
                flag=flag_key,
                customer_id=customer_id,
                error=str(exc),
                result=default,
            )
            return default

    @staticmethod
    def _build_context(customer_id: str | None) -> dict:
        """Build a LaunchDarkly evaluation context."""
        try:
            import ldclient
            if customer_id:
                return ldclient.Context.create(str(customer_id))
            return ldclient.Context.create("anonymous", anonymous=True)
        except Exception:
            # Fallback: return a plain dict — older SDK versions accept this
            return {"key": str(customer_id) if customer_id else "anonymous"}

    def close(self) -> None:
        """Gracefully shut down the LaunchDarkly client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
