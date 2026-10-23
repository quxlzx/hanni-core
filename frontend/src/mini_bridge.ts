export type WindowState = {
  shortcut: string | null;
  error: string;
  choices: string[];
  pinned: boolean;
};

export type MiniControls = {
  get_state: () => Promise<WindowState>;
  dismiss: () => Promise<boolean>;
  pin: (value: boolean) => Promise<WindowState>;
  expand: () => Promise<boolean>;
  configure_hotkey: (shortcut: string) => Promise<WindowState>;
};

export function getMiniControls(api: unknown): MiniControls | null {
  if (!api || typeof api !== "object") return null;
  const candidate = api as Partial<MiniControls>;
  return [
    candidate.get_state,
    candidate.dismiss,
    candidate.pin,
    candidate.expand,
    candidate.configure_hotkey,
  ].every((method) => typeof method === "function")
    ? (candidate as MiniControls)
    : null;
}

export async function readMiniWindowState(api: unknown) {
  const controls = getMiniControls(api);
  return controls ? await controls.get_state() : null;
}
