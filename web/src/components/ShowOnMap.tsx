/** 🗺 Show on map (SPEC §3.15): beside one of a take-over step's things (a location field, a layer), it shows that
 * one on the map, opening the map if it's closed. Pressed while it's the one shown. */

import { useQuery } from "@tanstack/react-query";
import { Map as MapIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { dockNow, setDock, stepKey, summonMap, useDock } from "../lib/mapdock";
import { setStepPick } from "../lib/mapstep";
import { usePlace } from "../lib/place";
import { parseHash } from "../lib/route";
import { t } from "../wording";

export function ShowOnMap({
  id,
  shown,
  label,
  compact,
}: {
  id: string;
  shown: boolean;
  label?: string;
  /** Only the icon (a tight table cell): the label is its name and tooltip. */
  compact?: boolean;
}) {
  const text = label ?? (shown ? t.mapWindow.step.onMap : t.mapWindow.step.showOnMap);
  return (
    <Button
      className={`button button-small show-on-map${shown ? " on" : ""}${compact ? " show-on-map-icon" : ""}`}
      aria-pressed={shown}
      {...(compact ? { "aria-label": text } : {})}
      onPress={() => {
        setStepPick(id);
        const d = dockNow();
        setDock(d.out ? { follow: true } : { open: true, follow: true });
      }}
    >
      <MapIcon aria-hidden="true" size="1em" />
      {compact ? null : text}
    </Button>
  );
}

/** 🗺 Show on map beside something with a place (a field's values, a problem, a difference): the map opens on it. */
export function SummonMap({ field, label, compact }: { field: string; label?: string; compact?: boolean }) {
  const here = useStepHere();
  const d = useDock();
  const shown = !!here && d.follow && d.picks?.[here] === field;
  return (
    <Button
      className={`button button-small show-on-map${shown ? " on" : ""}${compact ? " show-on-map-icon" : ""}`}
      aria-pressed={shown}
      onPress={() => summonMap(field, here)}
      aria-label={label ?? t.mapWindow.step.showOnMap}
    >
      <MapIcon aria-hidden="true" size="1em" />
      {compact ? null : <span className="som-label">{label ?? t.mapWindow.step.showOnMap}</span>}
    </Button>
  );
}

/** The same button, for a step that keeps what's shown itself (Evaluate's group): pressed while it's the one shown. */
export function ShowOnMapButton({
  shown,
  onPress,
  label,
}: {
  shown: boolean;
  onPress: () => void;
  label?: string;
}) {
  return (
    <Button
      className={shown ? "button button-small show-on-map on" : "button button-small show-on-map"}
      aria-pressed={shown}
      onPress={() => {
        onPress();
        const d = dockNow();
        setDock(d.out ? { follow: true } : { open: true, follow: true });
      }}
    >
      <MapIcon aria-hidden="true" size="1em" />
      {label ?? (shown ? t.mapWindow.step.onMap : t.mapWindow.step.showOnMap)}
    </Button>
  );
}

/** 🗺 Map beside a variable (a column of the app's own outputs), when the map has it: the models' parcels first, then
 * the prepared, then as brought in. Nothing when it has none (a category split into columns, say). */
/** A field's Map button, only where the map has it (a field id of the map's: a column from the steps, a 💰 one, a
 * parcel file's); compact in a tight table cell. */
export function MapIfThere({ field, label, compact }: { field: string; label?: string; compact?: boolean }) {
  const projectId = usePlace().where?.projectId ?? "";
  const info = useQuery({
    queryKey: ["map-info", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map", { params: { path: { project_id: projectId } } }),
      ),
    enabled: !!projectId,
    meta: { quiet: true },
  });
  const m = info.data;
  const there =
    !!m &&
    (field.startsWith("sr:")
      ? m.sales.includes(field.slice(3))
      : (m.outs ?? []).some((o) => o.id === field) || m.fields.some((f) => f.id === field));
  return there ? (
    <SummonMap field={field} {...(label ? { label } : {})} {...(compact ? { compact } : {})} />
  ) : null;
}

export function MapVariable({ column }: { column: string }) {
  const projectId = usePlace().where?.projectId ?? "";
  const info = useQuery({
    queryKey: ["map-info", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map", { params: { path: { project_id: projectId } } }),
      ),
    enabled: !!projectId,
    meta: { quiet: true },
  });
  const outs = info.data?.outs ?? [];
  const id = ["modeled", "prepared", "universe"]
    .map((s) => `out:${s}:${column}`)
    .find((x) => outs.some((o) => o.id === x));
  return id ? <SummonMap field={id} label={t.mapWindow.step.mapIt} /> : null;
}

/** The step on screen (project/tab/step), as the map keys a Map button's pick: the Data wizard's from the address,
 * another tab's from its step list. */
function useStepHere(): string | null {
  const place = usePlace();
  const projectId = place.where?.projectId;
  const tab = place.where?.tab ?? null;
  if (!projectId) return null;
  const r = parseHash(typeof window === "undefined" ? "" : window.location.hash);
  const step =
    tab === "fields" ? (r.name === "project" ? (r.step ?? null) : null) : (place.frame?.current ?? null);
  return stepKey(projectId, tab, step);
}
