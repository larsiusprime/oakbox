import { useMemo, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import type { GroupField, ModelGroup } from "../api/client";
import { Choice } from "../components/Form";
import { Val } from "../components/Val";
import { newGroup } from "../lib/groups";
import { t } from "../wording";
import { useValues } from "./GroupEditor";

const g = t.groups;

const NONE = "__none";
const NEW = "__new";

/** Send each value of one field to a group: each group gets (or has replaced) its condition on that field. */
export function GroupFromField({
  projectId,
  fields,
  groups,
  colors,
  close,
  apply,
}: {
  projectId: string;
  fields: GroupField[];
  groups: ModelGroup[];
  colors: string[];
  close: () => void;
  apply: (groups: ModelGroup[]) => void;
}) {
  const cats = fields.filter((f) => f.kind === "category");
  const [field, setField] = useState(cats[0]?.name ?? "");
  const [list, setList] = useState<ModelGroup[]>(groups);
  // Where each value goes: what the groups already say about this field, until changed here (for this field).
  const said = useMemo(() => {
    const out: Record<string, string> = {};
    for (const x of groups)
      for (const c of x.rule.conditions)
        if (c.column === field && c.op === "isin") for (const v of c.values) out[v] = out[v] ?? x.id;
    return out;
  }, [field, groups]);
  const [edited, setEdited] = useState<{ field: string; sent: Record<string, string> } | null>(null);
  const sent = edited?.field === field ? edited.sent : said;
  const setSent = (next: Record<string, string>) => setEdited({ field, sent: next });
  const vals = useValues(projectId, field);
  const addGroup = (value: string) => {
    const x = newGroup(value || g.newName({ n: list.length + 1 }), list, colors);
    setList([...list, x]);
    return x.id;
  };
  const done = () => {
    const out = list.map((x) => {
      const values = Object.entries(sent)
        .filter(([, id]) => id === x.id)
        .map(([v]) => v);
      const others = x.rule.conditions.filter((c) => !(c.column === field && c.op === "isin"));
      const conditions = values.length ? [...others, { column: field, op: "isin" as const, values }] : others;
      return { ...x, rule: { ...x.rule, conditions } };
    });
    apply(out.filter((x) => x.rule.conditions.length > 0 || groups.some((y) => y.id === x.id)));
  };
  const groupOptions = [
    [NONE, g.ffNone] as const,
    ...list.map((x) => [x.id, x.name] as const),
    [NEW, g.ffNew] as const,
  ];
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal mg-ff">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {g.ffTitle}
          </Heading>
          <p className="rc-sub">{g.ffLede}</p>
          <Choice
            label={g.ffField}
            value={field}
            options={cats.map((f) => [f.name, `${f.label} · ${f.distinct.toLocaleString()}`] as const)}
            onChange={setField}
          />
          <div className="mg-ff-scroll">
            <table className="rc-tbl mg-ff-tbl">
              <thead>
                <tr>
                  <th className="rc-th">{g.ffValue}</th>
                  <th className="rc-th mg-num">{g.ffParcels}</th>
                  <th className="rc-th mg-num">{g.ffVacant}</th>
                  <th className="rc-th mg-num">{g.ffSales}</th>
                  <th className="rc-th">{g.ffGroup}</th>
                </tr>
              </thead>
              <tbody>
                {(vals.data?.rows ?? []).map((r) => (
                  <tr key={r.value}>
                    <td className="rc-td mono">{r.value ? <Val v={r.value} /> : g.blank}</td>
                    <td className="rc-td mg-num">{r.parcels.toLocaleString()}</td>
                    <td className="rc-td mg-num">{r.vacant.toLocaleString()}</td>
                    <td className="rc-td mg-num">{r.sales.toLocaleString()}</td>
                    <td className="rc-td">
                      <span className="mg-ff-pick">
                        <i
                          style={{
                            background: list.find((x) => x.id === sent[r.value])?.color ?? "transparent",
                          }}
                        />
                        <Choice
                          label={`${g.ffGroup}: ${r.value || g.blank}`}
                          hideLabel
                          value={sent[r.value] ?? NONE}
                          options={groupOptions}
                          onChange={(id) => {
                            const to = id === NEW ? addGroup(r.value) : id;
                            const next = { ...sent };
                            if (to === NONE) delete next[r.value];
                            else next[r.value] = to;
                            setSent(next);
                          }}
                        />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(vals.data?.more ?? 0) > 0 && <p className="rc-sub">{g.ffMore({ n: vals.data?.more ?? 0 })}</p>}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {g.cancel}
            </Button>
            <Button className="button button-primary" onPress={done}>
              {g.ffApply}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
