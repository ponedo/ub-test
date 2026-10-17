"""Validate report metadata only; this is NOT a routing-trace validator."""
import json
from pathlib import Path

m = json.loads(Path(__file__).with_name('access-metadata.json').read_text())
assert m['dataset_api_gated'] == 'auto'
assert m['sample_content_requests'] == m['sample_content_downloaded_bytes'] == 0
assert m['tree_pages_fetched'] == 1 and m['tree_has_next_page'] is True
assert m['tree_entries_returned'] == m['tree_file_entries_returned'] + m['tree_directory_entries_returned']
assert m['smallest_visible_file_metadata']['size'] > 0
assert m['raw_extraction_and_validation'] == m['per_layer_statistics'] == m['matched_synthetic_control'] == 'NOT_RUN'
for key in ('source_api_sha256', 'source_tree_page_sha256'):
    assert len(m[key]) == 64 and all(c in '0123456789abcdef' for c in m[key])
print('PASS: access-report metadata consistency only; raw trace validation NOT RUN')
