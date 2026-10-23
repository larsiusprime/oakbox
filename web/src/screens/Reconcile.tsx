import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  Heading,
  Input,
  Menu,
  MenuItem,
  MenuTrigger,
  Modal,
  ModalOverlay,
  Popover,
  TextField,
} from "react-aria-components";
import { api, type CleanStep, type ReconcileSample, unwrap, type WizardFile } from "../api/client";
import { Tick } from "../components/Form";
import { t } from "../strings";

const r = t.wizard.reconcile;
type Step = CleanStep;
type View = "unmatched" | "random";

/** The steps added from each menu item: the first few are complete as they are. */
const PRESETS: Record<string, Step> = {
  zeros: { kind: "zeros", text: "", to: "", n: 0 },
  hyphens: { kind: "remove", text: "-", to: "", n: 0 },
  spaces: { kind: "remove", text: " ", to: "", n: 0 },
  other: { kind: "remove", text: "./", to: "", n: 0 },
  trim: { kind: "trim", text: "", to: "", n: 0 },
  replace: { kind: "replace", text: "", to: "", n: 0 },
  first: { kind: "first", text: "", to: "", n: 6 },
  last: { kind: "last", text: "", to: "", n: 6 },
  before: { kind: "before", text: "-", to: "", n: 0 },
  after: { kind: "after", text: "-", to: "", n: 0 },
};

/** "remove leading zeros, then remove hyphens": the steps in a line, for the ID row. */
export function describeSteps(steps: Step[]): string {
  const d = r.describe;
  return steps
    .map((s) =>
      s.kind === "zeros"
        ? d.zeros
        : s.kind === "trim"
          ? d.trim
          : s.kind === "remove"
            ? d.remove(s.text)
            : s.kind === "replace"
              ? d.replace(s.text, s.to)
              : s.kind === "first"
                ? d.first(s.n)
                : s.kind === "last"
                  ? d.last(s.n)
                  : s.kind === "before"
                    ? d.before(s.text)
                    : d.after(s.text),
    )
    .join(", then ");
}

function pct(share: number): string {
  const p = share * 100;
  return p > 99 && p < 100 ? `${p.toFixed(1)}%` : p > 0 && p < 1 ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

/** Waits for typing to stop before asking the server again. */
function useSettled<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return settled;
}

