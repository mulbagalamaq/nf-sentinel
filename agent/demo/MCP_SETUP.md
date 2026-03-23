# Seqera MCP Demo Setup

## Prerequisites
- Claude Pro subscription (for Claude Code)
- Seqera Platform account (free tier: cloud.seqera.io)

## Setup (2 minutes)

```bash
# Add Seqera MCP server to Claude Code
claude mcp add --scope=user --transport=http seqera https://mcp.seqera.io/mcp
```

Browser opens for OAuth — authenticate with your Seqera account.

## Demo Queries

Once connected, try these in Claude Code:

1. "List my compute environments"
2. "Show my recent pipeline runs"
3. "Search nf-core modules for RNA-seq quality control"
4. "What's the status of my latest run?"
5. "Launch nf-sentinel with the test profile on my AWS spot environment"

## What MCP Exposes

Seqera MCP provides 74+ tools to Claude:
- `platform_list_workflows` — list runs
- `platform_launch_workflow` — launch pipelines
- `platform_list_compute_envs` — list compute environments
- `wave_get_container` — build containers on the fly
- `sra_search` — search NCBI SRA for public datasets
- `nfcore_search_modules` — search nf-core module registry

## Interview Framing

"I implemented two interfaces — MCP for interactive AI tools like Claude Code
and Cursor, which is what Seqera launched weeks ago, and a REST API wrapper
for headless automation and CI/CD. Same architecture, different transport.
Scientists get the MCP interface; CI/CD gets the REST API."
