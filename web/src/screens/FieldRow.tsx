import { useState } from "react";
import {
  Button,
  Dialog,
  Header,
  Heading,
  ListBoxItem,
  ListBoxSection,
  Modal,
  ModalOverlay,
} from "react-aria-components";
import type { Project, Wizard, WizardField, WizardFile } from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import { Combo, Marked, matches } from "../components/Combo";
import { FileLine, fileFacts } from "../components/FileEntry";
import { Choice } from "../components/Form";
import { TipOn } from "../components/Tip";
import { ValuesButton } from "../components/ValuesButton";
import { say, t } from "../wording";
import { DateDialog, NumberDialog, RuleDialog, ruleComplete } from "./FieldRules";
import { ABSENT, CompareDialog, PAIRS, SCALED, ScaleChoice, ScaleDialog, TiersDialog } from "./Quality";
import { CheckText, FilePicker, matchOptions } from "./WizardFiles";
import type { AreaUnit, MutateAsync } from "./wizardChange";

const w = t.wizard;

// Fields with no column that can instead be assumed, after a warning (SPEC F3d).
export const ASSUMABLE = ["valid_sale", "vacant_sale"];
export const NONE = "__none";
const ASSUME = "__assume";
const ELSEWHERE = "__elsewhere";
/** Amounts of money: read with a format when written as text, and checked for scale (SPEC F3d). */
function isMoney(key: string): boolean {
  return (
    key === "sale_price" || ((key.startsWith("assr_") || key.startsWith("vset")) && key.endsWith("_value"))
  );
}

