/** A project opening (its details, then its files read for the Data wizard): only the lid with its name and one
 * manila sheet: Opening Project "<name>"…, a loading bar, the time elapsed, and Cancel.
 * Nothing else to press until it's open: no tabs, no map, no settings. Cancel stops the reading here and goes back to
 * Projects (the server finishes what it's in the middle of on its own; its copies are kept for next time). */
import { hashKey, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { clock } from "../lib/format";
import { navigate } from "../lib/route";
import { t } from "../wording";
import { showHere } from "./Activity";
import { OakBand } from "./OakBand";
import { useReadings } from "./Reading";

const o = t.opening;

export function Opening({ projectId, name }: { projectId: string; name: string | null }) {
  const qc = useQueryClient();
  const readings = useReadings(projectId).data ?? [];
  const going = readings.filter((x) => x.state === "reading" || x.state === "waiting");
  const fraction = going.length ? going.reduce((a, x) => a + x.fraction, 0) / going.length : 0;
  // Said here, not also in the corner's Activity pill.
  useEffect(() => {
    const off = [showHere(hashKey(["project", projectId])), showHere(hashKey(["wizard", projectId]))];
    return () => {
      for (const f of off) f();
    };
  }, [projectId]);
  const [since] = useState(() => Date.now());
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const cancel = () => {
    void qc.cancelQueries({ queryKey: ["project", projectId] });
    void qc.cancelQueries({ queryKey: ["wizard", projectId] });
    navigate({ name: "home" });
  };
  return (
    <div className="project opening">
      <OakBand page={{ kind: "opening", name: name ?? "" }} />
      <section
        className="folder-panel opening-sheet"
        aria-busy="true"
        aria-label={o.title({ name: name ?? "" })}
      >
        <p className="opening-title">{o.title({ name: name ?? "…" })}</p>
        <div className="opening-row">
          {/* How far, while files' quick-read copies are made (the one measure there is); else a bar that moves. */}
          <span
            className={`engine-bar opening-bar ${going.length ? "" : "opening-bar-busy"}`}
            role="progressbar"
            aria-label={o.title({ name: name ?? "" })}
            {...(going.length
              ? { "aria-valuenow": Math.round(fraction * 100), "aria-valuemin": 0, "aria-valuemax": 100 }
              : {})}
          >
            <i style={going.length ? { width: `${fraction * 100}%` } : undefined} />
          </span>
          <span className="opening-time">{clock((now - since) / 1000)}</span>
          <Button className="button" onPress={cancel}>
            {o.cancel}
          </Button>
        </div>
      </section>
    </div>
  );
}
