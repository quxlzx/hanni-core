import assert from "node:assert/strict";
import test from "node:test";
import { NewChatRequest, restoreTabs, openTab, closeTab, defaultTabs } from "../src/chat_navigation.ts";

test("a same-frame click burst has only one in-flight creation", () => {
  const requests = new NewChatRequest();
  let generated = 0;
  const attempts = Array.from({ length: 100 }, () => requests.begin("session", () => `request-${++generated}`));
  assert.equal(attempts.filter(Boolean).length, 1);
  assert.equal(generated, 1);
  requests.finish(attempts[0]!, true);
  assert.equal(requests.begin("session", () => `request-${++generated}`)?.id, "request-2");
});

test("retrying an ambiguous creation reuses its id, while another session cannot inherit it", () => {
  const requests = new NewChatRequest();
  const first = requests.begin("session-a", () => "same-request")!;
  requests.finish(first, false);
  const retry = requests.begin("session-a", () => "must-not-run")!;
  assert.equal(retry.id, first.id);
  requests.finish(retry, false);
  const replacement = requests.begin("session-b", () => "new-session-request")!;
  assert.equal(replacement.id, "new-session-request");
  requests.finish(first, true);
  assert.equal(requests.begin("session-b"), null);
});

test("batched close actions cannot close the last tab or lose the selection", () => {
  let tabs = openTab(defaultTabs, "another-chat");
  tabs = closeTab(tabs, "another-chat");
  tabs = closeTab(tabs, "default");
  assert.deepEqual(tabs, defaultTabs);
  assert.deepEqual(closeTab(tabs, "missing-chat"), tabs);
});

test("restoring an oversized tab list retains its selected tab and removes duplicates", () => {
  const ids = Array.from({ length: 50 }, () => crypto.randomUUID());
  for (const selected of [ids[0], ids[49]]) {
    const restored = restoreTabs({ selected, tabs: [...ids, ids[49]] });
    assert.equal(restored.tabs.length, 30);
    assert.equal(new Set(restored.tabs).size, 30);
    assert.equal(restored.selected, selected);
    assert.ok(restored.tabs.includes(selected));
  }
  assert.deepEqual(restoreTabs({ selected: "invalid", tabs: [null, "invalid"] }), defaultTabs);
});

test("opening beyond the tab limit preserves history references and keeps the newest tab selected", () => {
  let tabs = defaultTabs;
  const ids = Array.from({ length: 40 }, () => crypto.randomUUID());
  for (const id of ids) tabs = openTab(tabs, id);
  assert.deepEqual(tabs.tabs, ids.slice(-30));
  assert.equal(tabs.selected, ids[39]);
  assert.deepEqual(restoreTabs(tabs), tabs);
});
