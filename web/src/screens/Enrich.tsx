import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Globe } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Input, Popover, TextField } from "react-aria-components";
import { api, type EnrichAddField, type Enrichments, type EnrichView, unwrap } from "../api/client";
import { CensusKey } from "../components/CensusKey";
import { Choice, Tick } from "../components/Form";
import { useAtOnce } from "../lib/hooks";
import { say, t } from "../wording";

const e = t.wizard.enrich;

/** F3e, Enrichments: public data about each parcel, downloaded as Bring in data runs. One card each: on or off,
 * where it comes from and what it sends, its options, and the fields it adds. */
export function EnrichStep({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["enrich", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/enrich", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  const save = useMutation({
    mutationFn: async (body: Enrichments) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/wizard/enrich", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: async (data) => {
      queryClient.setQueryData(["enrich", projectId], data);
      // The step's mark (census without a key or county) and Bring in data's "changed since".
      await queryClient.invalidateQueries({ queryKey: ["wizard", projectId] });
    },
  });
  const v = q.data;
  if (!v) return null;
  const s = v.settings;
  const set = (patch: Partial<Enrichments>) => save.mutate({ ...s, ...patch });
  const adds = (key: string) => v.adds.find((a) => a.enrichment === key)?.fields ?? [];
  // A field ticked or not: a distance kind, or a field of footprints, census or elevation.
  // Fields ticked or not in a list (saved together when it closes): distance kinds, or fields of footprints, census
  // or elevation.
  const kinds = (changes: [string, boolean][]) => {
    let k = [...s.kinds];
    for (const [key, on] of changes)
      k = on
        ? [...k.filter((x) => x !== key), key as Enrichments["kinds"][number]]
        : k.filter((x) => x !== key);
    set({ kinds: k });
  };
  const field = (changes: [string, boolean][]) => {
    let off = [...s.off];
    for (const [key, on] of changes)
      off = on ? off.filter((f) => f !== key) : [...off.filter((f) => f !== key), key];
    set({ off });
  };

  return (
    <div className="en">
      <p className="en-note">
        <Globe aria-hidden="true" size="1.1em" />
        <span>{e.online({ km2: v.area ? v.area.km2 : null })}</span>
      </p>

      <Card
        title={e.distances}
        from={e.distancesFrom}
        sends={e.distancesSends}
        on={s.distances}
        onChange={(distances) => set({ distances })}
      >
        <Distances view={v} save={(features) => set({ features })} />
        <Picks label={e.addsPerFeature} title={e.distances} fields={adds("distances")} toggle={kinds} />
      </Card>

      <Card
        title={e.footprints}
        from={e.footprintsFrom}
        sends={e.footprintsSends}
        on={s.footprints}
        onChange={(footprints) => set({ footprints })}
      >
        <Picks label={e.adds} title={e.footprints} fields={adds("footprints")} toggle={field} />
      </Card>

      <Card
        title={e.census}
        from={e.censusFrom}
        sends={e.censusSends}
        on={s.census}
        onChange={(census) => set({ census })}
        off={v.key_saved ? undefined : e.censusOff}
      >
        <CensusKey saved={v.key_saved ? v.key_end : null} />
        <div className="en-row">
          <span className="en-lab">{e.county}</span>
          <Choice
            label={e.county}
            hideLabel
            value={s.fips}
            placeholder={e.countyPick}
            options={v.counties.map((c) => [c.fips, `${c.name}, ${c.state} (${c.fips})`] as const)}
            onChange={(fips) => set({ fips })}
          />
          {s.fips && s.fips === v.county_guess && !v.county_off && (
            <span className="en-sub">{e.countyGuess}</span>
          )}
          {v.county_off && (
            <span className="wiz-warn">
              {v.county_off.replace(/^Census: /, "")}
              {v.county_guess && v.county_guess !== s.fips && (
                <>
                  {" "}
                  <Button className="button button-small" onPress={() => set({ fips: v.county_guess })}>
                    {e.useCounty}
                  </Button>
                </>
              )}
            </span>
          )}
        </div>
        <div className="en-row">
          <span className="en-lab">{e.year}</span>
          <Choice
            label={e.year}
            hideLabel
            value={String(s.census_year)}
            options={v.years.map((y) => [String(y), e.yearOf({ y })] as const)}
            onChange={(y) => set({ census_year: Number(y) })}
          />
        </div>
        <Picks label={e.addsByBlockGroup} title={e.census} fields={adds("census")} toggle={field} />
      </Card>

      <Card
        title={e.elevation}
        from={e.elevationFrom}
        sends={e.elevationSends}
        on={s.elevation}
        onChange={(elevation) => set({ elevation })}
      >
        <div className="en-row">
          <span className="en-lab">{e.detail}</span>
          <Choice
            label={e.detail}
            hideLabel
            value={String(s.resolution_m)}
            options={([10, 30, 60] as const).map((m) => [String(m), e.resolution({ m })] as const)}
            onChange={(m) => set({ resolution_m: Number(m) as 10 | 30 | 60 })}
          />
          <span className="en-sub">{e.suggested({ m: v.resolution, km2: v.area ? v.area.km2 : null })}</span>
        </div>
        <Picks label={e.adds} title={e.elevation} fields={adds("elevation")} toggle={field} />
      </Card>
      {save.error && (
        <p className="error" role="alert">
          {save.error.message}
        </p>
      )}
    </div>
  );
}

