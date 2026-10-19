import { ProgressBar } from "react-aria-components";

type Props = { fraction: number | null; label: string };

/** A sunken track with a raised fill. Indeterminate (striped) when the fraction is unknown. */
export function Progress({ fraction, label }: Props) {
  const indeterminate = fraction === null;
  return (
    <ProgressBar
      className="progress"
      aria-label={label}
      isIndeterminate={indeterminate}
      {...(indeterminate ? {} : { value: Math.round(fraction * 100) })}
    >
      {({ percentage }) => (
        <>
          <div className="progress-track">
            <div
              className={indeterminate ? "progress-fill progress-fill-indeterminate" : "progress-fill"}
              style={indeterminate ? undefined : { width: `${percentage ?? 0}%` }}
            />
          </div>
          <div className="progress-label">
            <span>{label}</span>
            {!indeterminate && <span className="progress-pct">{Math.round(percentage ?? 0)}%</span>}
          </div>
        </>
      )}
    </ProgressBar>
  );
}
