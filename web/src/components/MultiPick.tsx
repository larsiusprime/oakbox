import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Input, Popover, SearchField } from "react-aria-components";
import { num, short } from "../lib/format";
import { t } from "../wording";
import { AddButton } from "./AddButton";
import { Tick } from "./Form";
import { RemoveTextButton } from "./RemoveButton";
import { Val } from "./Val";

const m = t.multiPick;

/** Pick several things in one line, values or fields: the button lists what's chosen; it opens a searchable
 * checklist, each with its count or a note (a field's column). Values typed in are kept when the list doesn't show
 * them all. The one way to pick fields or values from a list: not chips, not a row of ticks. */
export function MultiPick({
  label,
  values,
  more = 0,
  chosen,
  onChange,
  countNoun,
  placeholder,
  brief = false,
}: {
  label: string;
  /** label: shown instead of the value (a field's name); note: beside it (its column); count: -1 or none for none. */
  values: { value: string; count?: number; label?: string; note?: string }[];
  more?: number;
  chosen: string[];
  onChange: (v: string[]) => void;
  /** What a count counts ("parcels"), for the list's foot; none without counts. */
  countNoun?: string;
  /** What the button says while nothing is chosen. */
  placeholder?: string;
  /** The button says the first chosen and how many more ("Sale price + 6 others"), not every one. */
  brief?: boolean;
}) {
  const [search, setSearch] = useState("");
  // While the list is open, the choice is a draft here: ticking, All and Clear change it at once and save nothing.
  // Closing the list saves it, once, if it changed (AGENTS.md: a box of choices isn't wired to saves while open).
  const [draft, setDraft] = useState<string[] | null>(null);
  const picked = draft ?? chosen;
  const onOpenChange = (open: boolean) => {
    if (open) {
      setDraft(chosen);
      return;
    }
    if (draft && (draft.length !== chosen.length || draft.some((v, i) => v !== chosen[i]))) onChange(draft);
    setDraft(null);
    setSearch("");
  };
  const listed = new Set(values.map((x) => x.value));
  const extra = picked
    .filter((c) => !listed.has(c))
    .map((value) => ({ value, count: -1 }) as (typeof values)[number]);
  const q = search.trim().toLowerCase();
  const text = (x: (typeof values)[number]) => x.label ?? (x.value || m.blank);
  const rows = [...extra, ...values].filter(
    (x) => !q || `${text(x)} ${x.note ?? ""}`.toLowerCase().includes(q),
  );
  const toggle = (value: string, on: boolean) =>
    setDraft((d) => {
      const now = d ?? chosen;
      return on ? [...now.filter((c) => c !== value), value] : now.filter((c) => c !== value);
    });
  const typed = search.trim();
  const canAdd = typed !== "" && !listed.has(typed) && !picked.includes(typed);
  const labels = new Map(values.map((x) => [x.value, text(x)]));
  const named = values.some((x) => x.label);
  const names = picked.map((c) => labels.get(c) ?? (c ? short(c) : m.blank));
  const shown = names.join(", ");
  const said =
    brief && names.length > 1 ? m.plusOthers({ first: names[0] ?? "", n: names.length - 1 }) : shown;
  return (
    <DialogTrigger onOpenChange={onOpenChange}>
      <Button className="mp-button" aria-label={`${label}: ${picked.length ? shown : m.none}`}>
        <span className={picked.length ? (named ? "mp-text" : "mp-text mono") : "mp-text mp-placeholder"}>
          {picked.length ? said : (placeholder ?? m.choose)}
        </span>
        {picked.length > 1 && !brief && <span className="pill pill-info">{picked.length}</span>}
        <ChevronDown aria-hidden="true" size="0.9em" />
      </Button>
      <Popover className="popover mp-popover" placement="bottom start" offset={0}>
        <Dialog className="mp-body" aria-label={label}>
          {(values.length > 10 || more > 0) && (
            <SearchField
              aria-label={m.search}
              value={search}
              onChange={setSearch}
              className="vals-search"
              autoFocus
            >
              <Input className="input vals-search-input" placeholder={m.search} />
            </SearchField>
          )}
          <div className="mp-head">
            <span>{m.chosen({ n: picked.length, of: values.length + extra.length })}</span>
            <span className="mp-grow" />
            <Button
              className="button button-small"
              isDisabled={rows.length === 0}
              onPress={() => setDraft([...new Set([...picked, ...rows.map((x) => x.value)])])}
            >
              {q ? m.allShown : m.all}
            </Button>
            <RemoveTextButton small isDisabled={picked.length === 0} onPress={() => setDraft([])}>
              {m.clear}
            </RemoveTextButton>
          </div>
          <div className="mp-list">
            {rows.map((x) => (
              <Tick
                key={x.value}
                isSelected={picked.includes(x.value)}
                onChange={(on) => toggle(x.value, on)}
              >
                <span className={x.label ? "mp-value" : "mp-value mono"}>
                  <Val v={text(x)} max={60} />
                </span>
                {x.note && <span className="mp-n mono">{x.note}</span>}
                {x.count !== undefined && x.count >= 0 && <span className="mp-n">{num(x.count)}</span>}
              </Tick>
            ))}
            {rows.length === 0 && !canAdd && <p className="vals-sub">{m.noMatch}</p>}
          </div>
          {canAdd && more > 0 && (
            <AddButton
              onPress={() => {
                setDraft([...picked, typed]);
                setSearch("");
              }}
            >
              {m.add({ v: typed })}
            </AddButton>
          )}
          {more > 0 && <p className="vals-sub">{m.more({ n: more })}</p>}
          {countNoun && <p className="vals-sub mp-noun">{m.counts({ noun: countNoun })}</p>}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}
