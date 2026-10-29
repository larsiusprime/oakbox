import "leaflet/dist/leaflet.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import { ChevronUp, Map as MapIcon, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { api, type Project, unwrap, type Wizard } from "../api/client";
import { addBasemap } from "../components/basemap";
import { Choice } from "../components/Form";
import { ValuesButton } from "../components/ValuesButton";
import { t } from "../strings";

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
            {v.center ? l.centerSet(v.center[0], v.center[1]) : shown ? l.centerMiddle : l.centerMiddleHidden}{" "}
            {v.center && (
              <Button className="wiz-link" onPress={() => move.mutate(null)}>
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

const PIN = L.divIcon({
  className: "wiz-pin",
  html: "<span></span>",
  iconSize: [22, 22],
  iconAnchor: [11, 22],
});

/** The parcels as dots on a street map, and the centre as a pin to drag. */
function ParcelMap({ view, onMove }: { view: MapView; onMove: (lat: number, lon: number) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pin = useRef<L.Marker | null>(null);
  const move = useRef(onMove);
  useEffect(() => {
    move.current = onMove;
  }, [onMove]);

  // The map and its dots, once.
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { preferCanvas: true, scrollWheelZoom: false });
    addBasemap(m);
    const renderer = L.canvas();
    for (const [lat, lon] of view.points) {
      L.circleMarker([lat, lon], {
        renderer,
        radius: 2,
        weight: 0,
        fillOpacity: 0.7,
        fillColor: "#1d5bb8",
      }).addTo(m);
    }
    m.fitBounds(L.latLngBounds(view.points), { padding: [12, 12] });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      pin.current = null;
    };
  }, [view.points]);

  // The pin: where the centre is now.
  const at = view.center ?? view.middle;
  useEffect(() => {
    const m = map.current;
    if (!m || !at) return;
    if (!pin.current) {
      pin.current = L.marker(at, { draggable: true, icon: PIN, title: l.pinTitle, keyboard: true }).addTo(m);
      pin.current.on("dragend", () => {
        const p = pin.current?.getLatLng();
        if (p) move.current(p.lat, p.lng);
      });
    } else {
      pin.current.setLatLng(at);
    }
  }, [at]);

  return <div ref={el} className="wiz-map" role="img" aria-label={l.mapLabel} />;
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
        <div className="wiz-grid">
          {data.locations.map((x) => (
            <div key={x.name} className="wiz-loc">
              <span className="mono">{x.name}</span>
              <span className="wiz-from">
                {x.column} · {x.file}
              </span>
              <span className={x.check.warn ? "wiz-warn" : x.check.ok ? "wiz-ok" : "wiz-warn"}>
                {x.check.text}
              </span>
              <ValuesButton
                projectId={projectId}
                file={x.file}
                column={x.column}
                distinct={x.distinct}
                noun={l.areas(x.distinct ?? 0)}
              />
              <Button
                className="rc-x"
                aria-label={l.remove(x.name)}
                onPress={() => change({ kind: "location", name: x.name, file: null, column: null })}
              >
                <X size="0.9em" />
              </Button>
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
        <Button type="submit" className="button" isDisabled={!file || !name}>
          {l.add}
        </Button>
      </form>
    </section>
  );
}
