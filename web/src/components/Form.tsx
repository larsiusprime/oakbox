import { Check, ChevronDown } from "lucide-react";
import {
  Button,
  Checkbox,
  CheckboxGroup,
  FieldError,
  Focusable,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  RadioGroup,
  type RadioGroupProps,
  Select,
  SelectValue,
  Text,
  TextField,
} from "react-aria-components";
import { useAtOnce } from "../lib/hooks";
import { Combo, Marked, matches, TYPE_FROM } from "./Combo";
import { FileName } from "./FileEntry";
import { Tip } from "./Tip";

/** A labelled text input. Inputs look sunken; they are filled, not pressed. */
export function Field(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  help?: string;
  /** Help shown on hover and focus instead (SPEC D42). */
  tip?: string;
  type?: "text" | "date" | "number";
  width?: "short" | "medium" | "long";
  autoFocus?: boolean;
}) {
  return (
    <TextField
      className={`field field-${props.width ?? "medium"}`}
      value={props.value}
      onChange={props.onChange}
      {...(props.onBlur ? { onBlur: props.onBlur } : {})}
      type={props.type ?? "text"}
      {...(props.autoFocus ? { autoFocus: true } : {})}
    >
      <Label className="field-label">{props.label}</Label>
      {props.tip ? (
        <Tip text={props.tip}>
          <Focusable>
            <Input className="input" />
          </Focusable>
        </Tip>
      ) : (
        <Input className="input" />
      )}
      {props.help && (
        <Text slot="description" className="field-help">
          {props.help}
        </Text>
      )}
      <FieldError className="error" />
    </TextField>
  );
}

/** A dropdown. Options are [value, label] pairs. With 7 or more, it can be typed in to narrow the list (Combo). */
export function Choice<V extends string>(props: {
  label: string;
  value: V | null;
  /** [value, label], or [value, label, file name]: a file's own name, shown after the label like code. */
  options: readonly (readonly [V, string] | readonly [V, string, string])[];
  onChange: (v: V) => void;
  placeholder?: string;
  hideLabel?: boolean;
  isDisabled?: boolean;
  /** A note beside an option in the list (e.g. "not installed · 97 MB"). */
  aside?: Partial<Record<V, string>>;
}) {
  // What was picked shows at once, while it saves (AGENTS.md).
  const [value, pick_] = useAtOnce(props.value);
  const onPick = (v: V) => {
    if (v === value) return; // picked again: nothing to save
    pick_(v);
    props.onChange(v);
  };
  const aside = (v: V) => props.aside?.[v] && <span className="choice-aside">{props.aside[v]}</span>;
  if (props.options.length >= TYPE_FROM) {
    const pick = (q: string) =>
      props.options.filter(([, label, file]) => matches(`${label} ${file ?? ""}`, q));
    return (
      <Combo
        label={props.label}
        selectedKey={value}
        onChange={(k) => onPick(k as V)}
        placeholder={props.placeholder ?? ""}
        size={Math.min(
          40,
          Math.max(...props.options.map(([, l, f]) => l.length + (f ? f.length + 1 : 0))) + 1,
        )}
        {...(props.hideLabel ? { hideLabel: true } : {})}
        {...(props.isDisabled ? { isDisabled: true } : {})}
        count={(q) => [pick(q).length, props.options.length]}
        first={(q) => pick(q)[0]?.[0] ?? null}
      >
        {(q) =>
          pick(q).map(([value, label, file]) => (
            <ListBoxItem key={value} id={value} className="choice-item" textValue={label}>
              <Marked text={label} query={q} />
              {file && (
                <>
                  {" "}
                  <FileName filename={file} />
                </>
              )}
              {aside(value)}
            </ListBoxItem>
          ))
        }
      </Combo>
    );
  }
  return (
    <Select
      className="field choice"
      {...(props.isDisabled ? { isDisabled: true } : {})}
      selectedKey={value}
      onSelectionChange={(k) => k !== null && onPick(String(k) as V)}
      placeholder={props.placeholder ?? ""}
      {...(props.hideLabel ? { "aria-label": props.label } : {})}
    >
      {!props.hideLabel && <Label className="field-label">{props.label}</Label>}
      <Button className="choice-button">
        <SelectValue className="choice-value" />
        <span className="combo-arrow" aria-hidden="true">
          <ChevronDown size="0.9em" />
        </span>
      </Button>
      <Popover className="popover choice-popover" offset={0}>
        <ListBox className="choice-list">
          {props.options.map(([value, label, file]) => (
            <ListBoxItem key={value} id={value} className="choice-item" textValue={label}>
              {label}
              {file && (
                <>
                  {" "}
                  <FileName filename={file} />
                </>
              )}
              {aside(value)}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}

/** Several checkboxes, e.g. what a file contains. */
export function CheckList<V extends string>(props: {
  label: string;
  value: readonly V[];
  options: readonly (readonly [V, string])[];
  onChange: (v: V[]) => void;
  help?: string;
}) {
  const [value, press] = useAtOnce<readonly V[]>(props.value);
  return (
    <CheckboxGroup
      className="field checklist"
      value={[...value]}
      onChange={(v) => {
        press(v as V[]);
        props.onChange(v as V[]);
      }}
    >
      <Label className="field-label">{props.label}</Label>
      <div className="checklist-items">
        {props.options.map(([value, label]) => (
          <Tick key={value} value={value}>
            {label}
          </Tick>
        ))}
      </div>
      {props.help && (
        <Text slot="description" className="field-help">
          {props.help}
        </Text>
      )}
    </CheckboxGroup>
  );
}

/** A radio group whose choice shows at once while it saves (AGENTS.md): react-aria's RadioGroup, otherwise the same. */
export function Radios(props: RadioGroupProps) {
  const [value, press] = useAtOnce(props.value);
  const { onChange } = props;
  return (
    <RadioGroup
      {...props}
      {...(value !== undefined ? { value } : {})}
      {...(onChange
        ? {
            onChange: (v: string) => {
              if (v === value) return; // the one already chosen: nothing to save
              if (props.value !== undefined) press(v);
              onChange(v);
            },
          }
        : {})}
    />
  );
}

export function Tick(props: {
  value?: string;
  isSelected?: boolean;
  isDisabled?: boolean;
  onChange?: (v: boolean) => void;
  children: React.ReactNode;
}) {
  const [selected, press] = useAtOnce(props.isSelected);
  const onChange = props.onChange;
  return (
    <Checkbox
      className="tick"
      {...(props.isDisabled ? { isDisabled: true } : {})}
      {...(props.value !== undefined ? { value: props.value } : {})}
      {...(selected !== undefined ? { isSelected: selected } : {})}
      {...(onChange
        ? {
            onChange: (v: boolean) => {
              if (props.isSelected !== undefined) press(v);
              onChange(v);
            },
          }
        : {})}
    >
      {({ isSelected }) => (
        <>
          <span className="tick-box" aria-hidden="true">
            {isSelected && <Check size="0.85em" strokeWidth={3.5} />}
          </span>
          <span>{props.children}</span>
        </>
      )}
    </Checkbox>
  );
}
