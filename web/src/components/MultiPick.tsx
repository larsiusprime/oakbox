import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Input, Popover, SearchField } from "react-aria-components";
import { t } from "../strings";
import { Tick } from "./Form";

const m = t.multiPick;

/** Pick several values in one line: the button lists what's chosen; it opens a searchable checklist with each
 * value's count. Values typed in are kept when the list doesn't show them all. */
export function MultiPick({
  label,
  values,
  more = 0,
  chosen,
  onChange,
  countNoun,
}: {
  label: string;
  values: { value: string; count: number }[];
  more?: number;
  chosen: string[];
  onChange: (v: string[]) => void;
  /** What a count counts ("parcels"), for the list's header. */
  countNoun: string;
}) {
  const [search, setSearch] = useState("");
  const listed = new Set(values.map((x) => x.value));
  const extra = chosen.filter((c) => !listed.has(c)).map((value) => ({ value, count: -1 }));
  const q = search.trim().toLowerCase();
  const rows = [...extra, ...values].filter((x) => !q || (x.value || m.blank).toLowerCase().includes(q));
  const toggle = (value: string, on: boolean) =>
    onChange(on ? [...chosen, value] : chosen.filter((c) => c !== value));
  const typed = search.trim();
  const canAdd = typed !== "" && !listed.has(typed) && !chosen.includes(typed);
  const shown = chosen.map((c) => c || m.blank).join(", ");
  return (
    <DialogTrigger onOpenChange={(open) => !open && setSearch("")}>
      <Button className="mp-button" aria-label={`${label}: ${chosen.length ? shown : m.none}`}>
        <span className={chosen.length ? "mp-text mono" : "mp-text mp-placeholder"}>
          {chosen.length ? shown : m.choose}
        </span>
        {chosen.length > 1 && <span className="pill pill-info">{chosen.length}</span>}
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
            <span>{m.chosen(chosen.length, values.length + extra.length)}</span>
            <span className="mp-grow" />
            <Button
              className="wiz-link"
              isDisabled={rows.length === 0}
              onPress={() => onChange([...new Set([...chosen, ...rows.map((x) => x.value)])])}
            >
              {q ? m.allShown : m.all}
            </Button>
            <Button className="wiz-link" isDisabled={chosen.length === 0} onPress={() => onChange([])}>
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
                <span className="mp-value mono">{x.value || m.blank}</span>
                {x.count >= 0 && <span className="mp-n">{x.count.toLocaleString()}</span>}
              </Tick>
            ))}
            {rows.length === 0 && !canAdd && <p className="vals-sub">{m.noMatch}</p>}
          </div>
          {canAdd && more > 0 && (
            <Button
              className="wiz-link"
              onPress={() => {
                onChange([...chosen, typed]);
                setSearch("");
              }}
            >
              {m.add(typed)}
            </Button>
          )}
          {more > 0 && <p className="vals-sub">{m.more(more)}</p>}
          <p className="vals-sub mp-noun">{m.counts(countNoun)}</p>
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}
