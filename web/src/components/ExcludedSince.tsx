/** Sales excluded since a step ran (Check sales' review, Outliers): said quietly, never making the step out of date
 * (SPEC F6, 2026-11-11): what's after it leaves them out from now on; this step's results still have them until it
 * runs again, which is offered, not asked. */
import { Button } from "react-aria-components";
import { t } from "../wording";

export function ExcludedSince({
  n,
  run,
  check,
}: {
  n: number | undefined;
  run?: () => void;
  check?: boolean;
}) {
  if (!n) return null;
  return (
    <p className="wiz-from excluded-since">
      {check ? t.step.excludedSinceCheck({ n }) : t.step.excludedSince({ n })}{" "}
      {run && (
        <Button className="button button-small" onPress={run}>
          {t.step.runAgain}
        </Button>
      )}
    </p>
  );
}
