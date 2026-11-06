import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
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
import { Disclose } from "../components/Disclose";
import { NamesFiles, SubEntry } from "../components/FileEntry";
import { Choice } from "../components/Form";
import { Seg } from "../components/Seg";
import { LANDING_MARK, LandingPage, StepFoot, useFrame } from "../components/Steps";
import { Tip, TipOn } from "../components/Tip";
import { lastStep, markSeen, OVERVIEW, seen } from "../lib/place";
import { navigate } from "../lib/route";
import { say, t } from "../wording";
import { CustomFields } from "./CustomFields";
import { DeedNames } from "./DeedNames";
import { EnrichStep } from "./Enrich";
import { FieldHistogram } from "./FieldHistogram";
import { ASSUMABLE, FieldRow, shortName } from "./FieldRow";
import { Coordinates, LocationFields } from "./Location";
import { PermitsStep } from "./Permits";
import { QualityStep } from "./QualityStep";
import { SalesFieldPage } from "./SalesParts";
import { ShapefilesStep } from "./Shapefiles";
import { CondoStep, UnitsPointer } from "./Units";
import { ValueSetsStep } from "./ValueSets";
import { CheckText, FilePicker, IdCheck, IdRow, isMainSales, MatchPanel, StepFile } from "./WizardFiles";
import { type Change, type Mutate, type MutateAsync, useChange } from "./wizardChange";

// Quality and condition: numbers or categories, on a page of their own (QualityStep).
const QUALITY_STEPS = ["quality", "condition"];
// Sales' field parts: each field on a page of its own, read and checked under it (SalesFieldPage).
const SALES_FIELD_STEPS = ["sale_price", "sale_date", "valid_sale", "vacant_sale"];
// More files' parts made from its files: "more:" and the file's name (the server's StepView.title).
const MORE = "more:";

