import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useState } from "react";
import { Button, Label, Radio, RadioGroup } from "react-aria-components";
import { api, type FileCheck, type Project, unwrap } from "../api/client";
import { FileEntry } from "../components/FileEntry";
import { Choice, Field } from "../components/Form";
import { size } from "../lib/format";
import { t } from "../wording";

/** Pick-then-add (SPEC F2), also used inside the Data wizard (F3d), which learns the new entry's name. */
export function AddFile(props: {
  project: Project;
  path: string;
  onBrowse: () => void;
  onDone: () => void;
  onAdded?: (name: string) => void;
}) {
  const f = t.inputFiles;
  const { project, path } = props;
  const check = useQuery({
    queryKey: ["file-check", project.id, path],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files/check", {
          params: { path: { project_id: project.id } },
          body: { path },
        }),
      ),
    gcTime: 0,
    staleTime: 0,
  });
  const found = check.data && !check.data.problem ? check.data : null;
  const problem = check.error?.message ?? check.data?.problem ?? null;
  // The file's own name, from the path as Windows or the rest write it.
  const filename = found?.filename ?? path.split(/[\\/]/).pop() ?? path;
  return (
    <FileEntry
      filename={filename}
      path={path}
      facts={found && <Pills found={found} />}
      actions={
        <Button className="button" onPress={props.onBrowse}>
          <FolderOpen aria-hidden="true" size="1em" />
          {f.browse}
        </Button>
      }
      removeLabel={t.files.dontImport({ filename })}
      onRemove={props.onDone}
    >
      {problem && (
        <p className="error" role="alert">
          {problem}
        </p>
      )}
      {found ? (
        // Keyed by path, so picking another file starts its choices afresh.
        <Choices
          key={found.path}
          project={project}
          found={found}
          onDone={props.onDone}
          {...(props.onAdded ? { onAdded: props.onAdded } : {})}
        />
      ) : (
        <div className="form-actions">
          <Button className="button button-primary" isDisabled>
            {f.addButton}
          </Button>
        </div>
      )}
    </FileEntry>
  );
}

function Pills({ found }: { found: FileCheck }) {
  const companions = found.files
    .filter((name) => name !== found.filename)
    .map((name) => name.slice(name.lastIndexOf(".")));
  return (
    <span className="pills">
      <span className="pill">{found.format}</span>
      <span className="pill">{size(found.size_bytes)}</span>
      {companions.length > 0 && <span className="pill">{f_companions(companions)}</span>}
    </span>
  );
}

const f_companions = (exts: string[]) => t.inputFiles.companions({ exts: exts.join(" ") });

function Choices({
  project,
  found,
  onDone,
  onAdded,
}: {
  project: Project;
  found: FileCheck;
  onDone: () => void;
  onAdded?: (name: string) => void;
}) {
  const f = t.inputFiles;
  const queryClient = useQueryClient();
  const [name, setName] = useState(found.suggested_name);
  const [mode, setMode] = useState<"move" | "copy">("copy");
  const [layer, setLayer] = useState<string | null>(
    found.layers.length === 1 ? (found.layers[0] ?? null) : null,
  );
  const stem = found.filename.replace(/\.[^.]+$/, "");
  const ext = found.filename.slice(stem.length);
  const [filename, setFilename] = useState(found.filename_taken ? `${stem}_2${ext}` : "");
  const add = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files", {
          params: { path: { project_id: project.id } },
          body: {
            path: found.path,
            mode,
            name: name.trim(),
            layer,
            filename: found.filename_taken ? filename.trim() : null,
          },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      onAdded?.(name.trim());
      onDone();
    },
  });
  const ready =
    name.trim() && (found.layers.length === 0 || layer) && (!found.filename_taken || filename.trim());
  return (
    <div className="file-choices">
      {/* Labels in one column, what's set in the next (style guide). */}
      <div className="set-grid">
        <Field label={f.name} tip={f.nameHelp} value={name} onChange={setName} />
        {found.filename_taken && (
          <Field
            label={f.newFilename}
            tip={f.newFilenameHelp({ taken: found.filename })}
            value={filename}
            onChange={setFilename}
          />
        )}
        {found.layers.length > 1 && (
          <Choice
            label={f.layer}
            value={layer}
            options={found.layers.map((l) => [l, l] as const)}
            onChange={setLayer}
          />
        )}
        {found.already_in_project ? (
          <div className="field">
            <span className="field-label">{f.how}</span>
            <span className="already">{f.already}</span>
          </div>
        ) : (
          <RadioGroup className="field radios" value={mode} onChange={(v) => setMode(v as "move" | "copy")}>
            <Label className="field-label">{f.how}</Label>
            <Radio value="copy" className="radio">
              <span className="radio-dot" aria-hidden="true" />
              {f.copy}
            </Radio>
            <Radio value="move" className="radio">
              <span className="radio-dot" aria-hidden="true" />
              {f.move}
            </Radio>
          </RadioGroup>
        )}
      </div>
      <div className="form-actions">
        <Button
          className="button button-primary"
          isDisabled={!ready || add.isPending}
          onPress={() => add.mutate()}
        >
          {add.isPending ? f.adding({ mode }) : f.addButton}
        </Button>
      </div>
      {add.error && (
        <p className="error" role="alert">
          {add.error.message}
        </p>
      )}
    </div>
  );
}
