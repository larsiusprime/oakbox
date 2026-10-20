import type { StageId } from "../../api/client";
import {
  LooksRight,
  Part,
  StageFrame,
  StageStatusMark,
  StaleNote,
  UnderTheHood,
} from "../../components/Stage";
import { t } from "../../strings";
import type { StageProps } from "./common";

/** Columns and Sales basics get their screens in M1c. Until then the sample's answers are shown read-only. */
export function LaterStage({
  detail,
  stage,
}: StageProps & { stage: Extract<StageId, "columns" | "sales_basics"> }) {
  const { project } = detail;
  const status = project.stages[stage];
  const setup = project.setup;
  return (
    <StageFrame
      title={t.stages[stage].title}
      what={t.stages[stage].what}
      status={<StageStatusMark status={status} />}
      note={project.notes[stage]}
    >
      <StaleNote status={status} />
      <Part title={t.later.title}>
        <p className="row-meta">{t.later.body}</p>
        {stage === "columns" && Object.keys(setup.columns.fields).length > 0 && (
          <table className="data-table summary-table">
            <tbody>
              {Object.entries(setup.columns.fields).map(([field, src]) => (
                <tr key={field}>
                  <th scope="row" className="mono">
                    {field}
                  </th>
                  <td className="mono">
                    {src.column ?? (src.transform ? `${src.transform.column} × ${src.transform.factor}` : "")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {stage === "sales_basics" && setup.sales_basics && (
          <table className="data-table summary-table">
            <tbody>
              {Object.entries(setup.sales_basics).map(([k, v]) => (
                <tr key={k}>
                  <th scope="row" className="mono">
                    {k}
                  </th>
                  <td className="mono">{Array.isArray(v) ? v.join(", ") : String(v ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Part>
      <LooksRight projectId={project.id} stage={stage} status={status} />
      <UnderTheHood projectId={project.id} stage={stage} />
    </StageFrame>
  );
}
