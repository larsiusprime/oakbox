/** Something taking a moment (AGENTS.md: every action acknowledged at once): what it's doing, how long it's been,
 * and a way out. */
import { hashKey, type QueryKey, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { clock } from "../lib/format";
import { t } from "../wording";
import { showHere } from "./Activity";

/** A screen's first load: Waiting with Stop while it reads; after Stop, Try again. Its query is left out of the
 * corner's Activity pill while it's shown here (one place says it, not two). `sheet`: on the bare wood (the project
 * still loading), on a sheet of paper. */
export function Loading({
  q,
  qkey,
  doing,
  sheet = false,
}: {
  q: { isFetching: boolean; refetch: () => unknown };
  qkey: QueryKey;
  doing: string;
  sheet?: boolean;
}) {
  const qc = useQueryClient();
  const hash = hashKey(qkey);
  useEffect(() => showHere(hash), [hash]);
  const cls = sheet ? "waiting waiting-sheet" : "waiting";
  if (!q.isFetching)
    return (
      <p className={cls}>
        {t.activity.stopped}
        <Button className="button" onPress={() => void q.refetch()}>
          {t.activity.again}
        </Button>
      </p>
    );
  return <Waiting doing={doing} className={cls} onCancel={() => void qc.cancelQueries({ queryKey: qkey })} />;
}

export function Waiting({
  doing,
  onCancel,
  className = "waiting",
}: {
  doing: string;
  onCancel?: () => void;
  className?: string;
}) {
  const [since] = useState(() => Date.now());
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <p className={className} role="status">
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
