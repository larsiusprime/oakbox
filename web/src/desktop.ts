import { useEffect, useState } from "react";

/** Native dialogs from the desktop window (pywebview's js_api). Absent in a plain browser. */
type DesktopApi = {
  pick_folder?: () => Promise<string | null>;
  pick_file?: () => Promise<string | null>;
  set_title?: (title: string) => Promise<void>;
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
  /** The native title bar (SPEC D44); the browser tab in browser mode. */
  setTitle: (title: string) => {
    document.title = title;
    void window.pywebview?.api?.set_title?.(title);
  },
};

/** Whether the file picker is there. pywebview injects its API after the page loads. */
export function useCanPickFile(): boolean {
  const [can, setCan] = useState(desktop.canPickFile);
  useEffect(() => {
    const update = () => setCan(desktop.canPickFile());
    window.addEventListener("pywebviewready", update);
    update();
    return () => window.removeEventListener("pywebviewready", update);
  }, []);
  return can;
}
