"""Elasticsearch connection management.

This module is the **only** place that touches :class:`elasticsearch.Elasticsearch`
directly.  Everything else uses the lazily-initialised, process-wide singleton
``ESClient.instance()``.

Connection parameters come from :data:`app.config.settings.settings`, which in
turn reads them from ``.env`` — credentials are never hard-coded here.
"""
from __future__ import annotations

import warnings
from typing import Any, Optional

from elasticsearch import Elasticsearch

from app.config.logging_config import get_logger
from app.config.settings import settings

logger = get_logger("database")


class ElasticsearchConnectionError(RuntimeError):
    """Raised when the Elasticsearch cluster cannot be reached or queried."""


class ESClient:
    """Lazily-constructed singleton wrapper around the Elasticsearch client."""

    _instance: Optional["ESClient"] = None

    def __init__(self) -> None:
        self._client: Optional[Elasticsearch] = None

    # ------------------------------------------------------------------ #
    @classmethod
    def instance(cls) -> "ESClient":
        """Return the shared :class:`ESClient`, creating it on first use."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ #
    def connect(self) -> Elasticsearch:
        """Build (once) and return the underlying :class:`elasticsearch.Elasticsearch`.

        Raises:
            ElasticsearchConnectionError: if the client object cannot be built.
        """
        if self._client is not None:
            return self._client

        if not settings.es_verify_certs:
            # Fully-offline / self-signed clusters: silence the (expected) TLS warnings
            # so the console stays readable.
            warnings.filterwarnings("ignore", message=".*verify_certs=False is insecure.*")
            warnings.filterwarnings("ignore", message="Unverified HTTPS request")
            try:  # pragma: no cover - depends on urllib3 being importable
                import urllib3

                urllib3.disable_warnings()
            except Exception:  # noqa: BLE001
                pass

        logger.info(
            "Creating Elasticsearch client (host=%s, user=%s, pass=%s, verify_certs=%s)",
            settings.es_host, settings.es_username, settings.masked_password(), settings.es_verify_certs,
        )
        try:
            client = Elasticsearch(
                settings.es_host,
                basic_auth=(settings.es_username, settings.es_password),
                verify_certs=settings.es_verify_certs,
                # Only emit the urllib3 "no certificate verification" warning when
                # we are actually supposed to be verifying.
                ssl_show_warn=settings.es_verify_certs,
                request_timeout=settings.es_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to construct Elasticsearch client")
            raise ElasticsearchConnectionError(f"Could not build Elasticsearch client: {exc}") from exc

        self._client = client
        return client

    @property
    def client(self) -> Elasticsearch:
        """The live Elasticsearch client (connects lazily on first access)."""
        return self.connect()

    # ------------------------------------------------------------------ #
    def ping(self) -> bool:
        """Return ``True`` if the cluster responds to a ping, ``False`` otherwise."""
        try:
            return bool(self.client.ping())
        except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
            logger.warning("Elasticsearch ping failed: %s", exc)
            return False

    def cluster_info(self) -> dict[str, Any]:
        """Return ``{name, cluster_name, version}`` for the connected cluster."""
        try:
            info = dict(self.client.info())
        except Exception as exc:  # noqa: BLE001
            logger.error("Unable to fetch cluster info: %s", exc)
            raise ElasticsearchConnectionError(str(exc)) from exc
        return {
            "name": info.get("name"),
            "cluster_name": info.get("cluster_name"),
            "version": (info.get("version") or {}).get("number"),
        }

    def close(self) -> None:
        """Close the underlying transport.  Safe to call multiple times."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._client = None
