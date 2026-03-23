"""
Seqera Platform REST API client.

Thin wrapper around the Tower API for pipeline orchestration.
Used by sentinel_agent.py for headless/CI automation.

Usage:
    client = SeqeraClient(token="...", workspace_id="...")
    runs = client.list_workflows()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


@dataclass
class SeqeraClient:
    """Minimal client for the Seqera Platform REST API."""

    token: str = field(default_factory=lambda: os.environ.get("TOWER_ACCESS_TOKEN", ""))
    workspace_id: str = field(default_factory=lambda: os.environ.get("TOWER_WORKSPACE_ID", ""))
    base_url: str = "https://api.cloud.seqera.io"

    def __post_init__(self):
        if not self.token:
            raise ValueError(
                "Seqera access token required. "
                "Set TOWER_ACCESS_TOKEN env var or pass token= argument."
            )

    # -- Public API --------------------------------------------------------

    def list_workflows(self, max_results: int = 10) -> list[dict[str, Any]]:
        """List recent pipeline runs."""
        params = {"max": max_results}
        data = self._get("/workflow", params=params)
        return data.get("workflows", [])

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get details of a specific pipeline run."""
        data = self._get(f"/workflow/{workflow_id}")
        return data.get("workflow", {})

    def list_compute_envs(self) -> list[dict[str, Any]]:
        """List available compute environments."""
        data = self._get("/compute-envs")
        return data.get("computeEnvs", [])

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List pipelines configured in the workspace launchpad."""
        data = self._get("/pipelines")
        return data.get("pipelines", [])

    def launch_workflow(
        self,
        pipeline: str,
        compute_env_id: str,
        work_dir: str,
        params_: dict[str, Any] | None = None,
        profiles: list[str] | None = None,
        revision: str | None = None,
    ) -> str:
        """Launch a pipeline run. Returns the workflow ID."""
        body: dict[str, Any] = {
            "launch": {
                "pipeline": pipeline,
                "computeEnvId": compute_env_id,
                "workDir": work_dir,
            }
        }
        if params_:
            body["launch"]["paramsText"] = json.dumps(params_)
        if profiles:
            body["launch"]["profiles"] = profiles
        if revision:
            body["launch"]["revision"] = revision

        data = self._post("/workflow/launch", body=body)
        return data.get("workflowId", "")

    # -- HTTP layer --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}{path}"
        query: dict[str, Any] = {}
        if self.workspace_id:
            query["workspaceId"] = self.workspace_id
        if params:
            query.update(params)
        if query:
            url += f"?{urlencode(query)}"
        return url

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._build_url(path, params)
        req = Request(url, headers=self._headers(), method="GET")
        return self._request(req)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = self._build_url(path)
        data = json.dumps(body).encode()
        req = Request(url, data=data, headers=self._headers(), method="POST")
        return self._request(req)

    @staticmethod
    def _request(req: Request) -> dict[str, Any]:
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise RuntimeError(
                f"Seqera API error {e.code}: {e.reason}\n{body}"
            ) from e
