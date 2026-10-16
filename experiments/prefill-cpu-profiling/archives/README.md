# Raw evidence

Each tar.gz retains the publication export of a raw directory or standalone file. Inherited credential strings in DWARF stack bytes were redacted at equal length; original raw profiles remain local in /workspace/prefill-cpu-raw and are not published. See ../evidence/publication-redactions.json for exact file hashes/counts and proof that decoded stacks are byte-identical. All other raw files are unchanged. File-by-file SHA256 was rechecked by reading the compressed archive; live raw files were not deleted. See ../evidence/archive-manifest.json.

If split, concatenate numbered parts in order: `cat NAME.tar.gz.part* > NAME.tar.gz`. Extract each archive into a fresh directory with `tar -xzf NAME.tar.gz -C DEST`. The local original data are preserved; export/redaction and compression happened after measurements.
