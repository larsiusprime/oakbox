/** The computer check (SPEC §5): on first run, before the projects page, and again from Settings or when the
 * computer's memory or cores change. Each line fills in as its check finishes; then the tier, why, and the settings
 * it recommends. */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { api, type MachineFound, type MachineView, unwrap } from "../api/client";
import { OakBand } from "../components/OakBand";
import { choiceLabel, TIER_PILL } from "../components/SettingsDialog";
import { drawTest, openSettings, renderer } from "../lib/machine";
import { say, t } from "../wording";

const m = t.machine;

type Basics = Pick<
  MachineFound,
  "memory_gb" | "memory_free_gb" | "cores" | "threads" | "processor" | "remote"
>;
type Graphics = { graphics: string | null; draw_ms: number | null };

export function MachineCheck({
  again,
  onDone,
}: {
  again: "first" | "changed" | "asked";
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [basics, setBasics] = useState<Basics | null>(null);
  const [graphics, setGraphics] = useState<Graphics | null>(null);
  const [speed, setSpeed] = useState<number | null | undefined>(undefined);
  const [disk, setDisk] = useState<number | null | undefined>(undefined);
  const [result, setResult] = useState<MachineView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);
  const before = useRef(queryClient.getQueryData<MachineView>(["machine"])?.machine?.tier ?? null);

  const save = async (found: MachineFound) => {
    const view = unwrap(await api.PUT("/api/machine", { body: found }));
    queryClient.setQueryData(["machine"], view);
    return view;
  };

  // The checks, one after another; each line fills in as its check finishes. Once (React's dev mode mounts twice).
  const started = useRef(false);
  const runChecks = useEffectEvent(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      try {
        const b = unwrap(await api.POST("/api/machine/basics"));
        setBasics(b);
        const name = renderer();
        const ms = name ? await drawTest() : null;
        const g = { graphics: name, draw_ms: ms };
        setGraphics(g);
        if (cancelled.current) return;
        const s = unwrap(await api.POST("/api/machine/speed")).speed;
        setSpeed(s);
        if (cancelled.current) return;
        const d = unwrap(await api.POST("/api/machine/disk")).disk_mb_s;
        setDisk(d);
        if (cancelled.current) return;
        const view = await save({ ...b, ...g, speed: s, disk_mb_s: d, cancelled: false });
        // Checked again because the computer changed, and its tier didn't: nothing to say.
        if (again === "changed" && view.machine?.tier === before.current) onDone();
        else setResult(view);
      } catch (e) {
        setError(String(e instanceof Error ? e.message : e));
      }
    })();
  });
  useEffect(() => runChecks(), []);

  const cancel = async () => {
    cancelled.current = true;
    const cores = navigator.hardwareConcurrency || 1;
    await save({
      ...(basics ?? { memory_gb: 0, cores, threads: cores, processor: "", remote: false }),
      ...(graphics ?? {}),
      cancelled: true,
    });
    onDone();
  };

  const mach = result?.machine;
  const rec = result?.recommended;
  return (
    <>
      <OakBand page={{ kind: "check" }} />
      <div className="panel mc">
        <h2 className="mc-title">{m.title}</h2>
        {!result && <p className="mc-lede">{again === "changed" ? m.changed : m.lede}</p>}
        <dl className="mc-checks">
          <Line label={m.memory} done={!!basics}>
            {basics && (
              <>
                {m.memoryValue({ gb: basics.memory_gb })}
                <small>
                  {basics.memory_free_gb != null && m.memoryFree({ gb: basics.memory_free_gb })}
                  {basics.remote && ` · ${m.remote}`}
                </small>
              </>
            )}
          </Line>
          <Line label={m.processor} done={!!basics}>
            {basics && (
              <>
                {basics.processor || m.processorValue({ cores: basics.cores })}
                {basics.processor && <small>{m.processorValue({ cores: basics.cores })}</small>}
              </>
            )}
          </Line>
          <Line label={m.speed} done={speed !== undefined}>
            {speed != null && (
              <>
                {speed}
                <small>{m.speedNote}</small>
              </>
            )}
          </Line>
          <Line label={m.disk} done={disk !== undefined}>
            {disk === null ? (
              <small>{m.diskNone}</small>
            ) : (
              disk !== undefined && (
                <>
                  {m.diskValue({ mbs: disk })}
                  <small>{m.diskNote}</small>
                </>
              )
            )}
          </Line>
          <Line label={m.graphics} done={!!graphics}>
            {graphics &&
              (graphics.graphics ? (
                <>
                  {graphics.graphics}
                  <small>
                    {mach?.graphics_software
                      ? m.graphicsSoftware
                      : graphics.draw_ms != null &&
                        m.graphicsDrew({ s: (graphics.draw_ms / 1000).toFixed(1) })}
                  </small>
                </>
              ) : (
                <small>{m.graphicsNone}</small>
              ))}
          </Line>
        </dl>
        {error && (
          <p className="error" role="alert">
            {m.failed({ error })}
          </p>
        )}
        {mach && rec && (
          <>
            <div className="mc-tier">
              <span className={`pill mc-tier-pill ${TIER_PILL[mach.tier]}`}>
                {m.tier({ tier: mach.tier })}
              </span>
              <p>{say.machineWhy(mach, result.memory_for_oakbox_gb)}</p>
            </div>
            <dl className="mc-recs">
              <dt>{t.settings.folds}</dt>
              <dd>{choiceLabel("fold_workers", rec.fold_workers, result.cores_workers)}</dd>
              <dt>{t.settings.maps}</dt>
              <dd>{choiceLabel("maps", rec.maps)}</dd>
              <dt>{t.settings.detail}</dt>
              <dd>{choiceLabel("map_detail", rec.map_detail)}</dd>
              <dt>{t.settings.street}</dt>
              <dd>{choiceLabel("street_map", rec.street_map)}</dd>
            </dl>
            {mach.graphics_software && <p className="mc-note">{m.whySoftware}</p>}
          </>
        )}
        <div className="form-actions mc-actions">
          {result ? (
            <>
              <Button className="button button-primary" onPress={onDone} autoFocus>
                {m.use}
              </Button>
              <Button
                className="button"
                onPress={() => {
                  onDone();
                  openSettings("performance");
                }}
              >
                {m.change}
              </Button>
            </>
          ) : (
            <Button className="button" onPress={() => void cancel()}>
              {m.cancel}
            </Button>
          )}
        </div>
      </div>
    </>
  );
}

function Line({ label, done, children }: { label: string; done: boolean; children: React.ReactNode }) {
  return (
    <div className="mc-line">
      <span className={done ? "mc-tick" : "mc-tick mc-wait"} aria-hidden="true">
        {done ? "✓" : "…"}
      </span>
      <dt>{label}</dt>
      <dd>{done ? children : <span className="mc-checking">{m.checking}</span>}</dd>
    </div>
  );
}
