process SALMON_QUANT {
    tag "$meta.id"
    label 'process_medium'
    container 'quay.io/biocontainers/salmon:1.10.3--h6dccd9a_2'

    input:
    tuple val(meta), path(reads)
    path index

    output:
    tuple val(meta), path("${meta.id}_quant"), emit: results

    script:
    def input_reads = meta.single_end
        ? "-r ${reads}"
        : "-1 ${reads[0]} -2 ${reads[1]}"
    """
    salmon quant \\
        --index ${index} \\
        --libType A \\
        ${input_reads} \\
        --output ${meta.id}_quant \\
        --gcBias \\
        --seqBias \\
        --validateMappings \\
        --threads ${task.cpus}
    """

    stub:
    """
    mkdir -p ${meta.id}_quant
    printf 'Name\\tLength\\tEffectiveLength\\tTPM\\tNumReads\\n' > ${meta.id}_quant/quant.sf
    printf 'tx1\\t1000\\t750.0\\t500000.0\\t100.0\\n' >> ${meta.id}_quant/quant.sf
    printf 'tx2\\t2000\\t1750.0\\t500000.0\\t200.0\\n' >> ${meta.id}_quant/quant.sf
    mkdir -p ${meta.id}_quant/aux_info
    echo '{"num_mapped": 900, "num_processed": 1000}' > ${meta.id}_quant/aux_info/meta_info.json
    """
}
