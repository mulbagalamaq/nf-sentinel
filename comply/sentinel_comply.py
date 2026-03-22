#!/usr/bin/env python3
"""
sentinel_comply — Compliance gateway for Nextflow pipelines.

Validates a pipeline directory against organizational standards.
Produces markdown + JSON reports. Exit 0 if score >= threshold, else 1.

Usage:
    python sentinel_comply.py [pipeline_dir] [--threshold 70] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    rule: str
    description: str
    passed: bool
    details: str
    issues: list[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    pipeline: str
    score: float
    threshold: float
    results: list[RuleResult]

    @property
    def passed(self) -> bool:
        return self.score >= self.threshold

    def to_json(self) -> str:
        return json.dumps(
            {
                "pipeline": self.pipeline,
                "score": round(self.score, 1),
                "threshold": self.threshold,
                "passed": self.passed,
                "rules": [asdict(r) for r in self.results],
            },
            indent=2,
        )

    def to_markdown(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"# Compliance Report — {status}",
            "",
            f"**Score: {self.score:.0f}%** (threshold: {self.threshold:.0f}%)",
            "",
            "| # | Rule | Status | Details |",
            "|---|------|--------|---------|",
        ]
        for i, r in enumerate(self.results, 1):
            icon = "PASS" if r.passed else "FAIL"
            lines.append(f"| {i} | {r.rule} | {icon} | {r.details} |")

        failing = [r for r in self.results if not r.passed]
        if failing:
            lines.append("")
            lines.append("## Issues")
            for r in failing:
                lines.append(f"### {r.rule}")
                for issue in r.issues:
                    lines.append(f"- {issue}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rule interface
# ---------------------------------------------------------------------------

class ComplianceRule(ABC):
    """Base class for all compliance rules."""

    name: str
    description: str

    @abstractmethod
    def check(self, pipeline_dir: Path) -> RuleResult:
        ...


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class ContainerPinning(ComplianceRule):
    """Every process must pin containers to a specific version tag."""

    name = "container_pinning"
    description = "All containers must be pinned to a specific version"

    CONTAINER_RE = re.compile(r"container\s+['\"]([^'\"]+)['\"]")

    def check(self, pipeline_dir: Path) -> RuleResult:
        issues: list[str] = []
        total = 0
        pinned = 0

        for nf in pipeline_dir.rglob("*.nf"):
            content = nf.read_text()
            for match in self.CONTAINER_RE.finditer(content):
                total += 1
                image = match.group(1)
                if image.endswith(":latest") or ":" not in image:
                    issues.append(f"{nf.relative_to(pipeline_dir)}: {image}")
                else:
                    pinned += 1

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=(total == 0 or pinned == total),
            details=f"{pinned}/{total} containers pinned",
            issues=issues,
        )


class ResourceLabels(ComplianceRule):
    """Every module process should use a resource label."""

    name = "resource_labels"
    description = "All modules must use resource labels (process_low/medium/high/single)"

    PROCESS_RE = re.compile(r"^\s*process\s+\w+", re.MULTILINE)
    LABEL_RE = re.compile(r"label\s+['\"]process_\w+['\"]")

    def check(self, pipeline_dir: Path) -> RuleResult:
        modules_dir = pipeline_dir / "modules"
        if not modules_dir.exists():
            return RuleResult(self.name, self.description, True, "no modules/")

        issues: list[str] = []
        total = 0
        labeled = 0

        for nf in modules_dir.rglob("main.nf"):
            content = nf.read_text()
            if self.PROCESS_RE.search(content):
                total += 1
                if self.LABEL_RE.search(content):
                    labeled += 1
                else:
                    issues.append(str(nf.relative_to(pipeline_dir)))

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=(total == 0 or labeled == total),
            details=f"{labeled}/{total} modules have resource labels",
            issues=issues,
        )


class TestCoverage(ComplianceRule):
    """Every module should have a corresponding test directory."""

    name = "test_coverage"
    description = "Every module must have a test directory under tests/modules/"

    def check(self, pipeline_dir: Path) -> RuleResult:
        modules_dir = pipeline_dir / "modules"
        tests_dir = pipeline_dir / "tests" / "modules"

        if not modules_dir.exists():
            return RuleResult(self.name, self.description, True, "no modules/")

        module_names = {d.name for d in modules_dir.iterdir() if d.is_dir()}
        test_names = (
            {d.name for d in tests_dir.iterdir() if d.is_dir()}
            if tests_dir.exists()
            else set()
        )

        missing = module_names - test_names
        covered = module_names & test_names

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=len(missing) == 0,
            details=f"{len(covered)}/{len(module_names)} modules have test directories",
            issues=[f"missing tests/modules/{m}/" for m in sorted(missing)],
        )


class FairMetadata(ComplianceRule):
    """Pipeline must include metadata capture and a JSON schema."""

    name = "fair_metadata"
    description = "Pipeline must capture FAIR metadata with JSON schema validation"

    def check(self, pipeline_dir: Path) -> RuleResult:
        issues: list[str] = []

        has_module = (pipeline_dir / "modules" / "metadata_capture" / "main.nf").exists()
        if not has_module:
            issues.append("missing modules/metadata_capture/main.nf")

        has_schema = any(pipeline_dir.glob("assets/*schema*.json"))
        if not has_schema:
            issues.append("missing assets/*schema*.json")

        module_str = "yes" if has_module else "no"
        schema_str = "yes" if has_schema else "no"

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=has_module and has_schema,
            details=f"metadata_module={module_str}, schema={schema_str}",
            issues=issues,
        )


class Documentation(ComplianceRule):
    """Required documentation files must exist."""

    name = "documentation"
    description = "README.md, CHANGELOG.md, and nextflow.config must exist"

    REQUIRED_FILES = ["README.md", "CHANGELOG.md", "nextflow.config"]

    def check(self, pipeline_dir: Path) -> RuleResult:
        missing = [f for f in self.REQUIRED_FILES if not (pipeline_dir / f).exists()]
        present = len(self.REQUIRED_FILES) - len(missing)

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=len(missing) == 0,
            details=f"{present}/{len(self.REQUIRED_FILES)} docs present",
            issues=[f"missing {f}" for f in missing],
        )


class MetaPattern(ComplianceRule):
    """Per-sample modules must use tuple val(meta), path(...) input pattern."""

    name = "meta_pattern"
    description = "Per-sample modules must use tuple val(meta), path(...) pattern"

    # Aggregation modules don't process individual samples
    AGGREGATION_MODULES = {"multiqc", "gene_summarize", "metadata_capture", "untar"}
    META_RE = re.compile(r"tuple\s+val\s*\(\s*meta\s*\)")

    def check(self, pipeline_dir: Path) -> RuleResult:
        modules_dir = pipeline_dir / "modules"
        if not modules_dir.exists():
            return RuleResult(self.name, self.description, True, "no modules/")

        issues: list[str] = []
        total = 0
        conforming = 0

        for mod_dir in sorted(modules_dir.iterdir()):
            if not mod_dir.is_dir() or mod_dir.name in self.AGGREGATION_MODULES:
                continue
            nf = mod_dir / "main.nf"
            if not nf.exists():
                continue

            total += 1
            if self.META_RE.search(nf.read_text()):
                conforming += 1
            else:
                issues.append(str(nf.relative_to(pipeline_dir)))

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=(total == 0 or conforming == total),
            details=f"{conforming}/{total} per-sample modules use meta pattern",
            issues=issues,
        )


class NoHardcodedPaths(ComplianceRule):
    """No hardcoded absolute paths in pipeline code."""

    name = "no_hardcoded_paths"
    description = "No hardcoded absolute paths (/home/, /data/, /mnt/, etc.)"

    PATH_PATTERNS = re.compile(
        r"/home/\w+|/data/|/mnt/|/scratch/|/tmp/\w+|C:\\"
    )

    def check(self, pipeline_dir: Path) -> RuleResult:
        issues: list[str] = []

        for source in self._iter_source_files(pipeline_dir):
            rel = source.relative_to(pipeline_dir)
            for lineno, line in enumerate(source.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("//", "*", "#")):
                    continue
                match = self.PATH_PATTERNS.search(line)
                if match:
                    issues.append(f"{rel}:{lineno}: {match.group()}")

        return RuleResult(
            rule=self.name,
            description=self.description,
            passed=len(issues) == 0,
            details=f"{len(issues)} hardcoded paths found",
            issues=issues,
        )

    @staticmethod
    def _iter_source_files(pipeline_dir: Path):
        yield from pipeline_dir.rglob("*.nf")
        for py in pipeline_dir.rglob("*.py"):
            if "sentinel_comply" not in py.name:
                yield py


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class ComplianceRunner:
    """Runs all compliance rules and produces a report."""

    DEFAULT_RULES: list[type[ComplianceRule]] = [
        ContainerPinning,
        ResourceLabels,
        TestCoverage,
        FairMetadata,
        Documentation,
        MetaPattern,
        NoHardcodedPaths,
    ]

    def __init__(self, pipeline_dir: Path, threshold: float = 70.0):
        self.pipeline_dir = pipeline_dir.resolve()
        self.threshold = threshold
        self.rules = [cls() for cls in self.DEFAULT_RULES]

    def run(self) -> ComplianceReport:
        results = [rule.check(self.pipeline_dir) for rule in self.rules]
        passed_count = sum(1 for r in results if r.passed)
        score = (passed_count / len(results)) * 100 if results else 0

        return ComplianceReport(
            pipeline=str(self.pipeline_dir),
            score=score,
            threshold=self.threshold,
            results=results,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="nf-sentinel compliance gateway")
    parser.add_argument(
        "pipeline_dir", nargs="?", default=".",
        help="Pipeline root directory (default: current directory)",
    )
    parser.add_argument(
        "--threshold", type=float, default=70.0,
        help="Minimum passing score in percent (default: 70)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON instead of markdown",
    )
    args = parser.parse_args()

    pipeline_dir = Path(args.pipeline_dir)
    if not (pipeline_dir / "main.nf").exists():
        print(
            f"Error: {pipeline_dir} does not look like a Nextflow pipeline (no main.nf)",
            file=sys.stderr,
        )
        sys.exit(1)

    runner = ComplianceRunner(pipeline_dir, threshold=args.threshold)
    report = runner.run()

    print(report.to_json() if args.json else report.to_markdown())
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
