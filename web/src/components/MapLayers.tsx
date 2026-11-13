/** The map window's layers and legend (SPEC §3.15), one thing: closed, a chip in the map's top left corner with the legend
 * in brief (pressed, it opens); open, a panel over the map; pinned (📌), the same as a drawer beside the map, which
 * it narrows. It holds one data layer, the record the field is from: 🌐 Parcels or 💰 Sales (the parcels then only
 * faint outlines under the dots), with its 👁, what it's coloured by, its legend, and a switch to the same field in
 * the other record when that has it; then the street map underneath. */
import { ArrowLeftRight, ChevronDown, ChevronUp, Eye, EyeOff, Layers, Pin } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "react-aria-components";
import { t } from "../wording";
import { SmallButton, ToolButton } from "./Buttons";

const w = t.mapWindow;

export type LayersState = "closed" | "open" | "pinned";

export type DataLayer = {
  /** 🌐 Parcels or 💰 Sales. */
  name: string;
  /** How many there are (parcels, or sales on the map); null while not known. */
  count: number | null;
  shown: boolean;
  onShown: (on: boolean) => void;
  /** The same field in the other record: pressed, the map shows that instead. */
  switchTo?: { label: string; onPress: () => void } | undefined;
  /** Said where there's no switch (the field is only this record's). */
  only?: string | undefined;
  /** A line under it (squares drawn now). */
  note?: string | undefined;
};

export type BaseLayer = { id: string; name: string; shown: boolean; onShown: (on: boolean) => void };

export function MapLayers({
  state,
  onState,
  brief,
  data,
  colourBy,
  legend,
  base,
}: {
  state: LayersState;
  onState: (s: LayersState) => void;
  /** The legend in brief, on the closed chip. */
  brief: ReactNode;
  data: DataLayer;
  /** What it's coloured by: the field picker. */
  colourBy: ReactNode;
  legend: ReactNode;
  /** Under it: the street map. */
  base: BaseLayer[];
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
        <ChevronDown aria-hidden="true" size="1em" />
      </Button>
    );
  const pinned = state === "pinned";
  return (
    <section className={`mapwin-ly ${pinned ? "pinned" : "floating"}`} aria-label={w.ly.title}>
      <div className="mapwin-ly-head">
        <Layers aria-hidden="true" size="1.05em" className="mapwin-ly-icon" />
        <b>{w.ly.title}</b>
        <ToolButton
          plain
          label={pinned ? w.ly.unpin : w.ly.pin}
          pressed={pinned}
          onPress={() => onState(pinned ? "open" : "pinned")}
        >
          <Pin aria-hidden="true" size="1em" {...(pinned ? { fill: "currentColor" } : {})} />
        </ToolButton>
        <ToolButton plain label={w.ly.close} onPress={() => onState("closed")}>
          <ChevronUp aria-hidden="true" size="1em" />
        </ToolButton>
      </div>
      <div className="mapwin-ly-scroll">
        <div className={`mapwin-ly-data ${data.shown ? "" : "off"}`}>
          <div className="mapwin-ly-line">
            <Eye3 name={data.name} shown={data.shown} onShown={data.onShown} />
            <span className="mapwin-ly-name">{data.name}</span>
            {data.count !== null && <small className="mapwin-ly-count">{data.count.toLocaleString()}</small>}
            <span className="mapwin-ly-gap" />
            {data.switchTo ? (
              <SmallButton onPress={data.switchTo.onPress}>
                <ArrowLeftRight aria-hidden="true" size="0.9em" /> {data.switchTo.label}
              </SmallButton>
            ) : (
              data.only && <small className="mapwin-ly-count">{data.only}</small>
            )}
          </div>
          {data.note && <small className="mapwin-ly-note">{data.note}</small>}
          <div className="mapwin-by">{colourBy}</div>
          {data.shown && <div className="mapwin-ly-legend">{legend}</div>}
        </div>
        {base.map((b) => (
          <div key={b.id} className={`mapwin-ly-base ${b.shown ? "" : "off"}`}>
            <Eye3 name={b.name} shown={b.shown} onShown={b.onShown} />
            <span className="mapwin-ly-name">{b.name}</span>
            <span className="mapwin-ly-gap" />
            <small className="mapwin-ly-count">{b.shown ? w.ly.underneath : w.ly.hidden}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

/** A layer's 👁: shown, or hidden (struck through). */
function Eye3({ name, shown, onShown }: { name: string; shown: boolean; onShown: (on: boolean) => void }) {
  return (
    <ToolButton
      plain
      label={shown ? w.ly.hide({ what: name }) : w.ly.show({ what: name })}
      pressed={shown}
      onPress={() => onShown(!shown)}
    >
      {shown ? <Eye aria-hidden="true" size="1.1em" /> : <EyeOff aria-hidden="true" size="1.1em" />}
    </ToolButton>
  );
}
