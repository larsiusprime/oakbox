import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Input, Popover, SearchField } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { useSettled } from "../lib/hooks";
import { say, t } from "../wording";
import { type ValueSort, ValueTable } from "./ValueTable";

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
      <Button
        className="button button-small vals-button"
        aria-label={`${say.wizard.values.button(distinct, noun)}: ${column}`}
      >
        {say.wizard.values.button(distinct, noun)}
        <ChevronDown aria-hidden="true" size="0.85em" />
      </Button>
      <Popover className="popover vals-popover" placement="bottom start" offset={0}>
        <Dialog className="vals-body" aria-label={v.title({ column, file })}>
          {open && <ValuesList projectId={projectId} file={file} column={column} />}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function ValuesList({ projectId, file, column }: { projectId: string; file: string; column: string }) {
  const [search, setSearch] = useState("");
  // Asked once typing pauses, not per keystroke; the list stays up meanwhile.
  const asked = useSettled(search.trim(), 250);
  const [sort, setSort] = useState<ValueSort>(null);
  const q = useQuery({
    queryKey: ["column-values", projectId, file, column, asked, sort],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/files/{name}/values", {
          params: {
            path: { project_id: projectId, name: file },
            query: { column, search: asked, ...(sort ? { sort: sort.by, desc: sort.desc } : {}) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const d = q.data;
  return (
    <>
      <Heading slot="title" className="vals-title">
        <span className="mono">{column}</span> <span className="vals-file">· {file}</span>
      </Heading>
      {d && <p className="vals-sub">{v.summary({ distinct: d.distinct, rows: d.rows, blank: d.blank })}</p>}
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
        <ValueTable values={d.values} sort={sort} onSort={setSort} />
      )}
      {d && d.more > 0 && <p className="vals-sub">{v.more({ n: d.more })}</p>}
    </>
  );
}