export function FieldRow({
  project,
  data,
  field,
  sales,
  change,
  label,
  inGroup,
}: {
  project: Project;
  data: Wizard;
  field: WizardField;
  sales: boolean;
  change: MutateAsync;
  /** A numbered section's title, shown instead of the field's name (which moves underneath). */
  label?: string;
  inGroup?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [elsewhere, setElsewhere] = useState(false);
  const [ruling, setRuling] = useState(false);
  const [dating, setDating] = useState(false);
  const [reading, setReading] = useState(false);
  // Quality and condition: compare the columns, say what a number means, or rank a category's tiers.
  const [qc, setQc] = useState<"compare" | "scale" | "tiers" | null>(null);
  const scaled = SCALED.includes(field.key);
  const paired = field.key in PAIRS;
  const money = isMoney(field.key);
  // Under a numbered title, the field's own name only when it says more ("4. Quality" needs no "Quality").
  const name = shortName(field);
  // (or only adds what the card says: "Market value" in the Acme AVM card needs no "Acme AVM market value").
  const titled = label?.replace(/^\d+\.\s*/, "").toLowerCase();
  const same = !!titled && (titled === name.toLowerCase() || name.toLowerCase().endsWith(` ${titled}`));
  const sub = [label && !same ? name : null, w.hints[field.key]].filter(Boolean).join(" · ");
  const files = data.files.filter((f) => f.holds === (sales ? "sales" : "parcels"));
  const source = field.sources[0];
  const value = field.assumed
    ? ASSUME
    : field.absent
      ? ABSENT
      : source
        ? `${source.file}\u0000${source.column}`
        : NONE;
  const sourceFile = source ? files.find((f) => f.name === source.file) : undefined;
  const column = source && sourceFile?.columns.find((c) => c.name === source.column);
  const pick = (v: string) => {
    if (v === ASSUME) setConfirming(true);
    else if (v === ABSENT) void change({ kind: "field", key: field.key, absent: true }).catch(() => {});
    else if (v === ELSEWHERE) setElsewhere(true);
    else if (v === NONE) void change({ kind: "field", key: field.key }).catch(() => {});
    else {
      const [file, col] = v.split("\u0000");
      void change({ kind: "field", key: field.key, file: file ?? null, column: col ?? null })
        .then((next) => {
          // Not yes/no (Q/U, a deed code): straight on to choosing which values mean yes (SPEC F3d).
          const now = next.fields.find((f) => f.key === field.key);
          if (now?.rule && !ruleComplete(now.rule)) setRuling(true);
          // A sale price that needs reading, or whose amounts look wrong: straight to how it's read.
          if (field.key === "sale_price" && now?.check && (!now.check.ok || now.check.warn)) setReading(true);
          // A category for a number: straight to ranking its tiers; a condition number: to what it means.
          if (now?.scale?.kind === "tiers" && Object.keys(now.scale.tiers).length === 0) setQc("tiers");
          else if (field.key === "bldg_condition_num" && now?.scale && !now.scale.kind) setQc("scale");
        })
        .catch(() => {});
    }
  };
  return (
    <>
      <div className={inGroup ? "wiz-label wiz-in-group" : "wiz-label"}>
        <TipOn text={field.description || field.name}>
          <span>{label ?? w.rowNames[field.key] ?? shortName(field)}</span>
        </TipOn>
        {sub && <small>{sub}</small>}
      </div>
      <div
        className={
          field.area_unit || (scaled && source && field.scale && field.scale.kind !== "tiers")
            ? "wiz-pair"
            : undefined
        }
      >
        <ColumnChoice
          field={field}
          files={files}
          used={data.used}
          names={Object.fromEntries(data.fields.map((f) => [f.key, shortName(f)]))}
          types={Object.fromEntries(data.fields.map((f) => [f.key, f.type]))}
          value={value}
          many={files.length > 1}
          elsewhere={!sales}
          onChange={pick}
        />
        {scaled && source && (
          <ScaleChoice
            field={field}
            source={source}
            change={(c) => void change({ kind: "field", ...c }).catch(() => {})}
          />
        )}
        {field.area_unit && source && (
          // The unit the column is in: OAK box converts it to the project's (SPEC F3d).
          <div className="wiz-unit">
            <Choice
              label={say.wizard.areaUnitFor(shortName(field))}
              hideLabel
              value={field.area_unit}
              options={Object.entries(w.areaUnits) as [AreaUnit, string][]}
              onChange={(area_unit) =>
                void change({
                  kind: "field",
                  key: field.key,
                  file: source.file,
                  column: source.column,
                  area_unit,
                }).catch(() => {})
              }
            />
          </div>
        )}
      </div>
      <div className="wiz-samples">
        {field.assumed ? (
          <span className="wiz-warn">
            {w.assumed}: {w.assumedValue[field.key]}
          </span>
        ) : (
          <>
            <CheckText check={field.check} />
            {field.absent && <span className="wiz-from">{w.quality.absentNote}</span>}
            {paired &&
            !source &&
            !field.absent &&
            data.fields.find((f) => f.key === PAIRS[field.key])?.sources.length
              ? !scaled && <span className="wiz-from">{w.numberUsed}</span>
              : null}
            {scaled && source && field.scale && (
              <Button
                className="button button-small"
                onPress={() => setQc(field.scale?.kind === "tiers" ? "tiers" : "scale")}
              >
                {field.scale.kind === "tiers"
                  ? Object.keys(field.scale.tiers).length
                    ? w.quality.reRank
                    : w.quality.rank
                  : field.key === "bldg_quality_num"
                    ? w.quality.checkDirection
                    : w.quality.checkMeaning}
              </Button>
            )}
            {paired && !scaled && (
              // One per section, on the category row: its text is short, so the link always shows.
              <Button className="button button-small" onPress={() => setQc("compare")}>
                {w.quality.compare}
              </Button>
            )}
            {sourceFile && column && field.type === "boolean" && sales && (
              <Button className="button button-small" onPress={() => setRuling(true)}>
                {!field.rule ? w.rule.make : ruleComplete(field.rule) ? w.rule.edit : w.rule.choose}
              </Button>
            )}
            {sourceFile && column && field.type === "date" && column.type !== "date" && (
              <Button className="button button-small" onPress={() => setDating(true)}>
                {field.check?.warn || !field.check?.ok ? w.dates.check : w.dates.change}
              </Button>
            )}
            {sourceFile && column && money && (
              <Button className="button button-small" onPress={() => setReading(true)}>
                {field.check?.warn || !field.check?.ok ? w.numbers.check : w.numbers.change}
              </Button>
            )}
            {sourceFile && column && !field.rule && (
              <ValuesButton
                projectId={project.id}
                file={sourceFile.name}
                column={column.name}
                distinct={field.distinct}
              />
            )}
          </>
        )}
      </div>
      {ruling && sourceFile && (
        <RuleDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          price={data.fields.find((f) => f.key === "sale_price")}
          close={() => setRuling(false)}
          save={(rule) =>
            void change({ kind: "rule", key: field.key, rule })
              .then(() => setRuling(false))
              .catch(() => {})
          }
        />
      )}
      {dating && sourceFile && source && (
        <DateDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          column={source.column}
          close={() => setDating(false)}
          save={(date_format) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              date_format,
            })
              .then(() => setDating(false))
              .catch(() => {})
          }
        />
      )}
      {reading && sourceFile && source && (
        <NumberDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          column={source.column}
          close={() => setReading(false)}
          save={(number_format) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              number_format,
            })
              .then(() => setReading(false))
              .catch(() => {})
          }
        />
      )}
      {qc === "compare" && (
        <CompareDialog
          projectId={project.id}
          data={data}
          numKey={scaled ? field.key : (PAIRS[field.key] ?? field.key)}
          close={() => setQc(null)}
          save={(num, txt) =>
            void change({ kind: "field", ...num })
              .then(() => change({ kind: "field", ...txt }))
              .then((next) => {
                const now = next.fields.find((f) => f.key === num.key);
                setQc(null);
                if (
                  num.key === field.key &&
                  now?.scale?.kind === "tiers" &&
                  !Object.keys(now.scale.tiers).length
                )
                  setQc("tiers");
              })
              .catch(() => {})
          }
        />
      )}
      {qc === "scale" && source && (
        <ScaleDialog
          projectId={project.id}
          field={field}
          source={source}
          close={() => setQc(null)}
          save={(scale) =>
            void change({ kind: "field", key: field.key, file: source.file, column: source.column, scale })
              .then(() => setQc(null))
              .catch(() => {})
          }
        />
      )}
      {qc === "tiers" && source && (
        <TiersDialog
          projectId={project.id}
          field={field}
          source={source}
          close={() => setQc(null)}
          save={(tiers) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              scale: { kind: "tiers", fraction: false, low: null, high: null, tiers },
            })
              .then(() => setQc(null))
              .catch(() => {})
          }
        />
      )}
      {confirming && (
        <AssumeDialog
          field={field.key}
          close={() => setConfirming(false)}
          confirm={() => {
            setConfirming(false);
            void change({ kind: "field", key: field.key, assume: true }).catch(() => {});
          }}
        />
      )}
      {elsewhere && (
        <OtherFileDialog
          project={project}
          data={data}
          field={field}
          change={change}
          close={() => setElsewhere(false)}
        />
      )}
    </>
  );
}

