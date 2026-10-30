import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { ChevronDown, Map as MapIcon, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Button,
  Dialog,
  DialogTrigger,
  Input,
  Label,
  Menu,
  MenuItem,
  MenuTrigger,
  Popover,
  TextField,
} from "react-aria-components";
import { api, type LayerView, type Overlay, type Project, unwrap, type Wizard } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import { addBasemap } from "../components/basemap";
import { Choice, Tick } from "../components/Form";
import { Seg } from "../components/Seg";
import { t } from "../strings";
import { FilePicker } from "./WizardFiles";

const s = t.wizard.shapefiles;
type Kind = Overlay["fields"][number]["kind"];
type Unit = Overlay["unit"];
export type LayerChange = { kind: "layer"; name: string; overlay: Overlay | null };

const EMPTY: Overlay = {
  use: null,
  fields: [],
  feature: "",
  max_distance: null,
  unit: "km",
  store_top: false,
  top_n: 0,
  sort_field: null,
  name_column: null,
};

/** "school_zones" from "School Zones.shp": a starting name the user can change. */
function nameFor(text: string): string {
  const n = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(n) ? n : `f_${n}`;
}

/** F3d, More details › Shapefiles: map layers stamped onto the parcels, or measured to. */
export function ShapefilesStep({
  project,
  data,
  change,
}: {
  project: Project;
  data: Wizard;
  change: (c: LayerChange) => void;
}) {
  const [adding, setAdding] = useState(data.layers.length === 0);
  const taken = data.files
    .filter((f) => f.base || f.holds === "parcels" || f.holds === "sales")
    .map((f) => f.name);
  return (
    <>
      {data.layers.map((layer) => (
        <LayerCard key={layer.name} project={project} layer={layer} change={change} />
      ))}
      {adding ? (
        <div className="wiz-extra">
          <FilePicker
            project={project}
            data={data}
            exclude={[...taken, ...data.layers.map((x) => x.name)]}
            onChosen={(name) => {
              change({ kind: "layer", name, overlay: EMPTY });
              setAdding(false);
            }}
          />
          <p className="wiz-from">{s.formats}</p>
          {data.layers.length > 0 && (
            <Button className="wiz-link" onPress={() => setAdding(false)}>
              {t.wizard.cancel}
            </Button>
          )}
        </div>
      ) : (
        <Button className="button wiz-add-id" onPress={() => setAdding(true)}>
          <Plus aria-hidden="true" size="1em" />
          {data.layers.length ? s.another : s.first}
        </Button>
      )}
    </>
  );
}

/** One layer, compact: a header line (what it is, how it's used, its check, map, remove), then one line for
 * the fields it stamps or the distance it gives. */
function LayerCard({
  project,
  layer,
  change,
}: {
  project: Project;
  layer: LayerView;
  change: (c: LayerChange) => void;
}) {
  const o = layer.overlay;
  const [mapShown, setMapShown] = useState(false);
  const set = (patch: Partial<Overlay>) =>
    change({ kind: "layer", name: layer.name, overlay: { ...o, ...patch } });
  const kinds = [
    layer.polygons ? s.polygons(layer.polygons) : null,
    layer.points ? s.points(layer.points) : null,
    layer.lines ? s.lines(layer.lines) : null,
  ].filter(Boolean);
  const defaultUnit: Unit = project.units === "imperial" ? "mile" : "km";
  const noStamp = !layer.polygons && o.use !== "stamp";
  return (
    <section className="ly">
      <div className="ly-head">
        <span className="mono ly-name">{layer.name}</span>
        <span className="wiz-from">
          {layer.filename} · {kinds.join(", ") || s.empty}
        </span>
        <Seg
          label={s.how}
          value={o.use}
          options={[
            ["stamp", s.stampShort],
            ["distance", s.distanceShort],
          ]}
          disabled={noStamp ? ["stamp"] : []}
          titles={{
            stamp: noStamp ? (layer.points ? s.onlyPoints : layer.lines ? s.onlyLines : s.noShapes) : s.stamp,
            distance: s.distance,
          }}
          onChange={(use) =>
            set(
              use === "distance"
                ? { use, feature: o.feature || nameFor(layer.name), unit: o.feature ? o.unit : defaultUnit }
                : { use: "stamp" },
            )
          }
        />
        {layer.check && (
          <span className={layer.check.ok && !layer.check.warn ? "wiz-ok" : "wiz-warn"}>
            {layer.check.text}
          </span>
        )}
        <span className="ly-grow" />
        {layer.projected && (
          <Button
            className={mapShown ? "ly-icon on" : "ly-icon"}
            aria-label={mapShown ? s.hideMap : s.showMap}
            aria-pressed={mapShown}
            onPress={() => setMapShown(!mapShown)}
          >
            <MapIcon aria-hidden="true" size="1em" />
          </Button>
        )}
        <Button
          className="ly-icon"
          aria-label={s.drop}
          onPress={() => change({ kind: "layer", name: layer.name, overlay: null })}
        >
          <X aria-hidden="true" size="1em" />
        </Button>
      </div>
      {layer.left.length > 0 && (
        <ul className="ly-left">
          {layer.left.map((x) => (
            <li key={x.text} className={x.blocking ? "wiz-blocking" : "wiz-caution"}>
              <img src={x.blocking ? blockingIcon : warningIcon} alt="" className="wiz-inline-icon" />
              {x.text}
            </li>
          ))}
        </ul>
      )}
      {o.use === "stamp" && <StampFields layer={layer} set={set} />}
      {o.use === "distance" && <DistanceOptions layer={layer} set={set} />}
      {mapShown && <LayerMap projectId={project.id} name={layer.name} />}
    </section>
  );
}

