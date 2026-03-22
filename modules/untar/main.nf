process UNTAR {
    tag "$archive"
    label 'process_single'

    input:
    path archive

    output:
    path "$untar_dir", emit: untar

    script:
    untar_dir = archive.toString().replace('.tar.gz', '').replace('.tgz', '')
    """
    mkdir -p ${untar_dir}
    tar xzf ${archive} -C ${untar_dir} --strip-components 1
    """

    stub:
    untar_dir = archive.toString().replace('.tar.gz', '').replace('.tgz', '')
    """
    mkdir -p ${untar_dir}
    """
}
