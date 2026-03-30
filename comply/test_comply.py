#!/usr/bin/env python3
"""Tests for sentinel_comply compliance gateway."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel_comply import (
    ComplianceRunner,
    ContainerPinning,
    Documentation,
    FairMetadata,
    MetaPattern,
    NoHardcodedPaths,
    ResourceLabels,
    RuleResult,
    TestCoverage,
)


class TestContainerPinning(unittest.TestCase):
    def setUp(self):
        self.rule = ContainerPinning()
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "modules" / "good").mkdir(parents=True)
        (self.tmpdir / "modules" / "bad").mkdir(parents=True)

    def test_pinned_container_passes(self):
        (self.tmpdir / "modules" / "good" / "main.nf").write_text(
            "process FOO {\n    container 'quay.io/biocontainers/fastp:0.23.4--h5f740d0_0'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertTrue(result.passed)

    def test_latest_tag_fails(self):
        (self.tmpdir / "modules" / "bad" / "main.nf").write_text(
            "process FOO {\n    container 'ubuntu:latest'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertFalse(result.passed)
        self.assertTrue(any("latest" in i for i in result.issues))

    def test_no_tag_fails(self):
        (self.tmpdir / "modules" / "bad" / "main.nf").write_text(
            "process FOO {\n    container 'ubuntu'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertFalse(result.passed)


class TestResourceLabels(unittest.TestCase):
    def setUp(self):
        self.rule = ResourceLabels()
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "modules" / "tool").mkdir(parents=True)

    def test_labeled_process_passes(self):
        (self.tmpdir / "modules" / "tool" / "main.nf").write_text(
            "process FOO {\n    label 'process_low'\n    script: 'echo hi'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertTrue(result.passed)

    def test_missing_label_fails(self):
        (self.tmpdir / "modules" / "tool" / "main.nf").write_text(
            "process FOO {\n    cpus 4\n    memory '8 GB'\n    script: 'echo hi'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertFalse(result.passed)


class TestNoHardcodedPaths(unittest.TestCase):
    def setUp(self):
        self.rule = NoHardcodedPaths()
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "modules" / "tool").mkdir(parents=True)

    def test_clean_code_passes(self):
        (self.tmpdir / "modules" / "tool" / "main.nf").write_text(
            "process FOO {\n    script: 'echo ${params.outdir}'\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertTrue(result.passed)

    def test_hardcoded_path_fails(self):
        bad_path = "/" + "home" + "/user/data.txt"
        (self.tmpdir / "modules" / "tool" / "main.nf").write_text(
            f"process FOO {{\n    script: 'cp {bad_path} .'\n}}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertFalse(result.passed)
        self.assertTrue(any("home" in i for i in result.issues))


class TestDocumentation(unittest.TestCase):
    def setUp(self):
        self.rule = Documentation()
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_all_docs_present_passes(self):
        (self.tmpdir / "README.md").write_text("# Project")
        (self.tmpdir / "CHANGELOG.md").write_text("# Changelog")
        (self.tmpdir / "nextflow.config").write_text("params {}")
        result = self.rule.check(self.tmpdir)
        self.assertTrue(result.passed)

    def test_missing_readme_fails(self):
        (self.tmpdir / "CHANGELOG.md").write_text("# Changelog")
        (self.tmpdir / "nextflow.config").write_text("params {}")
        result = self.rule.check(self.tmpdir)
        self.assertFalse(result.passed)


class TestMetaPattern(unittest.TestCase):
    def setUp(self):
        self.rule = MetaPattern()
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "modules" / "persample").mkdir(parents=True)

    def test_meta_pattern_passes(self):
        (self.tmpdir / "modules" / "persample" / "main.nf").write_text(
            "process FOO {\n    input:\n    tuple val(meta), path(reads)\n}\n"
        )
        result = self.rule.check(self.tmpdir)
        self.assertTrue(result.passed)


class TestRuleResult(unittest.TestCase):
    def test_result_fields(self):
        r = RuleResult(
            rule="test_rule",
            description="A test",
            passed=True,
            details="All good",
            issues=[],
        )
        self.assertEqual(r.rule, "test_rule")
        self.assertTrue(r.passed)
        self.assertEqual(r.issues, [])

    def test_failed_result_has_issues(self):
        r = RuleResult(
            rule="test_rule",
            description="A test",
            passed=False,
            details="Failed",
            issues=["bad thing 1", "bad thing 2"],
        )
        self.assertFalse(r.passed)
        self.assertEqual(len(r.issues), 2)


class TestComplianceRunner(unittest.TestCase):
    """Integration test: run all rules against the actual repo."""

    def test_nf_sentinel_passes(self):
        repo_root = Path(__file__).resolve().parent.parent
        runner = ComplianceRunner(repo_root)
        report = runner.run()
        self.assertGreaterEqual(report.score, 70.0)

    def test_report_json_serializable(self):
        repo_root = Path(__file__).resolve().parent.parent
        runner = ComplianceRunner(repo_root)
        report = runner.run()
        output = report.to_json()
        parsed = json.loads(output)
        self.assertIn("score", parsed)
        self.assertIn("rules", parsed)

    def test_report_markdown_output(self):
        repo_root = Path(__file__).resolve().parent.parent
        runner = ComplianceRunner(repo_root)
        report = runner.run()
        md = report.to_markdown()
        self.assertIn("Compliance Report", md)


if __name__ == "__main__":
    unittest.main()