/** The columns it copies onto the parcels, as chips (name ← column, used as), and + Field. */
function StampFields({ layer, set }: { layer: LayerView; set: (p: Partial<Overlay>) => void }) {
  const o = layer.overlay;
  const kinds = Object.entries(s.kindsShort) as [Kind, string][];
  return (
    <div className="ly-body">
      <span className="ly-label">{s.copies}</span>
      {o.fields.map((f) => (
        <span key={f.name} className="ly-chip">
          <span className="mono">{f.name}</span>
          <span className="wiz-from">← {f.column}</span>
          <MenuTrigger>
            <Button className="ly-kind" aria-label={`${s.kind}: ${f.name}`}>
              {s.kindsShort[f.kind]}
              <ChevronDown aria-hidden="true" size="0.8em" />
            </Button>
            <Popover className="popover" placement="bottom start">
              <Menu
                className="choice-list"
                onAction={(k) =>
                  set({ fields: o.fields.map((x) => (x.name === f.name ? { ...x, kind: k as Kind } : x)) })
                }
              >
                {kinds.map(([k, label]) => (
                  <MenuItem key={k} id={k} className="choice-item" textValue={label}>
                    {s.kinds[k]}
                  </MenuItem>
                ))}
              </Menu>
            </Popover>
          </MenuTrigger>
          <Button
            className="ly-x"
            aria-label={s.remove(f.name)}
            onPress={() => set({ fields: o.fields.filter((x) => x.name !== f.name) })}
          >
            <X size="0.85em" />
          </Button>
        </span>
      ))}
      <AddStamp layer={layer} add={(f) => set({ fields: [...o.fields, f] })} />
    </div>
  );
}

function AddStamp({ layer, add }: { layer: LayerView; add: (f: Overlay["fields"][number]) => void }) {
  const o = layer.overlay;
  const [open, setOpen] = useState(false);
  const [column, setColumn] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind>("location");
  const kinds = Object.entries(s.kinds) as [Kind, string][];
  const used = new Set(o.fields.map((f) => f.column));
  const free = layer.columns.filter((c) => !used.has(c.name));
  if (free.length === 0) return null;
  return (
    <DialogTrigger isOpen={open} onOpenChange={setOpen}>
      <Button className="ly-add">
        <Plus aria-hidden="true" size="0.9em" />
        {s.addField}
      </Button>
      <Popover className="popover" placement="bottom start">
        <Dialog className="popover-body ly-pop" aria-label={s.addField}>
          <form
            className="ly-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (column && name) {
                add({ column, name, kind });
                setColumn(null);
                setName("");
                setOpen(false);
              }
            }}
          >
            <Choice
              label={s.column}
              value={column}
              placeholder={s.pickColumn}
              options={free.map((c) => [c.name, c.name] as const)}
              onChange={(c) => {
                setColumn(c);
                setName(nameFor(c));
              }}
            />
            <TextField value={name} onChange={setName} className="field">
              <Label className="field-label">{s.name}</Label>
              <Input className="input" placeholder={s.namePlaceholder} />
            </TextField>
            <Choice label={s.kind} value={kind} options={kinds} onChange={setKind} />
            <Button type="submit" className="button button-primary" isDisabled={!column || !name}>
              {s.add}
            </Button>
          </form>
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

