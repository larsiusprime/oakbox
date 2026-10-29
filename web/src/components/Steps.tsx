import { Button } from "react-aria-components";
import type { Job } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { Busy, clock } from "../screens/BringIn";
import { t } from "../strings";

/** A step's mark, as on Data (SPEC F3d): ✅ done, ⚠ to look at, ❌ blocks it; blank shows its number. */
export type StepStatus = "done" | "attention" | "blocked" | "blank";
export type Step = { key: string; title: string; status: StepStatus; disabled?: boolean };

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
  return (
    <div className={wide ? "wiz wiz-wide" : "wiz"}>
      <ol className="wiz-steps">
        {steps.map((s, i) => {
          const icon = ICONS[s.status];
          return (
            <li key={s.key} className={["wiz-step", s.key === current ? "now" : "", s.status].join(" ")}>
              <button
                type="button"
                disabled={s.disabled}
                onClick={() => go(s.key)}
                aria-current={s.key === current ? "step" : undefined}
              >
                <span className="n" aria-hidden="true">
                  {icon ? <img src={icon} alt="" className="wiz-step-icon" /> : String(i + 1)}
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
      <h3>{t.bringIn.running(clock(elapsed), left !== null ? clock(left) : null)}</h3>
      <div className="bi-prog">
        <i style={{ width: `${Math.round(100 * fraction)}%` }} />
      </div>
      <ul className="bi-steps">
        {steps.length === 0 && (
          <li className="now">
            <span className="bi-pulse" aria-hidden="true" />
            {t.bringIn.starting}
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
