import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate, type Route } from "./App";
import { api, unwrap } from "./api/client";
import { desktop } from "./desktop";
import { type MenuCommand, requestAddFile, useMenu } from "./menu";
import { t } from "./strings";

/** What the native menus and their shortcuts do on the page (SPEC §3.14), and the display settings (D43). */
export function AppMenus({ route }: { route: Route }) {
  const queryClient = useQueryClient();
  const [about, setAbout] = useState(false);
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const display = settings.data?.display;

  // Display settings live on <html>, where the styles read them.
  useEffect(() => {
    const root = document.documentElement.dataset;
    if (display?.density) root.density = display.density;
    else delete root.density;
    if (display?.large_text) root.text = "large";
    else delete root.text;
    if (display?.high_contrast) root.contrast = "high";
    else delete root.contrast;
  }, [display]);

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
        return void queryClient.invalidateQueries({ queryKey: ["app-settings"] });
      // The menu greys these out outside a project; the shortcuts still arrive here.
      case "tab-metadata":
        return projectId && navigate({ name: "project", id: projectId, tab: "metadata" });
      case "tab-files":
        return projectId && navigate({ name: "project", id: projectId, tab: "files" });
      case "add-file":
        if (!projectId) return;
        navigate({ name: "project", id: projectId, tab: "files" });
        return requestAddFile();
      case "about":
        return setAbout(true);
    }
  };
  useMenu(run);

  // The web view has the keyboard, so the page handles the shortcuts the menus show, and passes
  // Alt (+ a letter) on to the Windows menu bar, as Windows would.
  useEffect(() => {
    let altAlone = false;
    const onKey = (e: KeyboardEvent) => {
      altAlone = e.key === "Alt" && !e.ctrlKey && !e.metaKey && !e.shiftKey;
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
        const command = ({ n: "new-project", "1": "tab-metadata", "2": "tab-files" } as const)[e.key];
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
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  return <About isOpen={about} onClose={() => setAbout(false)} />;
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
