import { useState } from "react";
import { Button } from "react-aria-components";
import type { Project, Wizard, WizardFile, WizardStep } from "../api/client";
import { AddButton } from "../components/AddButton";
import { Choice } from "../components/Form";
import { Seg } from "../components/Seg";
import { Waiting } from "../components/Waiting";
import { afterPaint } from "../lib/hooks";
import { t } from "../wording";
import { UnitsPointer } from "./Units";
import { FilePicker, IdRow, isMainSales, MatchPanel, StepFile } from "./WizardFiles";
import type { Change, Mutate } from "./wizardChange";

const w = t.wizard;
// More files' parts made from its files: "more:" and the file's name (the server's StepView.title).
export const MORE = "more:";

// F3d: More files, one by one: what each joins to (parcels or sales), the ID it joins on, and its checks.

/** More files' files: those it joins (or appends), and those added here not said yet what they hold. */
function extraFiles(data: Wizard): WizardFile[] {
  const main = data.files.find(isMainSales);
  return data.files.filter(
    (f) =>
      !f.base &&
      f !== main &&
      (f.holds === "parcels" ||
        f.holds === "sales" ||
        f.holds === "parcel_rows" ||
        f.holds === "sale_rows" ||
        f.holds === null),
  );
}

/** F3d (revised 2026-11-05): More files' first part: add the files, one by one, nothing else asked. Each then has a
 * part of its own (FileStep). */
export function AddFilesStep({
  project,
  data,
  change,
  go,
}: {
  project: Project;
  data: Wizard;
  change: Mutate;
  go: (key: string) => void;
}) {
  const base = data.files.find((f) => f.base);
  const main = data.files.find(isMainSales);
  const extras = extraFiles(data);
  const [adding, setAdding] = useState(extras.length === 0);
  return (
    <div className="entry-list">
      {extras.map((f) => (
        <StepFile
          projectId={project.id}
          key={f.name}
          file={f}
          onRemove={() => change({ kind: "file", name: f.name, holds: "unused" })}
          undo={() => change(restoreFile(f))}
          actions={
            <Button className="button button-small" onPress={() => go(`${MORE}${f.name}`)}>
              {w.extraFiles.configure}
            </Button>
          }
        />
      ))}
      {adding ? (
        <FilePicker
          project={project}
          data={data}
          exclude={[...(base ? [base.name] : []), ...(main ? [main.name] : []), ...extras.map((f) => f.name)]}
          onChosen={(name) => {
            change({ kind: "file", name, added: true });
            setAdding(false);
          }}
          {...(extras.length > 0 ? { onCancel: () => setAdding(false) } : {})}
        />
      ) : (
        <AddButton end onPress={() => setAdding(true)}>
          {extras.length ? w.extraFiles.another : w.extraFiles.first}
        </AddButton>
      )}
    </div>
  );
}

/** What puts a file set aside back as it was: its part, or one of More files' files not said yet what it holds. */
function restoreFile(f: WizardFile): Change {
  if (f.holds === "sales") return { kind: "file", name: f.name, holds: "sales", match: "key_sale" };
  if (f.holds && f.holds !== "unused" && f.holds !== "overlay" && f.holds !== "permits")
    return { kind: "file", name: f.name, holds: f.holds };
  return { kind: "file", name: f.name, added: true };
}

/** One of More files' files, on a part of its own: what it's about, how it joins, its ID, and whether its rows find
 * theirs, laid out under it (what "See them…", "Reconcile…" and the ⚠ held). */
export function FileStep({
  project,
  data,
  step,
  change,
  go,
}: {
  project: Project;
  data: Wizard;
  step: WizardStep;
  change: Mutate;
  go: (key: string) => void;
}) {
  const file = data.files.find((f) => f.name === step.title);
  if (!file) return null;
  const base = data.files.find((f) => f.base);
  const main = data.files.find(isMainSales);
  return (
    <>
      <ExtraFile
        project={project}
        data={data}
        file={file}
        base={base}
        main={main}
        change={change}
        drop={() => {
          change({ kind: "file", name: file.name, holds: "unused" });
          go("more_add");
        }}
        restore={() => change(restoreFile(file))}
      />
      {file.holds && <MatchPanel projectId={project.id} data={data} file={file} change={change} />}
    </>
  );
}

