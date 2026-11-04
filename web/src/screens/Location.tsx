import { ScatterplotLayer } from "@deck.gl/layers";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronUp, Map as MapIcon } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { api, type Project, unwrap, type Wizard } from "../api/client";
import { AddButton } from "../components/AddButton";
import { Choice } from "../components/Form";
import { boundsOf, MapView as MapBox, rgba } from "../components/MapView";
import { RemoveButton } from "../components/RemoveButton";
import { ValuesButton } from "../components/ValuesButton";
import { say, t } from "../wording";

const l = t.wizard.location;
const MAP_KEY = "oakbox.locationMap";
type MapView = {
  points: [number, number][];
  middle: [number, number] | null;
  center: [number, number] | null;
};

/** F3d, on the Location step: coordinates OpenAVMKit works out, and the user's own location fields. */
export function LocationExtras({
  project,
  data,
  change,
}: {
  project: Project;
  data: Wizard;
  change: (c: { kind: "location"; name: string; file: string | null; column: string | null }) => void;
}) {
  return (
    <>
      <Coordinates projectId={project.id} hasShapes={data.files.some((f) => f.base && f.geometry)} />
      <LocationFields projectId={project.id} data={data} change={change} />
    </>
  );
}

function Coordinates({ projectId, hasShapes }: { projectId: string; hasShapes: boolean }) {
  const queryClient = useQueryClient();
  const view = useQuery({
    queryKey: ["map", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/map", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled: hasShapes,
  });
  const move = useMutation({
    mutationFn: async (center: { latitude: number; longitude: number } | null) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/center", {
          params: { path: { project_id: projectId } },
          ...(center ? { body: center } : {}),
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(["map", projectId], data),
  });
  const v = view.data as MapView | undefined;
  // Hidden until asked for (it's big), and remembered on this computer.
  const [shown, setShown] = useState(() => {
    try {
      return localStorage.getItem(MAP_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggle = () => {
    setShown((on) => {
      try {
        localStorage.setItem(MAP_KEY, on ? "0" : "1");
      } catch {
        // no storage (a private window): the choice lasts until the page closes
      }
      return !on;
    });
  };
  return (
    <section className="wiz-section">
      <h3 className="wiz-group">{l.coordinates}</h3>
      <ul className="wiz-auto">
        <li>
          <span className="wiz-ok">✓ {l.latlon}</span> <span className="wiz-from">{l.latlonHow}</span>
        </li>
        <li>
          <span className="wiz-ok">✓ {l.polar}</span> <span className="wiz-from">{l.polarHow}</span>
        </li>
      </ul>
      {!hasShapes ? (
        <p className="wiz-note">{l.noShapes}</p>
      ) : v && v.points.length > 0 ? (
        <>
          <Button className="button wiz-map-toggle" aria-expanded={shown} onPress={toggle}>
            {shown ? <ChevronUp aria-hidden="true" size="1em" /> : <MapIcon aria-hidden="true" size="1em" />}
            {shown ? l.hideMap : l.showMap}
          </Button>
          {shown && (
            <ParcelMap view={v} onMove={(lat, lon) => move.mutate({ latitude: lat, longitude: lon })} />
          )}
          <p className="wiz-note">
            {v.center
              ? say.wizard.location.centerSet(v.center[0], v.center[1])
              : shown
                ? l.centerMiddle
                : l.centerMiddleHidden}{" "}
            {v.center && (
              <Button className="button button-small" onPress={() => move.mutate(null)}>
                {l.useMiddle}
              </Button>
            )}
          </p>
        </>
      ) : view.isPending ? (
        <p className="wiz-note">{l.loading}</p>
      ) : (
        <p className="wiz-note">{l.noMap}</p>
      )}
      {(view.error || move.error) && (
        <p className="error" role="alert">
          {(view.error ?? move.error)?.message}
        </p>
      )}
    </section>
  );
}

/** The pin's look: a drop, its point on the place. */
function pinElement(): HTMLElement {
  const el = document.createElement("div");
  el.className = "wiz-pin";
  el.title = l.pinTitle;
  el.appendChild(document.createElement("span"));
  return el;
}

/** The parcels as dots on a street map, and the centre as a pin to drag. */
function ParcelMap({ view, onMove }: { view: MapView; onMove: (lat: number, lon: number) => void }) {
  const [m, setM] = useState<maplibregl.Map | null>(null);
  const pin = useRef<maplibregl.Marker | null>(null);
  const move = useRef(onMove);
  useEffect(() => {
    move.current = onMove;
  }, [onMove]);
  const points = useMemo(() => view.points.map(([lat, lon]) => [lon, lat] as const), [view.points]);
  const layers = useMemo(
    () => [
      new ScatterplotLayer({
        id: "parcels",
        data: points,
        getPosition: (p) => [p[0], p[1]],
        getRadius: 2,
        radiusUnits: "pixels",
        getFillColor: rgba("#1d5bb8", 0.7),
      }),
    ],
    [points],
  );

  // The pin: where the centre is now.
  const at = view.center ?? view.middle;
  const lat = at?.[0];
  const lon = at?.[1];
  useEffect(() => {
    if (!m || lat == null || lon == null) return;
    if (!pin.current) {
      const p = new maplibregl.Marker({ element: pinElement(), draggable: true, anchor: "bottom" })
        .setLngLat([lon, lat])
        .addTo(m);
      p.on("dragend", () => {
        const q = p.getLngLat();
        move.current(q.lat, q.lng);
      });
      pin.current = p;
    } else {
      pin.current.setLngLat([lon, lat]);
    }
  }, [m, lat, lon]);
  useEffect(
    () => () => {
      pin.current?.remove();
      pin.current = null;
    },
    [],
  );

  return (
    <MapBox
      className="wiz-map"
      label={l.mapLabel}
      layers={layers}
      bounds={boundsOf(points)}
      fitKey={String(points.length)}
      scrollZoom={false}
      onMap={setM}
    />
  );
}

/** "market_area" from "MARKET AREA": a starting name the user can change. */
function nameFor(column: string): string {
  const n = column
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(n) ? n : `loc_${n}`;
}

function LocationFields({
  projectId,
  data,
  change,
}: {
  projectId: string;
  data: Wizard;
  change: (c: { kind: "location"; name: string; file: string | null; column: string | null }) => void;
}) {
  const files = data.files.filter((f) => f.holds === "parcels");
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");
  const options = files.flatMap((f) =>
    f.columns.map((c) => {
      const as = data.used[f.name]?.[c.name];
      return [
        `${f.name}\u0000${c.name}`,
        as ? `${c.name} · ${f.name} (${as})` : `${c.name} · ${f.name}`,
      ] as const;
    }),
  );
  const [file, column] = picked ? picked.split("\u0000") : [null, null];
  return (
    <section className="wiz-section">
      <h3 className="wiz-group">{l.fields}</h3>
      <p className="wiz-lede">{l.fieldsLede}</p>
      {data.locations.length > 0 && (
        <div className="entry-list">
          {data.locations.map((x) => (
            <div key={x.name} className="wiz-loc">
              <span className="mono">{x.name}</span>
              <span className="wiz-from">
                {x.column} · <span className="file-label">{x.file}</span>
              </span>
              <span className={x.check.warn ? "wiz-warn" : x.check.ok ? "wiz-ok" : "wiz-warn"}>
                {x.check.text}
              </span>
              <ValuesButton
                projectId={projectId}
                file={x.file}
                column={x.column}
                distinct={x.distinct}
                noun={l.areas({ n: x.distinct ?? 0 })}
              />
              <RemoveButton
                what={x.name}
                onPress={() => change({ kind: "location", name: x.name, file: null, column: null })}
                undo={() => change({ kind: "location", name: x.name, file: x.file, column: x.column })}
              />
            </div>
          ))}
        </div>
      )}
      <form
        className="wiz-loc-add"
        onSubmit={(e) => {
          e.preventDefault();
          if (file && column && name) {
            change({ kind: "location", name, file, column });
            setPicked(null);
            setName("");
          }
        }}
      >
        <Choice
          label={l.column}
          hideLabel
          value={picked}
          placeholder={l.pickColumn}
          options={options}
          onChange={(v) => {
            setPicked(v);
            setName(nameFor(v.split("\u0000")[1] ?? ""));
          }}
        />
        <TextField aria-label={l.name} value={name} onChange={setName} className="rl-mini">
          <Input className="input rl-input" placeholder={l.namePlaceholder} />
        </TextField>
        <AddButton type="submit" isDisabled={!file || !name}>
          {l.add}
        </AddButton>
      </form>
    </section>
  );
}
