/** The map window's layers and legend (SPEC §3.15), one thing: closed, a chip over the map's corner with the legend
 * in brief (pressed, it opens); open, a panel over the map with what's coloured by (the field), each layer with its
 * 👁 (shown or not), its legend and its options; pinned (📌), the same as a drawer beside the map, which it narrows. */
import { ChevronDown, ChevronUp, Eye, EyeOff, Layers, Pin, SlidersHorizontal } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "react-aria-components";
import { t } from "../wording";
import { ToolButton } from "./Buttons";

const w = t.mapWindow;

export type LayersState = "closed" | "open" | "pinned";

export type LayerRow = {
  id: string;
  name: string;
  /** Drawn or not, its 👁; no 👁 when it can't be hidden. */
  shown: boolean;
  onShown?: (on: boolean) => void;
  /** The legend in brief, on its line (a count, a dot). */
  brief?: ReactNode;
  /** Its legend, under its line while it's shown. */
  legend?: ReactNode;
  /** Its options, under a ⚙ of its own. */
  options?: ReactNode;
};

export function MapLayers({
  state,
  onState,
  brief,
  colourBy,
  rows,
}: {
  state: LayersState;
  onState: (s: LayersState) => void;
  /** The legend in brief, on the closed chip. */
  brief: ReactNode;
  /** What the map is coloured by: the field picker. */
  colourBy: ReactNode;
  rows: LayerRow[];
}) {
  if (state === "closed")
    return (
      <Button
        className="mapwin-ly-chip"
        aria-expanded={false}
        aria-label={w.ly.open}
        onPress={() => onState("open")}
      >
        <Layers aria-hidden="true" size="1.05em" className="mapwin-ly-icon" />
        <span className="mapwin-ly-brief">{brief}</span>
        <ChevronUp aria-hidden="true" size="1em" />
      </Button>
    );
  const pinned = state === "pinned";
  return (
    <section className={`mapwin-ly ${pinned ? "pinned" : "floating"}`} aria-label={w.ly.title}>
      <div className="mapwin-ly-head">
        <Layers aria-hidden="true" size="1.05em" className="mapwin-ly-icon" />
        <b>{w.ly.title}</b>
        <ToolButton
          label={pinned ? w.ly.unpin : w.ly.pin}
          pressed={pinned}
          onPress={() => onState(pinned ? "open" : "pinned")}
        >
          <Pin aria-hidden="true" size="1em" {...(pinned ? { fill: "currentColor" } : {})} />
        </ToolButton>
        <ToolButton label={w.ly.close} onPress={() => onState("closed")}>
          <ChevronDown aria-hidden="true" size="1em" />
        </ToolButton>
      </div>
      <div className="mapwin-ly-scroll">
        <div className="mapwin-ly-by">{colourBy}</div>
        {rows.map((r) => (
          <Row key={r.id} row={r} />
        ))}
      </div>
    </section>
  );
}

function Row({ row }: { row: LayerRow }) {
  const [opts, setOpts] = useState(false);
  const words = { what: row.name };
  return (
    <div className={`mapwin-ly-layer ${row.shown ? "" : "off"}`}>
      <div className="mapwin-ly-line">
        {row.onShown ? (
          <ToolButton
            label={row.shown ? w.ly.hide(words) : w.ly.show(words)}
            pressed={row.shown}
            onPress={() => row.onShown?.(!row.shown)}
          >
            {row.shown ? <Eye aria-hidden="true" size="1.1em" /> : <EyeOff aria-hidden="true" size="1.1em" />}
          </ToolButton>
        ) : (
          <span className="mapwin-ly-noeye" aria-hidden="true" />
        )}
        <span className="mapwin-ly-name">{row.name}</span>
        <span className="mapwin-ly-brief">{row.shown ? row.brief : <small>{w.ly.hidden}</small>}</span>
        {row.options && (
          <ToolButton label={w.ly.options(words)} pressed={opts} onPress={() => setOpts(!opts)}>
            <SlidersHorizontal aria-hidden="true" size="1em" />
          </ToolButton>
        )}
      </div>
      {row.shown && row.legend && <div className="mapwin-ly-legend">{row.legend}</div>}
      {opts && row.options && <div className="mapwin-ly-opts">{row.options}</div>}
    </div>
  );
}
