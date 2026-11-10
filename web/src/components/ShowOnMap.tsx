/** 🗺 Show on map (SPEC §3.15): beside one of a take-over step's things (a location field, a layer), it shows that
 * one on the map, opening the map if it's closed. Pressed while it's the one shown. */
import { Map as MapIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { dockNow, setDock, summonMap } from "../lib/mapdock";
import { setStepPick } from "../lib/mapstep";
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
