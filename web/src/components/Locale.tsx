import { Label, Radio, RadioGroup } from "react-aria-components";
import type { Regions } from "../api/client";
import { t } from "../strings";
import { Choice } from "./Form";

export type LocaleValue = {
  units: "imperial" | "metric";
  currency: string;
  numbers: "1,234.56" | "1.234,56" | "1 234,56" | "1'234.56" | "1 234.56";
};

/** What a project in this country starts with (SPEC F1); the user can change each. */
export function countryLocale(regions: Regions | undefined, country: string): LocaleValue | null {
  const d = regions?.defaults[country];
  return d ? { units: d.units, currency: d.currency, numbers: d.numbers } : null;
}

/** Units, currency and number style: on the new-project form and under Metadata (SPEC F1). */
export function LocaleFields({
  regions,
  value,
  onChange,
}: {
  regions: Regions | undefined;
  value: LocaleValue;
  onChange: (patch: Partial<LocaleValue>) => void;
}) {
  const s = t.newProject;
  const currencies = (regions?.currencies ?? []).map(
    (c) =>
      [
        c.code,
        c.symbol && c.symbol !== c.code ? `${c.code} · ${c.name} (${c.symbol})` : `${c.code} · ${c.name}`,
      ] as const,
  );
  return (
    <>
      <div className="form-row">
        <Choice
          label={s.currency}
          value={value.currency}
          options={currencies.length ? currencies : [[value.currency, value.currency] as const]}
          onChange={(currency) => onChange({ currency })}
        />
        <Choice
          label={s.numbers}
          value={value.numbers}
          options={Object.entries(s.numberStyles) as [LocaleValue["numbers"], string][]}
          onChange={(numbers) => onChange({ numbers })}
        />
      </div>
      <RadioGroup
        className="field radios"
        value={value.units}
        onChange={(v) => onChange({ units: v as LocaleValue["units"] })}
      >
        <Label className="field-label">{s.units}</Label>
        <Radio value="imperial" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {s.imperial}
        </Radio>
        <Radio value="metric" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {s.metric}
        </Radio>
      </RadioGroup>
    </>
  );
}
