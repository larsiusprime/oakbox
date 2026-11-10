/** 🗺 Show on map (SPEC §3.15): beside one of a take-over step's things (a location field, a layer), it shows that
 * one on the map, opening the map if it's closed. Pressed while it's the one shown. */
import { Map as MapIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { dockNow, setDock } from "../lib/mapdock";
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
