import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Input, Popover, SearchField } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { t } from "../strings";

const v = t.wizard.values;

/** "33 values ▾" beside a field: opens every value of its column with how many rows have each, searchable.
 * The one way the wizard shows what a column holds, so rows stay short however many values there are. */
export function ValuesButton({
  projectId,
  file,
  column,
  distinct,
  noun,
}: {
  projectId: string;
  file: string;
  column: string;
  distinct: number | null | undefined;
  /** "areas" for a location field; "values" otherwise. */
  noun?: string;
}) {
  const [open, setOpen] = useState(false);
  if (distinct == null) return null;
  return (
    <DialogTrigger isOpen={open} onOpenChange={setOpen}>
      <Button className="vals-button" aria-label={`${v.button(distinct, noun)}: ${column}`}>
        {v.button(distinct, noun)}
        <ChevronDown aria-hidden="true" size="0.85em" />
      </Button>
      <Popover className="popover vals-popover" placement="bottom start">
        <Dialog className="vals-body" aria-label={v.title(column, file)}>
          {open && <ValuesList projectId={projectId} file={file} column={column} />}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function ValuesList({ projectId, file, column }: { projectId: string; file: string; column: string }) {
  const [search, setSearch] = useState("");
  const q = useQuery({
    queryKey: ["column-values", projectId, file, column, search],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/files/{name}/values", {
          params: { path: { project_id: projectId, name: file }, query: { column, search } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const d = q.data;
  const top = d?.values[0]?.count ?? 1;
  return (
    <>
      <Heading slot="title" className="vals-title">
        <span className="mono">{column}</span> <span className="vals-file">· {file}</span>
      </Heading>
      {d && <p className="vals-sub">{v.summary(d.distinct, d.rows, d.blank)}</p>}
      {(d?.distinct ?? 0) > 12 && (
        <SearchField
          aria-label={v.search}
          value={search}
          onChange={setSearch}
          className="vals-search"
          autoFocus
        >
          <Input className="input vals-search-input" placeholder={v.search} />
        </SearchField>
      )}
      {!d ? (
        <p className="vals-sub">{q.error?.message ?? v.loading}</p>
      ) : d.values.length === 0 ? (
        <p className="vals-sub">{v.none}</p>
      ) : (
        <div className="vals-scroll">
          <table className="vals-tbl">
            <thead>
              <tr>
                <th className="vals-th">{v.value}</th>
                <th className="vals-th vals-n">{v.rows}</th>
              </tr>
            </thead>
            <tbody>
              {d.values.map((x) => (
                <tr key={x.value}>
                  <td className="vals-td mono vals-v">{x.value}</td>
                  <td className="vals-td vals-n">
                    <span className="vals-bar" style={{ width: `${Math.max(2, (100 * x.count) / top)}%` }} />
                    {x.count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {d && d.more > 0 && <p className="vals-sub">{v.more(d.more)}</p>}
    </>
  );
}
