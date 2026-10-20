import { useState } from "react";
import { Label, Radio, RadioGroup } from "react-aria-components";
import type { Basics } from "../../api/client";
import { Field } from "../../components/Form";
import {
  LooksRight,
  Part,
  StageFrame,
  StageStatusMark,
  StaleNote,
  UnderTheHood,
} from "../../components/Stage";
import { t } from "../../strings";
import { api, type StageProps, useSave } from "./common";

function slug(b: Basics): string {
  const name = b.name.toLowerCase().replace(/[^a-z0-9]/g, "") || "project";
  return `us-${(b.state || "xx").toLowerCase()}-${name}`;
}

export function BasicsStage({ detail }: StageProps) {
  const { project } = detail;
  const saved = project.setup.basics;
  // Local draft while typing; each field is saved when the user leaves it.
  const [draft, setDraft] = useState<Basics>(saved);
  const save = useSave(project.id, (b: Basics) =>
    api.PUT("/api/projects/{project_id}/basics", { params: { path: { project_id: project.id } }, body: b }),
  );
  const commit = (next: Basics = draft) => {
    if (JSON.stringify(next) !== JSON.stringify(saved)) save.mutate(next);
  };
  const set = (patch: Partial<Basics>) => setDraft((d) => ({ ...d, ...patch }));
  const status = project.stages.basics;
  const s = t.basics;

  return (
    <StageFrame
      title={t.stages.basics.title}
      what={t.stages.basics.what}
      status={<StageStatusMark status={status} />}
      note={project.notes.basics}
    >
      <StaleNote status={status} />
      <Part title={t.frame.decide}>
        <div className="form-grid">
          <Field
            label={s.name}
            value={draft.name}
            onChange={(v) => set({ name: v })}
            onBlur={() => commit()}
            width="long"
          />
          <Field
            label={s.state}
            help={s.stateHelp}
            value={draft.state}
            onChange={(v) => set({ state: v.toUpperCase().slice(0, 2) })}
            onBlur={() => commit()}
            width="short"
          />
          <Field
            label={s.taxYear}
            type="number"
            value={draft.tax_year?.toString() ?? ""}
            onChange={(v) => set({ tax_year: v ? Number.parseInt(v, 10) : null })}
            onBlur={() => commit()}
            width="short"
          />
          <Field
            label={s.valuationDate}
            help={s.valuationHelp}
            type="date"
            value={draft.valuation_date ?? ""}
            onChange={(v) => set({ valuation_date: v || null })}
            onBlur={() => commit()}
            width="medium"
          />
          <RadioGroup
            className="field radios"
            value={draft.units}
            onChange={(v) => {
              const next = { ...draft, units: v as Basics["units"] };
              setDraft(next);
              commit(next);
            }}
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
        </div>
        {save.error && (
          <p className="error" role="alert">
            {save.error.message}
          </p>
        )}
      </Part>
      <Part title={t.frame.check}>
        <p className="row-meta">{s.slug(slug(draft))}</p>
      </Part>
      <LooksRight projectId={project.id} stage="basics" status={status} />
      <UnderTheHood projectId={project.id} stage="basics" />
    </StageFrame>
  );
}
