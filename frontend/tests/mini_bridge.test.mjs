import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/mini_bridge.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { getMiniControls, readMiniWindowState } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);
const state = { shortcut: "Ctrl+Shift+Space", error: "", choices: [], pinned: false };

test("partial pywebview injection waits without invoking native methods", async () => {
  let calls = 0;
  const api = {
    get_state: async () => { calls += 1; return state; },
    dismiss: async () => true,
    pin: async () => state,
    expand: async () => true,
    configure_hotkey: async () => state,
  };
  for (const value of [undefined, null, {}, "not an API"]) {
    assert.equal(getMiniControls(value), null);
    assert.equal(await readMiniWindowState(value), null);
  }
  for (const method of Object.keys(api)) {
    const partial = { ...api };
    delete partial[method];
    assert.equal(await readMiniWindowState(partial), null);
    partial[method] = {};
    assert.equal(await readMiniWindowState(partial), null);
  }
  assert.equal(calls, 0);
  assert.equal(getMiniControls(api), api);
  assert.equal(await readMiniWindowState(api), state);
  assert.equal(calls, 1);
});

test("a real native status failure can recover on the next poll", async () => {
  let unavailable = true;
  const api = {
    get_state: async () => {
      if (unavailable) throw new Error("Native session temporarily unavailable");
      return state;
    },
    dismiss: async () => true,
    pin: async () => state,
    expand: async () => true,
    configure_hotkey: async () => state,
  };
  await assert.rejects(readMiniWindowState(api), /temporarily unavailable/);
  unavailable = false;
  assert.equal(await readMiniWindowState(api), state);
});
