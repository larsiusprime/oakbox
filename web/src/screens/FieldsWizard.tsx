import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
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
import { navigate } from "../App";
import {
  api,
  type Project,
  type ProjectDetail,
  unwrap,
  type Wizard,
  type WizardField,
  type WizardFile,
  type WizardStep,
} from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { AddButton } from "../components/AddButton";
import { Choice } from "../components/Form";
import { LANDING_MARK, LandingPage, useFrame } from "../components/Steps";
import { Tip, TipOn } from "../components/Tip";
import { lastStep, markSeen, OVERVIEW, seen } from "../lib/place";
import { say, t } from "../wording";
import { CustomFields } from "./CustomFields";
import { DeedNames } from "./DeedNames";
import { EnrichStep } from "./Enrich";
import { ASSUMABLE, FieldRow, NONE, shortName } from "./FieldRow";
import { LocationExtras } from "./Location";
import { PermitsStep } from "./Permits";
import { ShapefilesStep } from "./Shapefiles";
import { CondoStep, UnitsPointer } from "./Units";
import { ValueSetsStep } from "./ValueSets";
import { CheckText, FileHeader, FilePicker, IdCheck, IdRow, isMainSales } from "./WizardFiles";
import { type Mutate, type MutateAsync, useChange } from "./wizardChange";

const w = t.wizard;
const L = t.landing.pages;
const MAKE = "__make";

/** F3d: the Fields tab, a guided wizard over all of the project's files (SPEC §3.0). */
export function FieldsTab({ detail, step }: { detail: ProjectDetail; step: string | null }) {
  const projectId = detail.project.id;
  const wizard = useQuery({
    queryKey: ["wizard", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard", { params: { path: { project_id: projectId } } }),
      ),
  });
  if (wizard.isPending) return <p className="empty">{w.loading}</p>;
  if (wizard.error) return <p className="error">{wizard.error.message}</p>;
  return <WizardView project={detail.project} data={wizard.data} step={step} />;
}

/** Steps in the order Next goes through them: the parts of a step that has them (More details, Condo units), not
 * the step itself. */
function order(steps: WizardStep[]): WizardStep[] {
  return steps.filter((s) => !steps.some((x) => x.parent === s.key));
}

/** A step with parts (More details, Condo units): it opens on its landing page, Start goes on to its first part. */
function firstPart(steps: WizardStep[], key: string): string | null {
  return steps.find((s) => s.parent === key)?.key ?? null;
}

