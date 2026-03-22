process GENE_SUMMARIZE {
    tag "gene_summarize"
    label 'process_single'
    container 'python:3.11'

    input:
    path quant_dirs
    path tx2gene

    output:
    path "gene_counts.tsv",    emit: counts
    path "gene_tpm.tsv",       emit: tpm
    path "summary_stats.json", emit: stats

    script:
    """
    #!/usr/bin/env python3
    import csv, json
    from collections import defaultdict
    from pathlib import Path

    # --- Load tx2gene mapping ---
    tx_map = {}
    with open("${tx2gene}") as f:
        reader = csv.reader(f, delimiter="\\t")
        for row in reader:
            if len(row) >= 2:
                tx_map[row[0]] = row[1]  # transcript_id -> gene_id

    # --- Find all quant.sf files ---
    quant_files = sorted(Path(".").glob("*_quant/quant.sf"))
    if not quant_files:
        raise FileNotFoundError("No quant.sf files found")

    sample_names = [qf.parent.name.replace("_quant", "") for qf in quant_files]

    # --- Parse quant.sf per sample, aggregate to gene level ---
    gene_counts = defaultdict(lambda: {s: 0.0 for s in sample_names})
    gene_tpm    = defaultdict(lambda: {s: 0.0 for s in sample_names})

    for qf, sample in zip(quant_files, sample_names):
        with open(qf) as f:
            reader = csv.DictReader(f, delimiter="\\t")
            for row in reader:
                tx_id = row["Name"]
                gene_id = tx_map.get(tx_id, tx_id)  # fallback to transcript ID
                gene_counts[gene_id][sample] += float(row["NumReads"])
                gene_tpm[gene_id][sample]    += float(row["TPM"])

    genes = sorted(gene_counts.keys())

    # --- Write count matrix ---
    with open("gene_counts.tsv", "w") as f:
        f.write("gene_id\\t" + "\\t".join(sample_names) + "\\n")
        for gene in genes:
            vals = [str(round(gene_counts[gene][s], 2)) for s in sample_names]
            f.write(gene + "\\t" + "\\t".join(vals) + "\\n")

    # --- Write TPM matrix ---
    with open("gene_tpm.tsv", "w") as f:
        f.write("gene_id\\t" + "\\t".join(sample_names) + "\\n")
        for gene in genes:
            vals = [str(round(gene_tpm[gene][s], 2)) for s in sample_names]
            f.write(gene + "\\t" + "\\t".join(vals) + "\\n")

    # --- Summary stats ---
    all_counts = []
    for gene in genes:
        for s in sample_names:
            all_counts.append(gene_counts[gene][s])

    nonzero = [c for c in all_counts if c > 0]
    stats = {
        "total_genes": len(genes),
        "genes_detected": len([g for g in genes if any(gene_counts[g][s] > 0 for s in sample_names)]),
        "samples": len(sample_names),
        "sample_names": sample_names,
        "median_count": round(sorted(nonzero)[len(nonzero)//2], 2) if nonzero else 0
    }

    with open("summary_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    """

    stub:
    """
    printf 'gene_id\\tsample1\\ngene1\\t100.0\\n' > gene_counts.tsv
    printf 'gene_id\\tsample1\\ngene1\\t500000.0\\n' > gene_tpm.tsv
    echo '{"total_genes":1,"genes_detected":1,"samples":1,"sample_names":["sample1"],"median_count":100.0}' > summary_stats.json
    """
}
