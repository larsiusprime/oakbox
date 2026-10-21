import { useEffect, useLayoutEffect, useRef } from "react";

/** Commands from the native menus (SPEC §3.14), sent by oakbox/menus.py. Keep in step with PAGE_COMMANDS. */
export const MENU_COMMANDS = [
  "new-project",
  "show-folder",
  "close-project",
  "density-compact",
  "density-comfortable",
  "large-text",
  "high-contrast",
  "tab-metadata",
  "tab-files",
  "add-file",
  "about",
] as const;
export type MenuCommand = (typeof MENU_COMMANDS)[number];

declare global {
  interface Window {
    oakboxMenu?: (command: string) => void;
  }
}

/** Handle menu commands while mounted. */
export function useMenu(handler: (command: MenuCommand) => void): void {
  const latest = useRef(handler);
  useLayoutEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    window.oakboxMenu = (command) => {
      if ((MENU_COMMANDS as readonly string[]).includes(command)) latest.current(command as MenuCommand);
    };
    return () => {
      delete window.oakboxMenu;
    };
  }, []);
}

// Project → Add a file… may arrive before the Input files tab is on screen: keep it until it is.
let addFilePending = false;
const addFileListeners = new Set<() => void>();

export function requestAddFile(): void {
  if (addFileListeners.size > 0) for (const listener of addFileListeners) listener();
  else addFilePending = true;
}

/** Run `pick` when Add a file… is chosen from the menu (now, or when this mounts after it was). */
export function useAddFileRequest(pick: () => void): void {
  const latest = useRef(pick);
  useLayoutEffect(() => {
    latest.current = pick;
  });
  useEffect(() => {
    const listener = () => latest.current();
    if (addFilePending) {
      addFilePending = false;
      listener();
    }
    addFileListeners.add(listener);
    return () => {
      addFileListeners.delete(listener);
    };
  }, []);
}
