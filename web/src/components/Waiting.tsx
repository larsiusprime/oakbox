/** Something taking a moment (AGENTS.md: every action acknowledged at once): what it's doing, how long it's been,
 * and a way out. */
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { clock } from "../lib/format";
import { t } from "../wording";

export function Waiting({ doing, onCancel }: { doing: string; onCancel?: () => void }) {
  const [since] = useState(() => Date.now());
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <p className="waiting" role="status">
      <span className="bi-pulse" aria-hidden="true" />
      {doing} · {clock((now - since) / 1000)}
      {onCancel && (
        <Button className="button" onPress={onCancel}>
          {t.step.stop}
        </Button>
      )}
    </p>
  );
}