function WizardView({ project, data, step }: { project: Project; data: Wizard; step: string | null }) {
  // Reads which landing pages have been seen (localStorage) as it draws.
  "use no memo";
  const projectId = project.id;
  const flat = order(data.steps);
  // Opens at the first step not done yet, or at Review (SPEC F3d).
  const [opening] = useState(() => flat.find((s) => s.status !== "done")?.key ?? "review");
  // No step asked for: the one last open here, else the tab's landing page the first time, else the first not done.
  const asked = step ?? lastStep(projectId, "fields")?.key ?? (seen(projectId, "fields") ? null : OVERVIEW);
  const landing = asked === OVERVIEW;
  // Back and Next go through every step, a major step's landing page before its parts.
  const seq = data.steps;
  const current = seq.find((s) => s.key === asked) ?? seq.find((s) => s.key === opening) ?? seq[0];
  const change = useChange(projectId);
  const [unfinished, setUnfinished] = useState(false);
  const go = (key: string) => navigate({ name: "project", id: projectId, tab: "fields", step: key });

  // Showing a step fills in its guesses, once (the server keeps track).
  const key = landing ? null : current?.key;
  const visit = change.mutate;
  useEffect(() => {
    if (key) visit({ kind: "visit", step: key });
  }, [key, visit]);
  useEffect(() => {
    if (landing) markSeen(projectId, "fields");
  }, [landing, projectId]);

  if (!current) return null;
  const index = seq.indexOf(current);
  const prev = seq[index - 1];
  const next = seq[index + 1];
  const tops = data.steps.filter((s) => !s.parent);
  const top = current.parent ?? current.key;
  const list = <StepList steps={data.steps} current={landing ? OVERVIEW : current.key} go={go} />;
  const tabPage = L.fields;
  if (landing && tabPage) {
    // Start goes to the list's next item, its first step, not to the first one not done.
    const first = seq.find((s) => !s.parent) ?? current;
    return (
      <div className="wiz">
        {list}
        <div className="wiz-main">
          <LandingPage
            page={tabPage}
            start={w.steps[first.key]?.title ?? first.key}
            onStart={() => go(first.key)}
          />
        </div>
      </div>
    );
  }
  const part = firstPart(data.steps, current.key);
  const page = L[current.key];
  if (part && page) {
    return (
      <div className="wiz">
        {list}
        <div className="wiz-main">
          <LandingPage
            page={page}
            kicker={`${t.tabs.fields} · ${w.stepOf({ n: tops.indexOf(current) + 1, of: tops.length })}`}
            start={w.steps[part]?.title ?? part}
            onStart={() => go(part)}
            back={prev ? () => go(prev.key) : null}
          />
        </div>
      </div>
    );
  }
  const copy = w.steps[current.key] ?? { title: current.key, question: "", lede: "" };
  const kicker = [
    w.stepOf({ n: tops.findIndex((s) => s.key === top) + 1, of: tops.length }),
    current.parent ? `${w.steps[current.parent]?.title} › ${copy.title}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  // Sales must have their fields; a step of optional fields (deeds, too) can be answered "I don't have these".
  const skippable = current.fields.length > 0 && current.key !== "sales";
  // Next is greyed until the step is ✅, but still answers a click: it says what's left (SPEC F3d).
  // Only what stops a run greys Next; warnings and notes stay on the step without holding it up.
  const gated = current.status === "blocked";
  // Review's own to-dos are what stops a run.
  const blocking =
    current.key === "review"
      ? data.problems.map((text) => ({ text, blocking: true }))
      : current.left.filter((l) => l.blocking);
  // After the last step, the next tab: Bring in data.
  const ahead = () => (next ? go(next.key) : navigate({ name: "project", id: projectId, tab: "bring" }));
  const onward = () =>
    // Moving on confirms the step: an optional step is then complete (SPEC F3d).
    change.mutate({ kind: "confirm", step: current.key }, { onSuccess: ahead });

  return (
    <div className="wiz">
      {list}
      <div className="wiz-main">
        <div className="wiz-body">
          <p className="wiz-kicker">{kicker}</p>
          <h2 className="wiz-q">{copy.question}</h2>
          {copy.lede && <p className="wiz-lede">{copy.lede}</p>}
          {current.key === "universe" && (
            <UniverseStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "sales" && <SalesStep project={project} data={data} change={change.mutate} />}
          {current.key === "more_files" && (
            <MoreFilesStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "review" && (
            <ReviewStep projectId={projectId} data={data} go={go} change={change.mutate} />
          )}
          {current.key === "assessed" && (
            <ValueSetsStep project={project} data={data} change={change.mutateAsync} />
          )}
          {current.fields.length > 0 &&
            current.key !== "assessed" &&
            (current.key !== "sales" || data.sale_id.file) && (
              <FieldsStep project={project} data={data} step={current} change={change.mutateAsync} />
            )}
          {current.key === "location" && (
            <LocationExtras project={project} data={data} change={change.mutate} />
          )}
          {current.key === "property_type" && (
            <CustomFields projectId={projectId} data={data} change={change.mutate} />
          )}
          {current.key === "shapefiles" && (
            <ShapefilesStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "deeds" && data.deeds && (
            <p className={data.deeds.ok ? "wiz-note" : "wiz-note wiz-warn"}>{data.deeds.text}</p>
          )}
          {current.key === "deeds" && <DeedNames projectId={projectId} />}
          {current.key === "enrich" && <EnrichStep projectId={projectId} />}
          {current.key === "permits" && <PermitsStep project={project} data={data} change={change.mutate} />}
          {current.parent === "condos" && (
            <CondoStep step={current.key} projectId={projectId} data={data} change={change.mutate} />
          )}
          {change.error && (
            <p className="error" role="alert">
              {change.error.message}
            </p>
          )}
        </div>
        {next && gated && current.left.length > 0 && (
          <p className="wiz-left">
            {say.wizard.left(
              current.left.length,
              current.left.map((l) => l.text),
            )}
          </p>
        )}
        <div className="wiz-foot">
          <span className="wiz-grow" />
          {prev && (
            <Button className="button" onPress={() => go(prev.key)}>
              {w.back}
            </Button>
          )}
          {skippable && (
            <Button
              className="button"
              onPress={() =>
                change.mutate({ kind: "skip", step: current.key }, { onSuccess: () => next && go(next.key) })
              }
            >
              {w.skip}
            </Button>
          )}
          <Button
            className={gated ? "button button-primary is-gated" : "button button-primary"}
            aria-disabled={gated}
            onPress={() => (gated ? setUnfinished(true) : onward())}
          >
            {next ? t.step.next : w.toBringIn}
          </Button>
        </div>
      </div>
      {unfinished && (
        <UnfinishedDialog
          copy={next ? w.unfinished : w.unfinishedRun}
          left={blocking}
          close={() => setUnfinished(false)}
          skip={() => {
            setUnfinished(false);
            ahead();
          }}
        />
      )}
    </div>
  );
}

/** Clicking the greyed Next: what's left on the step, and the choice to move on anyway. */
function UnfinishedDialog({
  copy,
  left,
  close,
  skip,
}: {
  copy: typeof w.unfinished;
  left: WizardStep["left"];
  close: () => void;
  skip: () => void;
}) {
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal wiz-unfinished">
        <Dialog className="modal-body" role="alertdialog">
          <Heading slot="title" className="modal-title">
            {copy.title}
          </Heading>
          <ul className="wiz-left-list">
            {left.map((item) => (
              <li key={item.text} className={item.blocking ? "wiz-blocking" : "wiz-caution"}>
                <img src={item.blocking ? blockingIcon : warningIcon} alt="" className="wiz-inline-icon" />
                {item.text}
              </li>
            ))}
          </ul>
          <p className="wiz-from">{copy.body}</p>
          <div className="form-actions wiz-unfinished-actions">
            <Button className="button" onPress={skip}>
              {copy.skip}
            </Button>
            <Button className="button button-primary" onPress={close} autoFocus>
              {copy.finish}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

// A step's mark (SPEC F3d): ✅ complete, ⚠ to decide, ❌ blocks a run; beside its number, which always shows.
const STATUS_ICONS: Record<string, string | null> = {
  done: resolvedIcon,
  attention: warningIcon,
  blocked: blockingIcon,
  blank: null,
};

function StepList({ steps, current, go }: { steps: WizardStep[]; current: string; go: (k: string) => void }) {
  const tops = steps.filter((s) => !s.parent);
  useFrame(
    [
      { key: OVERVIEW, title: t.landing.overview, status: "blank" },
      ...steps.map((s) => ({
        key: s.key,
        title: w.steps[s.key]?.title ?? s.key,
        status: s.status,
        ...(s.parent ? { parent: s.parent } : {}),
      })),
    ],
    current,
    go,
  );
  return (
    <ol className="wiz-steps">
      <li className={current === OVERVIEW ? "wiz-step now blank" : "wiz-step blank"}>
        <button
          type="button"
          onClick={() => go(OVERVIEW)}
          aria-current={current === OVERVIEW ? "step" : undefined}
        >
          <span className="n" aria-hidden="true">
            {LANDING_MARK}
          </span>
          <span className="mark" />
          {t.landing.overview}
        </button>
      </li>
      {steps.map((s) => {
        const n = tops.indexOf(s) + 1;
        const icon = STATUS_ICONS[s.status];
        const classes = ["wiz-step", s.parent ? "sub" : "", s.key === current ? "now" : "", s.status].join(
          " ",
        );
        return (
          <li key={s.key} className={classes}>
            <button
              type="button"
              onClick={() => go(s.key)}
              aria-current={s.key === current ? "step" : undefined}
            >
              {!s.parent && (
                <span className="n" aria-hidden="true">
                  {n}
                </span>
              )}
              <span className="mark" aria-hidden="true">
                {icon && <img src={icon} alt="" className="wiz-step-icon" />}
              </span>
              {w.steps[s.key]?.title ?? s.key}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function UniverseStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const [replacing, setReplacing] = useState(false);
  const [adding, setAdding] = useState(false);
  if (!base || replacing) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={base ? [base.name] : []}
        onChosen={(name) =>
          change({ kind: "file", name, universe: true }, { onSuccess: () => setReplacing(false) })
        }
      />
    );
  }
  const columns = base.columns.map((c) => [c.name, c.name] as const);
  return (
    <>
      <FileHeader file={base} onReplace={() => setReplacing(true)} />
      <p className="wiz-ok">{w.geometryFound}</p>
      <div className="wiz-grid frame">
        <div className="wiz-label">
          <TipOn text={w.parcelIdTip}>
            <span>{w.parcelId}</span>
          </TipOn>
        </div>
        <Choice
          label={w.parcelId}
          hideLabel
          value={base.id_column}
          placeholder={w.choose}
          options={columns}
          onChange={(id_column) => change({ kind: "file", name: base.name, id_column })}
        />
        <IdCheck projectId={project.id} data={data} file={base} change={change} />
        {base.extra_ids.map((e) => (
          <ExtraIdRow key={e.field} file={base} extra={e} change={change} />
        ))}
        {adding && <NewExtraIdRow file={base} change={change} done={() => setAdding(false)} />}
      </div>
      {!adding && base.extra_ids.length < EXTRA_IDS.length && (
        <Tip text={w.extraIdTip}>
          <AddButton end onPress={() => setAdding(true)}>
            {w.addId({ ordinal: w.idOrdinal[EXTRA_IDS[base.extra_ids.length] ?? "key2"] ?? "" })}
          </AddButton>
        </Tip>
      )}
    </>
  );
}

const EXTRA_IDS = ["key2", "key3"] as const;

function ExtraIdRow({
  file,
  extra,
  change,
}: {
  file: WizardFile;
  extra: WizardFile["extra_ids"][number];
  change: Mutate;
}) {
  const ordinal = w.idOrdinal[extra.field] ?? extra.field;
  return (
    <>
      <div className="wiz-label">
        <TipOn text={w.extraIdTip}>
          <span>{ordinal}</span>
        </TipOn>
        <small>{w.optional}</small>
      </div>
      <Choice
        label={ordinal}
        hideLabel
        value={extra.column}
        options={[[NONE, w.removeId] as const, ...file.columns.map((c) => [c.name, c.name] as const)]}
        onChange={(v) =>
          change({
            kind: "file",
            name: file.name,
            extra_field: extra.field,
            extra_column: v === NONE ? null : v,
          })
        }
      />
      <div />
    </>
  );
}

function NewExtraIdRow({ file, change, done }: { file: WizardFile; change: Mutate; done: () => void }) {
  const field = EXTRA_IDS[file.extra_ids.length] ?? "key2";
  const ordinal = w.idOrdinal[field] ?? field;
  return (
    <>
      <div className="wiz-label">
        <TipOn text={w.extraIdTip}>
          <span>{ordinal}</span>
        </TipOn>
        <small>{w.optional}</small>
      </div>
      <Choice
        label={ordinal}
        hideLabel
        value={null}
        placeholder={w.choose}
        options={file.columns.map((c) => [c.name, c.name] as const)}
        onChange={(v) =>
          change({ kind: "file", name: file.name, extra_field: field, extra_column: v }, { onSuccess: done })
        }
      />
      <div className="wiz-samples">
        <Button className="wiz-link" onPress={done}>
          {w.cancel}
        </Button>
      </div>
    </>
  );
}

function SalesStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  const [replacing, setReplacing] = useState(false);
  if (!sales || replacing) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={[...(base ? [base.name] : []), ...(sales ? [sales.name] : [])]}
        onChosen={(name) =>
          change({ kind: "file", name, holds: "sales" }, { onSuccess: () => setReplacing(false) })
        }
      />
    );
  }
  return (
    <>
      <FileHeader file={sales} onReplace={() => setReplacing(true)} />
      {/* Its two IDs, in one frame: the parcel each sale finds, and the sale's own. */}
      <div className="frame">
        <IdRow projectId={project.id} data={data} file={sales} base={base} change={change} />
        <div className="wiz-grid">
          <div className="wiz-label">
            <TipOn text={w.saleIdTip}>
              <span>{w.saleIdColumn}</span>
            </TipOn>
          </div>
          <Choice
            label={w.saleIdColumn}
            hideLabel
            value={data.sale_id.made ? MAKE : data.sale_id.column}
            placeholder={w.choose}
            options={[[MAKE, w.makeSaleId] as const, ...sales.columns.map((c) => [c.name, c.name] as const)]}
            onChange={(v) => change({ kind: "saleId", column: v === MAKE ? null : v, make: v === MAKE })}
          />
          <div className="wiz-samples">
            <CheckText check={data.sale_id.check} />
          </div>
        </div>
      </div>
    </>
  );
}

/** F3d: more files, one by one: what each joins to (parcels or sales), the ID it joins on, and its checks. */
function MoreFilesStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const main = data.files.find(isMainSales);
  // Picked here this visit: shown even before it's said what it holds.
  const [chosen, setChosen] = useState<string[]>([]);
  const extras = data.files.filter(
    (f) =>
      !f.base &&
      f !== main &&
      (f.holds === "parcels" ||
        f.holds === "sales" ||
        f.holds === "parcel_rows" ||
        f.holds === "sale_rows" ||
        f.holds === null ||
        chosen.includes(f.name)),
  );
  const [adding, setAdding] = useState(extras.length === 0);
  return (
    <>
      {extras.map((f) => (
        <ExtraFile
          key={f.name}
          project={project}
          data={data}
          file={f}
          base={base}
          main={main}
          change={change}
          drop={() => {
            setChosen((c) => c.filter((n) => n !== f.name));
            change({ kind: "file", name: f.name, holds: "unused" });
          }}
        />
      ))}
      {adding ? (
        <div className="wiz-extra">
          <FilePicker
            project={project}
            data={data}
            exclude={[
              ...(base ? [base.name] : []),
              ...(main ? [main.name] : []),
              ...extras.map((f) => f.name),
            ]}
            onChosen={(name) => {
              setChosen((c) => [...c, name]);
              setAdding(false);
            }}
          />
          {extras.length > 0 && (
            <Button className="wiz-link" onPress={() => setAdding(false)}>
              {w.cancel}
            </Button>
          )}
        </div>
      ) : (
        <AddButton end onPress={() => setAdding(true)}>
          {extras.length ? w.extraFiles.another : w.extraFiles.first}
        </AddButton>
      )}
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
}: {
  project: Project;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  main: WizardFile | undefined;
  change: Mutate;
  drop: () => void;
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
  const set = (holds: "parcels" | "sales" | "parcel_rows" | "sale_rows") =>
    change(
      holds === "sales"
        ? { kind: "file", name: file.name, holds, match: "key_sale" }
        : { kind: "file", name: file.name, holds },
    );
  const joined = about === "parcels" ? "parcels" : "sales";
  const rows = about === "parcels" ? "parcel_rows" : "sale_rows";
  return (
    <section className="wiz-extra">
      <div className="wiz-file">
        <span className="mono">{file.name}</span>
        <span className="wiz-from">{file.filename}</span>
        {file.rows !== null && <span className="wiz-from">· {file.rows.toLocaleString()} rows</span>}
        <Button className="wiz-link" onPress={drop}>
          {m.drop}
        </Button>
      </div>
      <RadioGroup
        className="field radios wiz-holds"
        value={about}
        onChange={(v) =>
          set(v === "sales" ? (appended ? "sale_rows" : "sales") : appended ? "parcel_rows" : "parcels")
        }
      >
        <Label className="field-label">{m.what}</Label>
        <Radio value="parcels" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {m.parcels}
        </Radio>
        <Radio value="sales" className="radio" isDisabled={!main}>
          <span className="radio-dot" aria-hidden="true" />
          {m.sales}
          {!main && <small className="wiz-from"> {m.needsSales}</small>}
        </Radio>
      </RadioGroup>
      {about && (
        <RadioGroup
          className="field radios wiz-holds wiz-how"
          value={appended ? "rows" : "joined"}
          onChange={(v) => set(v === "rows" ? rows : joined)}
        >
          <Label className="field-label">{m.how}</Label>
          <Radio value="joined" className="radio">
            <span className="radio-dot" aria-hidden="true" />
            {about === "parcels" ? m.joinedParcels : m.joinedSales}
          </Radio>
          <Radio value="rows" className="radio" isDisabled={about === "parcels" && !file.geometry}>
            <span className="radio-dot" aria-hidden="true" />
            {about === "parcels" ? m.rowsParcels : m.rowsSales}
            {about === "parcels" && !file.geometry && <small className="wiz-from"> {m.needsShapes}</small>}
          </Radio>
        </RadioGroup>
      )}
      {about && <IdRow projectId={project.id} data={data} file={file} base={base} change={change} />}
      {file.appended && <Appended file={file} change={change} />}
      {file.holds === "parcels" && <UnitsPointer projectId={project.id} file={file} />}
    </section>
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

// ---------- The fields, a few at a time ----------

function FieldsStep({
  project,
  data,
  step,
  change,
}: {
  project: Project;
  data: Wizard;
  step: WizardStep;
  change: MutateAsync;
}) {
  const [more, setMore] = useState(false);
  const mine = data.fields.filter((f) => f.step === step.key && !f.hidden);
  // Only the universe so far: building details are often in a separate file (a CAMA export).
  const onlyBase = step.key === "big_five" && data.files.filter((f) => f.holds === "parcels").length <= 1;
  // A field under More that's loaded (guessed or chosen) always shows: nothing loaded is ever out of sight.
  const inUse = (f: WizardField) => f.sources.length > 0 || f.assumed || f.absent;
  const shown = mine.filter((f) => !f.more || more || inUse(f));
  const hidden = mine.filter((f) => f.more && !inUse(f)).length;
  return (
    <>
      {onlyBase && <p className="wiz-note wiz-another">{w.anotherFileHint}</p>}
      <div className="wiz-grid frame">
        {groupsFor(step.key, shown).map(([title, fields]) =>
          // A section of one field is that row, numbered; a section of several gets a heading.
          title && fields.length === 1 && fields[0]
            ? [
                <FieldRow
                  key={fields[0].key}
                  project={project}
                  data={data}
                  field={fields[0]}
                  sales={step.sales}
                  change={change}
                  label={title}
                />,
              ]
            : [
                title && (
                  <h3 key={`group-${title}`} className="wiz-group">
                    {title}
                  </h3>
                ),
                ...fields.map((f) => (
                  <FieldRow
                    key={f.key}
                    project={project}
                    data={data}
                    field={f}
                    sales={step.sales}
                    change={change}
                    inGroup={Boolean(title)}
                  />
                )),
              ],
        )}
      </div>
      {hidden > 0 && (
        <Button className="wiz-more" onPress={() => setMore(!more)}>
          {more ? w.fewer : w.more({ n: hidden })}
        </Button>
      )}
    </>
  );
}

/** The Big five step's numbered sections (year built and effective year built are one: age). */
function groupsFor(step: string, fields: WizardField[]): [string | null, WizardField[]][] {
  if (step !== "big_five") return [[null, fields]];
  return w.bigFive
    .map(([title, keys], i) => [`${i + 1}. ${title}`, fields.filter((f) => keys.includes(f.key))] as const)
    .filter(([, group]) => group.length > 0)
    .map(([title, group]) => [title, [...group]]);
}

// ---------- Step 9: Review ----------

function ReviewStep({
  projectId,
  data,
  go,
  change,
}: {
  projectId: string;
  data: Wizard;
  go: (k: string) => void;
  change: Mutate;
}) {
  const loaded = data.fields.filter((f) => f.sources.length > 0 || f.assumed);
  const columns = loaded.reduce((n, f) => n + f.sources.length, 0);
  const required = new Set(["sale_price", "sale_date", ...ASSUMABLE]);
  const groups = order(data.steps).filter((s) => s.fields.length > 0);
  return (
    <>
      <p className="wiz-lede">
        {w.summary({ fields: loaded.length, columns })}{" "}
        {data.not_loaded.map((n) => say.wizard.notLoaded(n.file, n.columns)).join(" ")}
      </p>
      {data.files
        .filter((f) => f.holds === "parcels" && (f.repeats?.extra ?? 0) > 0)
        .map((f) => (
          <div key={f.name} className="wiz-grid wiz-review-ids">
            <div className="wiz-label mono">{f.name}</div>
            <div className="mono">{f.id_column}</div>
            <IdCheck projectId={projectId} data={data} file={f} change={change} />
          </div>
        ))}
      <h3 className="wiz-sub">{w.problems}</h3>
      {data.problems.length ? (
        <ul className="wiz-problems">
          {data.problems.map((p) => (
            <li key={p} className="wiz-warn">
              {p}
            </li>
          ))}
        </ul>
      ) : (
        <p className="wiz-ok">✓ {w.noProblems}</p>
      )}
      {data.warnings.length > 0 && (
        <>
          <h3 className="wiz-sub">{w.warnings}</h3>
          <ul className="wiz-problems">
            {data.warnings.map((p) => (
              <li key={p} className="wiz-warn">
                {p}
              </li>
            ))}
          </ul>
        </>
      )}
      <table className="wiz-review">
        <tbody>
          {groups.map((s) => {
            const rows = data.fields.filter(
              (f) => f.step === s.key && (f.sources.length > 0 || f.assumed || required.has(f.key)),
            );
            if (rows.length === 0) return null;
            return [
              <tr key={s.key} className="wiz-review-head">
                <th colSpan={3}>
                  {s.parent ? `${w.steps[s.parent]?.title} › ` : ""}
                  {w.steps[s.key]?.title}
                </th>
              </tr>,
              ...rows.map((f) => (
                <tr key={f.key}>
                  <td>{shortName(f)}</td>
                  <td className={f.sources.length ? "mono" : "wiz-none"}>
                    {f.assumed
                      ? `${w.assumed}: ${w.assumedValue[f.key]}`
                      : f.sources.map((x) => w.from({ column: x.column, file: x.file })).join("; ") ||
                        w.nothing}
                  </td>
                  <td>
                    <Button className="wiz-link" onPress={() => go(s.key)}>
                      {w.change}
                    </Button>
                  </td>
                </tr>
              )),
            ];
          })}
        </tbody>
      </table>
    </>
  );
}