/** A step's title: a file's own part by its file's name, the others by their wording. */
function stepTitle(s: WizardStep | undefined): string {
  if (!s) return "";
  return s.title ?? w.steps[s.key]?.title ?? s.key;
}
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
  // A file's own part gone (the file set aside): back to adding files.
  const gone = asked?.startsWith(MORE) && !seq.some((s) => s.key === asked) ? "more_add" : null;
  const current = seq.find((s) => s.key === (gone ?? asked)) ?? seq.find((s) => s.key === opening) ?? seq[0];
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
  if (part && current.key === "sales") {
    // Sales opens on its file: picked here, then the parts (its date, its IDs, the rest) one by one.
    const sales = data.files.find(isMainSales);
    const startPart = stepTitle(data.steps.find((s) => s.key === part)) ?? part;
    return (
      <div className="wiz">
        {list}
        <div className="wiz-main">
          <div className="wiz-body">
            <h2 className="wiz-q">{w.steps.sales?.question}</h2>
            <p className="wiz-lede">{w.steps.sales?.lede}</p>
            <SalesFile project={project} data={data} change={change.mutate} />
          </div>
          <StepFoot
            back={prev ? () => go(prev.key) : null}
            next={{ label: t.landing.start({ step: startPart }), onPress: () => go(part), disabled: !sales }}
          />
        </div>
      </div>
    );
  }
  const page = L[current.key];
  if (part && page) {
    return (
      <div className="wiz">
        {list}
        <div className="wiz-main">
          <LandingPage
            page={page}
            start={stepTitle(data.steps.find((s) => s.key === part)) ?? part}
            onStart={() => go(part)}
            back={prev ? () => go(prev.key) : null}
          />
        </div>
      </div>
    );
  }
  const copy = current.key.startsWith(MORE)
    ? { title: stepTitle(current), question: stepTitle(current), lede: w.extraFiles.stepLede }
    : (w.steps[current.key] ?? { title: current.key, question: "", lede: "" });
  // Sales must have their fields; a step of optional fields (deeds, too) can be answered "I don't have these".
  const skippable = current.fields.length > 0 && current.parent !== "sales";
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
          <h2 className="wiz-q">{copy.question}</h2>
          {copy.lede && <p className="wiz-lede">{copy.lede}</p>}
          {current.key === "universe" && (
            <UniverseStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "sales_ids" && <SalesIds project={project} data={data} change={change.mutate} />}
          {SALES_FIELD_STEPS.includes(current.key) && (
            <SalesFieldPage project={project} data={data} step={current} change={change.mutateAsync} />
          )}
          {current.key === "more_add" && (
            <AddFilesStep project={project} data={data} change={change.mutate} go={go} />
          )}
          {current.key.startsWith(MORE) && (
            <FileStep project={project} data={data} step={current} change={change.mutate} go={go} />
          )}
          {current.key === "review" && (
            <ReviewStep projectId={projectId} data={data} go={go} change={change.mutate} />
          )}
          {current.key === "assessed" && (
            <ValueSetsStep project={project} data={data} change={change.mutateAsync} />
          )}
          {current.fields.length > 0 &&
            current.key !== "assessed" &&
            !QUALITY_STEPS.includes(current.key) &&
            !SALES_FIELD_STEPS.includes(current.key) && (
              <FieldsStep project={project} data={data} step={current} change={change.mutateAsync} />
            )}
          {QUALITY_STEPS.includes(current.key) && (
            <QualityStep project={project} data={data} step={current} change={change.mutateAsync} />
          )}
          {current.key === "coordinates" && (
            <Coordinates projectId={projectId} hasShapes={data.files.some((f) => f.base && f.geometry)} />
          )}
          {current.key === "location" && (
            <LocationFields projectId={projectId} data={data} change={change.mutate} />
          )}
          {current.key === "custom" && (
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
        title: stepTitle(s),
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
              {stepTitle(s)}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function UniverseStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const [adding, setAdding] = useState(false);
  if (!base) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={[]}
        onChosen={(name) => change({ kind: "file", name, universe: true })}
      />
    );
  }
  const columns = base.columns.map((c) => [c.name, c.name] as const);
  return (
    <StepFile
      file={base}
      onRemove={() => change({ kind: "file", name: base.name, holds: "unused" })}
      undo={() => change({ kind: "file", name: base.name, universe: true })}
    >
      {/* Each ID its own box: each but the parcel ID can be taken away on its own. */}
      <div className="wiz-grid">
        <SubEntry
          label={
            <TipOn text={w.parcelIdTip}>
              <span>{w.parcelId}</span>
            </TipOn>
          }
          control={
            <Choice
              label={w.parcelId}
              hideLabel
              value={base.id_column}
              placeholder={w.choose}
              options={columns}
              onChange={(id_column) => change({ kind: "file", name: base.name, id_column })}
            />
          }
          after={<IdCheck projectId={project.id} data={data} file={base} change={change} />}
        />
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
    </StepFile>
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
    <SubEntry
      label={
        <>
          <TipOn text={w.extraIdTip}>
            <span>{ordinal}</span>
          </TipOn>
          <small>{w.optional}</small>
        </>
      }
      control={
        <Choice
          label={ordinal}
          hideLabel
          value={extra.column}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(v) =>
            change({ kind: "file", name: file.name, extra_field: extra.field, extra_column: v })
          }
        />
      }
      what={ordinal}
      onRemove={() => change({ kind: "file", name: file.name, extra_field: extra.field, extra_column: null })}
      // Removing the 2nd moves the 3rd up into its place: Undo puts both back where they were.
      undo={() => {
        const later = file.extra_ids.filter((e) => e.field > extra.field);
        const put = (i: number) => {
          const e = i === 0 ? extra : later[i - 1];
          if (!e) return;
          change(
            { kind: "file", name: file.name, extra_field: e.field, extra_column: e.column },
            { onSuccess: () => put(i + 1) },
          );
        };
        put(0);
      }}
    />
  );
}

function NewExtraIdRow({ file, change, done }: { file: WizardFile; change: Mutate; done: () => void }) {
  const field = EXTRA_IDS[file.extra_ids.length] ?? "key2";
  const ordinal = w.idOrdinal[field] ?? field;
  return (
    <SubEntry
      label={
        <>
          <TipOn text={w.extraIdTip}>
            <span>{ordinal}</span>
          </TipOn>
          <small>{w.optional}</small>
        </>
      }
      control={
        <Choice
          label={ordinal}
          hideLabel
          value={null}
          placeholder={w.choose}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(v) =>
            change(
              { kind: "file", name: file.name, extra_field: field, extra_column: v },
              { onSuccess: done },
            )
          }
        />
      }
      what={ordinal}
      onRemove={done}
    />
  );
}

