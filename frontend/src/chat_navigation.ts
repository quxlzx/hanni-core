export type TabState = { selected: string; tabs: string[] };
export const MAX_CHAT_TABS = 30;
export const defaultTabs: TabState = { selected: "default", tabs: ["default"] };

export function restoreTabs(value: unknown): TabState {
  if (!value || typeof value !== "object" || !("tabs" in value) || !Array.isArray(value.tabs))
    return defaultTabs;
  const ids = [...new Set(value.tabs.filter((id): id is string => typeof id === "string" &&
    /^(?:default|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.test(id)))];
  if (!ids.length) return defaultTabs;
  const selected = "selected" in value && typeof value.selected === "string" && ids.includes(value.selected)
    ? value.selected : ids[ids.length - 1];
  const tabs = ids.slice(-MAX_CHAT_TABS);
  if (!tabs.includes(selected)) tabs.splice(0, 1, selected);
  return { selected, tabs };
}

export function openTab(current: TabState, id: string): TabState {
  return { selected: id, tabs: current.tabs.includes(id) ? current.tabs : [...current.tabs.slice(1 - MAX_CHAT_TABS), id] };
}

export function closeTab(current: TabState, id: string): TabState {
  if (current.tabs.length <= 1 || !current.tabs.includes(id)) return current;
  const tabs = current.tabs.filter((tab) => tab !== id);
  return { tabs, selected: current.selected === id
    ? tabs[Math.max(0, current.tabs.indexOf(id) - 1)] : current.selected };
}

type Creation = { id: string; token: string };
export class NewChatRequest {
  private pending: Creation | null = null;
  private inFlight = false;

  begin(token: string, createId = () => crypto.randomUUID()): Creation | null {
    if (!token || this.inFlight) return null;
    if (this.pending?.token !== token) this.pending = { id: createId(), token };
    this.inFlight = true;
    return this.pending;
  }

  finish(request: Creation, succeeded: boolean) {
    if (this.pending !== request) return;
    this.inFlight = false;
    if (succeeded) this.pending = null;
  }
}
