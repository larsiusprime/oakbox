/** The parts of the Data wizard's file steps that other steps use too: choosing a file, its header, its ID column and
 * the checks on it (repeated and blank IDs, how many find their parcel). */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import {
  Button,
  Dialog,
  Heading,
  Label,
  Modal,
  ModalOverlay,
  Radio,
  RadioGroup,
} from "react-aria-components";
import {
  api,
  type Project,
  unwrap,
  type Wizard,
  type WizardCheck,
  type WizardFile,
  type WizardIssue,
} from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { Choice, Tick } from "../components/Form";
import { TipOn } from "../components/Tip";
import { desktop, useCanPickFile } from "../desktop";
import { band } from "../lib/format";
import { t } from "../strings";
import { AddFile } from "./AddFile";
import { describeSteps, ReconcileDialog } from "./Reconcile";
import { CondosLink } from "./Units";
import type { Mutate } from "./wizardChange";

const w = t.wizard;

// ---------- Welcome, parcel universe, sales ----------

/** The sales record itself, not a file of more about each sale. */
export /** The sales file the Sales step is about; more sales details join it on the sale ID. */
function isMainSales(f: WizardFile): boolean {
  return f.holds === "sales" && f.match !== "key_sale";
}

export function CheckText({ check }: { check: WizardCheck | null | undefined }) {
  if (!check) return null;
  if (check.ok && !check.warn) return <span className="wiz-ok">{check.text}</span>;
  // A warning of its own (a unit that looks wrong, a date that reads two ways) shows as one; a result
  // whose warnings are listed as issues beside it stays plain.
  const own = check.warn && check.issues.length === 0;
  return <span className={check.ok && !own ? "wiz-result" : "wiz-warn"}>{check.text}</span>;
}

/** The second line of a check: each issue (✅ decided, ⚠ to decide, ❌ blocks a run), then the action. */
function Issues({ issues, action }: { issues: WizardIssue[]; action?: ReactNode }) {
  if (issues.length === 0 && !action) return null;
  return (
    <span className="wiz-issues">
      {issues.map((issue, i) => (
        <span
          key={issue.text}
          className={issue.resolved ? "wiz-resolved" : issue.blocking ? "wiz-blocking" : "wiz-caution"}
        >
          {i > 0 && <span className="wiz-sep"> · </span>}
          <img
            src={issue.resolved ? resolvedIcon : issue.blocking ? blockingIcon : warningIcon}
            alt=""
            className="wiz-inline-icon"
          />
          {issue.text}
        </span>
      ))}
      {action}
    </span>
  );
}

