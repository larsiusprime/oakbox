/** A location stack (SPEC F9): the location fields a model reads, shown broadest first (the whole model group at the
 * top), written finest first as OpenAVMKit takes them. Each level: its areas, their median sales, the areas with
 * enough sales for a regression of their own, and whether it nests in the level above. Levels move up and down, go,
 * and are added from the location fields there are. */
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "react-aria-components";
import { useStack } from "../api/models";
import { num } from "../lib/format";
import { t } from "../strings";
import { AddButton } from "./AddButton";

const s = t.values.stack;

export function LocationStack({
  projectId,
  group,
  engine,
  finestFirst,
  offered,
  onChange,
}: {
  projectId: string;
  group: string;
  engine: string;
  /** As written: finest first. */
  finestFirst: string[];
  offered: { field: string; name: string }[];
  onChange: (finestFirst: string[]) => void;
}) {
  const broadest = [...finestFirst].reverse();
  const q = useStack(projectId, group, broadest);
  const names = Object.fromEntries(offered.map((x) => [x.field, x.name]));
  const levels = Object.fromEntries((q.data?.levels ?? []).map((x) => [x.field, x]));
  const left = offered.filter((x) => !broadest.includes(x.field));
  const save = (next: string[]) => onChange([...next].reverse());
  const move = (i: number, by: number) => {
    const next = [...broadest];
    const [x] = next.splice(i, 1);
    if (x !== undefined) next.splice(i + by, 0, x);
    save(next);
  };
  return (
    <div className="ls-stack">
      <p className="ls-title">{s.title}</p>
      <p className="wiz-from">{s.how(engine)}</p>
      {offered.length === 0 ? (
        <p className="wiz-warn">{s.noFields}</p>
      ) : (
        <table className="tbl ls-table">
          <thead>
            <tr>
              <th className="cs-n">#</th>
              <th>{s.level}</th>
              <th className="cs-n">{s.areas}</th>
              <th className="cs-n">{s.medianSales}</th>
              <th className="cs-n">{s.enough}</th>
              <th>{s.nesting}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="cs-n wiz-from">1</td>
              <td>
                <b>{s.whole}</b>
              </td>
              <td className="cs-n">1</td>
              <td className="cs-n">{q.data ? num(q.data.sales) : ""}</td>
              <td className="cs-n">{q.data ? (q.data.sales >= 15 ? 1 : 0) : ""}</td>
              <td />
              <td />
            </tr>
            {broadest.map((f, i) => {
              const l = levels[f];
              const above = i === 0 ? s.whole : (names[broadest[i - 1] ?? ""] ?? broadest[i - 1] ?? "");
              const name = names[f] ?? f;
              return (
                <tr key={f}>
                  <td className="cs-n wiz-from">{i + 2}</td>
                  <td>
                    <b>{name}</b> <span className="mono wiz-from">{f}</span>
                  </td>
                  <td className="cs-n">{l ? num(l.areas) : ""}</td>
                  <td className="cs-n">{l ? num(l.median_sales) : ""}</td>
                  <td className="cs-n">{l ? num(l.enough) : ""}</td>
                  <td>
                    {l && (
                      <span className="rv-cell-pill">
                        {l.split ? (
                          <span className="pill pill-warn">! {s.splits(l.split, above)}</span>
                        ) : (
                          <span className="pill pill-ok">{s.nests(above)}</span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="ls-tools">
                    <Button
                      className="ls-move"
                      aria-label={s.up(name)}
                      isDisabled={i === 0}
                      onPress={() => move(i, -1)}
                    >
                      <ArrowUp aria-hidden="true" size="0.9em" />
                    </Button>
                    <Button
                      className="ls-move"
                      aria-label={s.down(name)}
                      isDisabled={i === broadest.length - 1}
                      onPress={() => move(i, 1)}
                    >
                      <ArrowDown aria-hidden="true" size="0.9em" />
                    </Button>
                    <Button
                      className="wiz-link vs-remove"
                      onPress={() => save(broadest.filter((x) => x !== f))}
                    >
                      <X aria-hidden="true" size="0.9em" />
                      {s.remove}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {offered.length > 0 && (
        <p className="cs-row">
          {left.length ? (
            <MenuTrigger>
              <AddButton>{s.add}</AddButton>
              <Popover className="popover rc-menu" placement="bottom start">
                <Menu className="choice-list" onAction={(key) => save([...broadest, String(key)])}>
                  {left.map((x) => (
                    <MenuItem
                      key={x.field}
                      id={x.field}
                      className="choice-item rc-menu-item"
                      textValue={x.name}
                    >
                      {x.name}
                      <small className="mono">{x.field}</small>
                    </MenuItem>
                  ))}
                </Menu>
              </Popover>
            </MenuTrigger>
          ) : (
            <span className="wiz-from">{s.noneLeft}</span>
          )}
        </p>
      )}
      {finestFirst.length > 0 && (
        <p className="wiz-from">{s.written(`"locations": ${JSON.stringify(finestFirst)}`)}</p>
      )}
    </div>
  );
}
