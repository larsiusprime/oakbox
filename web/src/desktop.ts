/** Native dialogs from the desktop window (pywebview's js_api). Absent in a plain browser. */
type DesktopApi = {
  pick_folder?: () => Promise<string | null>;
  pick_file?: () => Promise<string | null>;
};

declare global {
  interface Window {
    pywebview?: { api?: DesktopApi };
  }
}

export const desktop = {
  canPickFolder: () => Boolean(window.pywebview?.api?.pick_folder),
  canPickFile: () => Boolean(window.pywebview?.api?.pick_file),
  pickFolder: async () => (await window.pywebview?.api?.pick_folder?.()) ?? null,
  pickFile: async () => (await window.pywebview?.api?.pick_file?.()) ?? null,
};