/** F3d: clean up the IDs on both sides of the sales join, live, until they match. */
export function ReconcileDialog({
  projectId,
  file,
  base,
  close,
  save,
}: {
  projectId: string;
  file: WizardFile;
  base: WizardFile;
  close: () => void;
  save: (fileSteps: Step[], baseSteps: Step[]) => void;
}) {
  const field = file.match;
  // What joins to what: the wording follows it.
  const k =
    file.match === "key_sale"
      ? r.kinds.more_sales(file.name)
      : file.holds === "sales"
        ? r.kinds.sales()
        : r.kinds.parcels(file.name);
  const [baseSteps, setBaseSteps] = useState<Step[]>(base.clean[field] ?? []);
  const [fileSteps, setFileSteps] = useState<Step[]>(file.clean[field] ?? []);
  const [same, setSame] = useState(
    baseSteps.length > 0 && JSON.stringify(baseSteps) === JSON.stringify(fileSteps),
  );
  const [view, setView] = useState<View>("random");
  const [seed, setSeed] = useState(0);
  const salesSteps = same ? baseSteps : fileSteps;
  const asked = useSettled({ base_steps: baseSteps, file_steps: salesSteps, view, seed });
  const post = async (body: object) =>
    unwrap(
      await api.POST("/api/projects/{project_id}/wizard/files/{name}/reconcile", {
        params: { path: { project_id: projectId, name: file.name } },
        body: { base_steps: [], file_steps: [], view: "unmatched", seed: 0, suggest: false, ...body },
      }),
    );
  const live = useQuery({
    queryKey: ["reconcile", projectId, file.name, asked],
    queryFn: () => post(asked),
    placeholderData: keepPreviousData,
  });
  // The suggestion is worked out once, from the steps as they were when the dialog opened.
  const [opened] = useState({ base_steps: baseSteps, file_steps: fileSteps });
  const hint = useQuery({
    queryKey: ["reconcile-suggest", projectId, file.name, opened],
    queryFn: () => post({ ...opened, suggest: true }),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const v = live.data;
  // Offered until tried: after that, trying it again would undo the user's own changes.
  const [tried, setTried] = useState(false);
  const suggestion = tried ? null : hint.data?.suggestion;
  const good = v ? v.share >= 0.95 : false;

  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rc">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {k.title}
          </Heading>
          <p className="rc-sub">{k.lede}</p>
          <div className={`rc-meter ${good ? "ok" : "bad"}`} aria-live="polite">
            {v ? (
              <>
                <b>
                  {good && "✓ "}
                  {k.meter(pct(v.share))}
                </b>
                <span className="rc-was">
                  {r.counts(v.matched, v.total)}
                  {Math.abs(v.share - v.saved_share) > 1e-9 && ` · ${r.was(pct(v.saved_share))}`}
                </span>
              </>
            ) : (
              <span className="rc-was">…</span>
            )}
          </div>
          {suggestion && (
            <p className="rc-suggest">
              <b>{r.suggest}</b> {suggestion.text}.{" "}
              <Button
                className="wiz-link"
                onPress={() => {
                  setBaseSteps(suggestion.base_steps);
                  setFileSteps(suggestion.file_steps);
                  setSame(false);
                  setTried(true);
                }}
              >
                {r.tryIt(pct(suggestion.share))}
              </Button>
            </p>
          )}
          <div className="rc-samplebar">
            <span>{r.samples}</span>
            <span className="rc-seg">
              {(["random", "unmatched"] as const).map((x) => (
                <Button key={x} className="rc-seg-btn" aria-pressed={view === x} onPress={() => setView(x)}>
                  {x === "unmatched" ? r.unmatched : r.random}
                </Button>
              ))}
            </span>
            <Button className="button" onPress={() => setSeed((s) => s + 1)}>
              {r.newSamples}
            </Button>
            <span className="wiz-grow" />
            <Tick
              isSelected={same}
              onChange={(on) => {
                setSame(on);
                if (!on) setFileSteps(baseSteps);
              }}
            >
              {r.same}
            </Tick>
          </div>
          <div className="rc-cols">
            <section className="rc-card">
              <h3>{k.target}</h3>
              <CleanSteps steps={baseSteps} onChange={setBaseSteps} />
              {v && <p className="rc-caption">{k.targetShown(v.base_samples.length, v.parcels)}</p>}
              <Samples rows={v?.base_samples ?? []} labels={k} target />
            </section>
            <section className="rc-card">
              <h3>{k.mine}</h3>
              {same ? (
                <p className="rc-same">{r.sameAsParcels}</p>
              ) : (
                <CleanSteps steps={fileSteps} onChange={setFileSteps} />
              )}
              {v && v.file_samples.length > 0 && (
                <p className="rc-caption">
                  {view === "unmatched"
                    ? k.unmatched(v.file_samples.length, v.total - v.matched)
                    : k.mineShown(v.file_samples.length, v.total)}
                </p>
              )}
              <Samples rows={v?.file_samples ?? []} labels={k} target={false} empty={view === "unmatched"} />
            </section>
          </div>
          <details className="rc-writes">
            <summary>{r.writes}</summary>
            <pre>
              {v && Object.keys(v.writes).length > 0
                ? Object.entries(v.writes)
                    .map(([name, calc]) => `"${name}": { "calc": { "${field}": ${JSON.stringify(calc)} } }`)
                    .join("\n")
                : r.nothing}
            </pre>
          </details>
          {live.error && (
            <p className="error" role="alert">
              {live.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {r.cancel}
            </Button>
            <Button className="button button-primary" onPress={() => save(salesSteps, baseSteps)}>
              {r.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function CleanSteps({ steps, onChange }: { steps: Step[]; onChange: (s: Step[]) => void }) {
  const set = (i: number, patch: Partial<Step>) =>
    onChange(steps.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  return (
    <>
      <ol className="rc-steps">
        {steps.length === 0 && <li className="rc-none">{r.none}</li>}
        {steps.map((s, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: steps have no id; their place is what they are
          <li key={i}>
            <span className="rc-n">{i + 1}</span>
            <span className="rc-grow">
              <StepText step={s} set={(patch) => set(i, patch)} />
            </span>
            <Button
              className="rc-x"
              aria-label={r.remove}
              onPress={() => onChange(steps.filter((_, j) => j !== i))}
            >
              <X size="0.9em" />
            </Button>
          </li>
        ))}
      </ol>
      <MenuTrigger>
        <Button className="button rc-add">{r.add}</Button>
        <Popover className="popover rc-menu" placement="bottom start">
          <Menu
            className="choice-list"
            onAction={(key) => onChange([...steps, { ...PRESETS[String(key)] } as Step])}
          >
            {Object.entries(r.menu).map(([key, [label, example]]) => (
              <MenuItem key={key} id={key} className="choice-item rc-menu-item" textValue={label}>
                {label}
                <small>{example}</small>
              </MenuItem>
            ))}
          </Menu>
        </Popover>
      </MenuTrigger>
    </>
  );
}

function Mini({
  label,
  value,
  onChange,
  width = "3.2rem",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  width?: string;
}) {
  return (
    <TextField aria-label={label} value={value} onChange={onChange} className="rc-mini">
      <Input className="input rc-input" style={{ width }} />
    </TextField>
  );
}

function StepText({ step, set }: { step: Step; set: (patch: Partial<Step>) => void }) {
  const s = r.step;
  switch (step.kind) {
    case "zeros":
      return <>{s.zeros}</>;
    case "trim":
      return <>{s.trim}</>;
    case "remove":
      return (
        <>
          {s.remove} <Mini label={s.remove} value={step.text} onChange={(text) => set({ text })} />
        </>
      );
    case "replace":
      return (
        <>
          {s.replace} <Mini label={s.replace} value={step.text} onChange={(text) => set({ text })} /> {s.with}{" "}
          <Mini label={s.with} value={step.to} onChange={(to) => set({ to })} />
        </>
      );
    case "first":
    case "last":
      return (
        <>
          {step.kind === "first" ? s.first : s.last}{" "}
          <Mini
            label={step.kind === "first" ? s.first : s.last}
            value={String(step.n)}
            onChange={(x) => set({ n: Math.max(0, Number.parseInt(x, 10) || 0) })}
            width="2.6rem"
          />{" "}
          {s.chars}
        </>
      );
    default:
      return (
        <>
          {step.kind === "before" ? s.before : s.after}{" "}
          <Mini label={s.before} value={step.text} onChange={(text) => set({ text })} width="2.2rem" />
        </>
      );
  }
}

type Labels = ReturnType<typeof r.kinds.sales>;

function Samples({
  rows,
  labels,
  target,
  empty,
}: {
  rows: ReconcileSample[];
  labels: Labels;
  target: boolean;
  empty?: boolean;
}) {
  const parcels = target; // the target side: whether the other file has it, never a failure
  if (rows.length === 0 && empty) return <p className="rc-same">{r.noUnmatched}</p>;
  return (
    <table className="rc-tbl">
      <thead>
        <tr>
          <th className="rc-th">{r.asIs}</th>
          <th className="rc-th" />
          <th className="rc-th">{r.cleanedCol}</th>
          <th className="rc-th">{target ? labels.targetCol : labels.mineCol}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.raw}>
            <td className="rc-td">{s.raw.trim() ? show(s.raw) : r.blank}</td>
            <td className="rc-td rc-arrow">→</td>
            <td className={s.clean === s.raw ? "rc-td rc-dim" : "rc-td"}>
              {s.clean === s.raw ? r.same_ : show(s.clean)}
            </td>
            <td className="rc-td rc-m">
              {parcels ? (
                s.hit ? (
                  <span className="rc-hit">✓ {labels.targetHit}</span>
                ) : (
                  <span className="rc-dim">{labels.targetMiss}</span>
                )
              ) : s.hit ? (
                <span className="rc-hit">✓ {r.matches}</span>
              ) : (
                <span className="rc-miss">✗ {r.noMatch}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Spaces made visible: a trailing space is exactly what's wrong with some IDs. */
function show(v: string): string {
  return v.replace(/ /g, "␣");
}
