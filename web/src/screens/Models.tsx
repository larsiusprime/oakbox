import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import type { EngineState, ModelEntry, ModelSetup } from "../api/client";
import { downloadEnded, mb, useEngineAction, useOptionalEngines } from "../api/engines";
import { useSetGroupModels, useSetSkip } from "../api/models";
import { setupKey } from "../api/steps";
import { AddButton } from "../components/AddButton";
import { SmallButton } from "../components/Buttons";
import { EngineProgress, InstallEngineDialog } from "../components/Engines";
import { Choice } from "../components/Form";
import { RemoveButton } from "../components/RemoveButton";
import { Seg } from "../components/Seg";
import { useAtOnce } from "../lib/hooks";
import { t } from "../wording";
import { ConfigSummary, ModelOptions } from "./ModelOptions";

const m = t.values.model;
const w = t.engines;

/** A model as it's saved. */
const entryOf = (e: ModelEntry): ModelEntry => ({
  key: e.key,
  name: e.name,
  engine: e.engine,
  list_id: e.list_id ?? null,
  locations: e.locations ?? null,
  log: e.log ?? null,
  intercept: e.intercept ?? null,
  interactions: e.interactions ?? null,
  optimize_vars: e.optimize_vars ?? null,
  n_trials: e.n_trials ?? null,
  use_gpu: e.use_gpu ?? null,
});

/** Model values › Models: a tab per modeled group (the others greyed, not modeled), its models in a table: each a
 * name, an engine, its variable list and (Multi-MRA, Local area) its location stack, opened in place one at a time;
 * Add a model; back to the default ones. */
