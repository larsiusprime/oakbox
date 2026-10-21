import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate, type Route } from "./App";
import { type AppSettingsView, api, unwrap } from "./api/client";
import { desktop } from "./desktop";
import { type MenuCommand, requestAddFile, useMenu } from "./menu";
import { t } from "./strings";

type Display = AppSettingsView["display"];

/** What the native menus and their shortcuts do on the page (SPEC §3.14), and the display settings (D43). */
export function AppMenus({ route }: { route: Route }) {
  const queryClient = useQueryClient();
  const [about, setAbout] = useState(false);
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const display = settings.data?.display;
  const setDisplay = useMutation({
    mutationFn: async (next: Display) => unwrap(await api.PUT("/api/app-settings/display", { body: next })),
    onSuccess: (view) => queryClient.setQueryData(["app-settings"], view),
  });

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
    if (route.name !== "project") desktop.setTitle(t.appTitle);
  }, [route.name]);

  const projectId = route.name === "project" ? route.id : null;
  const showFolder = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/show-in-folder", { params: { path: { project_id: id } } }),
      ),
  });

  const run = (command: MenuCommand) => {
    const change = (patch: Partial<Display>) => display && setDisplay.mutate({ ...display, ...patch });
    switch (command) {
      case "new-project":
        return navigate({ name: "new" });
      case "close-project":
        return navigate({ name: "home" });
      case "show-folder":
        return projectId && showFolder.mutate(projectId);
      case "density-compact":
        return change({ density: "compact" });
      case "density-comfortable":
        return change({ density: "comfortable" });
      case "large-text":
        return change({ large_text: !display?.large_text });
      case "high-contrast":
        return change({ high_contrast: !display?.high_contrast });
      // Project items do nothing outside a project: pywebview can't grey them out.
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

  // The menus can't carry shortcuts in pywebview, so the page does (and they work in browser mode too).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
      const command = ({ n: "new-project", "1": "tab-metadata", "2": "tab-files" } as const)[e.key];
      if (command) {
        e.preventDefault();
        window.oakboxMenu?.(command);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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