/** One line: the distance's name, its limit, and (folded away) feature names and the largest few. */
function DistanceOptions({ layer, set }: { layer: LayerView; set: (p: Partial<Overlay>) => void }) {
  const o = layer.overlay;
  // Typed values are saved when the box is left (or Enter), so each keystroke isn't a save.
  const [feature, setFeature] = useState(o.feature);
  const [max, setMax] = useState(o.max_distance === null ? "" : String(o.max_distance));
  const [topN, setTopN] = useState(String(o.top_n || 3));
  const units = Object.entries(s.units) as [Unit, string][];
  const saveFeature = () => {
    const f = nameFor(feature);
    if (f && f !== o.feature) set({ feature: f });
    setFeature(f || o.feature);
  };
  const saveMax = () => {
    const m = max.trim() === "" ? null : Number(max);
    if (m !== null && !(m > 0)) {
      setMax(o.max_distance === null ? "" : String(o.max_distance));
      return;
    }
    if (m !== o.max_distance) set({ max_distance: m });
  };
  const enter = (save: () => void) => (e: React.KeyboardEvent) => {
    if (e.key === "Enter") save();
  };
  const options = [
    o.name_column ? s.namesFrom(o.name_column) : null,
    o.store_top ? s.topShort(o.top_n) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="ly-body">
      <span className="ly-label">{s.gives}</span>
      <span className="mono ly-prefix">dist_to_</span>
      <TextField
        aria-label={s.featureName}
        value={feature}
        onChange={setFeature}
        onBlur={saveFeature}
        className="ly-feature"
      >
        <Input className="input ly-input" onKeyDown={enter(saveFeature)} />
      </TextField>
      <span className="ly-label">{s.upTo}</span>
      <TextField aria-label={s.maxDistance} value={max} onChange={setMax} onBlur={saveMax} className="ly-max">
        <Input
          className="input ly-input wiz-num"
          inputMode="decimal"
          placeholder={s.none}
          onKeyDown={enter(saveMax)}
        />
      </TextField>
      <span className="ly-unit">
        <Choice label={s.unit} hideLabel value={o.unit} options={units} onChange={(unit) => set({ unit })} />
      </span>
      <DialogTrigger>
        <Button className="ly-add">
          {s.options}
          {options && <span className="wiz-from"> · {options}</span>}
          <ChevronDown aria-hidden="true" size="0.8em" />
        </Button>
        <Popover className="popover" placement="bottom start">
          <Dialog className="popover-body ly-pop" aria-label={s.options}>
            <div className="ly-form">
              <p className="wiz-from ly-help">
                {s.columns(o.feature || "…")}. {s.maxHelp}
              </p>
              <Choice
                label={s.nameColumn}
                value={o.name_column ?? "__none"}
                options={[
                  ["__none", s.noNames] as const,
                  ...layer.columns.map((c) => [c.name, c.name] as const),
                ]}
                onChange={(c) => set({ name_column: c === "__none" ? null : c })}
              />
              <Tick
                isSelected={o.store_top}
                onChange={(on) => set({ store_top: on, top_n: on ? Number(topN) || 3 : 0 })}
              >
                {s.top}
              </Tick>
              {o.store_top && (
                <div className="ly-inline">
                  <TextField
                    aria-label={s.topN}
                    value={topN}
                    onChange={setTopN}
                    onBlur={() => set({ top_n: Math.max(1, Number.parseInt(topN, 10) || 1) })}
                    className="ly-max"
                  >
                    <Input className="input ly-input wiz-num" inputMode="numeric" />
                  </TextField>
                  <span>{s.sortBy}</span>
                  <Choice
                    label={s.sortBy}
                    hideLabel
                    value={o.sort_field ?? (layer.lines && !layer.polygons ? "length" : "area")}
                    options={[
                      ["area", s.byArea],
                      ["length", s.byLength],
                    ]}
                    onChange={(sort_field) => set({ sort_field })}
                  />
                </div>
              )}
            </div>
          </Dialog>
        </Popover>
      </DialogTrigger>
    </div>
  );
}

/** The layer's shapes over the parcel dots: does it line up? */
function LayerMap({ projectId, name }: { projectId: string; name: string }) {
  const el = useRef<HTMLDivElement>(null);
  const view = useQuery({
    queryKey: ["layer-map", projectId, name],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/layers/{name}/map", {
          params: { path: { project_id: projectId, name } },
        }),
      ),
  });
  const v = view.data;
  useEffect(() => {
    if (!el.current || !v) return;
    const m = L.map(el.current, { preferCanvas: true, scrollWheelZoom: false });
    addBasemap(m);
    const renderer = L.canvas();
    const points = v.points as [number, number][];
    for (const [lat, lon] of points) {
      L.circleMarker([lat, lon], {
        renderer,
        radius: 2,
        weight: 0,
        fillOpacity: 0.6,
        fillColor: "#1d5bb8",
      }).addTo(m);
    }
    const shapes = L.geoJSON(v.shapes as unknown as GeoJSON.GeoJsonObject, {
      style: { color: "#a3231b", weight: 2, fillOpacity: 0.08 },
      pointToLayer: (_f, at) => L.circleMarker(at, { renderer, radius: 5, color: "#a3231b", weight: 2 }),
    }).addTo(m);
    const bounds = shapes.getBounds();
    if (points.length) bounds.extend(L.latLngBounds(points));
    if (bounds.isValid()) m.fitBounds(bounds, { padding: [12, 12] });
    return () => {
      m.remove();
    };
  }, [v]);
  if (view.error) return <p className="error">{view.error.message}</p>;
  return <div ref={el} className="wiz-map" role="img" aria-label={s.mapLabel(name)} />;
}
