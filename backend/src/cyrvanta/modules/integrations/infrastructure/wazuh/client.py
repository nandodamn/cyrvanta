import json
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from cyrvanta.modules.integrations.domain.errors import (
    ConnectorError,
    ConnectorErrorCode,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.config import (
    WazuhConnectorConfigV1,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.schemas import (
    WazuhSearchResponse,
)


class WazuhIndexerClient:
    def __init__(self, configuration: WazuhConnectorConfigV1) -> None:
        self.configuration = configuration

    async def search_alerts(
        self,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        query_text: str | None = None,
    ) -> WazuhSearchResponse:
        filters: list[dict[str, Any]] = []
        if start_time or end_time:
            interval: dict[str, str] = {}
            if start_time:
                interval["gte"] = start_time.isoformat()
            if end_time:
                interval["lte"] = end_time.isoformat()
            filters.append({"range": {"timestamp": interval}})
        bool_query: dict[str, Any] = {"filter": filters}
        if query_text:
            bool_query["must"] = [
                {
                    "simple_query_string": {
                        "query": query_text[:500],
                        "fields": [
                            "rule.description",
                            "full_log",
                            "data.win.system.message",
                            "data.win.eventdata.data",
                            "data.extra_data",
                        ],
                        "flags": "NONE",
                    }
                }
            ]
        body: dict[str, Any] = {
            "size": min(max(limit, 1), 1000),
            "sort": [{"timestamp": "asc"}, {"_id": "asc"}],
            "query": {"bool": bool_query} if filters or query_text else {"match_all": {}},
            "_source": True,
        }
        if cursor:
            try:
                decoded = json.loads(cursor)
                if not isinstance(decoded, list):
                    raise ValueError
                body["search_after"] = decoded
            except (json.JSONDecodeError, ValueError) as exc:
                raise ConnectorError(
                    ConnectorErrorCode.CURSOR_INVALID, "Synchronization cursor is invalid"
                ) from exc
        pattern = quote(self.configuration.index_pattern, safe="*.-_")
        url = f"{str(self.configuration.indexer_url).rstrip('/')}/{pattern}/_search"
        try:
            async with httpx.AsyncClient(
                timeout=self.configuration.timeout_seconds,
                verify=self.configuration.verify_tls,
                follow_redirects=False,
            ) as client:
                response = await client.post(url, json=body)
            if len(response.content) > self.configuration.max_response_bytes:
                raise ConnectorError(
                    ConnectorErrorCode.SOURCE_SCHEMA_CHANGED,
                    "Source response exceeded the configured size limit",
                )
            if response.status_code in {401, 403}:
                code = (
                    ConnectorErrorCode.AUTHENTICATION_FAILED
                    if response.status_code == 401
                    else ConnectorErrorCode.AUTHORIZATION_FAILED
                )
                raise ConnectorError(code, "Indexer access was rejected")
            if response.status_code == 429:
                raise ConnectorError(ConnectorErrorCode.RATE_LIMITED, "Indexer rate limit reached")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError
            return WazuhSearchResponse.from_opensearch(payload)
        except httpx.TimeoutException as exc:
            raise ConnectorError(
                ConnectorErrorCode.SOURCE_TIMEOUT, "Indexer request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(
                ConnectorErrorCode.CONNECTOR_UNAVAILABLE, "Indexer is unavailable"
            ) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise ConnectorError(
                ConnectorErrorCode.SOURCE_SCHEMA_CHANGED,
                "Indexer returned an unexpected response",
            ) from exc
