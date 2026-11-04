import { Radio, RadioGroup } from "react-aria-components";
import type { Scale, Source, WizardField } from "../api/client";
import { Seg } from "../components/Seg";
import { say, t } from "../wording";

const q = t.wizard.quality;
type Kind = NonNullable<Scale["kind"]>;
export const SCALED = ["bldg_quality_num", "bldg_condition_num"];
export const PAIRS: Record<string, string> = {
  bldg_quality_num: "bldg_quality_txt",
  bldg_quality_txt: "bldg_quality_num",
  bldg_condition_num: "bldg_condition_txt",
  bldg_condition_txt: "bldg_condition_num",
};
const KINDS: Record<string, Kind[]> = {
  bldg_quality_num: ["higher", "lower"],
  bldg_condition_num: ["pct_good", "pct_depr", "higher", "lower", "life"],
};
export const ABSENT = "__absent";

/** What a change to a quality/condition field sends (FieldsWizard's field change). */
export type QualityChange = {
  key: string;
  file?: string | null;
  column?: string | null;
  scale?: Scale;
  absent?: boolean;
};

/** The meaning of a quality/condition number, beside its column: which way it runs, or what it measures. */
/** Which way a quality or condition number runs, right on its page (a row of the grid of its own): two ways
 * (quality) are a segmented control with a line under it on what the chosen one means; more (condition: % good, %
 * depreciation, life left…) are radio cards, a line each. */
export function ScaleChoice({
  field,
  source,
  change,
}: {
  field: WizardField;
  source: Source;
  change: (c: QualityChange) => void;
}) {
  const kinds = KINDS[field.key] ?? [];
  const scale = field.scale;
  if (!scale || scale.kind === "tiers") return null;
  const label = field.key === "bldg_quality_num" ? q.whichWayLabel : q.meansLabel;
  const set = (kind: Kind) =>
    change({ key: field.key, file: source.file, column: source.column, scale: { ...scale, kind } });
  return (
    <>
      {/* Level with the first choice when they're a list, not halfway down it. */}
      <div className={kinds.length <= 3 ? "wiz-label" : "wiz-label wiz-label-top"}>
        {label}
        {/* What the chosen meaning is, under the label (beside the list, where there's room). */}
        {kinds.length > 3 && scale.kind && <small className="scale-hint">{q.kindHints[scale.kind]}</small>}
      </div>
      {kinds.length <= 3 ? (
        <div className="wiz-span seg-row">
          <Seg
            label={say.wizard.quality.meaningOf(field.name)}
            value={scale.kind ?? null}
            options={kinds.map((k) => [k, cap(q.kinds[k] ?? k)] as const)}
            onChange={set}
          />
        </div>
      ) : (
        <RadioGroup
          aria-label={say.wizard.quality.meaningOf(field.name)}
          className="wiz-span scale-list"
          value={scale.kind ?? null}
          onChange={(k) => set(k as Kind)}
        >
          {kinds.map((k) => (
            // One line each; what the chosen one means is under the label.
            <Radio key={k} value={k} className="radio scale-item">
              <span className="radio-dot" aria-hidden="true" />
              <span>{cap(q.kinds[k] ?? k)}</span>
            </Radio>
          ))}
        </RadioGroup>
      )}
      {(scale.kind === "pct_good" || scale.kind === "pct_depr") && (
        // Percentages written as 0–1 or 0–100: found from the values, and the user's to change.
        <>
          <div className="wiz-label">{q.writtenAs}</div>
          <div className="wiz-span seg-row">
            <Seg
              label={q.writtenAs}
              value={scale.fraction ? "f" : "p"}
              options={[
                ["f", q.fractions],
                ["p", q.percents],
              ]}
              onChange={(x) =>
                change({
                  key: field.key,
                  file: source.file,
                  column: source.column,
                  scale: { ...scale, fraction: x === "f" },
                })
              }
            />
          </div>
        </>
      )}
    </>
  );
}

/** "higher is better" as an option's words: its first letter capital. */
function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
