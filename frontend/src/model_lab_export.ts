/** Preserve server JSON numeric types while validating a bounded export prefix. */
export type SerializedExportPage = {
  format: string;
  run_json: string;
  results_json: string[];
  export_complete: boolean;
  next_offset: number | null;
};

export const MAX_EXPORT_PREVIEW_BYTES = 8 * 1024 * 1024;

/** Read the complete serialized bytes without parsing or rewriting their JSON. */
export async function readExportPreview(blob: Blob): Promise<string> {
  if (blob.size > MAX_EXPORT_PREVIEW_BYTES)
    throw new Error(
      "JSON exceeds the 8 MiB preview limit; no partial preview was shown.",
    );
  return blob.text();
}

type Manifest = {
  id: string;
  completed: number;
  dataset_sha256: string;
  scorer_sha256: string;
  configuration_sha256: string;
  model_identity: string | null;
  settings: unknown;
  protocol_sha256?: string;
  environment_sha256?: string;
};
const fingerprint = (run: Manifest) =>
  JSON.stringify([
    run.id,
    run.dataset_sha256,
    run.scorer_sha256,
    run.configuration_sha256,
    run.model_identity,
    run.settings,
    run.protocol_sha256,
    run.environment_sha256,
  ]);

export class SerializedExport {
  readonly parts: BlobPart[];
  readonly committedCount: number;
  private readonly manifestFingerprint: string;
  exported = 0;
  nextOffset: number | null = null;

  constructor(page: SerializedExportPage, runId: string) {
    const run = this.readManifest(page);
    if (
      run.id !== runId ||
      !Number.isInteger(run.completed) ||
      run.completed < 0 ||
      run.completed > 50000
    )
      throw new Error(
        "Export manifest is invalid; no partial file was downloaded.",
      );
    this.committedCount = run.completed;
    this.manifestFingerprint = fingerprint(run);
    // These strings have already been safely redacted and serialized by Python.
    // Parsed values are used for validation only, never rewritten into the file.
    this.parts = [
      `{"format":"hanni-model-lab-v1","run":${page.run_json},"results":[`,
    ];
    this.append(page);
  }

  private readManifest(page: SerializedExportPage): Manifest {
    if (
      page.format !== "hanni-model-lab-v1" ||
      typeof page.run_json !== "string" ||
      !Array.isArray(page.results_json) ||
      page.results_json.length > 50000 ||
      new TextEncoder().encode(page.run_json).byteLength > 8 * 1024 * 1024
    )
      throw new Error(
        "Export representation is invalid; no partial file was downloaded.",
      );
    const run = JSON.parse(page.run_json) as Manifest;
    if (!run || typeof run !== "object")
      throw new Error("Invalid export manifest.");
    return run;
  }

  append(page: SerializedExportPage) {
    const run = this.readManifest(page);
    if (
      fingerprint(run) !== this.manifestFingerprint ||
      run.completed < this.committedCount
    )
      throw new Error(
        "Export protocol changed; no partial file was downloaded.",
      );
    let pageBytes = 0;
    for (const raw of page.results_json) {
      if (this.complete) break;
      if (
        typeof raw !== "string" ||
        (pageBytes += new TextEncoder().encode(raw).byteLength) >
          16 * 1024 * 1024
      )
        throw new Error(
          "Export page exceeded its bound; no partial file was downloaded.",
        );
      const row = JSON.parse(raw) as { ordinal?: number };
      if (!row || row.ordinal !== this.exported)
        throw new Error(
          "Export evidence order changed; no partial file was downloaded.",
        );
      if (this.exported++) this.parts.push(",");
      this.parts.push(raw);
    }
    this.nextOffset = this.complete ? null : page.next_offset;
    if (
      !this.complete &&
      (!Number.isInteger(this.nextOffset) || this.nextOffset !== this.exported)
    )
      throw new Error(
        "Export continuation is invalid; no partial file was downloaded.",
      );
  }

  get complete() {
    return this.exported === this.committedCount;
  }

  blob() {
    if (!this.complete)
      throw new Error("Export is incomplete; no partial file was downloaded.");
    return new Blob([...this.parts, '],"export_complete":true}'], {
      type: "application/json",
    });
  }
}