export function GroupModelsCard({ projectId, v, gid }: { projectId: string; v: ModelSetup; gid: string }) {
  const put = useSetGroupModels(projectId);
  const skip = useSetSkip(projectId);
  const [stack, setStack] = useState<string | null>(null);
  const [adding, setAdding] = useState<ModelEntry | null>(null);
  // XGBoost and CatBoost may not be installed (oakbox/engines.py): choosing one asks; a model added with it waits
  // for the download.
  const optional = useOptionalEngines();
  const engineAction = useEngineAction();
  const [ask, setAsk] = useState<{ engine: EngineState; back: string | null } | null>(null);
  const [waiting, setWaiting] = useState<ModelEntry | null>(null);
  const modeled = v.groups.filter((g) => g.modeled);
  const at = Math.max(
    0,
    modeled.findIndex((x) => x.id === gid),
  );
  const g = modeled[at];
  const queryClient = useQueryClient();
  /** Add the model once its engine is downloaded (to the group's models as they are then); if it isn't, back to
   * the adding row, which says why. */
  const addWhenInstalled = async (entry: ModelEntry, group: string) => {
    setWaiting(entry);
    setAdding(null);
    const end = await downloadEnded(queryClient, entry.engine);
    setWaiting(null);
    if (!end?.installed) return setAdding(entry);
    const now = queryClient.getQueryData<ModelSetup>(setupKey("model", projectId));
    const models = now?.groups.find((x) => x.id === group)?.models ?? [];
    put.mutate({ group, models: [...models.map(entryOf), { ...entry, key: "" }] });
    engineAction.mutate({ key: entry.engine, action: "seen" });
  };
  if (!g) return <p className="wiz-from">{t.groups.notModeled}</p>;
  const addingEngine = adding ? optional.get(adding.engine) : undefined;
  const waitingEngine = waiting ? optional.get(waiting.engine) : undefined;
  const engines = Object.fromEntries(v.engines.map((e) => [e.key, e]));
  const lists = Object.fromEntries(v.lists.map((x) => [x.id, x]));
  const entries: ModelEntry[] = g.models.map(entryOf);
  const places = Object.fromEntries(v.locations.map((x) => [x.field, x.name]));
  const save = (models: ModelEntry[] | null, group = g.id) => put.mutate({ group, models });
  const change = (i: number, patch: Partial<ModelEntry>) =>
    save(entries.map((e, j) => (j === i ? { ...e, ...patch } : e)));
  const firstList = (engine: string) => {
    const kind = engines[engine]?.kind;
    // As the backend proposes: the first of its type for this group; none, rather than another group's.
    return v.lists.find((x) => x.kind === kind && x.groups.includes(g.id))?.id;
  };
  const listOptions = v.lists.map((x) => [x.id, m.list({ name: x.name, n: x.count })] as const);
  const engineOptions = v.engines.map((x) => [x.key, x.name] as const);
  const aside = Object.fromEntries(
    optional.all
      .filter((e) => !e.installed)
      .map((e) => [e.key, e.can_install ? w.notInstalled({ mb: mb(e.download) }) : w.notInstalledShort]),
  );
  return (
    <div className="cs-step">
      <div className="gm-head">
        <span className="gm-of">{m.groupOf({ n: at + 1, of: modeled.length })}</span>
        <h3 className="gm-title">
          <span className="mg-sw ab-sw big" style={{ background: g.color }} />
          {g.name}
        </h3>
        <span className="wiz-from">{m.salesTab({ n: g.sales })}</span>
      </div>
      {/* Model it, or not: a group not modeled is left unvalued (Model groups unchanged). */}
      <div className="gm-skip">
        <Seg
          label={m.modelThis}
          value={g.skipped ? "skip" : "model"}
          options={[
            ["model", m.modelIt],
            ["skip", m.skipIt],
          ]}
          onChange={(x) => skip.mutate({ group: g.id, skip: x === "skip" })}
        />
      </div>
      {g.skipped ? (
        <p className="wiz-from">{m.skippedNote}</p>
      ) : (
        <>
          {g.sales < 15 && <p className="wiz-warn">{m.tooFew}</p>}
          <InstallEngineDialog
            engine={ask?.engine ?? null}
            onClose={() => {
              // Not now: the row goes back to the engine it had.
              if (ask?.back && adding)
                setAdding({ ...adding, engine: ask.back, list_id: firstList(ask.back) ?? null });
              setAsk(null);
            }}
            onInstall={() => {
              if (ask?.back !== null && adding) void addWhenInstalled(adding, g.id);
              setAsk(null);
            }}
          />
          {entries.length === 0 && !adding && !waiting ? (
            <p className="wiz-warn">{m.noModels}</p>
          ) : (
            <table className="tbl gm-models">
              <thead>
                <tr>
                  <th>{m.model}</th>
                  <th>{m.engine}</th>
                  <th>{m.variables}</th>
                  <th>{m.configuration}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {g.models.map((e, i) => {
                  const eng = engines[e.engine];
                  const open = stack === e.key;
                  const options = eng?.options ?? [];
                  const entry = entries[i] ?? e;
                  const need = optional.missing(e.engine);
                  return [
                    <tr key={e.key}>
                      <td>
                        <NameCell
                          value={e.name}
                          label={m.nameLabel}
                          onCommit={(name) => change(i, { name })}
                        />
                      </td>
                      <td>
                        {eng?.name ?? e.engine}
                        {need && (
                          <>
                            {" "}
                            {need.install?.status === "running" ? (
                              <EngineProgress engine={need} />
                            ) : (
                              <>
                                <span className="choice-aside">{w.notInstalledShort}</span>{" "}
                                <SmallButton onPress={() => setAsk({ engine: need, back: null })}>
                                  {w.installAsk}
                                </SmallButton>
                              </>
                            )}
                          </>
                        )}
                      </td>
                      <td>
                        {eng?.takes_list ? (
                          <Choice
                            label={`${m.variables}: ${e.name}`}
                            hideLabel
                            value={e.list_id ?? null}
                            options={listOptions}
                            placeholder={m.chooseList}
                            onChange={(list_id) => change(i, { list_id })}
                          />
                        ) : (
                          <span className="wiz-from">{m.takesNoList}</span>
                        )}
                        {e.warnings
                          .filter((w) => w.code !== "no_locations")
                          .map((w) => (
                            <p key={w.code} className="wiz-warn gm-warn">
                              {w.code === "kind_mismatch"
                                ? m.warn.kind_mismatch({
                                    engine: eng?.name ?? e.engine,
                                    kind: lists[e.list_id ?? ""]?.kind ?? "",
                                  })
                                : w.code === "blanks_left_out"
                                  ? m.warn.blanks_left_out({ n: w.n })
                                  : m.warn[w.code as "list_missing" | "list_empty" | "no_list"]}
                            </p>
                          ))}
                      </td>
                      <td>
                        {options.length ? (
                          <>
                            <ConfigSummary e={e} options={options} defaults={v.defaults} places={places} />{" "}
                            <Button
                              className="button button-small"
                              onPress={() => setStack(open ? null : e.key)}
                            >
                              {open ? m.done : m.change}
                            </Button>
                          </>
                        ) : (
                          <span className="wiz-from">{m.noSettings}</span>
                        )}
                        {e.warnings
                          .filter((w) => w.code === "no_locations")
                          .map((w) => (
                            <p key={w.code} className="wiz-warn gm-warn">
                              {m.warn.no_locations({ engine: e.engine })}
                            </p>
                          ))}
                      </td>
                      <td>
                        <RemoveButton
                          what={e.engine}
                          onPress={() => save(entries.filter((_, j) => j !== i))}
                          undo={() => save(entries)}
                        />
                      </td>
                    </tr>,
                    open && (
                      <tr key={`${e.key}-config`} className="gm-detail">
                        <td colSpan={5}>
                          <ModelOptions
                            projectId={projectId}
                            group={g.id}
                            e={entry}
                            name={e.name}
                            options={options}
                            defaults={v.defaults}
                            offered={v.locations}
                            change={(patch) => change(i, patch)}
                          />
                        </td>
                      </tr>
                    ),
                  ];
                })}
                {adding && (
                  <tr className="gm-adding">
                    <td>
                      <TextField
                        aria-label={m.nameLabel}
                        value={adding.name ?? ""}
                        onChange={(name) => setAdding({ ...adding, name })}
                      >
                        <Input
                          className="input"
                          placeholder={engines[adding.engine]?.name ?? m.namePlaceholder}
                        />
                      </TextField>
                    </td>
                    <td>
                      <Choice
                        label={m.engine}
                        hideLabel
                        value={adding.engine}
                        options={engineOptions}
                        aside={aside}
                        onChange={(engine) => {
                          setAdding({ ...adding, engine, list_id: firstList(engine) ?? null });
                          const need = optional.missing(engine);
                          if (need) setAsk({ engine: need, back: adding.engine });
                        }}
                      />
                    </td>
                    <td>
                      {engines[adding.engine]?.takes_list ? (
                        <Choice
                          label={m.variables}
                          hideLabel
                          value={adding.list_id ?? null}
                          options={listOptions}
                          placeholder={m.chooseList}
                          onChange={(list_id) => setAdding({ ...adding, list_id })}
                        />
                      ) : (
                        <span className="wiz-from">{m.takesNoList}</span>
                      )}
                      <p className="wiz-from gm-warn">{engines[adding.engine]?.note}</p>
                      {addingEngine && <EngineProgress engine={addingEngine} />}
                    </td>
                    <td className="wiz-from">{m.configLater}</td>
                    <td>
                      <div className="gm-addtools">
                        <Button
                          className="button button-primary"
                          onPress={() => {
                            const need = optional.missing(adding.engine);
                            if (need) {
                              setAsk({ engine: need, back: adding.engine });
                              return;
                            }
                            save([...entries, { ...adding, key: "" }]);
                            setAdding(null);
                          }}
                        >
                          {m.addIt}
                        </Button>
                        <Button className="button button-small" onPress={() => setAdding(null)}>
                          {m.cancel}
                        </Button>
                      </div>
                    </td>
                  </tr>
                )}
                {waiting && waitingEngine && (
                  <tr className="gm-adding">
                    <td>{waiting.name || waitingEngine.name}</td>
                    <td>{waitingEngine.name}</td>
                    <td colSpan={3}>
                      <EngineProgress engine={waitingEngine} />
                      <p className="wiz-from gm-warn">{w.addedWhenIn}</p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
          <p className="cs-row add-row">
            {!adding && !waiting && (
              <AddButton
                onPress={() =>
                  setAdding({
                    key: "",
                    name: "",
                    engine: "lightgbm",
                    list_id: firstList("lightgbm") ?? null,
                    locations: null,
                  })
                }
              >
                {m.add}
              </AddButton>
            )}
            {g.custom && (
              <Button className="button button-small" onPress={() => save(null)}>
                {m.backToDefault}
              </Button>
            )}
          </p>
          {put.error && (
            <p className="error" role="alert">
              {put.error.message}
            </p>
          )}
        </>
      )}
      {skip.error && (
        <p className="error" role="alert">
          {skip.error.message}
        </p>
      )}
    </div>
  );
}

function NameCell({
  value,
  label,
  onCommit,
}: {
  value: string;
  label: string;
  onCommit: (v: string) => void;
}) {
  const [text, setText] = useState<string | null>(null);
  // What was saved stays shown while it saves, not the old value (AGENTS.md).
  const [held, hold] = useAtOnce(value);
  const save = () => {
    const next = text?.trim();
    if (next && next !== held) {
      hold(next);
      onCommit(next);
    }
    setText(null);
  };
  return (
    <TextField aria-label={label} value={text ?? held} onChange={setText} onBlur={save} className="gm-name">
      <Input
        className="input"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}
