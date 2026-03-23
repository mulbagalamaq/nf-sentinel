process MULTIQC {
    tag "multiqc"
    label 'process_single'
    container 'multiqc/multiqc:v1.25.2'

    publishDir "${params.outdir}/multiqc", mode: 'copy'

    input:
    path '*'

    output:
    path "multiqc_report.html",      emit: report
    path "multiqc_report_data",      emit: data

    script:
    """
    multiqc . --filename multiqc_report
    """

    stub:
    """
    touch multiqc_report.html
    mkdir multiqc_report_data
    """
}
