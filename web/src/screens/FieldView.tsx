import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, List } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  ComboBox,
  Header,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  ListBoxSection,
  Popover,
  Radio,
  RadioGroup,
  SearchField,
  TextField,
} from "react-aria-components";
import {
  api,
  type DictionaryField,
  type FileColumn,
  type FileColumns,
  type ProjectDetail,
  unwrap,
} from "../api/client";
import { Choice, Tick } from "../components/Form";
import { Tip, TipOn } from "../components/Tip";
import { size } from "../lib/format";
import { t } from "../strings";

/** What OpenAVMKit casts a loaded column to; "asis" writes the bare column (no cast). */
type Cast = "asis" | "string" | "float" | "int" | "bool" | "datetime";
type Row = {
  column: string;
  loaded: boolean;
  /** A dictionary key, or a custom name when `custom`. */
  field: string;
  custom: boolean;
  cast: Cast;
  /** Date format or blank handling, for datetime and bool. */
  extra: string;
  /** In load, but not a column of the file. */
  notInFile?: boolean;
};

const NAME = /^[a-z][a-z0-9_]*$/;
const CUSTOM = "__custom__";

/** F3c: choose which columns of one input file load, as what, and cast to what (SPEC §3.0). */
export function FieldView({ detail, name }: { detail: ProjectDetail; name: string }) {
  const f = t.fields;
  const project = detail.project;
  const file = detail.files.find((x) => x.name === name);
  const entry = project.files.find((x) => x.name === name);
  const columns = useQuery({
    queryKey: ["columns", project.id, name],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/files/{name}/columns", {
          params: { path: { project_id: project.id, name } },
        }),
      ),
    enabled: Boolean(file && !file.missing),
  });
  const dictionary = useQuery({
    queryKey: ["dictionary", detail.project.jurisdiction],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/dictionary", {
          params: { query: { jurisdiction: detail.project.jurisdiction } },
        }),
      ),
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <div className="field-view">
      <a className="back-link" href={`#/projects/${project.id}/files`}>
        <ChevronLeft aria-hidden="true" size="1.1em" />
        {f.back}
      </a>
      {!file || !entry ? (
        <p className="error">{t.inputFiles.missingFile(name)}</p>
      ) : (
        <>
          <h2 className="field-view-title">
            <span className="mono">{file.name}</span>
            <span className="row-meta">
              {f.summary(file.filename, file.format, size(file.size_bytes), columns.data?.rows ?? null)}
            </span>
          </h2>
          {file.missing && <p className="error">{t.inputFiles.missingFile(file.filename)}</p>}
          {columns.error && <p className="error">{columns.error.message}</p>}
          {(columns.isPending || dictionary.isPending) && !file.missing && (
            <p className="empty">{f.reading}</p>
          )}
          {columns.data && dictionary.data && (
            <FieldTable
              projectId={project.id}
              name={name}
              load={entry.load}
              file={columns.data}
              dictionary={dictionary.data}
            />
          )}
        </>
      )}
    </div>
  );
}

function castFor(dictType: string | null, kind: FileColumn["type"]): Cast {
  const byDict: Record<string, Cast> = {
    number: "float",
    percent: "float",
    string: "string",
    boolean: "bool",
    date: "datetime",
  };
  if (dictType && byDict[dictType]) return byDict[dictType];
  return ({ text: "string", number: "float", "yes/no": "bool", date: "datetime", geometry: "asis" } as const)[
    kind
  ];
}

function defaultExtra(cast: Cast, column: FileColumn | undefined): string {
  if (cast === "datetime") return column?.date_format ?? "";
  if (cast === "bool") return "na_false";
  return "";
}

const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "");

function lowerName(column: string): string {
  const name = column
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(name) ? name : `f_${name}`;
}

/** What ticking a column would choose: a dictionary field its name matches, else its own name. */
function suggest(column: FileColumn, dictionary: DictionaryField[]): Row {
  const match = dictionary.find(
    (d) => d.offered && (squash(d.key) === squash(column.name) || squash(d.name) === squash(column.name)),
  );
  // A text column whose samples read as dates is suggested as a date (SPEC F3c).
  const cast = castFor(match?.type ?? (column.date_format ? "date" : null), column.type);
  return {
    column: column.name,
    loaded: false,
    field: match ? match.key : lowerName(column.name),
    custom: !match,
    cast,
    extra: defaultExtra(cast, column),
  };
}

