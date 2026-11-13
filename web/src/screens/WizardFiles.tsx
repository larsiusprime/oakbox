/** The parts of the Data wizard's file steps that other steps use too: choosing a file, its header, its ID column and
 * the checks on it (repeated and blank IDs, how many find their parcel). */

import { useIsMutating, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Button, Dialog, Heading, Label, Modal, ModalOverlay, Radio } from "react-aria-components";
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
import { AddButton } from "../components/AddButton";
import { firstSentence } from "../components/Callout";
import { DialogFoot, DialogSection } from "../components/DialogParts";
import { FileEntry, FileName, FileSlot, fileFacts, NamesFile } from "../components/FileEntry";
import { Choice, Radios, Tick } from "../components/Form";
import { ReadingLine } from "../components/Reading";
import { RemoveButton } from "../components/RemoveButton";
import { SummonMap } from "../components/ShowOnMap";
import { TipOn } from "../components/Tip";
import { Val } from "../components/Val";
import { Waiting } from "../components/Waiting";
import { WarnChip } from "../components/WarnChip";
import { desktop, useCanPickFile } from "../desktop";
import { t } from "../wording";
import { AddFile } from "./AddFile";
import { describeSteps, ReconcileDialog, ReconcilePanel } from "./Reconcile";
import { CondosLink } from "./Units";
import type { Mutate } from "./wizardChange";

const w = t.wizard;

// ---------- Welcome, parcel universe, sales ----------

/** The sales record itself: the sales file the Sales step is about, not a file of more about each sale (which joins
 * it on the sale ID). */
