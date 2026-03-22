#!/usr/bin/env nextflow

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    nf-sentinel: RNA-seq Quantification Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    FASTP → SALMON_QUANT → GENE_SUMMARIZE → MULTIQC → METADATA_CAPTURE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

// -- Import modules ------------------------------------------------------

include { FASTP            } from './modules/fastp/main'
include { SALMON_QUANT     } from './modules/salmon_quant/main'
include { GENE_SUMMARIZE   } from './modules/gene_summarize/main'
include { MULTIQC          } from './modules/multiqc/main'
include { METADATA_CAPTURE } from './modules/metadata_capture/main'

// -- Main workflow --------------------------------------------------------

workflow {

    log.info """
    ===================================
     nf-sentinel v${workflow.manifest.version}
    ===================================
     input      : ${params.input}
     outdir     : ${params.outdir}
     profile    : ${workflow.profile}
    ===================================
    """.stripIndent()

    // -- Validate required params -----------------------------------------

    if (!params.input)       { error "Please provide --input samplesheet.csv" }
    if (!params.salmon_index){ error "Please provide --salmon_index" }
    if (!params.tx2gene)     { error "Please provide --tx2gene" }

    // -- Parse samplesheet ------------------------------------------------
    // Each row becomes: [meta_map, [fastq_1, fastq_2]]

    ch_reads = Channel
        .fromPath(params.input, checkIfExists: true)
        .splitCsv(header: true)
        .map { row ->
            def meta = [
                id:         row.sample,
                single_end: !row.fastq_2
            ]
            def reads = row.fastq_2
                ? [file(row.fastq_1, checkIfExists: true), file(row.fastq_2, checkIfExists: true)]
                : [file(row.fastq_1, checkIfExists: true)]
            [meta, reads]
        }

    // -- Reference inputs (value channels — reused per sample) ------------

    ch_index  = file(params.salmon_index, checkIfExists: true)
    ch_tx2gene = file(params.tx2gene, checkIfExists: true)
    ch_schema = file("${projectDir}/assets/metadata_schema.json", checkIfExists: true)

    // -- FASTP: QC + trimming ---------------------------------------------

    FASTP(ch_reads)

    // -- SALMON: quantification -------------------------------------------

    SALMON_QUANT(FASTP.out.reads, ch_index)

    // -- GENE_SUMMARIZE: transcript → gene aggregation --------------------

    ch_quant_dirs = SALMON_QUANT.out.results
        .collect { meta, quant_dir -> quant_dir }

    GENE_SUMMARIZE(ch_quant_dirs, ch_tx2gene)

    // -- MULTIQC: aggregate QC reports ------------------------------------

    ch_multiqc = Channel.empty()
        .mix(FASTP.out.json.collect { meta, json -> json })
        .mix(SALMON_QUANT.out.results.collect { meta, dir -> dir })
        .collect()

    MULTIQC(ch_multiqc)

    // -- METADATA_CAPTURE: provenance + QC gates --------------------------

    ch_fastp_jsons = FASTP.out.json
        .collect { meta, json -> json }

    ch_salmon_dirs = SALMON_QUANT.out.results
        .collect { meta, dir -> dir }

    METADATA_CAPTURE(
        ch_fastp_jsons,
        ch_salmon_dirs,
        GENE_SUMMARIZE.out.stats,
        ch_schema
    )
}
