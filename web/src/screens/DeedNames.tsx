import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Button, Input, Radio, TextField } from "react-aria-components";
import { api, type NamesView, unwrap } from "../api/client";
import { setupKey, stepChanged } from "../api/steps";
import { Radios } from "../components/Form";
import { Val } from "../components/Val";
import { t } from "../wording";

const n = t.wizard.names;
type FormatId = NamesView["formats"][number]["id"];

/** Data › Deeds: how buyers' and sellers' names are written, so sales scrutiny can read their surnames (SPEC F3f).
 * The format is guessed and shown with real names read by it, live; the user confirms it, picks another or writes
 * a regular expression. */
export function DeedNames({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const saved = useQuery({
    queryKey: ["names", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/names", { params: { path: { project_id: projectId } } }),
      ),
  });
  const [tried, setTried] = useState<FormatId | null>(null);
  const [pattern, setPattern] = useState<string | null>(null);
  const v0 = saved.data;
  const format: FormatId | null = tried ?? v0?.format ?? v0?.guess ?? null;
  const typed = useDeferredValue(pattern ?? (v0?.format === "custom" ? v0.pattern : ""));
  const trying = tried !== null || pattern !== null;
  const preview = useQuery({
    queryKey: ["names", projectId, format, format === "custom" ? typed : null],
    enabled: trying && format !== null,
    placeholderData: (prev) => prev,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/names", {
          params: {
            path: { project_id: projectId },
            query: { format, ...(format === "custom" ? { pattern: typed } : {}) },
          },
        }),
      ),
  });
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/names", {
          params: { path: { project_id: projectId } },
          body: { format: format as FormatId, pattern: format === "custom" ? typed : null },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["names", projectId], data);
      void queryClient.invalidateQueries({ queryKey: setupKey("clean", projectId) });
      stepChanged(queryClient, projectId, "clean");
      setTried(null);
      setPattern(null);
    },
  });
  if (!v0) return null;
  if (!v0.available) return <p className="wiz-from">{n.none}</p>;
  const v = (trying && preview.data) || v0;
  const inUse = v0.format !== null && !trying;
  return (
    <section className="dn" aria-label={n.title}>
      <h3 className="wiz-group">{n.title}</h3>
      <p className="wiz-from">{n.lede}</p>
      {v.surname_fields && <p className="wiz-note">{n.surnameFields}</p>}
      <Radios
        aria-label={n.how}
        className="dn-formats"
        value={format}
        onChange={(x) => {
          setTried(x as FormatId);
          if (x !== "custom") setPattern(null);
        }}
      >
        {v.formats.map((f) => (
          <Radio key={f.id} value={f.id} className="radio dn-format">
            <span className="radio-dot" aria-hidden="true" />
            <span>
              {f.label}: <span className="mono">{f.example}</span>
              {v.guess === f.id && <span className="wiz-from"> · {n.looks({ why: v.why })}</span>}
            </span>
          </Radio>
        ))}
        <Radio value="custom" className="radio dn-format">
          <span className="radio-dot" aria-hidden="true" />
          <span>{n.custom}</span>
        </Radio>
      </Radios>
      {format === "custom" && (
        <TextField
          className="field field-long"
          value={pattern ?? (v0.format === "custom" ? v0.pattern : "")}
          onChange={setPattern}
          aria-label={n.patternLabel}
        >
          <span className="field-label">{n.patternLabel}</span>
          <Input className="input mono" placeholder={n.patternPlaceholder} spellCheck={false} />
          <span className="wiz-from">{n.patternHelp}</span>
        </TextField>
      )}
      {v.error ? (
        <p className="error" role="alert">
          {v.error}
        </p>
      ) : (
        <>
          <p className="wiz-from">
            {n.counts({
              sales: v.sales,
              read: v.read,
              companies: v.companies,
              unread: v.unread,
              shared: v.shared,
              sampled: v.sampled,
            })}
          </p>
          <table className="tbl dn-tbl">
            <thead>
              <tr>
                <th>{n.seller}</th>
                <th>{n.surname}</th>
                <th>{n.buyer}</th>
                <th>{n.surname}</th>
                <th>{n.shared}</th>
              </tr>
            </thead>
            <tbody>
              {v.rows.map((r) => (
                <tr key={`${r.seller}|${r.buyer}`} className={r.shared.length ? "dn-hit" : undefined}>
                  <td className="mono">
                    <Val v={r.seller} max={60} />
                  </td>
                  <td>{r.seller_surnames.join(", ") || <span className="wiz-from">{n.noSurname}</span>}</td>
                  <td className="mono">
                    <Val v={r.buyer} max={60} />
                  </td>
                  <td>{r.buyer_surnames.join(", ") || <span className="wiz-from">{n.noSurname}</span>}</td>
                  <td>{r.shared.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <div className="cs-row">
        {inUse ? (
          <span className="wiz-ok">{n.inUse}</span>
        ) : (
          <Button
            className="button button-primary"
            isDisabled={!format || !!v.error || save.isPending || preview.isFetching}
            onPress={() => save.mutate()}
          >
            {v0.format === null && !trying ? n.confirm : n.use}
          </Button>
        )}
        {trying && (
          <Button
            className="button"
            onPress={() => {
              setTried(null);
              setPattern(null);
            }}
          >
            {n.cancel}
          </Button>
        )}
      </div>
      {save.error && (
        <p className="error" role="alert">
          {save.error.message}
        </p>
      )}
      <p className="wiz-from">{n.outside}</p>
    </section>
  );
}