function ExtraFile({
  project,
  data,
  file,
  base,
  main,
  change,
  drop,
  restore,
}: {
  project: Project;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  main: WizardFile | undefined;
  change: Mutate;
  drop: () => void;
  restore: () => void;
}) {
  const m = w.extraFiles;
  // What it's about (parcels or sales), then how it joins: on the ID, or appended as extra rows.
  const about =
    file.holds === "parcels" || file.holds === "parcel_rows"
      ? "parcels"
      : file.holds === "sales" || file.holds === "sale_rows"
        ? "sales"
        : null;
  const appended = file.holds === "parcel_rows" || file.holds === "sale_rows";
  // Saying what it's about reads the file for its ID column: said on the page while it does.
  const [busy, setBusy] = useState(false);
  const set = (holds: "parcels" | "sales" | "parcel_rows" | "sale_rows") => {
    setBusy(true);
    afterPaint(() =>
      change(
        holds === "sales"
          ? { kind: "file", name: file.name, holds, match: "key_sale" }
          : { kind: "file", name: file.name, holds },
        { onSettled: () => setBusy(false) },
      ),
    );
  };
  const joined = about === "parcels" ? "parcels" : "sales";
  const rows = about === "parcels" ? "parcel_rows" : "sale_rows";
  return (
    <StepFile projectId={project.id} file={file} onRemove={drop} undo={restore}>
      {/* What it's about and how it joins, on the same two columns as its ID below. */}
      <div className="wiz-grid">
        <div className="wiz-label">{m.what}</div>
        <div className="wiz-span">
          <Seg
            label={m.what}
            value={about}
            options={[
              ["parcels", m.parcels],
              ["sales", m.sales],
            ]}
            disabled={main ? [] : ["sales"]}
            titles={main ? {} : { sales: m.needsSales }}
            onChange={(v) =>
              set(v === "sales" ? (appended ? "sale_rows" : "sales") : appended ? "parcel_rows" : "parcels")
            }
          />
        </div>
        {about && (
          <>
            <div className="wiz-label">{m.how}</div>
            <div className="wiz-span">
              <Seg
                label={m.how}
                value={appended ? "rows" : "joined"}
                options={[
                  ["joined", about === "parcels" ? m.joinedParcels : m.joinedSales],
                  ["rows", about === "parcels" ? m.rowsParcels : m.rowsSales],
                ]}
                disabled={about === "parcels" && !file.geometry ? ["rows"] : []}
                titles={about === "parcels" && !file.geometry ? { rows: m.needsShapes } : {}}
                onChange={(v) => set(v === "rows" ? rows : joined)}
              />
            </div>
          </>
        )}
      </div>
      {busy && <Waiting doing={m.working({ file: file.name })} className="waiting waiting-inline" />}
      {about && !busy && (
        <IdRow projectId={project.id} data={data} file={file} base={base} change={change} inline />
      )}
      {file.appended && <Appended file={file} change={change} />}
      {file.holds === "parcels" && <UnitsPointer projectId={project.id} file={file} />}
    </StepFile>
  );
}

/** A file appended as rows: how many of the main file's fields it has, whether its IDs look like the main file's,
 * its columns for those fields (each changeable), and what happens to rows in both. */
function Appended({ file, change }: { file: WizardFile; change: Mutate }) {
  const m = w.extraFiles;
  const a = file.appended;
  if (!a) return null;
  const sales = a.adds_to === "sales";
  const missing = a.fields.filter((f) => !f.column && !f.assumed).map((f) => f.name);
  const columns = [["", m.notIn] as const, ...file.columns.map((c) => [c.name, c.name] as const)];
  return (
    <div className="wiz-appended">
      <p className={a.few ? "wiz-warn" : "wiz-ok"}>
        {a.few ? "" : "✓ "}
        {m.has({ have: a.have, of: a.of, what: sales ? m.salesRecord : m.universe })}
        {missing.length > 0 && m.missing({ names: missing.join(", ") })}
        {a.few && ` ${m.few}`}
      </p>
      <p className={a.key_ok ? "wiz-ok" : "wiz-warn"}>
        {a.key_ok ? "✓ " : "! "}
        {a.key_text.charAt(0).toUpperCase() + a.key_text.slice(1)}.
      </p>
      <div className="wiz-grid">
        {a.fields.map((f) => [
          <div key={`${f.key}-l`} className="wiz-label">
            {f.name}
          </div>,
          <div key={`${f.key}-c`}>
            <Choice
              label={`${f.name}: ${file.name}`}
              hideLabel
              value={f.column ?? ""}
              options={columns}
              onChange={(column) =>
                change({ kind: "rowField", name: file.name, key: f.key, column: column || null })
              }
            />
          </div>,
          <div key={`${f.key}-n`} className="wiz-samples wiz-from">
            {f.assumed ? m.assumedNote : sales && f.key === "valid_sale" && f.column ? m.ruleNote : ""}
          </div>,
        ])}
      </div>
      {a.overlap > 0 && (
        <p className="wiz-warn">
          {sales ? m.overlapSales({ n: a.overlap }) : m.overlapParcels({ n: a.overlap })}
        </p>
      )}
      <p className="wiz-from">
        {sales ? m.appendedSales({ rows: a.rows }) : m.appendedParcels({ rows: a.rows })}
      </p>
    </div>
  );
}
