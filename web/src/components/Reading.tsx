/** A CSV's quick-read copy (SPEC §5): made once when the file is added, so its columns open in a moment. While it's
 * made, on the file's entry: how far, about how long to go, and Stop. Nothing waits on it: the file is read as it is
 * meanwhile. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { clock, pct } from "../lib/format";
import { t } from "../wording";
import { SmallButton } from "./Buttons";

type Reading = components["schemas"]["Reading"];
const r = t.reading;
const going = (x: Reading) => x.state === "reading" || x.state === "waiting";

export function useReadings(projectId: string) {
  return useQuery({
    queryKey: ["reading", projectId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/projects/{project_id}/reading", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
    meta: { quiet: true }, // its own progress
    refetchInterval: (q) => (q.state.data?.some(going) ? 1000 : false),
  });
}

function useAct(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, act }: { name: string; act: "stop" | "start" }) =>
      unwrap(
        await api.POST(`/api/projects/{project_id}/reading/{name}/${act}`, {
          params: { path: { project_id: projectId, name } },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(["reading", projectId], data),
  });
}

/** On a file's entry: its copy being made, stopped or failed. Nothing once it's made (or for a file that isn't a CSV). */
export function ReadingLine({ projectId, name }: { projectId: string; name: string }) {
  const q = useReadings(projectId);
  const act = useAct(projectId);
  const x = q.data?.find((f) => f.name === name);
  if (!x || x.state === "ready" || x.state === "none") return null;
  const file = x.filename;
  if (x.state === "stopped" || x.state === "failed")
    return (
      <span className="engine-progress reading">
        <span className="wiz-from">
          {x.state === "stopped" ? r.stopped({ file }) : r.failed({ file, error: x.error ?? "" })}
        </span>
        <SmallButton isDisabled={act.isPending} onPress={() => act.mutate({ name, act: "start" })}>
          {r.again}
        </SmallButton>
      </span>
    );
  return (
    <span className="engine-progress reading" role="status" title={r.why}>
      <span
        className="engine-bar"
        role="progressbar"
        aria-valuenow={Math.round(x.fraction * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <i style={{ width: `${x.fraction * 100}%` }} />
      </span>
      <span>
        {x.state === "waiting"
          ? r.waiting({ file })
          : r.making({ file, pct: pct(x.fraction), left: x.left == null ? "none" : clock(x.left) })}
      </span>
      <SmallButton isDisabled={act.isPending} onPress={() => act.mutate({ name, act: "stop" })}>
        {r.stop}
      </SmallButton>
    </span>
  );
}
