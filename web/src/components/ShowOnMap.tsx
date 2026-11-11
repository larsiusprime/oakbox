/** 🗺 Show on map (SPEC §3.15): beside one of a take-over step's things (a location field, a layer), it shows that
 * one on the map, opening the map if it's closed. Pressed while it's the one shown. */

import { useQuery } from "@tanstack/react-query";
import { Map as MapIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { dockNow, setDock, summonMap } from "../lib/mapdock";
import { setStepPick } from "../lib/mapstep";
import { usePlace } from "../lib/place";
import { t } from "../wording";

export function ShowOnMap({ id, shown, label }: { id: string; shown: boolean; label?: string }) {
  return (
    <Button
      className={shown ? "button button-small show-on-map on" : "button button-small show-on-map"}
      aria-pressed={shown}
      onPress={() => {
        setStepPick(id);
        const d = dockNow();
        setDock(d.out ? { follow: true } : { open: true, follow: true });
      }}
    >
      <MapIcon aria-hidden="true" size="1em" />
      {label ?? (shown ? t.mapWindow.step.onMap : t.mapWindow.step.showOnMap)}
    </Button>
  );
}

/** 🗺 Show on map beside something with a place (a field's values, a problem, a difference): the map opens on it. */
export function SummonMap({ field, label }: { field: string; label?: string }) {
  return (
    <Button className="button button-small show-on-map" onPress={() => summonMap(field)}>
      <MapIcon aria-hidden="true" size="1em" />
      {label ?? t.mapWindow.step.showOnMap}
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
