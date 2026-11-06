import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { appSettingsKey, useAppSettings } from "./api/app";
import { api, unwrap } from "./api/client";
import { ModelEnginesDialog } from "./components/Engines";
import { desktop } from "./desktop";
import { navigate, type Route } from "./lib/route";
import { type MenuCommand, useMenu } from "./menu";
import { t } from "./wording";

/** What the native menus and their shortcuts do on the page (SPEC §3.14), and the display settings (D43). */
export function AppMenus({ route }: { route: Route }) {
  const queryClient = useQueryClient();
  const [about, setAbout] = useState(false);
  const [engines, setEngines] = useState(false);
  const [flash, setFlash] = useState<number | null>(null); // the zoom level, shown for a moment after it changes
  const settings = useAppSettings();
  const display = settings.data?.display;

  // Display settings live on <html>, where the styles read them.
  useEffect(() => {
    const root = document.documentElement.dataset;
    if (display?.density === "compact") root.density = "compact";
    else delete root.density;
    document.documentElement.style.setProperty("--zoom", String((display?.zoom ?? 100) / 100));
  }, [display]);

  // Show the level for a moment when it changes (not on opening the app).
  const shown = useRef<number | null>(null);
  useEffect(() => {
    const z = display?.zoom;
    if (z === undefined) return;
    if (shown.current !== null && shown.current !== z) {
      setFlash(z);
      const timer = window.setTimeout(() => setFlash(null), 1200);
      shown.current = z;
      return () => window.clearTimeout(timer);
    }
    shown.current = z;
  }, [display?.zoom]);

  // Zoom in, out, or to actual size: one step at a time, in order (the wheel sends them fast).
  const zoomQueue = useRef<Promise<unknown>>(Promise.resolve());
  const zoom = useCallback(
    (by: -1 | 0 | 1) => {
      zoomQueue.current = zoomQueue.current.then(async () => {
        const view = unwrap(await api.POST("/api/app-settings/zoom", { body: { by } }));
        queryClient.setQueryData(appSettingsKey, view);
      });
    },
    [queryClient],
  );

  // Projects and New project say "OAK box"; a project sets its own title (ProjectScreen).
  useEffect(() => {
    if (route.name !== "project") desktop.setContext(t.appTitle, null);
  }, [route.name]);

  const projectId = route.name === "project" ? route.id : null;
  const showFolder = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/show-in-folder", { params: { path: { project_id: id } } }),
      ),
  });

  const run = (command: MenuCommand) => {
    if (typeof command === "object") return navigate({ name: "project", id: command.open });
    switch (command) {
      case "new-project":
        return navigate({ name: "new" });
      case "close-project":
        return navigate({ name: "home" });
      case "show-folder":
        return projectId && showFolder.mutate(projectId);
      // The View items save the setting in OAK box (oakbox/menus.py); restyle to match.
      case "display":
        return void queryClient.invalidateQueries({ queryKey: appSettingsKey });
      // The menu greys these out outside a project; the shortcuts still arrive here.
      case "tab-metadata":
        return projectId && navigate({ name: "project", id: projectId, tab: "metadata" });
      case "tab-data":
        return projectId && navigate({ name: "project", id: projectId, tab: "fields" });
      case "engines":
        return setEngines(true);
      case "about":
        return setAbout(true);
    }
  };
  useMenu(run);

  // Ctrl+mouse wheel zooms, as in a browser (never the web view's own zoom): a step per notch, a trackpad's small
  // movements added up to one.
  useEffect(() => {
    let sum = 0;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      sum += e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
      if (Math.abs(sum) >= 50) {
        zoom(sum < 0 ? 1 : -1);
        sum = 0;
      }
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, [zoom]);

  // The web view has the keyboard, so the page handles the shortcuts the menus show, and passes
  // Alt (+ a letter) on to the Windows menu bar, as Windows would.
  useEffect(() => {
    let altAlone = false;
    const onKey = (e: KeyboardEvent) => {
      altAlone = e.key === "Alt" && !e.ctrlKey && !e.metaKey && !e.shiftKey;
      // Zoom: Ctrl+= or Ctrl++ (with or without Shift, as keyboards differ), Ctrl+-, Ctrl+0.
      const by =
        (e.ctrlKey || e.metaKey) && !e.altKey
          ? ({ "=": 1, "+": 1, "-": -1, _: -1, "0": 0 } as const)[e.key]
          : undefined;
      if (by !== undefined) {
        e.preventDefault();
        zoom(by);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
        const command = ({ n: "new-project", "1": "tab-metadata", "2": "tab-data" } as const)[e.key];
        if (command) {
          e.preventDefault();
          window.oakboxMenu?.(command);
        }
      } else if (e.altKey && !e.ctrlKey && !e.metaKey && /^[a-z]$/i.test(e.key) && desktop.hasMenuBar()) {
        e.preventDefault();
        desktop.menuKey(e.key);
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Alt" && altAlone && desktop.hasMenuBar()) {
        e.preventDefault();
        desktop.menuKey("");
      }
      altAlone = false;
    };
    // A click while Alt is down (Alt+click) isn't Alt alone: Windows doesn't open the menu bar after it either.
    const onPointer = () => {
      altAlone = false;
    };
    window.addEventListener("pointerdown", onPointer, true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer, true);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [zoom]);

  return (
    <>
      <About isOpen={about} onClose={() => setAbout(false)} />
      <ModelEnginesDialog isOpen={engines} onClose={() => setEngines(false)} />
      {flash !== null && (
        <output className="zoom-flash" aria-live="polite">
          {t.zoomLevel({ percent: flash })}
        </output>
      )}
    </>
  );
}

function About({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const a = t.about;
  const versions = useQuery({
    queryKey: ["version"],
    queryFn: async () => unwrap(await api.GET("/api/version")),
    enabled: isOpen,
  });
  return (
    <ModalOverlay
      className="modal-overlay"
      isDismissable
      isOpen={isOpen}
      onOpenChange={(open) => !open && onClose()}
    >
      <Modal className="modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {t.appTitle}
          </Heading>
          <p className="about-tagline">{t.tagline}</p>
          {versions.data && (
            <dl className="facts">
              <div className="fact">
                <dt>{a.version}</dt>
                <dd className="mono">{versions.data.version}</dd>
              </div>
              <div className="fact">
                <dt>{a.openavmkit}</dt>
                <dd className="mono">{versions.data.openavmkit}</dd>
              </div>
            </dl>
          )}
          <p className="row-meta">{a.licences}</p>
          <div className="form-actions">
            <Button className="button" onPress={onClose} autoFocus>
              {a.close}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