/** Sales' own page: which file holds the sales. Nothing else is asked here; its parts come next. */
function SalesFile({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  if (!sales) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={base ? [base.name] : []}
        onChosen={(name) => change({ kind: "file", name, holds: "sales" })}
      />
    );
  }
  return (
    <StepFile
      file={sales}
      onRemove={() => change({ kind: "file", name: sales.name, holds: "unused" })}
      undo={() => change({ kind: "file", name: sales.name, holds: "sales" })}
    />
  );
}

/** Sales' IDs part: the parcel ID each sale carries and the sale's own ID (a column, or made from the parcel ID and
 * the sale date), then whether the sales find their parcels, why some don't, and the IDs cleaned up, under it. */
function SalesIds({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  if (!sales) return <p className="wiz-note">{w.salesParts.noFile}</p>;
  return (
    <>
      {/* Both IDs on one grid: their labels, controls and checks in the same columns. */}
      <div className="wiz-grid frame ids-box">
        <IdRow projectId={project.id} data={data} file={sales} base={base} change={change} inline />
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
      <MatchPanel projectId={project.id} data={data} file={sales} change={change} />
    </>
  );
}

/** F3d: more files, one by one: what each joins to (parcels or sales), the ID it joins on, and its checks. */
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
function AddFilesStep({
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
function FileStep({
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
  const set = (holds: "parcels" | "sales" | "parcel_rows" | "sale_rows") =>
    change(
      holds === "sales"
        ? { kind: "file", name: file.name, holds, match: "key_sale" }
        : { kind: "file", name: file.name, holds },
    );
  const joined = about === "parcels" ? "parcels" : "sales";
  const rows = about === "parcels" ? "parcel_rows" : "sale_rows";
  return (
    <StepFile file={file} onRemove={drop} undo={restore}>
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
      {about && <IdRow projectId={project.id} data={data} file={file} base={base} change={change} inline />}
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
  const onlyBase = step.parent === "big_five" && data.files.filter((f) => f.holds === "parcels").length <= 1;
  // A field under More that's loaded (guessed or chosen) always shows: nothing loaded is ever out of sight.
  const inUse = (f: WizardField) => f.sources.length > 0 || f.assumed || f.absent;
  const shown = mine.filter((f) => !f.more || more || inUse(f));
  const hidden = mine.filter((f) => f.more && !inUse(f)).length;
  return (
    <>
      {onlyBase && <p className="wiz-note wiz-another">{w.anotherFileHint}</p>}
      {step.parent === "big_five" ? (
        // Big five's parts: each field a capsule of its own, their columns lined up (one grid, each a subgrid).
        <div className="wiz-grid wiz-capsules">
          {shown.map((f) => (
            <div key={f.key} className="frame wiz-capsule">
              <FieldRow project={project} data={data} field={f} sales={step.sales} change={change} bare />
            </div>
          ))}
          {/* A size or a year: how its values spread, under the fields. */}
          {shown
            .filter((f) => f.sources.length > 0 && (f.area_unit || f.key.includes("year")))
            .map((f) => (
              <div key={`${f.key}-h`} className="wiz-capsule-wide">
                <FieldHistogram projectId={project.id} field={f} />
              </div>
            ))}
        </div>
      ) : (
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
      )}
      {hidden > 0 && (
        <Disclose className="wiz-more" open={more} onPress={() => setMore(!more)}>
          {more ? w.fewer : w.more({ n: hidden })}
        </Disclose>
      )}
    </>
  );
}

/** A step's fields in one section (Big five's parts are steps of their own now, not numbered sections). */
function groupsFor(_step: string, fields: WizardField[]): [string | null, WizardField[]][] {
  return [[null, fields]];
}

// ---------- Review ----------

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
        <NamesFiles
          items={data.not_loaded.map((n) => ({
            key: n.file,
            text: say.wizard.notLoaded(n.file, n.columns),
            name: n.file,
          }))}
        />
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
                  {stepTitle(s)}
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
