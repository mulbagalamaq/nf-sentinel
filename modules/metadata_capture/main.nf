process METADATA_CAPTURE {
    tag "metadata"
    label 'process_single'
    container 'python:3.11'

    publishDir "${params.outdir}", mode: 'copy'

    input:
    path fastp_jsons
    path salmon_dirs
    path gene_stats
    path schema

    output:
    path "run_metadata.json", emit: metadata

    script:
    """
    #!/usr/bin/env python3
    import json, glob
    from datetime import datetime, timezone
    from pathlib import Path

    # --- Pipeline provenance (Nextflow injects these) ---
    provenance = {
        "pipeline_name":    "${workflow.manifest.name}",
        "pipeline_version": "${workflow.manifest.version}",
        "nextflow_version": "${nextflow.version}",
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "run_name":         "${workflow.runName}",
        "session_id":       "${workflow.sessionId}",
        "profile":          "${workflow.profile}",
        "git_commit":       "${workflow.commitId ?: 'none'}",
    }

    # --- Parameters used ---
    params_used = {
        "input":              "${params.input}",
        "outdir":             "${params.outdir}",
        "salmon_index":       "${params.salmon_index}",
        "min_read_length":     ${params.min_read_length},
        "qualified_quality":   ${params.qualified_quality},
        "min_mapping_rate":    ${params.min_mapping_rate},
        "min_reads_after_trim": ${params.min_reads_after_trim},
    }

    # --- Per-sample QC from FASTP ---
    samples = {}
    for fj in sorted(glob.glob("*.fastp.json")):
        sample_id = fj.replace(".fastp.json", "")
        with open(fj) as f:
            data = json.load(f)
        summary = data.get("summary", {})
        before = summary.get("before_filtering", {})
        after  = summary.get("after_filtering", {})
        samples[sample_id] = {
            "reads_before_trim": before.get("total_reads", 0),
            "reads_after_trim":  after.get("total_reads", 0),
        }

    # --- Per-sample mapping rate from Salmon ---
    for sd in sorted(glob.glob("*_quant/aux_info/meta_info.json")):
        sample_id = Path(sd).parts[0].replace("_quant", "")
        with open(sd) as f:
            info = json.load(f)
        processed = info.get("num_processed", 0)
        mapped    = info.get("num_mapped", 0)
        rate = round((mapped / processed) * 100, 2) if processed > 0 else 0.0
        if sample_id in samples:
            samples[sample_id]["num_mapped"]   = mapped
            samples[sample_id]["num_processed"] = processed
            samples[sample_id]["mapping_rate"]  = rate

    # --- QC gates ---
    qc_gates = []
    for sid, metrics in samples.items():
        rate  = metrics.get("mapping_rate", 0)
        reads = metrics.get("reads_after_trim", 0)
        status = "PASS"
        warnings = []
        if rate < ${params.min_mapping_rate}:
            warnings.append(f"mapping_rate {rate}% < {${params.min_mapping_rate}}%")
            status = "WARN"
        if reads < ${params.min_reads_after_trim}:
            warnings.append(f"reads_after_trim {reads} < ${params.min_reads_after_trim}")
            status = "WARN"
        qc_gates.append({
            "sample": sid,
            "status": status,
            "warnings": warnings
        })

    # --- Gene-level stats ---
    gene_summary = {}
    stats_file = glob.glob("summary_stats.json")
    if stats_file:
        with open(stats_file[0]) as f:
            gene_summary = json.load(f)

    # --- Assemble metadata ---
    metadata = {
        "provenance": provenance,
        "parameters": params_used,
        "samples": samples,
        "qc_gates": qc_gates,
        "gene_summary": gene_summary,
        "containers": {
            "fastp":       "quay.io/biocontainers/fastp:0.23.4--h5f740d0_0",
            "salmon":      "quay.io/biocontainers/salmon:1.10.3--h6dccd9a_2",
            "multiqc":     "multiqc/multiqc:v1.25.2",
            "python":      "python:3.11",
        }
    }

    # --- Validate against schema if provided ---
    schema_file = "${schema}"
    if schema_file != "NO_SCHEMA":
        try:
            with open(schema_file) as f:
                sch = json.load(f)
            # Basic key validation (no jsonschema dependency)
            required = sch.get("required", [])
            missing  = [k for k in required if k not in metadata]
            if missing:
                print(f"SCHEMA WARNING: missing required keys: {missing}")
            else:
                print("Schema validation: all required keys present")
        except Exception as e:
            print(f"Schema validation skipped: {e}")

    with open("run_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata captured for {len(samples)} samples")
    for gate in qc_gates:
        icon = "PASS" if gate["status"] == "PASS" else "WARN"
        print(f"  [{icon}] {gate['sample']}: {gate['warnings'] if gate['warnings'] else 'all checks passed'}")
    """

    stub:
    """
    echo '{"provenance":{"pipeline_name":"nf-sentinel"},"samples":{},"qc_gates":[],"containers":{}}' > run_metadata.json
    """
}
