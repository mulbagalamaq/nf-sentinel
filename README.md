# nf-sentinel

[![Nextflow](https://img.shields.io/badge/Nextflow-DSL2-23aa62?logo=nextflow)](https://www.nextflow.io/)
[![CI](https://github.com/mulbagalamaq/nf-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/mulbagalamaq/nf-sentinel/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Production-grade RNA-seq quantification pipeline with FAIR metadata capture and automated compliance governance.

## Architecture

```
                    nf-sentinel
    ┌──────────────────────────────────────────┐
    │                                          │
    │   FASTP ──► SALMON_QUANT ──► GENE_SUMMARIZE
    │     │            │                │      │
    │     │            │                │      │
    │     └────────────┼───► MULTIQC    │      │
    │                  │                │      │
    │                  └────────────────┘      │
    │                        │                 │
    │                  METADATA_CAPTURE        │
    │                        │                 │
    │              run_metadata.json           │
    └──────────────────────────────────────────┘

    Layer 1: Pipeline (Nextflow DSL2)
    Layer 2: Compliance Gateway (Python CLI)
    Layer 3: AI Agent (Seqera MCP + REST API)
```

## Three Layers

| Layer | What | Why |
|-------|------|-----|
| **Pipeline** | FASTP → Salmon → Gene Summarize → MultiQC → Metadata Capture | Transcript quantification with FAIR provenance |
| **Compliance** | 7-rule static analyzer, CI-integrated, blocks non-conforming PRs | "Establish and govern pipeline development standards across R&D" |
| **AI Agent** | Seqera MCP for interactive tools + REST API for headless automation | Scientists use natural language; CI/CD uses the API |

## Quick Start

```bash
# Stub test (validates wiring, seconds)
nextflow run main.nf -profile test,docker -stub

# Full test with real data
nextflow run main.nf -profile test,docker

# Compliance check
python comply/sentinel_comply.py .

# AWS execution
nextflow run main.nf -profile test,aws,tower \
    --outdir s3://nf-sentinel-aymen/results/
```

## Modules

| Module | Container | Purpose |
|--------|-----------|---------|
| FASTP | `quay.io/biocontainers/fastp:0.23.4` | QC + adapter trimming (SE/PE) |
| SALMON_QUANT | `quay.io/biocontainers/salmon:1.10.3` | Transcript quantification via quasi-mapping |
| GENE_SUMMARIZE | `python:3.11` | Transcript → gene aggregation, count/TPM matrices |
| MULTIQC | `multiqc/multiqc:v1.25.2` | Aggregate QC report |
| METADATA_CAPTURE | `python:3.11` | FAIR provenance, QC gates, JSON schema validation |

## Compliance Rules

| Rule | What it checks |
|------|---------------|
| container_pinning | All containers pinned to specific version tags |
| resource_labels | All modules use resource labels (not hardcoded) |
| test_coverage | Every module has a test directory |
| fair_metadata | METADATA_CAPTURE process + JSON schema present |
| documentation | README, CHANGELOG, nextflow.config exist |
| meta_pattern | Per-sample modules use `tuple val(meta)` pattern |
| no_hardcoded_paths | No `/home/`, `/data/`, `/mnt/` in code |

## FAIR Metadata Output

Every run produces `run_metadata.json`:

```json
{
  "provenance": {
    "pipeline_name": "nf-sentinel",
    "pipeline_version": "0.1.0-dev",
    "nextflow_version": "25.10.4",
    "timestamp": "2026-03-22T23:36:24Z",
    "git_commit": "5cb61e7"
  },
  "samples": {
    "WT_REP1": {
      "reads_before_trim": 100000,
      "reads_after_trim": 95922,
      "mapping_rate": 80.28
    }
  },
  "qc_gates": [
    {"sample": "WT_REP1", "status": "PASS", "warnings": []}
  ],
  "gene_summary": {
    "total_genes": 125,
    "genes_detected": 102
  }
}
```

## Configuration Profiles

| Profile | Purpose | Usage |
|---------|---------|-------|
| `docker` | Run with Docker containers | `-profile docker` |
| `singularity` | Run with Singularity | `-profile singularity` |
| `test` | Minimal test data (nf-core yeast) | `-profile test,docker` |
| `aws` | AWS Batch executor (spot instances) | `-profile aws,tower` |
| `tower` | Seqera Platform monitoring | `-profile tower` |

## Project Structure

```
nf-sentinel/
├── main.nf                 # Workflow orchestration
├── nextflow.config         # Params, profiles, reporting
├── conf/                   # base, test, aws, tower configs
├── modules/                # DSL2 modules (one process each)
├── assets/                 # Samplesheet, tx2gene, JSON schema
├── comply/                 # Compliance gateway (Python)
├── agent/                  # AI agent (REST + MCP)
├── tests/                  # Module test scaffolding
└── .github/workflows/      # CI: stub test + compliance
```

## License

MIT
