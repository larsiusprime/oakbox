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
  Select,
  SelectValue,
  Text,
  TextField,
} from "react-aria-components";
import { Combo, Marked, matches, TYPE_FROM } from "./Combo";
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
  options: readonly (readonly [V, string])[];
  onChange: (v: V) => void;
  placeholder?: string;
  hideLabel?: boolean;
  isDisabled?: boolean;
  /** A note beside an option in the list (e.g. "not installed · 97 MB"). */
  aside?: Partial<Record<V, string>>;
}) {
  const aside = (v: V) => props.aside?.[v] && <span className="choice-aside">{props.aside[v]}</span>;
  if (props.options.length >= TYPE_FROM) {
    const pick = (q: string) => props.options.filter(([, label]) => matches(label, q));
    return (
      <Combo
        label={props.label}
        selectedKey={props.value}
        onChange={(k) => props.onChange(k as V)}
        placeholder={props.placeholder ?? ""}
        size={Math.min(40, Math.max(...props.options.map(([, l]) => l.length)) + 1)}
        {...(props.hideLabel ? { hideLabel: true } : {})}
        {...(props.isDisabled ? { isDisabled: true } : {})}
        count={(q) => [pick(q).length, props.options.length]}
        first={(q) => pick(q)[0]?.[0] ?? null}
      >
        {(q) =>
          pick(q).map(([value, label]) => (
            <ListBoxItem key={value} id={value} className="choice-item" textValue={label}>
              <Marked text={label} query={q} />
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
      selectedKey={props.value}
      onSelectionChange={(k) => k !== null && props.onChange(String(k) as V)}
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
      <Popover className="popover choice-popover">
        <ListBox className="choice-list">
          {props.options.map(([value, label]) => (
            <ListBoxItem key={value} id={value} className="choice-item" textValue={label}>
              {label}
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
  return (
    <CheckboxGroup
      className="field checklist"
      value={[...props.value]}
      onChange={(v) => props.onChange(v as V[])}
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

export function Tick(props: {
  value?: string;
  isSelected?: boolean;
  isDisabled?: boolean;
  onChange?: (v: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <Checkbox
      className="tick"
      {...(props.isDisabled ? { isDisabled: true } : {})}
      {...(props.value !== undefined ? { value: props.value } : {})}
      {...(props.isSelected !== undefined ? { isSelected: props.isSelected } : {})}
      {...(props.onChange ? { onChange: props.onChange } : {})}
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
