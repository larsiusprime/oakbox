import { type CalendarDate, parseDate } from "@internationalized/date";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import {
  Button,
  Calendar,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  DateInput,
  DatePicker,
  DateSegment,
  Dialog,
  Group,
  Heading,
  Label,
  Popover,
} from "react-aria-components";

function parse(value: string): CalendarDate | null {
  try {
    return value ? parseDate(value) : null;
  } catch {
    return null;
  }
}

/** A date: typed in its parts, or picked from a calendar that opens like the app's other dropdowns (not the
 * browser's own, which can't be styled). The value is ISO, 2026-01-01. */
export function DateField(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  width?: "short" | "medium" | "long";
}) {
  return (
    <DatePicker
      className={`field field-${props.width ?? "medium"} date-field`}
      value={parse(props.value)}
      onChange={(d) => props.onChange(d ? d.toString() : "")}
    >
      <Label className="field-label">{props.label}</Label>
      <Group className="date-group">
        <DateInput className="date-input">
          {(segment) => <DateSegment segment={segment} className="date-seg" />}
        </DateInput>
        <Button className="combo-arrow date-button">
          <CalendarDays aria-hidden="true" size="0.95em" />
        </Button>
      </Group>
      <Popover className="popover date-popover" placement="bottom start" offset={0}>
        <Dialog className="date-dialog">
          <Calendar className="cal">
            <header className="cal-head">
              <Button slot="previous" className="cal-nav">
                <ChevronLeft aria-hidden="true" size="1em" />
              </Button>
              <Heading className="cal-title" />
              <Button slot="next" className="cal-nav">
                <ChevronRight aria-hidden="true" size="1em" />
              </Button>
            </header>
            <CalendarGrid className="cal-grid">
              <CalendarGridHeader>
                {(day) => <CalendarHeaderCell className="cal-day">{day}</CalendarHeaderCell>}
              </CalendarGridHeader>
              <CalendarGridBody>
                {(date) => <CalendarCell date={date} className="cal-cell" />}
              </CalendarGridBody>
            </CalendarGrid>
          </Calendar>
        </Dialog>
      </Popover>
    </DatePicker>
  );
}
