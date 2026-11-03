import { useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import type { Job } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { type Landing, say, t } from "../copy";
import { clock } from "../lib/format";
import { currentWhere, type FrameStep, markSeen, OVERVIEW, publishFrame, seen } from "../lib/place";

/** A step's mark, as on Data (SPEC F3d): ✅ done, ⚠ to look at, ❌ blocks it; blank shows its number. */
export type StepStatus = "done" | "attention" | "blocked" | "blank";
/** parent: a step nested under another (a major step's parts), shown while the major step or one of its parts is
 * open. */
export type Step = { key: string; title: string; status: StepStatus; disabled?: boolean; parent?: string };

const ICONS: Record<StepStatus, string | null> = {
  done: resolvedIcon,
  attention: warningIcon,
  blocked: blockingIcon,
  blank: null,
};

/** Every tab is a list of steps on the left, one task at a time on the right, Back and Next at the bottom right
 * (SPEC §3.2): the Data wizard's frame. landing: the tab's landing page (t.landing.pages), an Overview above its
 * steps, open the first time the tab is (SPEC D21); it covers the step that's open, and Start goes on to it. */
export function StepFrame({
  steps,
  current,
  go,
  children,
  wide = false,
  landing,
}: {
  steps: Step[];
  current: string;
  go: (key: string) => void;
  children: React.ReactNode;
  wide?: boolean;
  landing?: string;
}) {
  // The landing page covers the steps until one is opened (its own page has nothing else to press).
  const [over, setOver] = useState(() => {
    const w = currentWhere();
    return !!landing && !!w && !seen(w.projectId, landing);
  });
  const showing = !!landing && over;
  useEffect(() => {
    const w = currentWhere();
    if (showing && landing && w) markSeen(w.projectId, landing);
  }, [showing, landing]);
  const goTo = (k: string) => {
    if (k === OVERVIEW) {
      setOver(true);
      return;
    }
    setOver(false);
    go(k);
  };
  const listed: Step[] = landing
    ? [{ key: OVERVIEW, title: t.landing.overview, status: "blank" }, ...steps]
    : steps;
  const now = showing ? OVERVIEW : current;
  const tops = steps.filter((s) => !s.parent);
  const open = steps.find((s) => s.key === current)?.parent ?? current;
  useFrame(listed, now, goTo);
  const page = landing ? t.landing.pages[landing] : undefined;
  return (
    <div className={wide && !showing ? "wiz wiz-wide" : "wiz"}>
      <ol className="wiz-steps">
        {listed.map((s) => {
          if (s.parent && s.parent !== open) return null;
          const icon = ICONS[s.status];
          return (
            <li
              key={s.key}
              className={["wiz-step", s.parent ? "sub" : "", s.key === now ? "now" : "", s.status].join(" ")}
            >
              <button
                type="button"
                disabled={s.disabled}
                onClick={() => goTo(s.key)}
                aria-current={s.key === now ? "step" : undefined}
              >
                <span className="n" aria-hidden="true">
                  {s.key === OVERVIEW ? (
                    LANDING_MARK
                  ) : icon ? (
                    <img src={icon} alt="" className="wiz-step-icon" />
                  ) : s.parent ? (
                    ""
                  ) : (
                    String(tops.indexOf(s) + 1)
                  )}
                </span>
                {s.title}
              </button>
            </li>
          );
        })}
      </ol>
      <div className="wiz-main">
        {showing && page ? (
          <LandingPage
            page={page}
            start={steps.find((s) => s.key === current)?.title ?? ""}
            onStart={() => setOver(false)}
          />
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/** How a landing page is marked in a step list: an introduction, never done or to look at. */
export const LANDING_MARK = "◆";

/** A major step's landing page (SPEC D21): what it's for, what happens in it, what you'll decide and end with, what
 * it needs; Start goes on to its first step. */
export function LandingPage({
  page,
  kicker,
  start,
  onStart,
  back,
}: {
  page: Landing;
  kicker?: string;
  start: string;
  onStart: () => void;
  back?: (() => void) | null;
}) {
  const l = t.landing;
  const list = (title: string, items: string[]) => (
    <section className="land-sec">
      <h3>{title}</h3>
      <ul>
        {items.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </section>
  );
  return (
    <>
      <div className="wiz-body land">
        <p className="wiz-kicker">{kicker ?? page.kicker}</p>
        <h2 className="wiz-q">{page.title}</h2>
        <p className="wiz-lede">{page.lede}</p>
        <div className="land-cols">
          {list(l.happens, page.happens)}
          {list(l.decide, page.decide)}
          {list(l.end, page.end)}
        </div>
        <p className="land-needs">
          <b>{l.needs}</b> {page.needs}
        </p>
      </div>
      <StepFoot back={back ?? null} next={{ label: l.start({ step: start }), onPress: onStart }} />
    </>
  );
}

/** One step's page: its question or title, then what it asks. flush: no padding, for a builder that fills it. */
export function StepBody({
  kicker,
  title,
  lede,
  flush = false,
  children,
}: {
  kicker?: string;
  title?: string;
  lede?: string;
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={flush ? "wiz-body wiz-flush" : "wiz-body"}>
      {kicker && <p className="wiz-kicker">{kicker}</p>}
      {title && <h2 className="wiz-q">{title}</h2>}
      {lede && <p className="wiz-lede">{lede}</p>}
      {children}
    </div>
  );
}

export type Action = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  primary?: boolean;
};

/** Back, then what moves on, always at the bottom right; extra (a second choice) goes before them. */
export function StepFoot({
  back,
  next,
  extra = [],
  note,
}: {
  back?: (() => void) | null;
  next?: Action | null;
  extra?: Action[];
  note?: React.ReactNode;
}) {
  return (
    <div className="wiz-foot">
      {note && <span className="wiz-foot-note">{note}</span>}
      <span className="wiz-grow" />
      {back && (
        <Button className="button" onPress={back}>
          {t.wizard.back}
        </Button>
      )}
      {extra.map((a) => (
        <Button
          key={a.label}
          className={a.primary ? "button button-primary" : "button"}
          isDisabled={!!a.disabled}
          onPress={a.onPress}
        >
          {a.label}
        </Button>
      ))}
      {next && (
        <Button
          className={next.primary === false ? "button" : "button button-primary"}
          isDisabled={!!next.disabled}
          onPress={next.onPress}
        >
          {next.label}
        </Button>
      )}
    </div>
  );
}

/** A run in progress: the parts done, the one it's on (with what it's doing inside it), the clock. */
export function RunProgress({
  job,
  lastSeconds,
  skip = () => {},
}: {
  job: Job | null | undefined;
  lastSeconds?: number | null;
  skip?: (part: string) => void;
}) {
  const steps = job?.steps ?? [];
  const fraction = [...steps].reverse().find((x) => x.fraction !== null)?.fraction ?? 0.02;
  const elapsed = job?.elapsed ?? 0;
  const left = lastSeconds && elapsed < lastSeconds ? lastSeconds - elapsed : null;
  return (
    <div className="bi-card">
      <h3>{say.step.running(clock(elapsed), left !== null ? clock(left) : null)}</h3>
      <div className="bi-prog">
        <i style={{ width: `${Math.round(100 * fraction)}%` }} />
      </div>
      <ul className="bi-steps">
        {steps.length === 0 && (
          <li className="now">
            <span className="bi-pulse" aria-hidden="true" />
            {t.step.starting}
          </li>
        )}
        {steps.map((x, i) => {
          const now = i === steps.length - 1;
          return (
            <li key={x.step} className={now ? "now" : "done"}>
              {now ? <span className="bi-pulse" aria-hidden="true" /> : "✓ "}
              {x.message}
              {now && job && <Busy job={job} since={x.at} skip={skip} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The step that's running, in detail: what it's doing, how far through, how long it's taken, that the run is
 * still alive (it says so every 2 seconds), and Skip for a step that can be left out. */
function Busy({ job, since, skip }: { job: Job; since: number; skip: (part: string) => void }) {
  const skipping = job.part !== null && job.skipping.includes(job.part);
  // Two missed heartbeats and more: it may be stuck (a frozen process says nothing at all).
  const silent = job.quiet > 10;
  return (
    <div className="bi-busy">
      {job.detail && <span className="bi-detail">{job.detail}</span>}
      {job.sub !== null && (
        <span className="bi-prog bi-sub">
          <i style={{ width: `${Math.round(100 * job.sub)}%` }} />
        </span>
      )}
      <span className={silent ? "wiz-warn" : "bi-alive"}>
        {silent
          ? t.step.silent({ quiet: clock(job.quiet) })
          : t.step.alive({ inStep: clock(Math.max(0, job.elapsed - since)) })}
      </span>
      {job.part && (
        <Button className="button bi-skip" isDisabled={skipping} onPress={() => job.part && skip(job.part)}>
          {skipping ? t.step.skipping : t.step.skip}
        </Button>
      )}
      {job.part && !skipping && <span className="bi-skip-note">{t.step.skipNote}</span>}
    </div>
  );
}

/** Tells the plate (lib/place) which steps are on screen and which is open, and remembers it as the tab's place; a
 * remembered step that can't be opened now falls back to the first that can. */
export function useFrame(steps: FrameStep[], current: string, go: (key: string) => void): void {
  const goRef = useRef(go);
  const [me] = useState(() => ({}));
  useEffect(() => {
    goRef.current = go;
  });
  const sig = JSON.stringify([
    steps.map((s) => [s.key, s.title, s.status, !!s.disabled, s.parent ?? ""]),
    current,
  ]);
  useEffect(() => {
    const [list, now] = JSON.parse(sig) as [[string, string, string, boolean, string][], string];
    const shown: FrameStep[] = list.map(([key, title, status, disabled, parent]) => ({
      key,
      title,
      status,
      disabled,
      ...(parent ? { parent } : {}),
    }));
    const open = shown.find((s) => s.key === now);
    if (!open || open.disabled) {
      const first = shown.find((s) => !s.disabled && s.key !== OVERVIEW);
      if (first && first.key !== now) {
        goRef.current(first.key);
        return;
      }
    }
    publishFrame({ steps: shown, current: now, go: (k) => goRef.current(k) }, me);
  }, [sig, me]);
  useEffect(() => () => publishFrame(null, me), [me]);
}
