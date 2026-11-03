import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate } from "../App";
import { api, type Project, unwrap } from "../api/client";
import { AddButton } from "../components/AddButton";
import { Field } from "../components/Form";
import { OakBand } from "../components/OakBand";
import { t } from "../copy";
import { desktop } from "../desktop";
import { size } from "../lib/format";

export function HomeScreen() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await api.GET("/api/projects")),
  });

  return (
    <>
      <OakBand page={{ kind: "projects" }} />
      <div className="home">
        <div className="home-main">
          <section className="panel" aria-labelledby="projects-title">
            <header className="panel-head">
              <h1 id="projects-title">{t.home.projectsTitle}</h1>
              <AddButton primary onPress={() => navigate({ name: "new" })}>
                {t.home.newProject}
              </AddButton>
            </header>
            {projects.data?.length === 0 && <p className="empty">{t.home.noProjects}</p>}
            <ul className="rows">
              {projects.data?.map((p) => (
                <ProjectRow key={p.id} project={p} />
              ))}
            </ul>
          </section>
          <StorageLocation />
        </div>
      </div>
    </>
  );
}

function ProjectRow({ project: p }: { project: Project }) {
  const show = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/show-in-folder", {
          params: { path: { project_id: p.id } },
        }),
      ),
  });
  return (
    <li className="row">
      <div className="row-main">
        <a className="row-title" href={`#/projects/${p.id}`}>
          {p.name}
        </a>
        <span className="row-meta">{t.home.taxYear({ year: p.tax_year })}</span>
        {show.error && (
          <p className="error" role="alert">
            {show.error.message}
          </p>
        )}
      </div>
      <div className="row-buttons">
        <Button className="button" onPress={() => navigate({ name: "project", id: p.id })}>
          {t.home.open}
        </Button>
        <Button className="button" isDisabled={show.isPending} onPress={() => show.mutate()}>
          <FolderOpen aria-hidden="true" size="1em" />
          {t.home.showInFolder}
        </Button>
        <DeleteProject project={p} />
      </div>
    </li>
  );
}

/** Delete sends the project folder to the Recycle Bin, after saying what's in it (SPEC §3.0 F1b). */
function DeleteProject({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  return (
    <DialogTrigger>
      <Button className="button">
        <Trash2 aria-hidden="true" size="1em" />
        {t.home.delete}
      </Button>
      <ModalOverlay className="modal-overlay" isDismissable>
        <Modal className="modal">
          <Dialog className="modal-body" role="alertdialog">
            {({ close }) => (
              <DeleteBody
                project={project}
                close={close}
                onDeleted={() => void queryClient.invalidateQueries({ queryKey: ["projects"] })}
              />
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}

function DeleteBody({
  project,
  close,
  onDeleted,
}: {
  project: Project;
  close: () => void;
  onDeleted: () => void;
}) {
  const disk = useQuery({
    queryKey: ["disk", project.id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/disk", { params: { path: { project_id: project.id } } }),
      ),
  });
  const remove = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/projects/{project_id}", { params: { path: { project_id: project.id } } }),
      ),
    onSuccess: () => {
      close();
      onDeleted();
    },
  });
  const d = t.deleteProject;
  return (
    <>
      <Heading slot="title" className="modal-title">
        {d.title({ name: project.name })}
      </Heading>
      <p>{disk.data ? d.body({ size: size(disk.data.bytes), files: disk.data.files }) : d.measuring}</p>
      {disk.data && <p className="row-meta mono">{disk.data.folder}</p>}
      {remove.error && (
        <p className="error" role="alert">
          {remove.error.message}
        </p>
      )}
      <div className="form-actions">
        <Button
          className="button button-danger"
          isDisabled={!disk.data || remove.isPending}
          onPress={() => remove.mutate()}
        >
          <Trash2 aria-hidden="true" size="1em" />
          {d.confirm}
        </Button>
        <Button className="button" onPress={close} autoFocus>
          {d.cancel}
        </Button>
      </div>
    </>
  );
}

/** Settings: where new projects are kept (SPEC §3.0 F1). */
function StorageLocation() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const [editing, setEditing] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (storage_location: string | null) =>
      unwrap(await api.PUT("/api/app-settings/storage-location", { body: { storage_location } })),
    onSuccess: (data) => {
      queryClient.setQueryData(["app-settings"], data);
      setEditing(null);
    },
  });
  const pick = async () => {
    const folder = await desktop.pickFolder();
    if (folder) setEditing(folder);
  };
  if (!settings.data) return null;
  const isDefault = settings.data.storage_location === settings.data.default_storage_location;
  return (
    <section className="panel settings-panel" aria-labelledby="storage-title">
      <header className="panel-head">
        <h2 id="storage-title">{t.home.storageTitle}</h2>
      </header>
      <div className="settings-body sheet">
        {editing === null ? (
          <div className="setting-line">
            <span className="mono">{settings.data.storage_location}</span>
            <Button className="button" onPress={() => setEditing(settings.data.storage_location)}>
              {t.home.change}
            </Button>
            {!isDefault && (
              <Button className="button" onPress={() => save.mutate(null)}>
                {t.home.useDefault}
              </Button>
            )}
          </div>
        ) : (
          <div className="setting-line">
            <Field label={t.home.folderLabel} value={editing} onChange={setEditing} width="long" autoFocus />
            {desktop.canPickFolder() && (
              <Button className="button" onPress={() => void pick()}>
                <FolderOpen aria-hidden="true" size="1em" />
                {t.home.change}
              </Button>
            )}
            <Button
              className="button button-primary"
              isDisabled={!editing.trim() || save.isPending}
              onPress={() => save.mutate(editing.trim())}
            >
              {t.home.save}
            </Button>
            <Button className="button" onPress={() => setEditing(null)}>
              {t.home.cancel}
            </Button>
          </div>
        )}
        <p className="row-meta">{t.home.storageNote}</p>
        {save.error && (
          <p className="error" role="alert">
            {save.error.message}
          </p>
        )}
      </div>
    </section>
  );
}
