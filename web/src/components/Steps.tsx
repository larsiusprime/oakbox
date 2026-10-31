import { Button } from "react-aria-components";
import type { Job } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { clock } from "../lib/format";
import { t } from "../strings";

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
 * (SPEC §3.2): the Data wizard's frame. */
export function StepFrame({
  steps,
  current,
  go,
  children,
  wide = false,
}: {
  steps: Step[];
  current: string;
  go: (key: string) => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const tops = steps.filter((s) => !s.parent);
  const open = steps.find((s) => s.key === current)?.parent ?? current;
  return (
    <div className={wide ? "wiz wiz-wide" : "wiz"}>
      <ol className="wiz-steps">
        {steps.map((s) => {
          if (s.parent && s.parent !== open) return null;
          const icon = ICONS[s.status];
          return (
            <li
              key={s.key}
              className={["wiz-step", s.parent ? "sub" : "", s.key === current ? "now" : "", s.status].join(
                " ",
              )}
            >
              <button
                type="button"
                disabled={s.disabled}
                onClick={() => go(s.key)}
                aria-current={s.key === current ? "step" : undefined}
              >
                <span className="n" aria-hidden="true">
                  {icon ? (
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
      <div className="wiz-main">{children}</div>
    </div>
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
      <h3>{t.step.running(clock(elapsed), left !== null ? clock(left) : null)}</h3>
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
        {silent ? t.step.silent(clock(job.quiet)) : t.step.alive(clock(Math.max(0, job.elapsed - since)))}
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
