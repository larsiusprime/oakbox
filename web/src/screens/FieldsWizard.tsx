import { useIsFetching, useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import {
  api,
  type Project,
  type ProjectDetail,
  unwrap,
  type Wizard,
  type WizardField,
  type WizardStep,
} from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { Disclose } from "../components/Disclose";
import { FileName } from "../components/FileEntry";
import { FootBar, LANDING_MARK, LandingPage, RailToggle, StepFoot, useFrame } from "../components/Steps";
import { Loading } from "../components/Waiting";
import { lastStep, markSeen, OVERVIEW, seen } from "../lib/place";
import { navigate } from "../lib/route";
import { railClass, useRail } from "../lib/stepsrail";
import { say, t } from "../wording";
import { AsSoldStep, AtSale, AtSaleTable, CapHead } from "./AsSold";
import { CustomFields } from "./CustomFields";
import { DeedNames } from "./DeedNames";
import { EnrichStep } from "./Enrich";
import { FieldHistogram } from "./FieldHistogram";
import { ASSUMABLE, FieldRow, shortName } from "./FieldRow";
import { Coordinates, LocationFields } from "./Location";
import { AddFilesStep, FileStep, MORE } from "./MoreFiles";
import { PermitsStep } from "./Permits";
import { SCALED } from "./Quality";
import { QualityStep } from "./QualityStep";
import { SalesFieldPage } from "./SalesParts";
import { ShapefilesStep } from "./Shapefiles";
import { CondoStep } from "./Units";
import { ValueSetsStep } from "./ValueSets";
import { IdCheck, isMainSales } from "./WizardFiles";
import { SalesFile, SalesIds, UniverseStep } from "./WizardIds";
import { type Mutate, type MutateAsync, useChange } from "./wizardChange";

// Quality and condition: numbers or categories, on a page of their own (QualityStep).
const QUALITY_STEPS = ["quality", "condition"];
/** The steps whose fields describe the property: each shows what its sales use (Sales record fields). */
const CHARACTERISTIC_STEPS = ["building_size", "land_size", "age", "quality", "condition", "property_type"];
// Sales' field parts: each field on a page of its own, read and checked under it (SalesFieldPage).
const SALES_FIELD_STEPS = ["sale_price", "sale_date", "valid_sale", "vacant_sale"];

/** A step's title: a file's own part by its file's name, the others by their wording. */
function stepTitle(s: WizardStep | undefined): string {
  if (!s) return "";
  return s.title ?? w.steps[s.key]?.title ?? s.key;
}
const w = t.wizard;
const L = t.landing.pages;

/** A step's content: while its first data is loading (just opened), a loading bar under the step's header in its
 * place, the content kept mounted behind it so its reads go on; shown once nothing of it is loading. Later reads (a
 * choice changed) show where they are, as before. */
function StepContent({ stepKey, children }: { stepKey: string; children: React.ReactNode }) {
  const busy = useIsFetching({
    predicate: (q) =>
      q.state.status === "pending" &&
      q.meta?.quiet !== true &&
      !String(q.queryKey[0]).startsWith("map") &&
      q.queryKey[0] !== "wizard",
  });
  const [settled, setSettled] = useState<string | null>(null);
  // Settled once nothing's been loading for a moment (the step's reads start as it mounts, just after).
  useEffect(() => {
    if (busy > 0 || settled === stepKey) return;
    const id = window.setTimeout(() => setSettled(stepKey), 120);
    return () => window.clearTimeout(id);
  }, [busy, stepKey, settled]);
  const loading = settled !== stepKey;
  return (
    <>
      {loading && busy > 0 && (
        <div className="step-loading" role="status" aria-label={t.step.loading}>
          <span className="engine-bar opening-bar opening-bar-busy">
            <i />
          </span>
        </div>
      )}
      <div className={loading ? "step-content step-content-loading" : "step-content"}>{children}</div>
    </>
  );
}

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
  if (wizard.isPending) return <Loading q={wizard} qkey={["wizard", projectId]} doing={w.loading} />;
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
  // Moving between steps (showing one, moving on from one) is quiet: not something to say "Saving" about; what it
  // changes shows on the steps themselves (a guess filled in, a ✅).
  const moving = useChange(projectId, { quiet: true });
  const visit = moving.mutate;
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
  // Moving on confirms the step (an optional step is then complete, SPEC F3d), and moves on at once: the next step
  // shows straight away, its content loading in it, not this one waiting on the save.
  const onward = () => {
    moving.mutate({ kind: "confirm", step: current.key });
    ahead();
  };

  return (
    <div className="wiz">
      {list}
      <div className="wiz-main">
        <div className="wiz-body">
          <h2 className="wiz-q">{copy.question}</h2>
          {copy.lede && <p className="wiz-lede">{copy.lede}</p>}
          <StepContent stepKey={current.key}>
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
              // Today's (the parcels') beside At the sale (the sales'): side by side where there's room, else stacked.
              <div className="as-pair">
                <div className="as-today">
                  <QualityStep
                    project={project}
                    data={data}
                    step={current}
                    change={change.mutateAsync}
                    capsule={
                      data.files.some((f) => f.holds === "sales") &&
                      data.fields.some(
                        (f) =>
                          current.fields.includes(f.key) && SCALED.includes(f.key) && f.sources.length > 0,
                      )
                    }
                  />
                </div>
                {data.fields
                  .filter(
                    (f) => current.fields.includes(f.key) && SCALED.includes(f.key) && f.sources.length > 0,
                  )
                  .map((f) => (
                    <AtSale key={f.key} projectId={project.id} field={f} />
                  ))}
              </div>
            )}
            {current.key === "as_sold" && <AsSoldStep projectId={project.id} go={go} />}
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
            {current.key === "permits" && (
              <PermitsStep project={project} data={data} change={change.mutate} />
            )}
            {current.parent === "condos" && (
              <CondoStep step={current.key} projectId={projectId} data={data} change={change.mutate} />
            )}
          </StepContent>
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
        <FootBar>
          <span className="wiz-grow" />
          {prev && (
            <Button className="button" onPress={() => go(prev.key)} data-nav="back">
              {w.back}
            </Button>
          )}
          {skippable && (
            <Button
              className="button"
              onPress={() => {
                change.mutate({ kind: "skip", step: current.key });
                if (next) go(next.key);
              }}
            >
              {w.skip}
            </Button>
          )}
          <Button
            className={gated ? "button button-primary is-gated" : "button button-primary"}
            aria-disabled={gated}
            onPress={() => (gated ? setUnfinished(true) : onward())}
            data-nav="next"
          >
            {next ? t.step.next : w.toBringIn}
          </Button>
        </FootBar>
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
  const rail = useRail();
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
    <ol className={railClass(rail)}>
      <RailToggle />
      <li className={current === OVERVIEW ? "wiz-step now blank" : "wiz-step blank"}>
        <button
          type="button"
          onClick={() => go(OVERVIEW)}
          aria-current={current === OVERVIEW ? "step" : undefined}
          title={t.landing.overview}
        >
          <span className="n" aria-hidden="true">
            {LANDING_MARK}
          </span>
          <span className="mark" />
          <span className="t">{t.landing.overview}</span>
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
              title={stepTitle(s)}
            >
              {!s.parent && (
                <span className="n" aria-hidden="true">
                  {n}
                </span>
              )}
              <span className="mark" aria-hidden="true">
                {icon && <img src={icon} alt="" className="wiz-step-icon" />}
              </span>
              <span className="t">{stepTitle(s)}</span>
            </button>
          </li>
        );
      })}
    </ol>
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
  // A sales file: each characteristic in the parcel universe gets its 💰 Sales Record capsule (Sales record fields, F3d).
  const hasSales = data.files.some((f) => f.holds === "sales");
  return (
    <>
      {onlyBase && <p className="wiz-note wiz-another">{w.anotherFileHint}</p>}
      {step.parent === "big_five" ? (
        // Big five's parts: each field a capsule of its own (Today's: the parcels'), how a size or a year spreads under
        // it, and beside it At the sale (the sales'): side by side where there's room, else stacked.
        <div className="as-pairs">
          {shown.map((f) => (
            <div key={f.key} className="as-pairs">
              {/* Two fields on the step (Age): each pair under its field's name; one, the question says it. */}
              {hasSales && shown.length > 1 && <h3 className="wiz-group">{shortName(f)}</h3>}
              <div className="as-pair">
                <CapPu paired={hasSales && f.sources.length > 0}>
                  {hasSales && f.sources.length > 0 && <CapHead kind="pu" />}
                  <div className="wiz-grid wiz-capsules">
                    <div className={hasSales && f.sources.length > 0 ? "wiz-capsule" : "frame wiz-capsule"}>
                      <FieldRow
                        project={project}
                        data={data}
                        field={f}
                        sales={step.sales}
                        change={change}
                        bare
                        {...(hasSales && f.sources.length > 0 ? { label: t.wizard.asSold.column } : {})}
                      />
                    </div>
                    {f.sources.length > 0 && (f.area_unit || f.key.includes("year")) && (
                      <div className="wiz-capsule-wide">
                        <FieldHistogram projectId={project.id} field={f} bare={hasSales} pair={hasSales} />
                      </div>
                    )}
                  </div>
                </CapPu>
                {hasSales && f.sources.length > 0 && <AtSale projectId={project.id} field={f} />}
              </div>
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
      {hasSales && step.parent !== "big_five" && CHARACTERISTIC_STEPS.includes(step.key) && (
        <AtSaleTable projectId={project.id} fields={shown.filter((f) => f.sources.length > 0)} />
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
  // Every file that loads with an ID of its own: the parcel files, then the sales files.
  const idFiles = data.files.filter((f) => (f.holds === "parcels" || f.holds === "sales") && f.id_column);
  const unloaded = data.not_loaded.reduce((n, x) => n + x.columns.length, 0);
  const [showUnloaded, setShowUnloaded] = useState(false);
  return (
    <>
      <p className="wiz-lede">{w.reviewSummary({ fields: loaded.length, columns, files: idFiles.length })}</p>
      {/* One quiet line per file: what's handled in grey, a pill and a button only where something wants a look. */}
      {idFiles.length > 0 && (
        <table className="rv-files">
          <tbody>
            {idFiles.map((f) => (
              <IdCheck key={f.name} projectId={projectId} data={data} file={f} change={change} review />
            ))}
          </tbody>
        </table>
      )}
      {unloaded > 0 && (
        <>
          <Disclose
            open={showUnloaded}
            onPress={() => setShowUnloaded(!showUnloaded)}
            className="rv-unloaded"
          >
            {w.notLoadedAll({ n: unloaded })}
          </Disclose>
          {showUnloaded && (
            <dl className="rv-unloaded-list">
              {data.not_loaded.map((n) => (
                <Fragment key={n.file}>
                  <dt>
                    <FileName filename={n.file} />
                  </dt>
                  <dd className="mono">{n.columns.join(", ")}</dd>
                </Fragment>
              ))}
            </dl>
          )}
        </>
      )}
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
                    <Button className="button button-small" onPress={() => go(s.key)}>
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

/** The 🌐 capsule of a Big five field beside its 💰 one: where it's too narrow for the column, its unit and the
 * values and Map buttons on one line (they ran past its edge), the buttons go under them (cap-narrow); back once the
 * sheet is wider than when they went. Measured, not a container query: the capsule is as wide as what's in it. */
function CapPu({ paired, children }: { paired: boolean; children: React.ReactNode }) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const [narrowAt, setNarrowAt] = useState<number | null>(null);
  useEffect(() => {
    if (!el || !paired) return;
    const sheet = el.closest(".wiz-body") ?? document.body;
    let frame = 0;
    const check = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const w = sheet.clientWidth;
        if (narrowAt === null) {
          // Past the capsule's edge, or over the column's picker beside them.
          const tools = el.querySelector(".wiz-capsule > .wiz-samples");
          const before = tools?.previousElementSibling;
          // The buttons spill out of their cell (narrower than they are): any of them reaching back over the picker.
          const edge = before?.getBoundingClientRect().right ?? Number.NEGATIVE_INFINITY;
          const overlaps =
            !!tools &&
            [...tools.querySelectorAll("button")].some((c) => c.getBoundingClientRect().left < edge - 1);
          if (el.scrollWidth > el.clientWidth + 1 || overlaps) setNarrowAt(w);
        } else if (w > narrowAt + 24) setNarrowAt(null);
      });
    };
    const ro = new ResizeObserver(check);
    ro.observe(sheet);
    ro.observe(el);
    // The buttons arrive after the capsule (its column read): checked again as what's in it changes.
    const mo = new MutationObserver(check);
    mo.observe(el, { childList: true, subtree: true });
    return () => {
      ro.disconnect();
      mo.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [el, paired, narrowAt]);
  return (
    <div
      ref={setEl}
      className={paired ? `frame as-cap as-pu${narrowAt !== null ? " cap-narrow" : ""}` : "as-today"}
    >
      {children}
    </div>
  );
}
