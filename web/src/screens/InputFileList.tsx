import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  Dialog,
  DialogTrigger,
  Heading,
  Input,
  Modal,
  ModalOverlay,
  TextField,
} from "react-aria-components";
import { api, type InputFile, type Project, unwrap } from "../api/client";
import folderIcon from "../assets/noto/emoji_u1f4c1.svg";
import binIcon from "../assets/noto/emoji_u1f5d1.svg";
import pencilIcon from "../assets/noto/emoji_u270f.svg";
import { Tick } from "../components/Form";
import { Tip } from "../components/Tip";
import { t } from "../strings";

const NAME = /^[a-z][a-z0-9_]*$/;

export function size(bytes: number): string {
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** F3b: the project's input files, one data.load entry per row (SPEC §3.0). */
export function InputFileList({ project, files }: { project: Project; files: InputFile[] }) {
  const f = t.inputFiles;
  const [renaming, setRenaming] = useState<string | null>(null);
  return (
    <table className="file-table">
      <colgroup>
        <col />
        <col className="col-type" />
        <col className="col-size" />
        <col className="col-geometry" />
        <col className="col-actions" />
      </colgroup>
      <thead>
        <tr>
          <th>{f.columns.name}</th>
          <th>{f.columns.type}</th>
          <th className="num">{f.columns.size}</th>
          <th>{f.columns.geometry}</th>
          <th>
            <span className="visually-hidden">{f.columns.actions}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {files.map((file) =>
          renaming === file.name ? (
            <RenameRow
              key={file.name}
              project={project}
              file={file}
              taken={files.filter((x) => x !== file).map((x) => x.name)}
              onDone={() => setRenaming(null)}
            />
          ) : (
            <tr key={file.name} className="file-row">
              <td>
                <span className="file-name">
                  <span className="mono">{file.name}</span>
                  <ShowFile project={project} file={file} />
                </span>
              </td>
              <FileFacts file={file} />
              <td className="row-actions">
                <Tip text={f.rename}>
                  <Button
                    className="icon-button"
                    aria-label={f.rename}
                    onPress={() => setRenaming(file.name)}
                  >
                    <img src={pencilIcon} alt="" />
                  </Button>
                </Tip>
                <RemoveFile project={project} file={file} />
              </td>
            </tr>
          ),
        )}
      </tbody>
    </table>
  );
}

function FileFacts({ file }: { file: InputFile }) {
  const f = t.inputFiles;
  return (
    <>
      <td>{file.format}</td>
      <td className="num">{file.missing ? "—" : size(file.size_bytes)}</td>
      <td>
        {file.missing ? (
          <span className="error-text">{f.missing}</span>
        ) : file.geometry === null ? (
          "—"
        ) : file.geometry ? (
          f.yes
        ) : (
          f.no
        )}
      </td>
    </>
  );
}

function ShowFile({ project, file }: { project: Project; file: InputFile }) {
  const f = t.inputFiles;
  const show = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files/{name}/show", {
          params: { path: { project_id: project.id, name: file.name } },
        }),
      ),
  });
  return (
    <Tip text={show.error ? show.error.message : f.file(file.filename, file.layer)}>
      <Button className="icon-button" aria-label={f.showFile(file.filename)} onPress={() => show.mutate()}>
        <img src={folderIcon} alt="" />
      </Button>
    </Tip>
  );
}

function RenameRow(props: { project: Project; file: InputFile; taken: string[]; onDone: () => void }) {
  const f = t.inputFiles;
  const { project, file } = props;
  const queryClient = useQueryClient();
  const [name, setName] = useState(file.name);
  const wanted = name.trim();
  const problem = !NAME.test(wanted)
    ? f.nameRules
    : props.taken.includes(wanted)
      ? f.nameTaken(wanted)
      : null;
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/files/{name}/name", {
          params: { path: { project_id: project.id, name: file.name } },
          body: { name: wanted },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      props.onDone();
    },
  });
  const submit = () => {
    if (wanted === file.name) props.onDone();
    else if (!problem && !save.isPending) save.mutate();
  };
  const error = (wanted !== file.name && problem) || save.error?.message || null;
  return (
    <>
      <tr className="file-row renaming">
        <td>
          <TextField
            className="field"
            aria-label={f.newName(file.name)}
            value={name}
            onChange={setName}
            isInvalid={Boolean(error)}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") props.onDone();
            }}
          >
            <Input
              className="input rename-input"
              {...(error ? { "aria-describedby": `rename-error-${file.name}` } : {})}
            />
          </TextField>
        </td>
        <FileFacts file={file} />
        <td className="row-actions">
          <Button
            className="button button-primary"
            isDisabled={Boolean(error) || save.isPending}
            onPress={submit}
          >
            {f.save}
          </Button>
          <Button className="button" onPress={props.onDone}>
            {f.cancel}
          </Button>
        </td>
      </tr>
      {/* On a line of its own, so a long message neither widens nor misaligns the row. */}
      {error && (
        <tr className="rename-error">
          <td colSpan={5}>
            <span id={`rename-error-${file.name}`} className="error" role="alert">
              {error}
            </span>
          </td>
        </tr>
      )}
    </>
  );
}

function RemoveFile({ project, file }: { project: Project; file: InputFile }) {
  const f = t.inputFiles;
  return (
    <DialogTrigger>
      <Tip text={f.remove}>
        <Button className="icon-button" aria-label={f.remove}>
          <img src={binIcon} alt="" />
        </Button>
      </Tip>
      <ModalOverlay className="modal-overlay" isDismissable>
        <Modal className="modal">
          <Dialog className="modal-body" role="alertdialog">
            {({ close }) => <RemoveBody project={project} file={file} close={close} />}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}

function RemoveBody({ project, file, close }: { project: Project; file: InputFile; close: () => void }) {
  const f = t.inputFiles;
  const queryClient = useQueryClient();
  const [trash, setTrash] = useState(false);
  const remove = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/projects/{project_id}/files/{name}", {
          params: { path: { project_id: project.id, name: file.name }, query: { trash } },
        }),
      ),
    onSuccess: async () => {
      close();
      await queryClient.invalidateQueries({ queryKey: ["project", project.id] });
    },
  });
  return (
    <>
      <Heading slot="title" className="modal-title">
        {f.removeTitle(file.name)}
      </Heading>
      {!file.missing && (
        <Tick isSelected={trash} onChange={setTrash}>
          {f.alsoTrash(file.filename)}
        </Tick>
      )}
      {remove.error && (
        <p className="error" role="alert">
          {remove.error.message}
        </p>
      )}
      <div className="form-actions">
        <Button
          className="button button-danger"
          isDisabled={remove.isPending}
          onPress={() => remove.mutate()}
        >
          {f.removeConfirm}
        </Button>
        <Button className="button" onPress={close} autoFocus>
          {f.cancel}
        </Button>
      </div>
    </>
  );
}
