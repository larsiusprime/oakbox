import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { ChevronUp, Map as MapIcon, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input, Label, Radio, RadioGroup, TextField } from "react-aria-components";
import { api, type LayerView, type Overlay, type Project, unwrap, type Wizard } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import { Choice, Tick } from "../components/Form";
import { t } from "../strings";
import { FilePicker } from "./FieldsWizard";

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
  const set = (patch: Partial<Overlay>) =>
    change({ kind: "layer", name: layer.name, overlay: { ...o, ...patch } });
  const kinds = [
    layer.polygons ? s.polygons(layer.polygons) : null,
    layer.points ? s.points(layer.points) : null,
    layer.lines ? s.lines(layer.lines) : null,
  ].filter(Boolean);
  const defaultUnit: Unit = project.units === "imperial" ? "mile" : "km";
  return (
    <section className="wiz-extra">
      <div className="wiz-file">
        <span className="mono">{layer.name}</span>
        <span className="wiz-from">{layer.filename}</span>
        <span className="wiz-from">· {kinds.join(", ") || s.empty}</span>
        <Button
          className="wiz-link"
          onPress={() => change({ kind: "layer", name: layer.name, overlay: null })}
        >
          {s.drop}
        </Button>
      </div>
      {layer.left.length > 0 && (
        <ul className="wiz-left-list">
          {layer.left.map((x) => (
            <li key={x.text} className={x.blocking ? "wiz-blocking" : "wiz-caution"}>
              <img src={x.blocking ? blockingIcon : warningIcon} alt="" className="wiz-inline-icon" />
              {x.text}
            </li>
          ))}
        </ul>
      )}
      <RadioGroup
        className="field radios wiz-holds"
        value={o.use}
        onChange={(use) =>
          set(
            use === "distance"
              ? { use, feature: o.feature || nameFor(layer.name), unit: o.feature ? o.unit : defaultUnit }
              : { use: "stamp" },
          )
        }
      >
        <Label className="field-label">{s.how}</Label>
        <Radio value="stamp" className="radio" isDisabled={!layer.polygons && o.use !== "stamp"}>
          <span className="radio-dot" aria-hidden="true" />
          {s.stamp}
          {!layer.polygons && (
            <small className="wiz-from">
              {" "}
              {layer.points ? s.onlyPoints : layer.lines ? s.onlyLines : s.noShapes}
            </small>
          )}
        </Radio>
        <Radio value="distance" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {s.distance}
        </Radio>
      </RadioGroup>
      {o.use === "stamp" && <StampFields layer={layer} set={set} />}
      {o.use === "distance" && <DistanceOptions layer={layer} set={set} />}
      {layer.check && (
        <p className={layer.check.ok && !layer.check.warn ? "wiz-ok" : "wiz-warn"}>{layer.check.text}</p>
      )}
      {layer.projected && <LayerMapToggle projectId={project.id} name={layer.name} />}
    </section>
  );
}

function StampFields({ layer, set }: { layer: LayerView; set: (p: Partial<Overlay>) => void }) {
  const o = layer.overlay;
  const [column, setColumn] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind>("location");
  const kinds = Object.entries(s.kinds) as [Kind, string][];
  const used = new Set(o.fields.map((f) => f.column));
  return (
    <div className="wiz-stamp">
      {o.fields.map((f) => (
        <div key={f.name} className="wiz-loc">
          <span className="mono">{f.name}</span>
          <span className="wiz-from">{f.column}</span>
          <Choice
            label={s.kind}
            hideLabel
            value={f.kind}
            options={kinds}
            onChange={(k) =>
              set({ fields: o.fields.map((x) => (x.name === f.name ? { ...x, kind: k } : x)) })
            }
          />
          <Button
            className="rc-x"
            aria-label={s.remove(f.name)}
            onPress={() => set({ fields: o.fields.filter((x) => x.name !== f.name) })}
          >
            <X size="0.9em" />
          </Button>
        </div>
      ))}
      <form
        className="wiz-loc-add"
        onSubmit={(e) => {
          e.preventDefault();
          if (column && name) {
            set({ fields: [...o.fields, { column, name, kind }] });
            setColumn(null);
            setName("");
          }
        }}
      >
        <Choice
          label={s.column}
          hideLabel
          value={column}
          placeholder={s.pickColumn}
          options={layer.columns.filter((c) => !used.has(c.name)).map((c) => [c.name, c.name] as const)}
          onChange={(c) => {
            setColumn(c);
            setName(nameFor(c));
          }}
        />
        <TextField aria-label={s.name} value={name} onChange={setName} className="rl-mini">
          <Input className="input rl-input" placeholder={s.namePlaceholder} />
        </TextField>
        <Choice label={s.kind} hideLabel value={kind} options={kinds} onChange={setKind} />
        <Button type="submit" className="button" isDisabled={!column || !name}>
          {s.add}
        </Button>
      </form>
    </div>
  );
}

