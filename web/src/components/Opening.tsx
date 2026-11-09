/** A project opening (its details, then its files read for the Data wizard): only the lid with its name and one
 * manila sheet saying what's happening, each file's quick-read copy as it's made, how long it's been, and Cancel.
 * Nothing else to press until it's open: no tabs, no map, no settings. Cancel stops the reading here and goes back to
 * Projects (the server finishes what it's in the middle of on its own; its copies are kept for next time). */
import { hashKey, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { clock, pct } from "../lib/format";
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
        <h2 className="opening-title">{name ? o.title({ name }) : o.titleNoName}</h2>
        <p className="opening-doing" role="status">
          <span className="bi-pulse" aria-hidden="true" />
          {going.length ? o.readingFiles : o.reading} · {clock((now - since) / 1000)}
        </p>
        {going.map((x) => (
          <div key={x.name} className="opening-file">
            <span className="mono">{x.filename}</span>
            <span
              className="engine-bar"
              role="progressbar"
              aria-label={x.filename}
              aria-valuenow={Math.round(x.fraction * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <i style={{ width: `${x.fraction * 100}%` }} />
            </span>
            <small>
              {x.state === "waiting"
                ? o.waiting
                : o.made({ pct: pct(x.fraction), left: x.left == null ? "none" : clock(x.left) })}
            </small>
          </div>
        ))}
        <p className="opening-why">{o.why}</p>
        <div className="opening-foot">
          <Button className="button" onPress={cancel}>
            {o.cancel}
          </Button>
        </div>
      </section>
    </div>
  );
}
