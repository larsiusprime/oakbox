import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";
import {
  api,
  type ModelFigures,
  type ModelGroupResult,
  type ModelPatch,
  type ModelSetup,
  type ModelView,
  unwrap,
} from "../api/client";
import { Tick } from "../components/Form";
import { InfoTip } from "../components/Tip";
import { t } from "../strings";
import { num } from "./CheckSales";
import { Score, signed } from "./CheckValues";

const m = t.values.model;
const card = t.ratio.card;

/** Step 5's models (SPEC F9): the run's state, polled while it runs. */
export function useModel(projectId: string) {
  return useQuery({
    queryKey: ["model", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/model", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 800 : false),
  });
}

/** The variables there are and the models offered; a change saves at once and puts the try out of date. */
export function useModelSetup(projectId: string, enabled: boolean) {
  const queryClient = useQueryClient();
  const setup = useQuery({
    queryKey: ["model-setup", projectId],
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/model/setup", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  const change = useMutation({
    mutationFn: async (body: ModelPatch) =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}/model/setup", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["model-setup", projectId], data);
      void queryClient.invalidateQueries({ queryKey: ["model", projectId] });
    },
  });
  return { setup, change };
}

type CardProps = { v: ModelSetup; set: (body: ModelPatch) => void };

/** One table of the variables, grouped by kind: ticked, how many parcels have it, blanks left, and which models
 * use it. Each kind is a heading that folds its rows away, with one tick for all of them. */
