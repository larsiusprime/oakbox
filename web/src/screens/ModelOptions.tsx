/** Model values › Models › Configuration (SPEC F9): a model's own settings, as OpenAVMKit reads them from its entry.
 * A one-line summary in its row (what differs from the default in bold), and the settings themselves in a panel
 * opened under the row: log price, intercept, interactions, trimming per area, tuning trials, the graphics card, and
 * the location stack. */

import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { EntryView, ModelEntry, ModelSetup } from "../api/client";
import { Tick } from "../components/Form";
import { LocationStack } from "../components/LocationStack";
import { Seg } from "../components/Seg";
import { t } from "../copy";

const c = t.values.model.config;
type Option = "log" | "intercept" | "interactions" | "optimize_vars" | "n_trials" | "use_gpu";
type Defaults = ModelSetup["defaults"];

/** An option's value, or its default. */
function value(e: ModelEntry, o: Option, defaults: Defaults) {
  return e[o] ?? defaults[o];
}

/** The row's summary: each setting the engine has, in a few words; what differs from the default in bold. */
export function ConfigSummary({
  e,
  options,
  defaults,
  places,
}: {
  e: EntryView;
  options: string[];
  defaults: Defaults;
  places: Record<string, string>;
}) {
  const parts: [string, string, boolean][] = [];
  const changed = (o: Option) => e[o] != null && e[o] !== defaults[o];
  for (const o of options) {
    if (o === "locations") {
      const names = [...(e.locations ?? [])].reverse().map((f) => places[f] ?? f);
      parts.push([
        o,
        names.length ? c.summary.locations({ names: names.join(" › ") }) : c.summary.noLocations,
        !names.length,
      ]);
    } else if (o === "log") {
      parts.push([o, value(e, o, defaults) ? c.summary.log : c.summary.noLog, changed(o)]);
    } else if (o === "intercept") {
      parts.push([o, value(e, o, defaults) ? c.summary.intercept : c.summary.noIntercept, changed(o)]);
    } else if (o === "interactions") {
      const on = value(e, o, defaults) === "default";
      parts.push([o, on ? c.summary.interactionsDefault : c.summary.interactionsNone, changed(o)]);
    } else if (o === "optimize_vars") {
      if (value(e, o, defaults)) parts.push([o, c.summary.optimizeVars, true]);
    } else if (o === "n_trials") {
      parts.push([o, c.summary.trials({ n: Number(value(e, o, defaults)) }), changed(o)]);
    } else if (o === "use_gpu") {
      if (!value(e, o, defaults)) parts.push([o, c.summary.noGpu, true]);
    }
  }
  return (
    <span className="mo-summary">
      {parts.map(([k, text, bold], i) => (
        <span key={k}>
          {i > 0 && " · "}
          {bold ? <b>{text}</b> : text}
        </span>
      ))}
    </span>
  );
}

function Trials({ value: v, onCommit }: { value: number; onCommit: (n: number) => void }) {
  const [text, setText] = useState<string | null>(null);
  const save = () => {
    const n = Number.parseInt(text ?? "", 10);
    if (text !== null && Number.isFinite(n) && n !== v) onCommit(Math.min(500, Math.max(1, n)));
    setText(null);
  };
  return (
    <TextField
      aria-label={c.trials}
      value={text ?? String(v)}
      onChange={setText}
      onBlur={save}
      className="mo-trials"
    >
      <Input
        className="input"
        inputMode="numeric"
        onKeyDown={(k) => {
          if (k.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

/** The panel under a model's row: each of its engine's settings, with what it does, and what to watch for. */
export function ModelOptions({
  projectId,
  group,
  e,
  name,
  options,
  defaults,
  offered,
  change,
}: {
  projectId: string;
  group: string;
  e: ModelEntry;
  name: string;
  options: string[];
  defaults: Defaults;
  offered: ModelSetup["locations"];
  change: (patch: Partial<ModelEntry>) => void;
}) {
  const has = (o: string) => options.includes(o);
  const warn: string[] = [];
  if (has("log") && !value(e, "log", defaults)) warn.push(c.warnLog);
  if (has("intercept") && !value(e, "intercept", defaults)) warn.push(c.warnIntercept);
  if (has("n_trials") && Number(value(e, "n_trials", defaults)) < 20) warn.push(c.warnTrials);
  const tick = (o: "log" | "intercept" | "optimize_vars" | "use_gpu", label: string, why: string) =>
    has(o) && (
      <div className="mo-option">
        <Tick isSelected={Boolean(value(e, o, defaults))} onChange={(on) => change({ [o]: on })}>
          {label}
        </Tick>
        <span className="wiz-from">{why}</span>
      </div>
    );
  return (
    <div className="mo-panel">
      <p className="ls-title">{c.title({ name })}</p>
      {tick("log", c.log, c.logWhy)}
      {tick("intercept", c.intercept, c.interceptWhy)}
      {has("interactions") && (
        <div className="mo-option">
          <span className="mo-label">{c.interactions}</span>
          <Seg
            label={c.interactions}
            value={value(e, "interactions", defaults) === "default" ? "default" : "none"}
            options={[
              ["none", c.interactionsNone],
              ["default", c.interactionsDefault],
            ]}
            onChange={(interactions) => change({ interactions })}
          />
          <span className="wiz-from">{c.interactionsWhy}</span>
        </div>
      )}
      {tick("optimize_vars", c.optimizeVars, c.optimizeVarsWhy)}
      {has("n_trials") && (
        <div className="mo-option">
          <span className="mo-label">{c.trials}</span>
          <Trials
            value={Number(value(e, "n_trials", defaults))}
            onCommit={(n_trials) => change({ n_trials })}
          />
          <span className="wiz-from">{c.trialsWhy}</span>
        </div>
      )}
      {tick("use_gpu", c.gpu, c.gpuWhy)}
      {warn.map((w) => (
        <p key={w} className="wiz-warn gm-warn">
          {w}
        </p>
      ))}
      {has("locations") && (
        <LocationStack
          projectId={projectId}
          group={group}
          engine={e.engine}
          finestFirst={e.locations ?? []}
          offered={offered}
          onChange={(locations) => change({ locations })}
        />
      )}
    </div>
  );
}