function DistanceOptions({ layer, set }: { layer: LayerView; set: (p: Partial<Overlay>) => void }) {
  const o = layer.overlay;
  // Typed values are kept here and saved on Save, so each keystroke isn't a save.
  const [feature, setFeature] = useState(o.feature);
  const [max, setMax] = useState(o.max_distance === null ? "" : String(o.max_distance));
  const [topN, setTopN] = useState(String(o.top_n || 3));
  const units = Object.entries(s.units) as [Unit, string][];
  const dirty = feature !== o.feature || max !== (o.max_distance === null ? "" : String(o.max_distance));
  return (
    <div className="wiz-dist">
      <div className="wiz-loc-add">
        <span>{s.named}</span>
        <TextField aria-label={s.featureName} value={feature} onChange={setFeature} className="rl-mini">
          <Input className="input rl-input" />
        </TextField>
        <span className="wiz-from">{s.columns(feature || "…")}</span>
      </div>
      <div className="wiz-loc-add">
        <span>{s.maxDistance}</span>
        <TextField aria-label={s.maxDistance} value={max} onChange={setMax} className="rl-mini">
          <Input className="input rl-input wiz-num" inputMode="decimal" placeholder={s.none} />
        </TextField>
        <Choice label={s.unit} hideLabel value={o.unit} options={units} onChange={(unit) => set({ unit })} />
        <span className="wiz-from">{s.maxHelp}</span>
      </div>
      {dirty && (
        <Button
          className="button button-primary"
          onPress={() => set({ feature, max_distance: max.trim() ? Number(max) : null })}
          isDisabled={max.trim() !== "" && !(Number(max) > 0)}
        >
          {s.save}
        </Button>
      )}
      <div className="wiz-loc-add">
        <span>{s.nameColumn}</span>
        <Choice
          label={s.nameColumn}
          hideLabel
          value={o.name_column ?? "__none"}
          options={[["__none", s.noNames] as const, ...layer.columns.map((c) => [c.name, c.name] as const)]}
          onChange={(c) => set({ name_column: c === "__none" ? null : c })}
        />
      </div>
      <div className="wiz-loc-add">
        <Tick
          isSelected={o.store_top}
          onChange={(on) => set({ store_top: on, top_n: on ? Number(topN) || 3 : 0 })}
        >
          {s.top}
        </Tick>
        {o.store_top && (
          <>
            <TextField
              aria-label={s.topN}
              value={topN}
              onChange={setTopN}
              onBlur={() => set({ top_n: Math.max(1, Number.parseInt(topN, 10) || 1) })}
              className="rl-mini"
            >
              <Input className="input rl-input wiz-num" inputMode="numeric" />
            </TextField>
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
          </>
        )}
      </div>
    </div>
  );
}

const MAP_KEY = "oakbox.layerMap";

function LayerMapToggle({ projectId, name }: { projectId: string; name: string }) {
  const [shown, setShown] = useState(() => {
    try {
      return localStorage.getItem(MAP_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggle = () =>
    setShown((on) => {
      try {
        localStorage.setItem(MAP_KEY, on ? "0" : "1");
      } catch {
        // no storage: the choice lasts until the page closes
      }
      return !on;
    });
  return (
    <>
      <Button className="button wiz-map-toggle" aria-expanded={shown} onPress={toggle}>
        {shown ? <ChevronUp aria-hidden="true" size="1em" /> : <MapIcon aria-hidden="true" size="1em" />}
        {shown ? t.wizard.location.hideMap : t.wizard.location.showMap}
      </Button>
      {shown && <LayerMap projectId={projectId} name={name} />}
    </>
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
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m);
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
