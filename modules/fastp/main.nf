process FASTP {
    tag "$meta.id"
    label 'process_medium'
    container 'quay.io/biocontainers/fastp:0.23.4--hadf994f_0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("${meta.id}_trimmed*.fastq.gz"), emit: reads
    tuple val(meta), path("${meta.id}.fastp.json"),        emit: json
    tuple val(meta), path("${meta.id}.fastp.html"),        emit: html

    script:
    if (meta.single_end) {
        """
        fastp \\
            --in1 ${reads} \\
            --out1 ${meta.id}_trimmed.fastq.gz \\
            --json ${meta.id}.fastp.json \\
            --html ${meta.id}.fastp.html \\
            --qualified_quality_phred ${params.qualified_quality} \\
            --length_required ${params.min_read_length} \\
            --thread ${task.cpus} \\
            ${params.adapter_fasta ? "--adapter_fasta ${params.adapter_fasta}" : ''}
        """
    } else {
        """
        fastp \\
            --in1 ${reads[0]} \\
            --in2 ${reads[1]} \\
            --out1 ${meta.id}_trimmed_R1.fastq.gz \\
            --out2 ${meta.id}_trimmed_R2.fastq.gz \\
            --json ${meta.id}.fastp.json \\
            --html ${meta.id}.fastp.html \\
            --qualified_quality_phred ${params.qualified_quality} \\
            --length_required ${params.min_read_length} \\
            --thread ${task.cpus} \\
            --detect_adapter_for_pe \\
            ${params.adapter_fasta ? "--adapter_fasta ${params.adapter_fasta}" : ''}
        """
    }

    stub:
    if (meta.single_end) {
        """
        touch ${meta.id}_trimmed.fastq.gz
        echo '{"summary":{"before_filtering":{"total_reads":1000},"after_filtering":{"total_reads":900}}}' > ${meta.id}.fastp.json
        touch ${meta.id}.fastp.html
        """
    } else {
        """
        touch ${meta.id}_trimmed_R1.fastq.gz
        touch ${meta.id}_trimmed_R2.fastq.gz
        echo '{"summary":{"before_filtering":{"total_reads":1000},"after_filtering":{"total_reads":900}}}' > ${meta.id}.fastp.json
        touch ${meta.id}.fastp.html
        """
    }
}
