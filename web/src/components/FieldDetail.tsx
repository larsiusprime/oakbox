import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Input, Popover, SearchField } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { t } from "../strings";

const d = t.bringIn.detail;

/** "details ▾" beside a field of the parcel universe or the sales record: a number's statistics, or every value
 * with its count (searchable). Notebook 1's "examine in ridiculous detail", one field at a time. */
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
      <Button className="vals-button" aria-label={d.label(field)}>
        {d.button}
        <ChevronDown aria-hidden="true" size="0.85em" />
      </Button>
      <Popover className="popover vals-popover" placement="bottom start">
        <Dialog className="vals-body" aria-label={d.label(field)}>
          {open && <Detail projectId={projectId} set={set} field={field} />}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function Detail({ projectId, set, field }: { projectId: string; set: "universe" | "sales"; field: string }) {
  const [search, setSearch] = useState("");
  const q = useQuery({
    queryKey: ["field-detail", projectId, set, field, search],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/bring-in/fields/{name}/{field}", {
          params: { path: { project_id: projectId, name: set, field }, query: { search } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = q.data;
  const top = Math.max(1, ...(v?.values.map((x) => x.count) ?? [1]));
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
          <p className="vals-sub">{d.summary(v.rows, v.blank, v.distinct, v.kind)}</p>
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
            <div className="vals-scroll">
              <table className="vals-tbl">
                <thead>
                  <tr>
                    <th className="vals-th">{v.kind === "date" ? d.year : t.wizard.values.value}</th>
                    <th className="vals-th vals-n">{t.wizard.values.rows}</th>
                  </tr>
                </thead>
                <tbody>
                  {v.values.map((x) => (
                    <tr key={x.value}>
                      <td className="vals-td mono vals-v">{x.value}</td>
                      <td className="vals-td vals-n">
                        <span
                          className="vals-bar"
                          style={{ width: `${Math.max(2, (100 * x.count) / top)}%` }}
                        />
                        {x.count.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {v.more > 0 && <p className="vals-sub">{t.wizard.values.more(v.more)}</p>}
        </>
      )}
    </>
  );
}
