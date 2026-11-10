/** A parcel's card in the map window (SPEC §3.15): picked on the map (a parcel, or a sale's dot), it shows the parcel
 * as each 🌐 parcel file has it, its fields first (the Big five first), each a link to the step that sets it, and its
 * 💰 sales, the latest first, with each sale's own values beside the parcel's and the differences flagged. Picking
 * never changes the step; only the links here go anywhere. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { t } from "../wording";
import { CloseButton, ToolButton } from "./Buttons";
import { Disclose } from "./Disclose";
import { Tip } from "./Tip";
import { Waiting } from "./Waiting";

const w = t.mapWindow.card;

/** Where a card at (x, y) is kept: inside the map's area, never past its edges. */
function clampIn(box: HTMLElement, card: HTMLElement, x: number, y: number) {
  return {
    x: Math.max(0, Math.min(x, box.clientWidth - card.offsetWidth)),
    y: Math.max(0, Math.min(y, box.clientHeight - card.offsetHeight)),
  };
}

/** A Data step's name, as the sidebar says it. */
const stepTitle = (key: string) => t.wizard.steps[key]?.title ?? key;

/** A value as the card shows it: a number with a long tail of decimals (a shape's computed area) to two places,
 * its unit kept; anything else as written. */
export function tidy(v: string): string {
  const m = v.match(/^(-?\d[\d,]*\.\d{3,})(\s.*)?$/);
  if (!m?.[1]) return v;
  const x = Number(m[1].replace(/,/g, ""));
  return Number.isFinite(x) ? `${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}${m[2] ?? ""}` : v;
}
type Card = components["schemas"]["ParcelCard"];

