import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Input, Popover, SearchField } from "react-aria-components";
import { short } from "../lib/format";
import { t } from "../wording";
import { AddButton } from "./AddButton";
import { Tick } from "./Form";
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
  const listed = new Set(values.map((x) => x.value));
  const extra = chosen
    .filter((c) => !listed.has(c))
    .map((value) => ({ value, count: -1 }) as (typeof values)[number]);
  const q = search.trim().toLowerCase();
  const text = (x: (typeof values)[number]) => x.label ?? (x.value || m.blank);
  const rows = [...extra, ...values].filter(
    (x) => !q || `${text(x)} ${x.note ?? ""}`.toLowerCase().includes(q),
  );
  const toggle = (value: string, on: boolean) =>
    onChange(on ? [...chosen, value] : chosen.filter((c) => c !== value));
  const typed = search.trim();
  const canAdd = typed !== "" && !listed.has(typed) && !chosen.includes(typed);
  const labels = new Map(values.map((x) => [x.value, text(x)]));
  const named = values.some((x) => x.label);
  const names = chosen.map((c) => labels.get(c) ?? (c ? short(c) : m.blank));
  const shown = names.join(", ");
  const said =
    brief && names.length > 1 ? m.plusOthers({ first: names[0] ?? "", n: names.length - 1 }) : shown;
  return (
    <DialogTrigger onOpenChange={(open) => !open && setSearch("")}>
      <Button className="mp-button" aria-label={`${label}: ${chosen.length ? shown : m.none}`}>
        <span className={chosen.length ? (named ? "mp-text" : "mp-text mono") : "mp-text mp-placeholder"}>
          {chosen.length ? said : (placeholder ?? m.choose)}
        </span>
        {chosen.length > 1 && !brief && <span className="pill pill-info">{chosen.length}</span>}
        <ChevronDown aria-hidden="true" size="0.9em" />
      </Button>
      <Popover className="popover mp-popover" placement="bottom start">
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
            <span>{m.chosen({ n: chosen.length, of: values.length + extra.length })}</span>
            <span className="mp-grow" />
            <Button
              className="button button-small"
              isDisabled={rows.length === 0}
              onPress={() => onChange([...new Set([...chosen, ...rows.map((x) => x.value)])])}
            >
              {q ? m.allShown : m.all}
            </Button>
            <Button
              className="button button-small"
              isDisabled={chosen.length === 0}
              onPress={() => onChange([])}
            >
              {m.clear}
            </Button>
          </div>
          <div className="mp-list">
            {rows.map((x) => (
              <Tick
                key={x.value}
                isSelected={chosen.includes(x.value)}
                onChange={(on) => toggle(x.value, on)}
              >
                <span className={x.label ? "mp-value" : "mp-value mono"}>
                  <Val v={text(x)} max={60} />
                </span>
                {x.note && <span className="mp-n mono">{x.note}</span>}
                {x.count !== undefined && x.count >= 0 && (
                  <span className="mp-n">{x.count.toLocaleString()}</span>
                )}
              </Tick>
            ))}
            {rows.length === 0 && !canAdd && <p className="vals-sub">{m.noMatch}</p>}
          </div>
          {canAdd && more > 0 && (
            <AddButton
              onPress={() => {
                onChange([...chosen, typed]);
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
