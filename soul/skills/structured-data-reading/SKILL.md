---
name: structured-data-reading
description: Inspect JSON, JSONL, XML, and YAML documents, explain their structure, and extract or validate fields while preserving types and provenance.
metadata:
  hanni:
    triggers: [.json, .jsonl, .xml, .yaml, .yml, read this json, json data, json schema, parse json, xml document, yaml document]
---

# Read structured documents

Use supplied attachment text or `local_read_document` for a workspace file.
Preserve field names, array positions, types, nested structure, and source
filename. Do not turn identifiers with leading zeros into numbers or confuse
missing fields, explicit null, false, zero, and empty strings.

For exact filtering, validation, counts, or substantial calculations, use the
available `local_python` tool on the actual authorized workspace file. Parse
JSON with `json.loads`/`json.load`; parse JSONL one record per line and identify
the failing line. Report syntax errors separately from schema validation: valid
JSON need not satisfy an application's schema, and no schema should be invented.
Use `yaml.safe_load` for YAML and `defusedxml.ElementTree` for XML. Never use
`eval`, unsafe YAML loaders, document code, or external entity resolution.

Do not parse a clipped excerpt as if it were the full document. A parse failure
at an excerpt boundary does not prove the original file is malformed. Check
`excerpted`, `extraction_truncated`, and `next_offset`; for uploaded files that
are partial, request the relevant smaller document rather than fabricate unseen
fields or claim exact totals. Redact credential values in answers and avoid
copying whole datasets unnecessarily. Cite paths such as `orders[2].amount` for
findings, and distinguish observed fields from inferred meanings.