function initialRows(
  load: Record<string, string[]>,
  file: FileColumns,
  dictionary: DictionaryField[],
): Row[] {
  // A loaded field the dropdown doesn't offer shows as a custom name (and is flagged if computed).
  const known = new Set(dictionary.filter((d) => d.offered).map((d) => d.key));
  const byColumn = new Map(Object.entries(load).map(([field, spec]) => [spec[0] ?? "", { field, spec }]));
  const rows: Row[] = [];
  // Columns the entry loads that the file doesn't have come first (SPEC F3c).
  for (const [column, { field, spec }] of byColumn) {
    if (!file.columns.some((c) => c.name === column)) {
      rows.push({
        column,
        loaded: true,
        field,
        custom: !known.has(field),
        cast: (spec[1] as Cast | undefined) ?? "asis",
        extra: spec[2] ?? "",
        notInFile: true,
      });
    }
  }
  for (const column of file.columns) {
    const existing = byColumn.get(column.name);
    if (existing) {
      const cast = (existing.spec[1] as Cast | undefined) ?? "asis";
      rows.push({
        column: column.name,
        loaded: true,
        field: existing.field,
        custom: !known.has(existing.field),
        cast,
        extra: existing.spec[2] ?? defaultExtra(cast, column),
      });
    } else {
      rows.push(suggest(column, dictionary));
    }
  }
  return rows;
}

/** A flag for a loaded field OpenAVMKit computes itself, picked or typed (SPEC F3c); null otherwise. */
function computedWarning(row: Row, dictionary: DictionaryField[]): string | null {
  if (!row.loaded || row.notInFile) return null;
  const source = dictionary.find((d) => d.key === row.field)?.source;
  if (source === "derived") return t.fields.derived(row.field);
  if (source === "reserved") return t.fields.reserved(row.field);
  return null;
}

/** Why a loaded row can't be written yet, or null when it can (SPEC F3c: saving). */
function problem(row: Row, rows: Row[]): string | null {
  const f = t.fields;
  if (!row.loaded || row.notInFile) return null;
  if (!row.field) return f.needsName;
  if (!NAME.test(row.field)) return f.badName;
  const first = rows.find((r) => r.loaded && r.field === row.field);
  if (first && first !== row) return f.clash(row.field);
  if (row.cast === "datetime" && !row.extra) return f.needsFormat;
  return null;
}

function toLoad(rows: Row[]): Record<string, string[]> {
  const load: Record<string, string[]> = {};
  for (const row of rows) {
    if (!row.loaded || problem(row, rows)) continue;
    const spec = [row.column];
    if (row.cast !== "asis") spec.push(row.cast);
    if (row.cast === "datetime" || row.cast === "bool") spec.push(row.extra);
    load[row.field] = spec;
  }
  return load;
}

