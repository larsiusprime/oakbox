import { useState } from "react";
import type { Project, Wizard, WizardFile } from "../api/client";
import { AddButton } from "../components/AddButton";
import { SubEntry } from "../components/FileEntry";
import { Choice } from "../components/Form";
import { Tip, TipOn } from "../components/Tip";
import { t } from "../wording";
import { CheckText, FilePicker, IdCheck, IdRow, isMainSales, MatchPanel, StepFile } from "./WizardFiles";
import type { Mutate } from "./wizardChange";

const w = t.wizard;
const MAKE = "__make";

// The Data wizard's ID steps: the parcels file and its IDs (Universe), the sales file and its IDs.

/** Universe: the parcels file, its parcel ID, and any further IDs it has. */
export function UniverseStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const [adding, setAdding] = useState(false);
  if (!base) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={[]}
        onChosen={(name) => change({ kind: "file", name, universe: true })}
      />
    );
  }
  const columns = base.columns.map((c) => [c.name, c.name] as const);
  return (
    <StepFile
      file={base}
      onRemove={() => change({ kind: "file", name: base.name, holds: "unused" })}
      undo={() => change({ kind: "file", name: base.name, universe: true })}
    >
      {/* Each ID its own box: each but the parcel ID can be taken away on its own. */}
      <div className="wiz-grid">
        <SubEntry
          label={
            <TipOn text={w.parcelIdTip}>
              <span>{w.parcelId}</span>
            </TipOn>
          }
          control={
            <Choice
              label={w.parcelId}
              hideLabel
              value={base.id_column}
              placeholder={w.choose}
              options={columns}
              onChange={(id_column) => change({ kind: "file", name: base.name, id_column })}
            />
          }
          after={<IdCheck projectId={project.id} data={data} file={base} change={change} />}
        />
        {base.extra_ids.map((e) => (
          <ExtraIdRow key={e.field} file={base} extra={e} change={change} />
        ))}
        {adding && <NewExtraIdRow file={base} change={change} done={() => setAdding(false)} />}
      </div>
      {!adding && base.extra_ids.length < EXTRA_IDS.length && (
        <Tip text={w.extraIdTip}>
          <AddButton end onPress={() => setAdding(true)}>
            {w.addId({ ordinal: w.idOrdinal[EXTRA_IDS[base.extra_ids.length] ?? "key2"] ?? "" })}
          </AddButton>
        </Tip>
      )}
    </StepFile>
  );
}

const EXTRA_IDS = ["key2", "key3"] as const;

function ExtraIdRow({
  file,
  extra,
  change,
}: {
  file: WizardFile;
  extra: WizardFile["extra_ids"][number];
  change: Mutate;
}) {
  const ordinal = w.idOrdinal[extra.field] ?? extra.field;
  return (
    <SubEntry
      label={
        <>
          <TipOn text={w.extraIdTip}>
            <span>{ordinal}</span>
          </TipOn>
          <small>{w.optional}</small>
        </>
      }
      control={
        <Choice
          label={ordinal}
          hideLabel
          value={extra.column}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(v) =>
            change({ kind: "file", name: file.name, extra_field: extra.field, extra_column: v })
          }
        />
      }
      what={ordinal}
      onRemove={() => change({ kind: "file", name: file.name, extra_field: extra.field, extra_column: null })}
      // Removing the 2nd moves the 3rd up into its place: Undo puts both back where they were.
      undo={() => {
        const later = file.extra_ids.filter((e) => e.field > extra.field);
        const put = (i: number) => {
          const e = i === 0 ? extra : later[i - 1];
          if (!e) return;
          change(
            { kind: "file", name: file.name, extra_field: e.field, extra_column: e.column },
            { onSuccess: () => put(i + 1) },
          );
        };
        put(0);
      }}
    />
  );
}

function NewExtraIdRow({ file, change, done }: { file: WizardFile; change: Mutate; done: () => void }) {
  const field = EXTRA_IDS[file.extra_ids.length] ?? "key2";
  const ordinal = w.idOrdinal[field] ?? field;
  return (
    <SubEntry
      label={
        <>
          <TipOn text={w.extraIdTip}>
            <span>{ordinal}</span>
          </TipOn>
          <small>{w.optional}</small>
        </>
      }
      control={
        <Choice
          label={ordinal}
          hideLabel
          value={null}
          placeholder={w.choose}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(v) =>
            change(
              { kind: "file", name: file.name, extra_field: field, extra_column: v },
              { onSuccess: done },
            )
          }
        />
      }
      what={ordinal}
      onRemove={done}
    />
  );
}

/** Sales' own page: which file holds the sales. Nothing else is asked here; its parts come next. */
export function SalesFile({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  if (!sales) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={base ? [base.name] : []}
        onChosen={(name) => change({ kind: "file", name, holds: "sales" })}
      />
    );
  }
  return (
    <StepFile
      file={sales}
      onRemove={() => change({ kind: "file", name: sales.name, holds: "unused" })}
      undo={() => change({ kind: "file", name: sales.name, holds: "sales" })}
    />
  );
}

/** Sales' IDs part: the parcel ID each sale carries and the sale's own ID (a column, or made from the parcel ID and
 * the sale date), then whether the sales find their parcels, why some don't, and the IDs cleaned up, under it. */
export function SalesIds({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  if (!sales) return <p className="wiz-note">{w.salesParts.noFile}</p>;
  return (
    <>
      {/* Both IDs on one grid: their labels, controls and checks in the same columns. */}
      <div className="wiz-grid frame ids-box">
        <IdRow projectId={project.id} data={data} file={sales} base={base} change={change} inline />
        <div className="wiz-grid">
          <div className="wiz-label">
            <TipOn text={w.saleIdTip}>
              <span>{w.saleIdColumn}</span>
            </TipOn>
          </div>
          <Choice
            label={w.saleIdColumn}
            hideLabel
            value={data.sale_id.made ? MAKE : data.sale_id.column}
            placeholder={w.choose}
            options={[[MAKE, w.makeSaleId] as const, ...sales.columns.map((c) => [c.name, c.name] as const)]}
            onChange={(v) => change({ kind: "saleId", column: v === MAKE ? null : v, make: v === MAKE })}
          />
          <div className="wiz-samples">
            <CheckText check={data.sale_id.check} />
          </div>
        </div>
      </div>
      <MatchPanel projectId={project.id} data={data} file={sales} change={change} />
    </>
  );
}
