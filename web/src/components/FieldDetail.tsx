import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Input, Popover, SearchField } from "react-aria-components";
import { api, type Histogram, unwrap } from "../api/client";
import { say, t } from "../wording";
import { type ValueSort, ValueTable } from "./ValueTable";

const d = t.bringIn.detail;

/** A field of the parcel universe or the sales record, as its own name: pressing it shows a number's statistics, or
 * every value with its count (searchable). Notebook 1's "examine in ridiculous detail", one field at a time. Its row
 * opens it too (see `openRow`), so one motif marks every field as inspectable. */
export function FieldDetail({
  projectId,
  set,
  field,
}: {
  projectId: string;
  set: "universe" | "sales";
  field: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <DialogTrigger isOpen={open} onOpenChange={setOpen}>
      <Button className="fd-name" aria-label={d.label({ field })}>
        {field}
        <Search aria-hidden="true" size="0.85em" className="fd-icon" />
      </Button>
      <Popover className="popover vals-popover" placement="bottom start">
        <Dialog className="vals-body" aria-label={d.label({ field })}>
          {open && <Detail projectId={projectId} set={set} field={field} />}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

/** A click anywhere on a field's row opens its details (not one inside the popover, whose clicks bubble through React). */
export function openRow(e: React.MouseEvent<HTMLElement>) {
  const target = e.target as HTMLElement;
  if (!e.currentTarget.contains(target) || target.closest("button, a, input")) return;
  e.currentTarget.querySelector<HTMLButtonElement>(".fd-name")?.click();
}

function Detail({ projectId, set, field }: { projectId: string; set: "universe" | "sales"; field: string }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<ValueSort>(null);
  const q = useQuery({
    queryKey: ["field-detail", projectId, set, field, search, sort],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/bring-in/fields/{name}/{field}", {
          params: {
            path: { project_id: projectId, name: set, field },
            query: { search, ...(sort ? { sort: sort.by, desc: sort.desc } : {}) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = q.data;
  return (
    <>
      <Heading slot="title" className="vals-title">
        <span className="mono">{field}</span>{" "}
        <span className="vals-file">· {set === "universe" ? d.universe : d.sales}</span>
      </Heading>
      {!v ? (
        <p className="vals-sub">{q.error?.message ?? t.wizard.values.loading}</p>
      ) : (
        <>
          <p className="vals-sub">{say.bringIn.detail.summary(v.rows, v.blank, v.distinct, v.kind)}</p>
          {v.stats.length > 0 && (
            <dl className="fd-stats">
              {v.stats.map((s) => (
                <div key={s.label} className="fd-stat">
                  <dt>{s.label}</dt>
                  <dd>{s.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {v.histogram && <Spread h={v.histogram} years={field.includes("year")} />}
          {v.distinct > 12 && (
            <SearchField
              aria-label={t.wizard.values.search}
              value={search}
              onChange={setSearch}
              className="vals-search"
            >
              <Input className="input vals-search-input" placeholder={t.wizard.values.search} />
            </SearchField>
          )}
          {v.values.length > 0 && (
            <ValueTable
              values={v.values}
              valueLabel={v.kind === "date" ? d.year : undefined}
              natural={v.kind === "date" ? "value" : "count"}
              sort={sort}
              onSort={setSort}
            />
          )}
          {v.more > 0 && <p className="vals-sub">{t.wizard.values.more({ n: v.more })}</p>}
        </>
      )}
    </>
  );
}

/** How a number's values spread: a bar per bin over the middle 98% (lowest and highest 1% counted apart), zeros
 * said apart; a log scale when the values span orders of magnitude. Each bar says its range and count on hover. */
function Spread({ h, years }: { h: Histogram; years: boolean }) {
  const top = Math.max(1, ...h.counts);
  const n = h.counts.length;
  const fmt = (x: number) =>
    years
      ? String(Math.round(x))
      : new Intl.NumberFormat(undefined, {
          notation: Math.abs(x) >= 10_000 ? "compact" : "standard",
          maximumSignificantDigits: 3,
        }).format(x);
  const mid = h.log
    ? Math.sqrt((h.edges[0] ?? 0) * (h.edges[n] ?? 0))
    : ((h.edges[0] ?? 0) + (h.edges[n] ?? 0)) / 2;
  const notes = [
    h.below + h.above > 0 ? say.bringIn.detail.outside(h.below, h.above) : null,
    h.zeros > 0 ? d.zeros({ n: h.zeros }) : null,
    h.log ? d.log : null,
  ].filter(Boolean);
  return (
    <figure className="fd-hist">
      <svg viewBox={`0 0 ${n} 40`} preserveAspectRatio="none" role="img" aria-label={d.histogram}>
        {h.counts.map((c, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: bins by position
          <rect key={i} x={i + 0.06} width={0.88} y={40 - (38 * c) / top} height={(38 * c) / top}>
            <title>{d.bin({ from: fmt(h.edges[i] ?? 0), to: fmt(h.edges[i + 1] ?? 0), n: c })}</title>
          </rect>
        ))}
      </svg>
      <div className="fd-axis">
        <span>{fmt(h.edges[0] ?? 0)}</span>
        <span>{fmt(mid)}</span>
        <span>{fmt(h.edges[n] ?? 0)}</span>
      </div>
      {notes.length > 0 && <figcaption className="vals-sub">{notes.join(" · ")}</figcaption>}
    </figure>
  );
}