function Card({
  title,
  from,
  sends,
  on,
  onChange,
  off,
  children,
}: {
  title: string;
  from: string;
  sends: string;
  on: boolean;
  onChange: (on: boolean) => void;
  off?: string | undefined;
  children: ReactNode;
}) {
  return (
    <section className={on ? "en-card" : "en-card is-off"}>
      <div className="en-head">
        <Tick isSelected={on} onChange={onChange}>
          <b>{title}</b>
        </Tick>
        <span className="en-sub">{from}</span>
      </div>
      <div className="en-body">
        <span className="en-online">
          <Globe aria-label={e.onlineShort} size="0.9em" /> {sends}
        </span>
        {on ? children : off && <span className="en-sub">{off}</span>}
      </div>
    </section>
  );
}

/** The fields an enrichment adds: "3 fields ▾" and their names; the button opens them as checkboxes, each saying
 * what it is. Unticked ones are dropped as the run ends, and an enrichment with none ticked isn't downloaded. */
function Picks({
  label,
  title,
  fields,
  toggle,
}: {
  label: string;
  title: string;
  fields: EnrichAddField[];
  /** The fields ticked or unticked while the list was open: saved once, when it closes. */
  toggle: (changes: [string, boolean][]) => void;
}) {
  const [open, setOpen] = useState(false);
  // While the list is open, the ticks are a draft here (AGENTS.md: a box of choices isn't wired to saves while open).
  const [draft, setDraft] = useState<Record<string, boolean> | null>(null);
  // Once closed, the ticks stay as left while they save, not as they were (AGENTS.md).
  const saved = Object.fromEntries(fields.map((f) => [f.key, f.on]));
  const [held, hold] = useAtOnce<Record<string, boolean>>(saved);
  const isOn = (f: EnrichAddField) => draft?.[f.key] ?? held[f.key] ?? f.on;
  const onOpenChange = (o: boolean) => {
    setOpen(o);
    if (o) return setDraft({});
    const changes = Object.entries(draft ?? {}).filter(([k, v]) => (held[k] ?? saved[k]) !== v);
    if (changes.length) {
      hold({ ...held, ...draft });
      toggle(changes);
    }
    setDraft(null);
  };
  const on = fields.filter(isOn);
  return (
    <div className="en-row">
      <span className="en-lab">{label}</span>
      <DialogTrigger isOpen={open} onOpenChange={onOpenChange}>
        <Button className="button button-small vals-button">
          {say.wizard.enrich.fieldsOf(on.length, fields.length)}
          <ChevronDown aria-hidden="true" size="0.85em" />
        </Button>
        <Popover className="popover" placement="bottom start" offset={0}>
          <Dialog className="popover-body en-fields" aria-label={e.fieldsTitle({ name: title })}>
            <Heading slot="title" className="vals-title">
              {e.fieldsTitle({ name: title })}
            </Heading>
            {fields.map((f) => (
              <Tick
                key={f.key}
                isSelected={isOn(f)}
                onChange={(v) => setDraft((x) => ({ ...x, [f.key]: v }))}
              >
                <span className="en-field">
                  <span className="mono">{f.name}</span>
                  <span className="en-sub">{f.what}</span>
                </span>
              </Tick>
            ))}
            <p className="en-sub">{e.fieldsNote}</p>
          </Dialog>
        </Popover>
      </DialogTrigger>
      {on.length ? (
        <span className="en-sub mono">{on.map((f) => f.name).join(", ")}</span>
      ) : (
        <span className="wiz-warn">{e.noneTicked}</span>
      )}
    </div>
  );
}

