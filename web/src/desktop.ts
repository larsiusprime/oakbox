import { useEffect, useState } from "react";

/** Native dialogs from the desktop window (pywebview's js_api). Absent in a plain browser. */
type DesktopApi = {
  pick_folder?: () => Promise<string | null>;
  pick_file?: () => Promise<string | null>;
  set_context?: (title: string, projectId: string | null) => Promise<void>;
  menu_key?: (key: string) => Promise<void>;
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
  /** Where the page is: the native title bar says so (SPEC D44), and the menus follow (§3.14). */
  setContext: (title: string, projectId: string | null) => {
    document.title = title;
    void window.pywebview?.api?.set_context?.(title, projectId);
  },
  /** Alt (+ a letter) opens the Windows menu bar; the web view keeps those keys otherwise. */
  hasMenuBar: () => Boolean(window.pywebview?.api?.menu_key),
  menuKey: (key: string) => void window.pywebview?.api?.menu_key?.(key),
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
