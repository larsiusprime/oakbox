import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import type { EngineState } from "../api/client";
import { mb, useEngineAction, useEngines } from "../api/engines";
import { t } from "../wording";
import { DeleteButton, SmallButton } from "./Buttons";

const w = t.engines;

/** XGBoost or CatBoost isn't installed: ask, then and there, whether to download it (SPEC §6, Optional engines). */
export function InstallEngineDialog({
  engine,
  onInstall,
  onClose,
}: {
  engine: EngineState | null;
  onInstall: (e: EngineState) => void;
  onClose: () => void;
}) {
  const install = useEngineAction();
  return (
    <ModalOverlay
      className="modal-overlay"
      isDismissable
      isOpen={engine !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <Modal className="modal">
        <Dialog className="modal-body">
          {engine && (
            <>
              <Heading slot="title" className="modal-title">
                {w.askTitle({ name: engine.name })}
              </Heading>
              <p>{w.askWhy({ name: engine.name })}</p>
              {engine.can_install ? (
                <>
                  <p>
                    <b>{w.askSize({ mb: mb(engine.download) })}</b>
                    {w.askSizeRest({ disk: mb(engine.disk) })}
                  </p>
                  <p className="wiz-from">{w.askAfter}</p>
                </>
              ) : (
                <p className="wiz-from">{w.askCheckout({ name: engine.name, key: engine.key })}</p>
              )}
              <div className="form-actions">
                <Button className="button" onPress={onClose} autoFocus>
                  {engine.can_install ? w.notNow : w.close}
                </Button>
                {engine.can_install && (
                  <Button
                    className="button button-primary"
                    isDisabled={install.isPending}
                    onPress={() =>
                      // Once the download has started, so whoever waits for it sees it running.
                      install
                        .mutateAsync({ key: engine.key, action: "install" })
                        .then(() => onInstall(engine))
                    }
                  >
                    {w.install({ name: engine.name, mb: mb(engine.download) })}
                  </Button>
                )}
              </div>
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** A download as it goes: a bar, how far, and Stop; or how it ended, if it didn't. */
export function EngineProgress({ engine }: { engine: EngineState }) {
  const act = useEngineAction();
  const job = engine.install;
  if (!job) return null;
  if (job.status === "failed" || job.status === "stopped")
    return (
      <p className="wiz-warn gm-warn">
        {job.status === "failed"
          ? w.failed({ name: engine.name, error: job.error ?? "" })
          : w.stopped({ name: engine.name })}
      </p>
    );
  if (job.status !== "running") return null;
  const share = job.total ? job.done / job.total : 0;
  return (
    <span className="engine-progress">
      <span
        className="engine-bar"
        role="progressbar"
        aria-valuenow={Math.round(share * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <i style={{ width: `${job.unpacking ? 100 : share * 100}%` }} />
      </span>
      <span>
        {job.unpacking
          ? w.unpacking({ name: engine.name })
          : w.installing({ name: engine.name, done: mb(job.done), total: mb(job.total) })}
      </span>
      {!job.unpacking && (
        <SmallButton onPress={() => act.mutate({ key: engine.key, action: "stop" })}>{w.stop}</SmallButton>
      )}
    </span>
  );
}

/** Help › Model engines: each optional engine, installed or not, to install or remove. */
export function ModelEnginesDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const engines = useEngines();
  const act = useEngineAction();
  return (
    <ModalOverlay
      className="modal-overlay"
      isDismissable
      isOpen={isOpen}
      onOpenChange={(open) => !open && onClose()}
    >
      <Modal className="modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {w.title}
          </Heading>
          <p>{w.lede}</p>
          <table className="tbl engines-table">
            <tbody>
              {(engines.data ?? []).map((e) => (
                <tr key={e.key}>
                  <th scope="row">{e.name}</th>
                  <td>
                    {e.install?.status === "running" ? (
                      <EngineProgress engine={e} />
                    ) : (
                      <>
                        {e.installed ? (
                          w.installed
                        ) : e.can_install ? (
                          <span className="wiz-from">
                            {w.sizes({ mb: mb(e.download), disk: mb(e.disk) })}
                          </span>
                        ) : (
                          <span className="wiz-from">{w.askCheckout({ name: e.name, key: e.key })}</span>
                        )}
                        <EngineProgress engine={e} />
                      </>
                    )}
                  </td>
                  <td className="engines-act">
                    {e.install?.status !== "running" &&
                      e.can_install &&
                      (e.installed ? (
                        <DeleteButton
                          confirm={w.removeConfirm({ name: e.name, mb: mb(e.download) })}
                          onDelete={() => act.mutate({ key: e.key, action: "remove" })}
                        >
                          {w.remove({ name: e.name })}
                        </DeleteButton>
                      ) : (
                        <Button
                          className="button"
                          onPress={() => act.mutate({ key: e.key, action: "install" })}
                        >
                          {w.installShort}
                        </Button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {act.error && <p className="wiz-warn">{String((act.error as Error).message ?? act.error)}</p>}
          <div className="form-actions">
            <Button className="button" onPress={onClose} autoFocus>
              {w.close}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
