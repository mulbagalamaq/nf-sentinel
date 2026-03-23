#!/usr/bin/env python3
"""
sentinel_agent — Natural language interface for Seqera Platform.

Parses user intent via Claude API, maps to SeqeraClient actions,
returns human-readable summaries.

Usage:
    python sentinel_agent.py "list my recent runs"
    python sentinel_agent.py "what compute environments are available?"
    python sentinel_agent.py --demo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from seqera_client import SeqeraClient


# ---------------------------------------------------------------------------
# Tool definitions for Claude function calling
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_workflows",
        "description": "List recent pipeline runs on Seqera Platform",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of runs to return (default 10)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_workflow",
        "description": "Get details of a specific pipeline run by workflow ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "The workflow/run ID",
                }
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "list_compute_envs",
        "description": "List available compute environments (AWS Batch, local, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_pipelines",
        "description": "List pipelines configured in the workspace launchpad",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "launch_workflow",
        "description": "Launch a pipeline run on Seqera Platform",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {
                    "type": "string",
                    "description": "Pipeline repository URL (e.g., github.com/user/pipeline)",
                },
                "compute_env_id": {
                    "type": "string",
                    "description": "Compute environment ID to run on",
                },
                "work_dir": {
                    "type": "string",
                    "description": "S3 or cloud work directory path",
                },
                "profiles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nextflow profiles to activate (e.g., ['test', 'aws'])",
                },
            },
            "required": ["pipeline", "compute_env_id", "work_dir"],
        },
    },
]

SYSTEM_PROMPT = """You are a bioinformatics pipeline assistant for nf-sentinel.
You help users interact with Seqera Platform to manage Nextflow pipeline runs.
Use the available tools to answer questions about pipeline runs, compute environments,
and to launch new pipeline executions. Be concise and direct."""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

@dataclass
class SentinelAgent:
    """NL interface to Seqera Platform via Claude API + SeqeraClient."""

    seqera: SeqeraClient
    anthropic_key: str
    model: str = "claude-sonnet-4-20250514"

    def query(self, user_input: str) -> str:
        """Process a natural language query and return a response."""
        # Step 1: Send to Claude with tools
        response = self._call_claude(user_input)

        # Step 2: If Claude wants to use a tool, execute it
        if response.get("stop_reason") == "tool_use":
            tool_results = self._execute_tools(response["content"])
            # Step 3: Send tool results back to Claude for summarization
            return self._summarize(user_input, response["content"], tool_results)

        # No tool use — direct response
        return self._extract_text(response["content"])

    def _call_claude(self, user_input: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": user_input}],
        }
        return self._api_request(body)

    def _summarize(
        self,
        user_input: str,
        assistant_content: list[dict],
        tool_results: list[dict],
    ) -> str:
        """Send tool results back to Claude for a human-readable summary."""
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results},
            ],
        }
        response = self._api_request(body)
        return self._extract_text(response["content"])

    def _execute_tools(self, content: list[dict]) -> list[dict]:
        """Execute tool calls from Claude's response."""
        results = []
        for block in content:
            if block.get("type") != "tool_use":
                continue

            name = block["name"]
            args = block.get("input", {})
            tool_id = block["id"]

            try:
                result = self._dispatch(name, args)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result, indent=2, default=str),
                })
            except Exception as e:
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Error: {e}",
                    "is_error": True,
                })

        return results

    def _dispatch(self, name: str, args: dict[str, Any]) -> Any:
        """Route tool calls to SeqeraClient methods."""
        dispatch_map = {
            "list_workflows": lambda: self.seqera.list_workflows(
                max_results=args.get("max_results", 10)
            ),
            "get_workflow": lambda: self.seqera.get_workflow(args["workflow_id"]),
            "list_compute_envs": lambda: self.seqera.list_compute_envs(),
            "list_pipelines": lambda: self.seqera.list_pipelines(),
            "launch_workflow": lambda: self.seqera.launch_workflow(
                pipeline=args["pipeline"],
                compute_env_id=args["compute_env_id"],
                work_dir=args["work_dir"],
                profiles=args.get("profiles"),
            ),
        }

        handler = dispatch_map.get(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")
        return handler()

    def _api_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """Call the Anthropic Messages API."""
        data = json.dumps(body).encode()
        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"Anthropic API error {e.code}: {body_text}") from e

    @staticmethod
    def _extract_text(content: list[dict]) -> str:
        return "\n".join(
            block.get("text", "") for block in content if block.get("type") == "text"
        )


# ---------------------------------------------------------------------------
# Demo mode
# ---------------------------------------------------------------------------

DEMO_QUERIES = [
    "What compute environments do I have available?",
    "Show me my recent pipeline runs",
    "List the pipelines in my launchpad",
]


def run_demo(agent: SentinelAgent):
    """Run demo queries to show the agent in action."""
    print("=" * 60)
    print("  nf-sentinel Agent Demo")
    print("=" * 60)
    for query in DEMO_QUERIES:
        print(f"\n> {query}")
        print("-" * 40)
        try:
            response = agent.query(query)
            print(response)
        except Exception as e:
            print(f"Error: {e}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="nf-sentinel AI agent")
    parser.add_argument("query", nargs="?", help="Natural language query")
    parser.add_argument("--demo", action="store_true", help="Run demo queries")
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY env var required", file=sys.stderr)
        sys.exit(1)

    try:
        seqera = SeqeraClient()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    agent = SentinelAgent(seqera=seqera, anthropic_key=anthropic_key)

    if args.demo:
        run_demo(agent)
    elif args.query:
        print(agent.query(args.query))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
