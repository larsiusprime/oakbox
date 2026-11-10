/** A take-over step's instruction card (SPEC §3.15): at the top of a step whose work is on the map, one imperative
 * sentence, said the same way on the map's banner (hovering here flashes it). With the map closed, or not showing the
 * step, it says so and offers to show it. */
import { Map as MapIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { setDock, useDock } from "../lib/mapdock";
import { flashBanner } from "../lib/mapstep";
import { t } from "../wording";

const w = t.mapWindow.step;

export function MapInstruction({ title, sub }: { title: string; sub?: string }) {
  const dock = useDock();
  const shown = dock.open || dock.out;
  const following = dock.follow;
  return (
    <div className="map-instr" role="note" onMouseEnter={flashBanner}>
      <MapIcon className="map-instr-icon" aria-hidden="true" size="1.4em" />
      <div className="map-instr-text">
        <b>{!shown ? w.closed : !following ? w.notShowing : title}</b>
        <span>{!shown ? w.closedSub : !following ? w.notShowingSub : sub}</span>
      </div>
      {!shown && (
        <Button
          className="button button-primary map-instr-show"
          onPress={() => setDock({ open: true, follow: true })}
        >
          {w.show}
        </Button>
      )}
      {shown && !following && (
        <Button className="button map-instr-show" onPress={() => setDock({ follow: true })}>
          {w.showHere}
        </Button>
      )}
    </div>
  );
}
