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
import { Tip, TipOn } from "../components/Tip";
import { t } from "../strings";
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

/** A step with parts opens at its first. */
function firstPart(steps: WizardStep[], key: string): string {
  return steps.find((s) => s.parent === key)?.key ?? key;
}

function WizardView({ project, data, step }: { project: Project; data: Wizard; step: string | null }) {
  const projectId = project.id;
  const flat = order(data.steps);
  // Opens at the first step not done yet, or at Review (SPEC F3d).
  const [opening] = useState(() => flat.find((s) => s.status !== "done")?.key ?? "review");
  const wanted = step ? firstPart(data.steps, step) : step;
  const current = flat.find((s) => s.key === wanted) ?? flat.find((s) => s.key === opening) ?? flat[0];
  const change = useChange(projectId);
  const [unfinished, setUnfinished] = useState(false);
  const go = (key: string) => navigate({ name: "project", id: projectId, tab: "fields", step: key });

  // Showing a step fills in its guesses, once (the server keeps track).
  const key = current?.key;
  const visit = change.mutate;
  useEffect(() => {
    if (key) visit({ kind: "visit", step: key });
  }, [key, visit]);

  if (!current) return null;
  const index = flat.indexOf(current);
  const prev = flat[index - 1];
  const next = flat[index + 1];
  const tops = data.steps.filter((s) => !s.parent);
  const top = current.parent ?? current.key;
  const copy = w.steps[current.key] ?? { title: current.key, question: "", lede: "" };
  const kicker = [
    w.stepOf(tops.findIndex((s) => s.key === top) + 1, tops.length),
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
      <StepList steps={data.steps} current={current.key} go={go} />
      <div className="wiz-main">
        <div className="wiz-body">
          <p className="wiz-kicker">{kicker}</p>
          <h2 className="wiz-q">{copy.question}</h2>
          {copy.lede && <p className="wiz-lede">{copy.lede}</p>}
          {current.key === "welcome" && <WelcomeStep />}
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
            {w.left(
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
            {current.key === "welcome" ? w.start : next ? t.step.next : w.toBringIn}
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

// A step's mark (SPEC F3d): ✅ complete, ⚠ to decide, ❌ blocks a run; blank shows its number.
const STATUS_ICONS: Record<string, string | null> = {
  done: resolvedIcon,
  attention: warningIcon,
  blocked: blockingIcon,
  blank: null,
};

function StepList({ steps, current, go }: { steps: WizardStep[]; current: string; go: (k: string) => void }) {
  const tops = steps.filter((s) => !s.parent);
  return (
    <ol className="wiz-steps">
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
              onClick={() => go(firstPart(steps, s.key))}
              aria-current={s.key === current ? "step" : undefined}
            >
              <span className="n" aria-hidden="true">
                {icon ? <img src={icon} alt="" className="wiz-step-icon" /> : s.parent ? "" : String(n)}
              </span>
              {w.steps[s.key]?.title ?? s.key}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function WelcomeStep() {
  return (
    <div className="wiz-welcome">
      {w.welcome.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
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
      <div className="wiz-grid">
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
          <AddButton onPress={() => setAdding(true)}>
            {w.addId(w.idOrdinal[EXTRA_IDS[base.extra_ids.length] ?? "key2"] ?? "")}
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
      <hr className="wiz-rule" />
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
      (f.holds === "parcels" || f.holds === "sales" || f.holds === null || chosen.includes(f.name)),
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
        <AddButton onPress={() => setAdding(true)}>
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
  const holds = file.holds === "parcels" || file.holds === "sales" ? file.holds : null;
  // More sales details join on the sale ID, so the main sales file needs one in a column.
  const salesOk = main !== undefined && main.id_column !== null && !data.sale_id.made;
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
        value={holds}
        onChange={(v) =>
          change(
            v === "sales"
              ? { kind: "file", name: file.name, holds: "sales", match: "key_sale" }
              : { kind: "file", name: file.name, holds: "parcels" },
          )
        }
      >
        <Label className="field-label">{m.what}</Label>
        <Radio value="parcels" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {m.parcels}
        </Radio>
        <Radio value="sales" className="radio" isDisabled={!salesOk && holds !== "sales"}>
          <span className="radio-dot" aria-hidden="true" />
          {m.sales}
          {!salesOk && <small className="wiz-from"> {m.salesNeedsId}</small>}
        </Radio>
      </RadioGroup>
      {holds && <IdRow projectId={project.id} data={data} file={file} base={base} change={change} />}
      {holds === "parcels" && <UnitsPointer projectId={project.id} file={file} />}
    </section>
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
      <div className="wiz-grid">
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
          {more ? w.fewer : w.more(hidden)}
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
        {w.summary(loaded.length, columns)}{" "}
        {data.not_loaded.map((n) => w.notLoaded(n.file, n.columns)).join(" ")}
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
                      : f.sources.map((x) => w.from(x.column, x.file)).join("; ") || w.nothing}
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
