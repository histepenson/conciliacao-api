import asyncio
import logging
from typing import Any

import httpx

from core.config import settings


TRANSIENT_STATUS_CODES: set[int] = set()


def protheus_async_client(auth: tuple[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        verify=False,
        timeout=settings.PROTHEUS_HTTP_TIMEOUT_SECONDS,
        auth=auth,
    )


async def protheus_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
    headers: dict[str, str],
    logger: logging.Logger,
    operation: str,
) -> httpx.Response:
    attempts = max(1, settings.PROTHEUS_HTTP_RETRY_ATTEMPTS)
    backoff = max(0.0, settings.PROTHEUS_HTTP_RETRY_BACKOFF_SECONDS)

    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code not in TRANSIENT_STATUS_CODES or attempt == attempts:
                raise

            wait_seconds = backoff * attempt
            logger.warning(
                "%s falhou com HTTP %s na tentativa %s/%s; nova tentativa em %.1fs",
                operation,
                status_code,
                attempt,
                attempts,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
        except httpx.ReadTimeout:
            raise
        except (httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ConnectError, httpx.NetworkError) as exc:
            if attempt == attempts:
                raise

            wait_seconds = backoff * attempt
            logger.warning(
                "%s falhou por %s na tentativa %s/%s; nova tentativa em %.1fs",
                operation,
                exc.__class__.__name__,
                attempt,
                attempts,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    raise RuntimeError(f"{operation} falhou apos {attempts} tentativas")