export function MapCard({
  projectId,
  index,
  stepOf,
  onGo,
  onColour,
  onClose,
  pinned,
  onPin,
  stage,
}: {
  projectId: string;
  index: number;
  /** The Data step that sets a field (its link), or null. */
  stepOf: (field: string) => string | null;
  /** A link followed: the main window goes to the step (from a popped-out map, it's asked to). */
  onGo: (step: string) => void;
  /** A field's name clicked: the map coloured by it (a 🌐 file:column, or a difference, pr:differs:<field>). */
  onColour: (id: string) => void;
  onClose: () => void;
  /** Pinned to the map's left side (📌), or floating over it. */
  pinned: boolean;
  onPin: (pinned: boolean) => void;
  /** The map's area: a floating card is dragged within it, never past its edges. */
  stage: React.RefObject<HTMLDivElement | null>;
}) {
  // Floating: where it was dragged to (its top left in the map's area); until then, the map's top right.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const me = useRef<HTMLElement>(null);
  // The map's area shrinks (the divider, the window): a dragged card stays inside it.
  useEffect(() => {
    const box = stage.current;
    const card = me.current;
    if (!box || !card || pinned) return;
    const ro = new ResizeObserver(() => setPos((p) => (p ? clampIn(box, card, p.x, p.y) : p)));
    ro.observe(box);
    return () => ro.disconnect();
  }, [stage, pinned]);
  const onDrag = (e: React.PointerEvent<HTMLElement>) => {
    if (pinned || (e.target as HTMLElement).closest("button")) return;
    const card = me.current;
    const box = stage.current;
    if (!card || !box) return;
    e.preventDefault();
    const head = e.currentTarget;
    head.setPointerCapture(e.pointerId);
    const start = { px: e.clientX, py: e.clientY, x: card.offsetLeft, y: card.offsetTop };
    const move = (ev: PointerEvent) =>
      setPos(clampIn(box, card, start.x + ev.clientX - start.px, start.y + ev.clientY - start.py));
    const up = () => {
      head.removeEventListener("pointermove", move);
      head.removeEventListener("pointerup", up);
    };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", up);
  };
  const q = useQuery({
    queryKey: ["map-card", projectId, index],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/parcel/{index}", {
          params: { path: { project_id: projectId, index } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const [more, setMore] = useState(false);
  // Esc closes it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const c: Card | undefined = q.data;
  const go = onGo;
  const loaded = c?.fields.filter((f) => f.field) ?? [];
  const others = c?.fields.filter((f) => !f.field) ?? [];
  const several = c ? Object.entries(c.rows).filter(([, n]) => n > 1) : [];
  const missing = c ? Object.entries(c.rows).filter(([, n]) => n === 0) : [];
  return (
    <section
      ref={me}
      className={`mapcard ${pinned ? "mapcard-pinned" : "mapcard-float"}`}
      style={!pinned && pos ? { left: pos.x, top: pos.y, right: "auto" } : undefined}
      aria-label={c ? w.title({ key: c.key || "—" }) : w.loading}
    >
      <header className="mapcard-head" onPointerDown={onDrag}>
        <b>{c ? w.title({ key: c.key || "—" }) : "…"}</b>
        {q.isFetching && c && <span className="mapcard-busy" aria-hidden="true" />}
        <ToolButton
          label={pinned ? w.unpinTip : w.pinTip}
          pressed={pinned}
          onPress={() => {
            setPos(null);
            onPin(!pinned);
          }}
        >
          <Pin aria-hidden="true" size="1em" />
        </ToolButton>
        <CloseButton label={w.close} onPress={onClose} />
      </header>
      {q.error ? (
        <p className="error">{q.error.message}</p>
      ) : !c ? (
        <Waiting doing={w.loading} />
      ) : (
        <div className="mapcard-body">
          <h3 className="mapcard-h">{w.pu}</h3>
          {loaded.length === 0 ? (
            <p className="mapcard-dim">{w.noFields}</p>
          ) : (
            <table className="mapcard-tbl">
              <tbody>
                {loaded.map((f) => {
                  const step = f.field ? stepOf(f.field) : null;
                  return (
                    <tr key={`${f.file}:${f.column}`}>
                      <th scope="row">
                        <Button className="wiz-link" onPress={() => onColour(`${f.file}:${f.column}`)}>
                          {f.label}
                        </Button>
                        {step && (
                          <Tip text={w.toStep({ step: stepTitle(step) })}>
                            <Button
                              className="wiz-link mapcard-step"
                              aria-label={w.toStep({ step: stepTitle(step) })}
                              onPress={() => go(step)}
                            >
                              ›
                            </Button>
                          </Tip>
                        )}
                      </th>
                      <td>{tidy(f.value) || <span className="mapcard-dim">{w.blank}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {several.length > 0 && (
            <p className="mapcard-dim">{several.map(([file, n]) => w.rows({ file, n })).join(" ")}</p>
          )}
          {missing.length > 0 && (
            <p className="mapcard-dim">{w.notIn({ files: missing.map(([f]) => f).join(", ") })}</p>
          )}
          {others.length > 0 && (
            <>
              <Disclose open={more} onPress={() => setMore(!more)} className="mapcard-more">
                {w.more({ n: others.length })}
              </Disclose>
              {more && (
                <table className="mapcard-tbl mapcard-raw">
                  <tbody>
                    {others.map((f) => (
                      <tr key={`${f.file}:${f.column}`}>
                        <th scope="row" className="mono">
                          <Button className="wiz-link" onPress={() => onColour(`${f.file}:${f.column}`)}>
                            {f.column}
                          </Button>
                        </th>
                        <td>{f.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
          <h3 className="mapcard-h">{w.sr({ n: c.sales.length })}</h3>
          {c.sales.length === 0 && <p className="mapcard-dim">{w.noSales}</p>}
          {c.sales.map((s) => (
            <div key={s.row} className="mapcard-sale">
              <div className="mapcard-sale-head">
                <b>{s.date || w.noDate}</b>
                <span>{s.price ? Number(s.price).toLocaleString() : w.noPrice}</span>
                {s.valid === 1 && <span className="mapcard-tag ok">{w.valid}</span>}
                {s.valid === 0 && <span className="mapcard-tag no">{w.invalid}</span>}
                {s.vacant === 1 && <span className="mapcard-tag">{w.vacant}</span>}
              </div>
              {s.compared.length > 0 && (
                <table className="mapcard-tbl mapcard-cmp">
                  <thead>
                    <tr>
                      <th />
                      <th scope="col">💰</th>
                      <th scope="col">🌐</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.compared.map((x) => (
                      <tr key={x.field} className={x.differs && !x.written_differently ? "differs" : ""}>
                        <th scope="row">
                          <Button className="wiz-link" onPress={() => onColour(`pr:differs:${x.field}`)}>
                            {x.label}
                          </Button>
                        </th>
                        <td>{tidy(x.sold)}</td>
                        <td>
                          {tidy(x.today)}
                          {x.differs && !x.written_differently && (
                            <span className="mapcard-ne" title={w.differs}>
                              {" "}
                              ≠
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
          {c.sales.some((s) => s.compared.length > 0) && (
            <Button className="wiz-link mapcard-link" onPress={() => go("as_sold")}>
              {w.toAsSold}
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