export function isMainSales(f: WizardFile): boolean {
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
  inline = false,
  review = false,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: Mutate;
  /** The Sales file part: matching is laid out under the file (MatchPanel), so no Reconcile button or ⚠ here. */
  inline?: boolean;
  /** Review's quiet line (a table row): what's handled in grey words with a link to change it; only what wants a
   * look gets a pill and a button. */
  review?: boolean;
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
  const dialogs = (
    <>
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
    </>
  );
  // The parcel universe's IDs have a place: its blank and repeated ones open on the map (SPEC §3.15, summon).
  const onMap = file.base ? (
    <>
      {(r?.blank ?? 0) > 0 && <SummonMap field="pr:blank_ids" label={t.mapWindow.step.mapBlank} />}
      {(r?.extra ?? 0) > 0 && <SummonMap field="pr:repeated_ids" label={t.mapWindow.step.mapRepeated} />}
    </>
  ) : null;
  if (review) {
    const issues = file.id_check?.issues ?? [];
    const handled = issues.filter((i) => i.resolved);
    const open_ = issues.filter((i) => !i.resolved);
    // What wants a look is said in a pill: matching under 95% (the step's own warning, SPEC F3d), or a check that's a
    // warning of its own (IDs repeated, nothing chosen yet). Every action is a small button, the same as elsewhere.
    const matchLook = reconcilable && share !== null && share !== undefined && share < 0.95;
    const own = !!file.id_check && !file.id_check.ok && issues.length === 0;
    const said = (file.id_check?.text ?? "").replace(/^✓\s*/, "");
    const act = (label: string, press: () => void) => (
      <Button className="button button-small" onPress={press}>
        {label}
      </Button>
    );
    return (
      <tr>
        <td>
          <FileName filename={file.name} />
        </td>
        <td className="mono wiz-from">{file.id_column}</td>
        <td>
          {own || matchLook ? <span className="pill pill-warn">{said}</span> : said}
          {steps.length > 0 && (
            <span className="wiz-from"> · {w.reconcile.cleaned({ what: describeSteps(steps) })}</span>
          )}
          {handled.length > 0 && (
            <span className="wiz-from"> · {handled.map((i) => i.text).join(" · ")}</span>
          )}
          {open_.map((i) => (
            <span key={i.text} className={i.blocking ? "pill pill-bad rv-pill" : "pill pill-warn rv-pill"}>
              {i.text}
            </span>
          ))}
          {onMap && <span className="rv-map-btns">{onMap}</span>}
          {missing && (
            <span className="pill pill-warn rv-pill">
              {missing.title || firstSentence(missing.lines[0] ?? "")}
            </span>
          )}
        </td>
        <td className="rv-act">
          {reconcilable && act(missing ? w.reconcile.seeThem : w.reconcile.open, () => setReconciling(true))}
        </td>
        <td className="rv-act">
          {resolvable && act(w.dupes.resolve, () => setOpen(true))}
          {dialogs}
        </td>
      </tr>
    );
  }
  const reconcile = reconcilable && !inline && (
    <Button className="button button-small" onPress={() => setReconciling(true)}>
      {missing ? w.reconcile.seeThem : w.reconcile.open}
    </Button>
  );
  return (
    // One line, as every row of settings: the check, its button, each issue, a warning as ⚠ and a few words.
    <div className="wiz-samples id-line">
      <CheckText check={file.id_check} />
      {reconcile}
      <Issues
        issues={file.id_check?.issues ?? []}
        action={
          resolvable && (
            <Button className="button button-small" onPress={() => setOpen(true)}>
              {w.dupes.resolve}
            </Button>
          )
        }
      />
      {onMap}
      {steps.length > 0 && (
        <span className="wiz-cleaned">{w.reconcile.cleaned({ what: describeSteps(steps) })}</span>
      )}
      {missing && !inline && (
        <WarnChip title={missing.title || firstSentence(missing.lines[0] ?? "")}>
          {missing.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {missing.units && <CondosLink projectId={projectId} />}
        </WarnChip>
      )}
      {dialogs}
    </div>
  );
}

type Level = { column: string; desc: boolean };

/** The example rows of each repeated ID in the order chosen, its first (the one kept) marked: as OpenAVMKit sorts
 * them (numbers as numbers, blanks last), ties in the file's order. */
function keptFirst(
  ex: { columns: string[]; rows: (string | null)[][]; bands: number[] },
  levels: Level[],
  numeric: Set<string>,
  marking: boolean,
): { row: (string | null)[]; band: number; kept: boolean }[] {
  const groups: { band: number; rows: (string | null)[][] }[] = [];
  ex.rows.forEach((row, i) => {
    const b = ex.bands[i] ?? 0;
    const last = groups.at(-1);
    if (last && last.band === b) last.rows.push(row);
    else groups.push({ band: b, rows: [row] });
  });
  const at = levels.map((l) => ({
    i: ex.columns.indexOf(l.column),
    desc: l.desc,
    num: numeric.has(l.column),
  }));
  const cmp = (a: (string | null)[], b: (string | null)[]) => {
    for (const l of at) {
      if (l.i < 0) continue;
      const x = a[l.i] ?? "";
      const y = b[l.i] ?? "";
      if (x === y) continue;
      if (x === "") return 1; // blanks last, whichever way
      if (y === "") return -1;
      const c =
        l.num && Number.isFinite(Number(x)) && Number.isFinite(Number(y))
          ? Number(x) - Number(y)
          : x < y
            ? -1
            : 1;
      return l.desc ? -c : c;
    }
    return 0;
  };
  return groups.flatMap((g) =>
    [...g.rows].sort(cmp).map((row, j) => ({ row, band: g.band, kept: marking && j === 0 })),
  );
}

function DupesDialog({
  projectId,
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
  const [policy, setPolicy] = useState<"first" | "all" | null>(r?.policy ?? null);
  // The order each ID's rows are kept in: the file's columns, level by level (ties keep the file's order).
  const [levels, setLevels] = useState<Level[]>(() =>
    (r?.by ?? []).map((k) => ({ column: k.column, desc: k.desc })),
  );
  const [blankOk, setBlankOk] = useState<boolean>(r?.blank_ok ?? false);
  if (!r) return null;
  const hasRepeats = r.extra > 0;
  const hasBlanks = r.blank > 0;
  const kept = policy === "all" ? r.singles : policy === "first" ? r.distinct : null;
  const columns = file.columns.filter((c) => c.type !== "geometry").map((c) => c.name);
  const numeric = new Set(file.columns.filter((c) => c.type === "number").map((c) => c.name));
  const shown = examples.data ? keptFirst(examples.data, levels, numeric, policy === "first") : null;
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal wiz-modal wiz-modal-wide">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            <NamesFile text={d.title({ file: file.name, column: file.id_column ?? "" })} name={file.name} />
          </Heading>
          {hasRepeats && (
            <DialogSection title={d.repeatsTitle({ n: r.repeated })} note={r.few ? d.fewMeans : d.manyMeans}>
              {examples.data && shown && (
                <div className="wiz-dupes-table">
                  <table className="tbl wiz-table">
                    <thead>
                      <tr>
                        {policy === "first" && <th />}
                        {examples.data.columns.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map(({ row, band: b, kept: k }, i) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: example rows have no identity of their own
                        <tr key={i} className={`${b ? "band-b" : "band-a"}${k ? " dupes-kept" : ""}`}>
                          {policy === "first" && (
                            <td>{k && <span className="pill pill-ok">{d.kept}</span>}</td>
                          )}
                          {row.map((v, j) => (
                            // biome-ignore lint/suspicious/noArrayIndexKey: cells by position
                            <td key={j} className="mono">
                              <Val v={v} />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Radios
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
                  <div className="wiz-indent dupes-levels">
                    {levels.length === 0 && <p className="wiz-from">{d.fileOrder}</p>}
                    {levels.map((l, i) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: a level is its place in the order
                      <div key={i} className="dupes-level">
                        <span className="dupes-level-label">{i === 0 ? d.sortBy : d.thenBy}</span>
                        <Choice
                          label={`${i === 0 ? d.sortBy : d.thenBy} (${i + 1})`}
                          hideLabel
                          value={l.column}
                          options={columns.map((c) => [c, c] as const)}
                          onChange={(column) =>
                            setLevels(levels.map((x, j) => (j === i ? { ...x, column } : x)))
                          }
                        />
                        <Choice
                          label={`${d.order} (${i + 1})`}
                          hideLabel
                          value={l.desc ? "desc" : "asc"}
                          options={[
                            ["asc", d.asc],
                            ["desc", d.desc],
                          ]}
                          onChange={(v) =>
                            setLevels(levels.map((x, j) => (j === i ? { ...x, desc: v === "desc" } : x)))
                          }
                        />
                        <RemoveButton
                          what={d.levelWhat({ column: l.column })}
                          onPress={() => setLevels(levels.filter((_, j) => j !== i))}
                          undo={() => setLevels(levels)}
                        />
                      </div>
                    ))}
                    <AddButton
                      onPress={() =>
                        setLevels([
                          ...levels,
                          {
                            column:
                              columns.find(
                                (c) => c !== file.id_column && !levels.some((x) => x.column === c),
                              ) ??
                              columns[0] ??
                              "",
                            desc: false,
                          },
                        ])
                      }
                    >
                      {levels.length ? d.addThen : d.addSort}
                    </AddButton>
                    {examples.data && <p className="wiz-from">{d.keptNote}</p>}
                  </div>
                )}
                <Radio value="all" className="radio">
                  <span className="radio-dot" aria-hidden="true" />
                  {d.all}
                </Radio>
              </Radios>
            </DialogSection>
          )}
          {hasBlanks && (
            <DialogSection
              title={d.blanksTitle({ n: r.blank })}
              note={d.blankMeans({ sales: file.holds === "sales" })}
            >
              <Tick isSelected={blankOk} onChange={setBlankOk}>
                {d.blankOk({ n: r.blank, sales: file.holds === "sales" })}
              </Tick>
            </DialogSection>
          )}
          <DialogFoot result={kept !== null && d.result({ rows: r.rows, kept })}>
            <Button
              className="button button-primary"
              isDisabled={!((hasRepeats && policy !== null) || (hasBlanks && blankOk !== r.blank_ok))}
              onPress={() =>
                change(
                  {
                    kind: "file",
                    name: file.name,
                    ...(hasRepeats && policy ? { dupes: policy } : {}),
                    ...(hasRepeats && policy === "first"
                      ? { dupes_by: levels.map((l) => ({ ...l, numeric: false })) }
                      : {}),
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
          </DialogFoot>
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
  onCancel,
}: {
  project: Project;
  data: Wizard;
  exclude: string[];
  onChosen: (name: string) => void;
  /** Where the slot can be taken away again (another file, not yet chosen): its red −. */
  onCancel?: () => void;
}) {
  const canPick = useCanPickFile();
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  // A file added or chosen: it's read for this step (all of it, for its columns and IDs: a big one takes a while),
  // said here until the step shows it. While the wizard reads the project again, and while the step saves it.
  const [chosen, setChosen] = useState<string | null>(null);
  const [settling, setSettling] = useState(false);
  const saving = useIsMutating() > 0;
  const choose = (name: string) => {
    setChosen(name);
    onChosen(name);
  };
  const pick = async () => {
    const path = await desktop.pickFile();
    if (path) setPicked(path);
  };
  const existing = data.files.filter((f) => !exclude.includes(f.name) && !f.problem);
  if (chosen !== null && (settling || saving)) {
    return (
      <FileSlot>
        <Waiting doing={w.readingChosen({ file: chosen })} />
      </FileSlot>
    );
  }
  if (picked !== null) {
    return (
      <AddFile
        project={project}
        path={picked}
        onBrowse={() => void pick()}
        onDone={() => setPicked(null)}
        onAdded={async (name) => {
          setChosen(name);
          setSettling(true);
          try {
            await queryClient.invalidateQueries({ queryKey: ["wizard", project.id] });
          } finally {
            setSettling(false);
          }
          onChosen(name);
        }}
      />
    );
  }
  return (
    <FileSlot>
      {canPick ? (
        <AddButton primary onPress={() => void pick()}>
          {w.addFile}
        </AddButton>
      ) : (
        <TipOn text={w.noPicker}>
          <AddButton isDisabled>{w.addFile}</AddButton>
        </TipOn>
      )}
      {existing.length > 0 && (
        <span className="entry-slot-or">
          <span className="wiz-from">{t.files.useExisting}</span>
          <Choice
            label={w.orExisting}
            hideLabel
            value={null}
            placeholder={w.choose}
            options={existing.map((f) => [f.name, f.name, f.filename] as const)}
            onChange={choose}
          />
        </span>
      )}
      {onCancel && (
        <span className="entry-acts">
          <RemoveButton what={w.cancel} label={w.cancel} onPress={onCancel} />
        </span>
      )}
    </FileSlot>
  );
}

/** A file a step uses: its entry, the red − taking it off the step (it stays in the project), its settings inside. */
export function StepFile({
  projectId,
  file,
  onRemove,
  undo,
  status,
  actions,
  children,
}: {
  projectId: string;
  file: WizardFile;
  onRemove: () => void;
  /** Puts it back on the step: Undo after the −. */
  undo?: () => void;
  status?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <FileEntry
      name={file.name}
      filename={file.filename}
      facts={fileFacts(file)}
      status={
        <>
          {status}
          <ReadingLine projectId={projectId} name={file.name} />
        </>
      }
      actions={actions}
      onRemove={onRemove}
      {...(undo ? { undo } : {})}
    >
      {children}
    </FileEntry>
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
  inline = false,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  change: Mutate;
  inline?: boolean;
}) {
  const options = matchOptions(base);
  // More sales details join on the sale ID (made from their parcel ID and date, if the sales record's is); rows
  // appended join on the parcel ID; anything else on the parcel ID or an extra ID.
  const made = file.match === "key_sale" && data.sale_id.made;
  const appended = file.holds === "parcel_rows" || file.holds === "sale_rows";
  const several = options.length > 1 && file.match !== "key_sale" && !appended;
  return (
    <div className="wiz-grid">
      <div className="wiz-label">
        {file.match === "key_sale" && !made ? w.saleIdLabel : several ? w.matchBy : w.parcelId}
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
          label={w.idColumnIn({ file: file.name })}
          hideLabel
          value={file.id_column}
          placeholder={w.choose}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(id_column) => change({ kind: "file", name: file.name, id_column })}
        />
      </div>
      <IdCheck projectId={projectId} data={data} file={file} change={change} inline={inline} />
      {made && (
        <>
          <div className="wiz-label">{w.extraFiles.saleDate}</div>
          <div className="wiz-pair">
            <Choice
              label={`${w.extraFiles.saleDate}: ${file.name}`}
              hideLabel
              value={file.date_column ?? null}
              placeholder={w.choose}
              options={file.columns.map((c) => [c.name, c.name] as const)}
              onChange={(column) => change({ kind: "rowField", name: file.name, key: "sale_date", column })}
            />
          </div>
          <div className="wiz-samples wiz-from">{w.extraFiles.madeId}</div>
        </>
      )}
    </div>
  );
}

/** The Sales file part, under the file: do its sales find their parcels? Why some don't, and their IDs cleaned
 * up live until they do (what "See them…", "Reconcile…" and the ⚠ held, laid out; saved as it's changed). */
export function MatchPanel({
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
  // What it joins to: the main sales file for more sales details, else the parcel universe.
  const base =
    file.match === "key_sale" ? data.files.find((f) => isMainSales(f)) : data.files.find((f) => f.base);
  const missing = file.not_in_universe;
  if (!base || file.id_column === null || file.id_check?.share == null) return null;
  const head = isMainSales(file)
    ? w.salesParts.matchHead
    : file.match === "key_sale"
      ? w.salesParts.matchSales
      : w.salesParts.matchParcels;
  return (
    <div className="frame qc-panel match-panel">
      <h3 className="wiz-group">{head}</h3>
      {missing && (
        <div className="rc-sub">
          {missing.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {missing.units && <CondosLink projectId={projectId} />}
        </div>
      )}
      <ReconcilePanel
        projectId={projectId}
        file={file}
        base={base}
        save={(file_steps, base_steps) =>
          change({ kind: "reconcile", name: file.name, file_steps, base_steps })
        }
      />
    </div>
  );
}