/** A file's ID check, and "Resolve…" when its IDs repeat: the duplicates dialog (SPEC F3d). */
export function IdCheck({
  projectId,
  data,
  file,
  change,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: Mutate;
}) {
  const [open, setOpen] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const r = file.repeats;
  const resolvable =
    (((file.holds === "parcels" || file.match === "key_sale") && (r?.extra ?? 0) > 0) ||
      (r?.blank ?? 0) > 0) &&
    (file.holds === "parcels" || file.holds === "sales");
  // The ID it joins on: the universe's own is its parcel ID.
  const field = file.base ? "key" : file.match;
  const steps = file.clean[field] ?? [];
  // What it joins to: the main sales file for more sales details, else the parcel universe.
  const base =
    file.match === "key_sale" ? data.files.find((f) => isMainSales(f)) : data.files.find((f) => f.base);
  const share = file.id_check?.share;
  // Reconcile: whenever some rows don't find their parcel (or sale), or to change the clean-up (SPEC F3d).
  const reconcilable =
    !file.base &&
    base !== undefined &&
    share !== null &&
    share !== undefined &&
    (share < 1 || steps.length > 0 || (base.clean[field] ?? []).length > 0);
  // Rows for parcels missing from the parcel universe: cleaning won't help, so it's a note and a look at them.
  const missing = file.not_in_universe;
  const reconcile = reconcilable && (
    <Button className="wiz-link wiz-resolve" onPress={() => setReconciling(true)}>
      {missing ? w.reconcile.seeThem : w.reconcile.open}
    </Button>
  );
  return (
    <div className="wiz-samples wiz-check-lines">
      <span>
        <CheckText check={file.id_check} />
        {(file.id_check?.issues ?? []).length === 0 && reconcile}
      </span>
      <Issues
        issues={file.id_check?.issues ?? []}
        action={
          <>
            {resolvable && (
              <Button className="wiz-link wiz-resolve" onPress={() => setOpen(true)}>
                {w.dupes.resolve}
              </Button>
            )}
            {(file.id_check?.issues ?? []).length > 0 && reconcile}
          </>
        }
      />
      {steps.length > 0 && <span className="wiz-cleaned">{w.reconcile.cleaned(describeSteps(steps))}</span>}
      {missing && (
        <div className="wiz-missing">
          {missing.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {missing.units && <CondosLink projectId={projectId} />}
        </div>
      )}
      {reconciling && base && (
        <ReconcileDialog
          projectId={projectId}
          file={file}
          base={base}
          close={() => setReconciling(false)}
          save={(file_steps, base_steps) =>
            change(
              { kind: "reconcile", name: file.name, file_steps, base_steps },
              { onSuccess: () => setReconciling(false) },
            )
          }
        />
      )}
      {open && (
        <DupesDialog
          projectId={projectId}
          data={data}
          file={file}
          change={change}
          close={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function DupesDialog({
  projectId,
  data,
  file,
  change,
  close,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: Mutate;
  close: () => void;
}) {
  const d = w.dupes;
  const r = file.repeats;
  const examples = useQuery({
    queryKey: ["repeats", projectId, file.name, file.id_column],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/files/{name}/repeats", {
          params: { path: { project_id: projectId, name: file.name } },
        }),
      ),
  });
  const id = file.base ? "key" : file.match;
  const [policy, setPolicy] = useState<"first" | "all" | null>(r?.policy ?? null);
  const [sort, setSort] = useState<string>(r?.sort ?? id);
  const [desc, setDesc] = useState<boolean>(r?.descending ?? false);
  const [blankOk, setBlankOk] = useState<boolean>(r?.blank_ok ?? false);
  if (!r) return null;
  const hasRepeats = r.extra > 0;
  const hasBlanks = r.blank > 0;
  const fieldsHere = Object.values(data.used[file.name] ?? {});
  const kept = policy === "all" ? r.singles : policy === "first" ? r.distinct : null;
  const nameOf = (key: string) => w.idNames[key] ?? data.fields.find((f) => f.key === key)?.name ?? key;
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal wiz-modal wiz-modal-wide">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {d.title(file.name, file.id_column ?? "")}
          </Heading>
          {hasRepeats && (
            <div className="wiz-section-head-row">
              <h3 className="wiz-sub">{d.repeatsTitle(r.repeated)}</h3>
              <span className="wiz-from">{r.few ? d.fewMeans : d.manyMeans}</span>
            </div>
          )}
          {hasRepeats && examples.data && (
            <div className="wiz-dupes-table">
              <table className="tbl wiz-table">
                <thead>
                  <tr>
                    {examples.data.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {examples.data.rows.map((row, i) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: example rows have no identity of their own
                    <tr key={i} className={band(examples.data.bands, i)}>
                      {row.map((v, j) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: cells by position
                        <td key={j} className="mono">
                          {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {hasRepeats && (
            <RadioGroup
              className="field radios wiz-act"
              value={policy}
              onChange={(v) => setPolicy(v as "first" | "all")}
            >
              <Label className="wiz-act-label">{d.what}</Label>
              <Radio value="first" className="radio">
                <span className="radio-dot" aria-hidden="true" />
                {d.first}
              </Radio>
              {policy === "first" && (
                <div className="wiz-pair wiz-indent">
                  <Choice
                    label={d.sortBy}
                    value={sort}
                    options={fieldsHere.map((k) => [k, nameOf(k)] as const)}
                    onChange={setSort}
                  />
                  <Choice
                    label={d.order}
                    value={desc ? "desc" : "asc"}
                    options={[
                      ["asc", d.asc],
                      ["desc", d.desc],
                    ]}
                    onChange={(v) => setDesc(v === "desc")}
                  />
                </div>
              )}
              <Radio value="all" className="radio">
                <span className="radio-dot" aria-hidden="true" />
                {d.all}
              </Radio>
            </RadioGroup>
          )}
          {hasRepeats && hasBlanks && <hr className="wiz-rule" />}
          {hasBlanks && (
            <>
              <div className="wiz-section-head-row">
                <h3 className="wiz-sub">{d.blanksTitle(r.blank)}</h3>
                <span className="wiz-from">{d.blankMeans(file.holds === "sales")}</span>
              </div>
              <div className="wiz-act">
                <span className="wiz-act-label">{d.confirm}</span>
                <Tick isSelected={blankOk} onChange={setBlankOk}>
                  {d.blankOk(r.blank, file.holds === "sales")}
                </Tick>
              </div>
            </>
          )}
          <hr className="wiz-rule" />
          {kept !== null && (
            <p>
              <strong>{d.result(r.rows, kept)}</strong>
            </p>
          )}
          <div className="form-actions">
            <Button
              className="button button-primary"
              isDisabled={!((hasRepeats && policy !== null) || (hasBlanks && blankOk !== r.blank_ok))}
              onPress={() =>
                change(
                  {
                    kind: "file",
                    name: file.name,
                    ...(hasRepeats && policy ? { dupes: policy } : {}),
                    ...(hasRepeats && policy === "first" ? { dupes_sort: sort, dupes_desc: desc } : {}),
                    ...(hasBlanks ? { blank_ok: blankOk } : {}),
                  },
                  { onSuccess: close },
                )
              }
            >
              {w.save}
            </Button>
            <Button className="button" onPress={close}>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** Add a file with the picker (SPEC F2), or take one already in the project. */
export function FilePicker({
  project,
  data,
  exclude,
  onChosen,
}: {
  project: Project;
  data: Wizard;
  exclude: string[];
  onChosen: (name: string) => void;
}) {
  const canPick = useCanPickFile();
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const pick = async () => {
    const path = await desktop.pickFile();
    if (path) setPicked(path);
  };
  const existing = data.files.filter((f) => !exclude.includes(f.name) && !f.problem);
  if (picked !== null) {
    return (
      <AddFile
        project={project}
        path={picked}
        onBrowse={() => void pick()}
        onDone={() => setPicked(null)}
        onAdded={async (name) => {
          await queryClient.invalidateQueries({ queryKey: ["wizard", project.id] });
          onChosen(name);
        }}
      />
    );
  }
  return (
    <div className="wiz-pick">
      {canPick ? (
        <Button className="button button-primary" onPress={() => void pick()}>
          {w.addFile}
        </Button>
      ) : (
        <TipOn text={w.noPicker}>
          <Button className="button" isDisabled>
            {w.addFile}
          </Button>
        </TipOn>
      )}
      {existing.length > 0 && (
        <Choice
          label={w.orExisting}
          value={null}
          placeholder={w.choose}
          options={existing.map((f) => [f.name, w.fileLabel(f.name, f.filename)] as const)}
          onChange={onChosen}
        />
      )}
    </div>
  );
}

export function FileHeader({ file, onReplace }: { file: WizardFile; onReplace: () => void }) {
  return (
    <div className="wiz-file">
      <span className="mono">{file.name}</span>
      <span className="wiz-from">{file.filename}</span>
      {file.rows !== null && <span className="wiz-from">· {file.rows.toLocaleString()} rows</span>}
      <Button className="wiz-link" onPress={onReplace}>
        {w.addOther}
      </Button>
    </div>
  );
}

/** The IDs a file can match the universe on: its parcel ID, then its extra IDs. */
export function matchOptions(base: WizardFile | undefined): (readonly ["key" | "key2" | "key3", string])[] {
  return [
    ["key", w.parcelId] as const,
    ...(base?.extra_ids ?? []).map((e) => [e.field, `${w.idOrdinal[e.field]} (${e.column})`] as const),
  ];
}

/** A file's ID column, and whether it matches the universe's parcel ID or its second ID. */
export function IdRow({
  projectId,
  data,
  file,
  base,
  change,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  change: Mutate;
}) {
  const options = matchOptions(base);
  // More sales details join on the sale ID; anything else on the parcel ID or an extra ID.
  const several = options.length > 1 && file.match !== "key_sale";
  return (
    <div className="wiz-grid">
      <div className="wiz-label">
        {file.match === "key_sale" ? w.saleIdLabel : several ? w.matchBy : w.parcelId}
      </div>
      <div className="wiz-pair">
        {several && (
          <Choice
            label={w.matchBy}
            hideLabel
            value={file.match}
            options={options}
            onChange={(match) => change({ kind: "file", name: file.name, match })}
          />
        )}
        <Choice
          label={w.idColumnIn(file.name)}
          hideLabel
          value={file.id_column}
          placeholder={w.choose}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(id_column) => change({ kind: "file", name: file.name, id_column })}
        />
      </div>
      <IdCheck projectId={projectId} data={data} file={file} change={change} />
    </div>
  );
}
