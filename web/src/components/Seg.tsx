import { Button } from "react-aria-components";
import { useAtOnce } from "../lib/hooks";

/** A row of buttons, one pressed: a choice of two or three short options in one line. None pressed while
 * nothing's chosen yet. */
export function Seg<V extends string>({
  value: chosen,
  options,
  onChange,
  label,
  disabled = [],
  titles = {},
}: {
  value: V | null;
  options: readonly (readonly [V, string])[];
  onChange: (v: V) => void;
  label?: string;
  /** Options that can't be chosen here; their title says why. */
  disabled?: readonly V[];
  titles?: Partial<Record<V, string>>;
}) {
  // The one pressed shows at once, while it saves (AGENTS.md).
  const [value, press] = useAtOnce(chosen);
  return (
    // biome-ignore lint/a11y/useSemanticElements: a button group, not a form field set
    <span className="seg" role="group" aria-label={label}>
      {options.map(([k, text]) => (
        <Button
          key={k}
          className={k === value ? "seg-b on" : "seg-b"}
          onPress={() => {
            // The one already pressed: nothing to change, nothing to save.
            if (k === value) return;
            press(k);
            onChange(k);
          }}
          aria-pressed={k === value}
          isDisabled={disabled.includes(k)}
          {...(titles[k] ? { "aria-description": titles[k] } : {})}
        >
          <span title={titles[k]}>{text}</span>
        </Button>
      ))}
    </span>
  );
}