/** The OpenStreetMap features: a line summing them up, and Change… for each one's options. */
function Distances({ view, save }: { view: EnrichView; save: (f: Enrichments["features"]) => void }) {
  const [open, setOpen] = useState(false);
  const s = view.settings;
  const unit = e.units[view.unit] ?? view.unit;
  const on = view.features.filter((f) => s.features[f.key]?.on);
  const set = (key: string, patch: Partial<Enrichments["features"][string]>) => {
    const f = s.features[key];
    if (f) save({ ...s.features, [key]: { ...f, ...patch } });
  };
  if (!open) {
    const far = on.map((f) => s.features[f.key]?.max_distance ?? 0);
    const range = far.length ? `${Math.min(...far)}–${Math.max(...far)}`.replace(/^(\S+)–\1$/, "$1") : "";
    return (
      <div className="en-row">
        <span className="en-sub">
          {say.wizard.enrich.summary(on.map((f) => f.label))}
          {range && ` · ${e.upTo} ${range} ${unit}`}
        </span>
        <Button className="button button-small" onPress={() => setOpen(true)}>
          {e.change}
        </Button>
      </div>
    );
  }
  return (
    <>
      <div className="en-feats">
        {view.features.map((f) => {
          const x = s.features[f.key];
          if (!x) return null;
          const taken = view.taken.includes(f.key);
          return (
            <div key={f.key} className="en-feat">
              <Tick isSelected={x.on} onChange={(v) => set(f.key, { on: v })}>
                {f.label}
              </Tick>
              <span className="en-sub">{f.what}</span>
              <span className="en-dist">
                <Num
                  label={e.maxDistance({ label: f.label })}
                  value={x.max_distance}
                  onChange={(max_distance) => set(f.key, { max_distance })}
                />
                {unit}
              </span>
              <span className="en-sub">
                {taken ? (
                  e.taken({ label: f.label })
                ) : f.named && x.on ? (
                  <Choice
                    label={e.largestLabel}
                    hideLabel
                    value={String(x.top_n)}
                    options={[0, 1, 2, 3, 5].map(
                      (n) => [String(n), n ? e.largest({ n }) : e.noneLargest] as const,
                    )}
                    onChange={(n) => set(f.key, { top_n: Number(n) })}
                  />
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
      <div className="en-row">
        <Button className="button button-small" onPress={() => setOpen(false)}>
          {e.done}
        </Button>
      </div>
    </>
  );
}

function Num({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  // What's typed, until it's saved; otherwise the value as it is.
  const [draft, setDraft] = useState<string | null>(null);
  // What was saved stays shown while it saves, not the old value (AGENTS.md).
  const [held, hold] = useAtOnce(value);
  const text = draft ?? String(held);
  const commit = () => {
    const n = Number.parseFloat(text);
    if (n > 0 && n !== held) {
      hold(n);
      onChange(n);
    }
    setDraft(null);
  };
  return (
    <TextField aria-label={label} value={text} onChange={setDraft} onBlur={commit} className="ly-max">
      <Input
        className="input ly-input wiz-num"
        inputMode="decimal"
        onKeyDown={(k) => {
          if (k.key === "Enter") commit();
        }}
      />
    </TextField>
  );
}
