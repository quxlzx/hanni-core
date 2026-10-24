import assert from "node:assert/strict";
import test from "node:test";
import { MAX_FILE_BYTES, fileSize, sameFiles, validateFile } from "../src/attachment_files.ts";

test("documents and code retain unicode names and literal shell characters", () => {
  for (const name of ["report Ω.pdf", "budget.csv", "notes.DOCX", "$(literal).py", "README.md"])
    assert.equal(validateFile({ name, size: 100 }), "");
});
test("unknown binary, empty, oversized and path-like files are rejected before reading", () => {
  for (const file of [{ name: "file.exe", size: 10 }, { name: "report.txt", size: 0 },
    { name: "large.pdf", size: MAX_FILE_BYTES + 1 }, { name: "../data.txt", size: 5 }, { name: "bad\u0000.txt", size: 5 }])
    assert.ok(validateFile(file));
  assert.equal(validateFile({ name: "report.pdf", size: MAX_FILE_BYTES }), "");
});
test("message retry identity includes the exact file set", () => {
  assert.ok(sameFiles(["a", "b"], ["b", "a"]));
  assert.ok(sameFiles(undefined, []));
  assert.equal(sameFiles(["a"], ["b"]), false);
  assert.equal(sameFiles(["a"], []), false);
  assert.equal(sameFiles(["a", "a"], ["a", "b"]), false);
});
test("file sizes use explicit byte units", () => {
  assert.equal(fileSize(10), "10 B"); assert.equal(fileSize(1025), "2 KiB");
  assert.equal(fileSize(MAX_FILE_BYTES), "8.0 MiB");
});
