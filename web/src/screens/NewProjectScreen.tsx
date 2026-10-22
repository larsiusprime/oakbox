import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Label, Radio, RadioGroup } from "react-aria-components";
import { navigate } from "../App";
import { api, type NewProject, unwrap } from "../api/client";
import { Choice, Field } from "../components/Form";
import { t } from "../strings";

/** Countries that measure land in feet and acres (SPEC §3.0 F1: units default from the country). */
const IMPERIAL = new Set(["US", "LR", "MM"]);

export function NewProjectScreen() {
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: async () => unwrap(await api.GET("/api/regions")),
  });
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const year = new Date().getFullYear();
  const [form, setForm] = useState<NewProject>({
    name: "",
    country: "US",
    region: "",
    jurisdiction: "",
    tax_year: year,
    valuation_date: `${year}-01-01`,
    units: "imperial",
  });
  // The valuation date follows the tax year until the user sets it themselves.
  const [dateTouched, setDateTouched] = useState(false);
  const set = (patch: Partial<NewProject>) => setForm((f) => ({ ...f, ...patch }));
  const create = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/projects", { body: form })),
    // Straight into the Data wizard, which starts by asking for the files (SPEC F3d).
    onSuccess: (p) => navigate({ name: "project", id: p.id, tab: "fields", step: "welcome" }),
  });
  const s = t.newProject;
  const states = regions.data?.subdivisions[form.country];
  const ready = form.name.trim() && form.jurisdiction.trim() && form.region.trim() && form.tax_year;

  return (
    <div className="narrow">
      <header className="page-head">
        <a className="back-link" href="#/">
          {t.project.back}
        </a>
        <h1>{s.title}</h1>
      </header>
      <form
        className="panel form-panel"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) create.mutate();
        }}
      >
        <p className="row-meta">{s.intro}</p>
        <Field
          label={s.name}
          help={s.nameHelp}
          value={form.name}
          onChange={(v) => set({ name: v })}
          width="long"
          autoFocus
        />
        <div className="form-row">
          <Choice
            label={s.country}
            value={form.country}
            options={(regions.data?.countries ?? []).map((c) => [c.code, c.name] as const)}
            onChange={(country) =>
              set({ country, region: "", units: IMPERIAL.has(country) ? "imperial" : "metric" })
            }
          />
          {states ? (
            <Choice
              label={s.state}
              value={form.region || null}
              placeholder=""
              options={states.map((r) => [r.code, r.name] as const)}
              onChange={(region) => set({ region })}
            />
          ) : (
            <Field label={s.region} value={form.region} onChange={(v) => set({ region: v })} />
          )}
        </div>
        <Field
          label={s.jurisdiction}
          help={s.jurisdictionHelp}
          value={form.jurisdiction}
          onChange={(v) => set({ jurisdiction: v })}
          width="long"
        />
        <div className="form-row">
          <Field
            label={s.taxYear}
            type="number"
            width="short"
            value={String(form.tax_year || "")}
            onChange={(v) => {
              const y = Number.parseInt(v, 10) || 0;
              set(dateTouched || !y ? { tax_year: y } : { tax_year: y, valuation_date: `${y}-01-01` });
            }}
          />
          <Field
            label={s.valuationDate}
            help={s.valuationHelp}
            type="date"
            value={form.valuation_date}
            onChange={(v) => {
              setDateTouched(true);
              set({ valuation_date: v });
            }}
          />
        </div>
        <RadioGroup
          className="field radios"
          value={form.units}
          onChange={(v) => set({ units: v as NewProject["units"] })}
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
        {settings.data && <p className="row-meta">{s.where(settings.data.storage_location)}</p>}
        <div className="form-actions">
          <Button type="submit" className="button button-primary" isDisabled={!ready || create.isPending}>
            {s.create}
          </Button>
          <Button className="button" onPress={() => navigate({ name: "home" })}>
            {s.cancel}
          </Button>
        </div>
        {create.error && (
          <p className="error" role="alert">
            {create.error.message}
          </p>
        )}
      </form>
    </div>
  );
}
