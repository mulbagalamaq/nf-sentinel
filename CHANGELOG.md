# Changelog

All notable changes to nf-sentinel will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-23

### Added
- RNA-seq quantification pipeline: FASTP → SALMON_QUANT → GENE_SUMMARIZE → MULTIQC → METADATA_CAPTURE
- FAIR metadata capture with JSON schema validation and QC gates
- Compliance gateway with 7 rules (container pinning, resource labels, test coverage, FAIR metadata, documentation, meta pattern, no hardcoded paths)
- AI agent with Seqera Platform REST client and MCP setup guide
- CI/CD with GitHub Actions (stub test + compliance check)
- Configuration profiles: docker, singularity, test, aws, tower
- Test data using nf-core yeast datasets (GSE110004)
- Gene-level count and TPM expression matrices
