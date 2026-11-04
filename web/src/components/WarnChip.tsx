import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import { CloseButton } from "./Buttons";

/** A warning inside a row of settings, kept to the row's one line: ⚠ and a title of a few words, as a button; the
 * whole explanation (and what to do) opens beside it. A long explanation on a line of its own is a Callout. */
export function WarnChip({ title, children }: { title: string; children: ReactNode }) {
  return (
    <DialogTrigger>
      <Button className="warn-chip">
        <img src={warningIcon} alt="" className="wiz-inline-icon" />
        {title}
        <ChevronDown aria-hidden="true" size="0.85em" />
      </Button>
      <Popover className="popover warn-pop" placement="bottom start">
        <Dialog className="popover-body warn-body" aria-label={title}>
          {({ close }) => (
            <>
              <span className="warn-close">
                <CloseButton onPress={close} />
              </span>
              {children}
            </>
          )}
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}