export function VariablesCard({ v, set, fill }: CardProps & { fill: () => void }) {
  const [shut, setShut] = useState<Set<string>>(() => new Set());
  if (!v.variables.length) return <p className="wiz-from">{m.none}</p>;
  const chosen = v.variables.filter((x) => x.chosen).map((x) => x.field);
  const total = Math.max(...v.variables.map((x) => x.parcels + x.blanks));
  const kinds = [...new Set(v.variables.map((x) => x.kind))];
  return (
    <div className="cs-step">
      {v.missing.length > 0 && <p className="wiz-warn">{m.missing(v.missing)}</p>}
      <ColumnsNote v={v} />
      <table className="bi-tbl cs-tbl md-vars">
        <thead>
          <tr>
            <th>{m.variable}</th>
            <th className="cs-n">{m.has}</th>
            <th className="cs-n">{m.blanks}</th>
            <th>
              <InfoTip label={m.usedBy} text={m.usedByWhy} />
            </th>
          </tr>
        </thead>
        {kinds.map((k) => (
          <tbody key={k}>
            <KindRow
              name={m.kinds[k] ?? k}
              fields={v.variables.filter((x) => x.kind === k).map((x) => x.field)}
              chosen={chosen}
              open={!shut.has(k)}
              toggle={() =>
                setShut((was) => {
                  const now = new Set(was);
                  if (now.has(k)) now.delete(k);
                  else now.add(k);
                  return now;
                })
              }
              set={set}
            />
            {v.variables
              .filter((x) => x.kind === k && !shut.has(k))
              .map((x) => (
                <tr key={x.field}>
                  <td>
                    <Tick
                      isSelected={x.chosen}
                      onChange={(on) =>
                        set({ variables: on ? [...chosen, x.field] : chosen.filter((f) => f !== x.field) })
                      }
                    >
                      {x.name} <span className="mono wiz-from">{x.field}</span>
                      {x.values != null && <span className="wiz-from"> · {m.valuesCount(x.values)}</span>}
                    </Tick>
                  </td>
                  <td className="cs-n">{`${Math.round((100 * x.parcels) / Math.max(total, 1))}%`}</td>
                  <td className="cs-n">{x.blanks ? num(x.blanks) : "—"}</td>
                  <td>
                    {x.trees_only ? (
                      <>
                        {m.treesOnly}
                        {x.numeric && (
                          <>
                            {" "}
                            <Button className="wiz-link" onPress={fill}>
                              {m.fillIt}
                            </Button>
                          </>
                        )}
                      </>
                    ) : (
                      m.allModels
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        ))}
      </table>
      {chosen.length < v.variables.length && (
        <p>
          <Button className="wiz-link" onPress={() => set({ every_variable: true })}>
            {m.everyVariable}
          </Button>
        </p>
      )}
    </div>
  );
}

/** A kind's heading: one tick for all its variables, its name (folding its rows away) and how many are ticked. */
function KindRow({
  name,
  fields,
  chosen,
  open,
  toggle,
  set,
}: {
  name: string;
  fields: string[];
  chosen: string[];
  open: boolean;
  toggle: () => void;
  set: (body: ModelPatch) => void;
}) {
  const on = fields.filter((f) => chosen.includes(f)).length;
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <tr className="md-kind">
      <td colSpan={4}>
        <span className="md-kind-row">
          <Tick
            isSelected={on === fields.length}
            onChange={(all) =>
              set({
                variables: all
                  ? [...new Set([...chosen, ...fields])]
                  : chosen.filter((f) => !fields.includes(f)),
              })
            }
          >
            <span className="visually-hidden">{name}</span>
          </Tick>
          <Button className="md-kind-name" aria-expanded={open} onPress={toggle}>
            <Chevron aria-hidden="true" size="1em" />
            {name}
            <span className="md-kind-count">{m.kindCount(on, fields.length)}</span>
          </Button>
        </span>
      </td>
    </tr>
  );
}

/** The models offered, each in a line; Choose for me; and what each model group has to learn from. */
/** How many columns the ticked variables become to the models: a number is one, a category one per value (one-hot).
 * Many category columns slow every model and give linear ones a coefficient each to fit. */
export function ColumnsNote({ v }: { v: ModelSetup }) {
  const ticked = v.variables.filter((x) => x.chosen);
  const cats = ticked.filter((x) => x.values != null);
  const dummies = cats.reduce((n, x) => n + (x.values ?? 0), 0);
  const columns = ticked.length - cats.length + dummies;
  const many = dummies > 40;
  const biggest = [...cats].sort((a, b) => (b.values ?? 0) - (a.values ?? 0)).slice(0, 3);
  return (
    <p className={many ? "wiz-warn" : "wiz-from"}>
      {m.columns(ticked.length, columns, cats.length, dummies)}
      {many && ` ${m.manyColumns(biggest.map((x) => `${x.name} (${x.values})`).join(", "))}`}
    </p>
  );
}

export function ModelsCard({ v, set }: CardProps) {
  const chosen = v.engines.filter((e) => e.chosen).map((e) => e.key);
  return (
    <div className="cs-step">
      <ColumnsNote v={v} />
      <div className="md-engines">
        {v.engines.map((e) => (
          <div key={e.key} className="md-engine">
            <Tick
              isSelected={e.chosen}
              isDisabled={e.chosen && chosen.length === 1}
              onChange={(on) => set({ models: on ? [...chosen, e.key] : chosen.filter((x) => x !== e.key) })}
            >
              <b>{e.name}</b>
            </Tick>
            <span className="wiz-from">{e.note}</span>
          </div>
        ))}
      </div>
      <p>
        {v.choose_for_me ? (
          <span className="wiz-ok">✓ {m.chosenForYou}</span>
        ) : (
          <Button className="wiz-link" onPress={() => set({ choose_for_me: true })}>
            {m.chooseForMe}
          </Button>
        )}{" "}
        <span className="wiz-from">{m.chooseForMeNote}</span>
      </p>
      {v.groups.length > 0 && (
        <>
          <h3 className="wiz-group">{m.groupsTitle}</h3>
          <table className="bi-tbl cs-tbl">
            <thead>
              <tr>
                <th>{m.group}</th>
                <th className="cs-n">{m.parcels}</th>
                <th className="cs-n">{m.sales}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {v.groups.map((g) => (
                <tr key={g.id}>
                  <td>
                    <span className="mg-sw ab-sw" style={{ background: g.color }} />
                    {g.name}
                  </td>
                  <td className="cs-n">{num(g.parcels)}</td>
                  <td className="cs-n">{num(g.sales)}</td>
                  <td className="wiz-warn">{g.sales < 15 ? m.tooFew : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

/** Each model group: its models on the holdout, the ensemble first, the roll's value above them on the same sales. */
export function HowTheyDid({ view }: { view: ModelView }) {
  const r = view.receipt;
  if (!r) return null;
  return (
    <div className="cs-receipt">
      {view.stale && <p className="wiz-warn">{m.stale}</p>}
      <table className="bi-tbl cs-tbl rv-score md-how">
        <thead>
          <tr>
            <th>{m.model}</th>
            <th className="cs-n">
              <InfoTip label={m.judgedOn} text={m.judgedOnWhy} />
            </th>
            <th>
              <InfoTip label={card.level} text={card.levelWhy} />
            </th>
            <th>
              <InfoTip label={card.uniform} text={card.uniformWhy} />
            </th>
            <th>
              <InfoTip label={card.vertical} text={t.ratio.table.prbWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={m.codTrimmed} text={m.codTrimmedWhy} />
            </th>
          </tr>
        </thead>
        {r.groups.map((g) => (
          <Group key={g.id} g={g} />
        ))}
      </table>
      <p className="wiz-from">{m.nextSlice}</p>
      {r.notes.length > 0 && (
        <details className="cs-step">
          <summary>{m.notesTitle}</summary>
          <ul className="cs-list-plain">
            {r.notes.map((n) => (
              <li key={n} className="wiz-from">
                {n}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Group({ g }: { g: ModelGroupResult }) {
  return (
    <tbody>
      <tr className="bi-grp">
        <td colSpan={6}>
          <span className="mg-sw ab-sw" style={{ background: g.color }} />
          {g.name} <span className="wiz-from">· {m.salesCount(g.sales)}</span>
        </td>
      </tr>
      {g.skipped ? (
        <tr>
          <td colSpan={6} className="wiz-warn">
            {m.skipped(g.skipped)}
          </td>
        </tr>
      ) : (
        [...(g.roll ? [g.roll] : []), ...g.models].map((f) => <Row key={f.model} f={f} />)
      )}
    </tbody>
  );
}

function Row({ f }: { f: ModelFigures }) {
  const level =
    f.median == null ? undefined : f.level_ok ? card.inRange : f.median < 1 ? card.low : card.high;
  const cod =
    f.cod == null ? undefined : f.cod_low ? card.tooEven : f.cod_ok === false ? card.varied : card.even;
  const tilt = (f.prb ?? 0) > 0 ? card.dearerHigher : card.dearerLower;
  const prb = f.prb == null ? undefined : f.prb_ok ? card.alike : f.prb_bad ? tilt : `${m.slight}: ${tilt}`;
  return (
    <tr className={f.model === "assessor" ? "md-roll" : undefined}>
      <td>
        {f.name}
        {f.model === "ensemble" && <span className="wiz-from"> · {m.shipped}</span>}
      </td>
      <td className="cs-n">{num(f.sales)}</td>
      <td>
        <Score ok={f.level_ok} figure={num(f.median, 2)} {...(level ? { word: level } : {})} />
      </td>
      <td>
        <Score ok={f.cod_low ? false : f.cod_ok} figure={num(f.cod, 1)} {...(cod ? { word: cod } : {})} />
      </td>
      <td>
        <Score
          ok={f.prb_bad ? false : f.prb_ok}
          figure={f.prb == null ? "—" : signed(f.prb, 3)}
          {...(prb ? { word: prb } : {})}
          note="PRB"
        />
      </td>
      <td className="cs-n">{num(f.cod_trimmed, 1)}</td>
    </tr>
  );
}
