import assert from "node:assert/strict";
import test from "node:test";
import { MAX_FILE_BYTES, clipboardImages, droppedFiles, hasFileDrag, fileSize, sameFiles, validateFile } from "../src/attachment_files.ts";

test("documents and code retain unicode names and literal shell characters", () => {
  for (const name of ["report Ω.pdf", "budget.csv", "notes.DOCX", "$(literal).py", "README.md",
    "budget.xlsx", "macros.XLSM", "legacy.xls", "tables.ods", "letter.odt", "slides.pptx",
    "export.html", "export.htm", "rows.tsv", "data.jsonl", "config.yaml"])
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

test("image attachments accept supported extensions but not SVG or filenames posing as paths", () => {
  for (const name of ["screen.PNG", "photo.jpeg", "photo.jpg", "image.webp", "animation.gif", "capture.bmp"])
    assert.equal(validateFile({ name, size: 100 }), "");
  assert.ok(validateFile({ name: "active.svg", size: 100 }));
  assert.ok(validateFile({ name: "../screen.png", size: 100 }));
});

test("clipboard images prefer actual file items without duplicating files fallback", () => {
  const image = new File(["synthetic"], "capture.png", { type: "image/png" });
  const text = { kind: "string", type: "text/plain", getAsFile: () => null };
  const picture = { kind: "file", type: "image/png", getAsFile: () => image };
  const result = clipboardImages({ items: [text, picture] as unknown as DataTransferItemList, files: [image] as unknown as FileList });
  assert.equal(result.length, 1); assert.equal(result[0], image);
  assert.deepEqual(clipboardImages({ items: [text] as unknown as DataTransferItemList, files: [] as unknown as FileList }), []);
  assert.equal(clipboardImages({ items: [] as unknown as DataTransferItemList, files: [image] as unknown as FileList })[0], image);
});

test("clipboard blobs with no extension get a matching filename", () => {
  const image = new File(["synthetic"], "image", { type: "image/png" });
  const result = clipboardImages({ items: [] as unknown as DataTransferItemList, files: [image] as unknown as FileList });
  assert.equal(result[0].name, "pasted-image-1.png");
  assert.equal(result[0].type, "image/png");
  assert.equal(result[0].size, image.size);
});

test("dragging files is recognized before the protected file list becomes readable", () => {
  assert.ok(hasFileDrag({ types: ["Files"], items: [] as unknown as DataTransferItemList }));
  assert.ok(hasFileDrag({ types: [], items: [{ kind: "file" }] as unknown as DataTransferItemList }));
  assert.equal(hasFileDrag({ types: ["text/plain"], items: [{ kind: "string" }] as unknown as DataTransferItemList }), false);
});

test("file drops retain the full batch, while folders fail without partly adding their contents", () => {
  const image = new File(["synthetic"], "capture.png", { type: "image/png" });
  const report = new File(["report"], "report.txt", { type: "text/plain" });
  const dropped = { items: [] as unknown as DataTransferItemList, files: [image, report] as unknown as FileList };
  assert.deepEqual(droppedFiles(dropped), { files: [image, report], error: "" });
  const folder = { kind: "file", webkitGetAsEntry: () => ({ isDirectory: true }) };
  const result = droppedFiles({ ...dropped, items: [folder] as unknown as DataTransferItemList });
  assert.equal(result.files.length, 0); assert.match(result.error, /Folders/);
  assert.match(droppedFiles({ ...dropped, files: [] as unknown as FileList }).error, /No files/);
});