/** The dictionary's name, without "Building" for building fields ("Year built"), except where "Building type"
 * sits beside "Land use". */
export function shortName(field: WizardField): string {
  if (!field.key.startsWith("bldg_") || field.step === "property_type") return field.name;
  const rest = field.name.replace(/^Building /, "");
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** Quality and condition fields can take the same column. */
/** Two fields can read one column when one of them is a yes/no rule (it tests the column's values, it doesn't take
 * it: valid sale and vacant sale from one sale type), or when they're the text and ranked number of one category. */
function shares(a: string, b: string, types: Record<string, string>): boolean {
  return (a in PAIRS && b in PAIRS) || types[a] === "boolean" || types[b] === "boolean";
}

/** A column dropdown grouped by file, with used columns shown but not pickable. */
function ColumnChoice({
  field,
  files,
  used,
  names,
  types,
  value,
  many,
  elsewhere,
  onChange,
}: {
  field: WizardField;
  files: WizardFile[];
  used: Wizard["used"];
  names: Record<string, string>;
  types: Record<string, string>;
  value: string;
  many: boolean;
  elsewhere: boolean;
  onChange: (v: string) => void;
}) {
  const disabled: string[] = [];
  const nameOf = (key: string) => w.idNames[key] ?? names[key] ?? key;
  for (const f of files) {
    for (const c of f.columns) {
      const as = used[f.name]?.[c.name];
      // Quality and condition can share a column: a category is the text and, ranked, the number.
      if (as && as !== field.key && !shares(field.key, as, types)) disabled.push(`${f.name}\u0000${c.name}`);
    }
  }
  const special = value === NONE || value === ASSUME || value === ABSENT;
  const columns = (q: string) => files.map((f) => ({ f, cols: f.columns.filter((c) => matches(c.name, q)) }));
  const all = files.reduce((n, f) => n + f.columns.length, 0);
  return (
    <Combo
      label={w.columnFor({ field: field.name })}
      hideLabel
      className="field choice wiz-choice"
      popoverClassName="popover choice-popover wiz-popover"
      selectedKey={value}
      onChange={onChange}
      disabledKeys={disabled}
      mono={!special}
      muted={value === NONE}
      count={(q) => [columns(q).reduce((n, x) => n + x.cols.length, 0), all]}
      first={(q) => {
        const x = columns(q).find((y) =>
          y.cols.some((c) => !disabled.includes(`${y.f.name}\u0000${c.name}`)),
        );
        const c = x?.cols.find((y) => !disabled.includes(`${x.f.name}\u0000${y.name}`));
        return x && c ? `${x.f.name}\u0000${c.name}` : null;
      }}
    >
      {(q) => (
        <>
          <ListBoxItem id={NONE} className="choice-item" textValue={w.none}>
            {w.none}
          </ListBoxItem>
          {columns(q)
            .filter((x) => x.cols.length > 0)
            .map(({ f, cols }) => (
              <ListBoxSection key={f.name} className="wiz-section">
                <Header className="wiz-section-head">{f.name}</Header>
                {cols.map((c) => {
                  const as = used[f.name]?.[c.name];
                  const other = as && as !== field.key;
                  const taken = other && !shares(field.key, as, types);
                  return (
                    <ListBoxItem
                      key={c.name}
                      id={`${f.name}\u0000${c.name}`}
                      className="choice-item wiz-item"
                      // The box shows the column, and its file when there are several.
                      textValue={many ? `${c.name} · ${f.name}` : c.name}
                    >
                      <span className="mono" title={c.name}>
                        <Marked text={c.name} query={q} />
                      </span>
                      <span className="wiz-item-note">
                        {taken
                          ? w.used({ field: nameOf(as) })
                          : other
                            ? w.alsoRead({ field: nameOf(as) })
                            : c.samples.slice(0, 3).join(", ")}
                      </span>
                    </ListBoxItem>
                  );
                })}
              </ListBoxSection>
            ))}
          {elsewhere && (
            <ListBoxItem id={ELSEWHERE} className="choice-item wiz-elsewhere" textValue={w.elsewhere}>
              {w.elsewhere}
            </ListBoxItem>
          )}
          {field.key === "bldg_condition_num" && (
            <ListBoxItem id={ABSENT} className="choice-item" textValue={w.quality.absent}>
              {w.quality.absent}
            </ListBoxItem>
          )}
          {ASSUMABLE.includes(field.key) && (
            <ListBoxItem id={ASSUME} className="choice-item" textValue={w.assumed}>
              {w.assume[field.key]}
            </ListBoxItem>
          )}
        </>
      )}
    </Combo>
  );
}

/** "It's in another file": the file (added here if need be), its ID column, and the field's column. */
function OtherFileDialog({
  project,
  data,
  field,
  change,
  close,
}: {
  project: Project;
  data: Wizard;
  field: WizardField;
  change: MutateAsync;
  close: () => void;
}) {
  const base = data.files.find((f) => f.base);
  const taken = data.files.filter((f) => f.base || f.holds === "sales").map((f) => f.name);
  const [file, setFile] = useState<string | null>(null);
  const [match, setMatch] = useState<"key" | "key2" | "key3">("key");
  const [idColumn, setIdColumn] = useState<string | null>(null);
  const [column, setColumn] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chosen = data.files.find((f) => f.name === file);
  const columns = (chosen?.columns ?? []).map((c) => [c.name, c.name] as const);
  const save = async () => {
    if (!file || !idColumn || !column) return;
    try {
      await change({ kind: "file", name: file, holds: "parcels", match, id_column: idColumn });
      await change({ kind: "field", key: field.key, file, column });
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal wiz-modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {w.otherTitle({ field: shortName(field) })}
          </Heading>
          {chosen ? (
            <div className="wiz-grid wiz-grid-dialog">
              <div className="wiz-label">{w.otherFile}</div>
              <FileLine name={chosen.name} filename={chosen.filename} facts={fileFacts(chosen)} />
              <div />
              {matchOptions(base).length > 1 && (
                <>
                  <div className="wiz-label">{w.matchBy}</div>
                  <Choice
                    label={w.matchBy}
                    hideLabel
                    value={match}
                    options={matchOptions(base)}
                    onChange={setMatch}
                  />
                  <div />
                </>
              )}
              <div className="wiz-label">{w.otherKey}</div>
              <Choice
                label={w.otherKey}
                hideLabel
                value={idColumn}
                placeholder={w.choose}
                options={columns}
                onChange={setIdColumn}
              />
              <div />
              <div className="wiz-label">{shortName(field)}</div>
              <Choice
                label={w.otherColumn({ field: shortName(field) })}
                hideLabel
                value={column}
                placeholder={w.choose}
                options={columns}
                onChange={setColumn}
              />
              <div />
            </div>
          ) : (
            <FilePicker project={project} data={data} exclude={taken} onChosen={setFile} />
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <Button
              className="button button-primary"
              isDisabled={!file || !idColumn || !column}
              onPress={() => void save()}
            >
              {w.save}
            </Button>
            <Button className="button" onPress={close}>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function AssumeDialog({ field, close, confirm }: { field: string; close: () => void; confirm: () => void }) {
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal">
        <Dialog className="modal-body" role="alertdialog">
          <Heading slot="title" className="modal-title wiz-warn-title">
            <img src={warningIcon} alt="" className="wiz-warn-icon" />
            {w.warnTitle[field]}
          </Heading>
          <p>{w.warnBody[field]}</p>
          <div className="form-actions">
            <Button className="button button-danger" onPress={confirm}>
              {w.warnConfirm}
            </Button>
            <Button className="button" onPress={close} autoFocus>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
