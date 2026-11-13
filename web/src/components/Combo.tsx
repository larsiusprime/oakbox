/** A dropdown you can type in to narrow its list (SPEC D43): every dropdown of 7 or more choices, and the column
 * picker. It looks like the others until clicked; clicking opens the whole list, typing keeps the choices whose
 * names hold what's typed (anywhere in the name), the letters marked; Enter picks the first, Esc or leaving puts
 * back what was chosen. */
import { ChevronDown } from "lucide-react";
import { type ReactNode, useContext, useEffect, useRef, useState } from "react";
import {
  Button,
  ComboBox,
  ComboBoxStateContext,
  Group,
  Input,
  Label,
  ListBox,
  Popover,
} from "react-aria-components";
import { afterPaint, useAtOnce } from "../lib/hooks";
import { t } from "../wording";

/** Dropdowns with this many choices or more can be typed in. */
export const TYPE_FROM = 7;

/** Whether a name holds what's typed (case aside); nothing typed: every name. */
export function matches(name: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  return !q || name.toLowerCase().includes(q);
}

/** A name with what's typed marked in it. */
export function Marked({ text, query }: { text: string; query: string }) {
  const q = query.trim().toLowerCase();
  const i = q ? text.toLowerCase().indexOf(q) : -1;
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="combo-mark">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

export function Combo({
  label,
  hideLabel = false,
  selectedKey,
  onChange,
  disabledKeys,
  isDisabled = false,
  className = "field choice",
  popoverClassName = "popover choice-popover",
  placeholder = "",
  size,
  mono = false,
  muted = false,
  count,
  first,
  children,
}: {
  label: string;
  hideLabel?: boolean;
  selectedKey: string | null;
  onChange: (key: string) => void;
  disabledKeys?: string[];
  isDisabled?: boolean;
  className?: string;
  popoverClassName?: string;
  placeholder?: string;
  /** The box's width, in characters: the longest choice, so it's as wide as the dropdown it replaces. */
  size?: number;
  /** The chosen name in the box is a column's: in the code font. */
  mono?: boolean;
  /** Nothing is chosen ("(none)"): the box's text greyed. */
  muted?: boolean;
  /** How many choices match what's typed, of how many. */
  count: (query: string) => [number, number];
  /** The first choice matching what's typed: highlighted, so Enter picks it. */
  first: (query: string) => string | null;
  /** The list's items for what's typed. */
  children: (query: string) => ReactNode;
}) {
  // What's typed to narrow the list: empty while the list is opened by a click (it shows every choice).
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const arrow = useRef<HTMLButtonElement>(null);
  // What was picked shows at once and the list closes (AGENTS.md); the work it starts (a save, a file read) only
  // after that's on screen.
  const [value, pick] = useAtOnce(selectedKey);
  const [shown, total] = count(query);
  return (
    <ComboBox
      className={className}
      selectedKey={value}
      onSelectionChange={(k) => {
        setQuery("");
        if (k === null || String(k) === value) return;
        const key = String(k);
        pick(key);
        afterPaint(() => onChange(key));
      }}
      onInputChange={setQuery}
      onOpenChange={(isOpen, how) => {
        setOpen(isOpen);
        if (!isOpen || how === "manual" || how === "focus") setQuery("");
      }}
      // The list is narrowed here (names only, marked), not by the box's own filter.
      defaultFilter={() => true}
      allowsEmptyCollection
      {...(disabledKeys ? { disabledKeys } : {})}
      {...(isDisabled ? { isDisabled: true } : {})}
      {...(hideLabel ? { "aria-label": label } : {})}
    >
      {!hideLabel && <Label className="field-label">{label}</Label>}
      <Group className="choice-button combo-field">
        <Input
          className={["combo-input", mono ? "mono" : "", muted ? "wiz-none" : ""].join(" ")}
          placeholder={placeholder}
          {...(size ? { size } : {})}
          // Coming to the box selects what's in it, so typing replaces it (not again while its list is open).
          onFocus={(e) => !open && e.currentTarget.select()}
          onClick={() => !open && arrow.current?.click()}
        />
        <Button ref={arrow} className="combo-arrow">
          <ChevronDown aria-hidden="true" size="0.9em" />
        </Button>
      </Group>
      <FirstMatch keyOf={query.trim() ? first(query) : null} />
      <Popover className={popoverClassName} offset={0}>
        <ListBox
          className="choice-list"
          renderEmptyState={() => <p className="combo-none">{t.combo.none}</p>}
        >
          {children(query)}
        </ListBox>
        {query.trim() && (
          <p className="combo-count">{t.combo.count({ n: shown, of: total, typed: query.trim() })}</p>
        )}
      </Popover>
    </ComboBox>
  );
}

/** Highlights the first match as the list narrows (the box itself highlights nothing until an arrow key). */
function FirstMatch({ keyOf }: { keyOf: string | null }) {
  const state = useContext(ComboBoxStateContext);
  useEffect(() => {
    if (state && keyOf !== null) state.selectionManager.setFocusedKey(keyOf);
  }, [state, keyOf]);
  return null;
}