function FieldTable(props: {
  projectId: string;
  name: string;
  load: Record<string, string[]>;
  file: FileColumns;
  dictionary: DictionaryField[];
}) {
  const f = t.fields;
  const queryClient = useQueryClient();
  const [rows, setRows] = useState(() => initialRows(props.load, props.file, props.dictionary));
  const [filter, setFilter] = useState("");
  const [show, setShow] = useState<"all" | "loaded">("all");
  const byName = useMemo(() => new Map(props.file.columns.map((c) => [c.name, c])), [props.file]);

  // Each change saves as you go; only complete rows are written (SPEC F3c).
  const load = useMemo(() => toLoad(rows), [rows]);
  const saved = useRef(JSON.stringify(props.load));
  const save = useMutation({
    mutationFn: async (next: Record<string, string[]>) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/files/{name}/load", {
          params: { path: { project_id: props.projectId, name: props.name } },
          body: { load: next },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["project", props.projectId] }),
  });
  const { mutate } = save;
  useEffect(() => {
    const text = JSON.stringify(load);
    if (text === saved.current) return;
    const timer = window.setTimeout(() => {
      saved.current = text;
      mutate(load);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [load, mutate]);

  const update = (column: string, change: Partial<Row>) =>
    setRows((old) => old.map((r) => (r.column === column ? { ...r, ...change } : r)));

  const loadedCount = rows.filter((r) => r.loaded).length;
  const needle = filter.trim().toLowerCase();
  const visible = rows.filter(
    (r) =>
      (show === "all" || r.loaded) &&
      (!needle ||
        r.column.toLowerCase().includes(needle) ||
        (byName.get(r.column)?.samples ?? []).some((s) => s.toLowerCase().includes(needle))),
  );

  return (
    <>
      <div className="field-tools">
        <SearchField className="field field-search" value={filter} onChange={setFilter} aria-label={f.filter}>
          <Input className="input" placeholder={`${f.filter}…`} />
        </SearchField>
        <RadioGroup
          className="show-choice"
          orientation="horizontal"
          value={show}
          onChange={(v) => setShow(v as "all" | "loaded")}
        >
          <Label className="field-label">{f.show}</Label>
          <Radio value="all" className="radio">
            <span className="radio-dot" aria-hidden="true" />
            {f.all(rows.length)}
          </Radio>
          <Radio value="loaded" className="radio">
            <span className="radio-dot" aria-hidden="true" />
            {f.loaded(loadedCount)}
          </Radio>
        </RadioGroup>
      </div>
      {save.error && (
        <p className="error" role="alert">
          {save.error.message}
        </p>
      )}
      <table className="field-table">
        <colgroup>
          <col className="col-load" />
          <col className="col-column" />
          <col className="col-kind" />
          <col />
          <col className="col-field" />
          <col className="col-cast" />
          <col className="col-extra" />
        </colgroup>
        <thead>
          <tr>
            <th>{f.columns.load}</th>
            <th>{f.columns.column}</th>
            <th>{f.columns.inFile}</th>
            <th>{f.columns.samples}</th>
            <th>{f.columns.field}</th>
            <th>{f.columns.type}</th>
            <th>
              <span className="visually-hidden">{f.columns.extra}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <FieldRow
              key={row.column}
              row={row}
              rows={rows}
              column={byName.get(row.column)}
              dictionary={props.dictionary}
              dateFormats={props.file.date_formats}
              onChange={(change) => update(row.column, change)}
            />
          ))}
          {visible.length === 0 && (
            <tr>
              <td colSpan={7} className="empty">
                {f.noMatches}
              </td>
            </tr>
          )}
          {props.file.geometry && show === "all" && !needle && (
            <tr className="geometry-row">
              <td />
              <td className="mono">geometry</td>
              <td>{f.kinds.geometry}</td>
              <td colSpan={4} className="row-meta">
                {f.geometry}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  );
}

function FieldRow(props: {
  row: Row;
  rows: Row[];
  column: FileColumn | undefined;
  dictionary: DictionaryField[];
  dateFormats: string[];
  onChange: (change: Partial<Row>) => void;
}) {
  const f = t.fields;
  const { row, column } = props;
  const why = problem(row, props.rows);
  const warning = why ? null : computedWarning(row, props.dictionary);
  const off = !row.loaded;
  const pickField = (key: string) => {
    if (key === CUSTOM) {
      props.onChange({ custom: true, field: lowerName(row.column) });
      return;
    }
    const d = props.dictionary.find((x) => x.key === key);
    const cast = castFor(d?.type ?? null, column?.type ?? "text");
    props.onChange({ custom: false, field: key, cast, extra: defaultExtra(cast, column) });
  };
  return (
    <>
      <tr className={`field-row${off ? " unloaded" : ""}${row.notInFile ? " not-in-file" : ""}`}>
        <td>
          <Tick isSelected={row.loaded} onChange={(loaded) => props.onChange({ loaded })}>
            <span className="visually-hidden">{f.loadColumn(row.column)}</span>
          </Tick>
        </td>
        <td className="mono cell-clip" title={row.column}>
          {row.column}
        </td>
        {row.notInFile ? (
          <td colSpan={5} className="error-text">
            {f.notInFile} · <span className="mono">{row.field}</span>
          </td>
        ) : (
          <>
            <td className="row-meta">{column ? f.kinds[column.type] : ""}</td>
            <td className="cell-clip samples" title={column?.samples.join(", ")}>
              {column?.samples.join(", ")}
            </td>
            <td>
              {row.custom ? (
                <span className="custom-field">
                  <TextField
                    aria-label={f.customName(row.column)}
                    value={row.field}
                    onChange={(field) => props.onChange({ field })}
                    isDisabled={off}
                    isInvalid={Boolean(why)}
                  >
                    <Input className="input mono" />
                  </TextField>
                  <Tip text={f.backToList}>
                    <Button
                      className="icon-button"
                      aria-label={f.backToList}
                      isDisabled={off}
                      onPress={() => props.onChange({ custom: false, field: "" })}
                    >
                      <List aria-hidden="true" size="1em" />
                    </Button>
                  </Tip>
                </span>
              ) : (
                <FieldPicker
                  label={f.fieldFor(row.column)}
                  value={row.field}
                  dictionary={props.dictionary}
                  isDisabled={off}
                  onPick={pickField}
                />
              )}
            </td>
            <td>
              <Choice
                label={f.typeFor(row.column)}
                hideLabel
                value={row.cast}
                options={(Object.keys(f.types) as Cast[]).map((k) => [k, f.types[k]] as const)}
                onChange={(cast) => props.onChange({ cast, extra: defaultExtra(cast, column) })}
                isDisabled={off}
              />
            </td>
            <td>
              {row.cast === "datetime" && (
                <DateFormat
                  label={f.formatFor(row.column)}
                  value={row.extra}
                  formats={props.dateFormats}
                  samples={column?.samples ?? []}
                  isDisabled={off}
                  onChange={(extra) => props.onChange({ extra })}
                />
              )}
              {row.cast === "bool" && (
                <TipOn text={f.yesValues}>
                  <Choice
                    label={f.blanksFor(row.column)}
                    hideLabel
                    value={row.extra as "na_false" | "na_true"}
                    options={[
                      ["na_false", f.blanks.na_false],
                      ["na_true", f.blanks.na_true],
                    ]}
                    onChange={(extra) => props.onChange({ extra })}
                    isDisabled={off}
                  />
                </TipOn>
              )}
            </td>
          </>
        )}
      </tr>
      {why && (
        <tr className="field-problem">
          <td />
          <td colSpan={6}>
            <span className="error" role="alert">
              {why}
            </span>
          </td>
        </tr>
      )}
      {warning && (
        <tr className="field-problem">
          <td />
          <td colSpan={6}>
            <span className="warning" role="status">
              ⚠ {warning}
            </span>
          </td>
        </tr>
      )}
    </>
  );
}

/** The data dictionary as a searchable dropdown, grouped, with Custom… first (SPEC F3c). */
function FieldPicker(props: {
  label: string;
  value: string;
  dictionary: DictionaryField[];
  isDisabled: boolean;
  onPick: (key: string) => void;
}) {
  const f = t.fields;
  const groups = useMemo(() => {
    const out = new Map<string, DictionaryField[]>();
    for (const d of props.dictionary.filter((x) => x.offered)) {
      const group = d.groups[0] ?? t.fields.otherGroup;
      out.set(group, [...(out.get(group) ?? []), d]);
    }
    return [...out.entries()];
  }, [props.dictionary]);
  const label = (d: DictionaryField) => `${d.name} (${d.key})`;
  return (
    <ComboBox
      className="field-picker"
      aria-label={props.label}
      selectedKey={props.value || null}
      onSelectionChange={(k) => k !== null && props.onPick(String(k))}
      isDisabled={props.isDisabled}
      menuTrigger="focus"
    >
      <div className="picker-input">
        <Input className="input" />
        <Button className="picker-button" aria-label={t.fields.showList}>
          <ChevronDown aria-hidden="true" size="1em" />
        </Button>
      </div>
      <Popover className="popover choice-popover picker-popover">
        <ListBox className="choice-list">
          <ListBoxItem id={CUSTOM} className="choice-item picker-custom" textValue={f.custom}>
            {f.custom}
          </ListBoxItem>
          {groups.map(([group, fields]) => (
            <ListBoxSection key={group} className="picker-section">
              <Header className="picker-header">{group}</Header>
              {fields.map((d) => (
                <ListBoxItem key={d.key} id={d.key} className="choice-item" textValue={label(d)}>
                  <span title={d.description}>
                    {d.name} <span className="mono row-meta">({d.key})</span>
                  </span>
                </ListBoxItem>
              ))}
            </ListBoxSection>
          ))}
        </ListBox>
      </Popover>
    </ComboBox>
  );
}

/** A date format: a common one or typed, checked live against the samples as OpenAVMKit reads them. */
function DateFormat(props: {
  label: string;
  value: string;
  formats: string[];
  samples: string[];
  isDisabled: boolean;
  onChange: (format: string) => void;
}) {
  const f = t.fields;
  const check = useQuery({
    queryKey: ["date-format", props.value, props.samples],
    queryFn: async () =>
      unwrap(await api.POST("/api/date-format", { body: { samples: props.samples, format: props.value } })),
    enabled: Boolean(props.value) && props.samples.length > 0 && !props.isDisabled,
  });
  const parsed = check.data?.parsed ?? [];
  const reads = parsed.length > 0 && parsed.every((p) => p !== null);
  return (
    <span className="date-format">
      <ComboBox
        aria-label={props.label}
        allowsCustomValue
        inputValue={props.value}
        onInputChange={props.onChange}
        isDisabled={props.isDisabled}
        menuTrigger="focus"
      >
        <div className="picker-input">
          <Input className="input mono" />
          <Button className="picker-button" aria-label={t.fields.showList}>
            <ChevronDown aria-hidden="true" size="1em" />
          </Button>
        </div>
        <Popover className="popover choice-popover">
          <ListBox className="choice-list">
            {props.formats.map((fmt) => (
              <ListBoxItem key={fmt} id={fmt} className="choice-item mono" textValue={fmt}>
                {fmt}
              </ListBoxItem>
            ))}
          </ListBox>
        </Popover>
      </ComboBox>
      {check.data &&
        (reads ? (
          <span className="date-ok">✓ {parsed[0]}</span>
        ) : (
          <TipOn text={f.unreadable}>
            <span className="error-text">✗</span>
          </TipOn>
        ))}
    </span>
  );
}
