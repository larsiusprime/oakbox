import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { desktop } from "../desktop";
import { t } from "../wording";
import { Field } from "./Form";

/** Where new projects are kept (SPEC §3.0 F1): under the title bar's Projects. */
export function StorageLocationDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <ModalOverlay
      className="modal-overlay"
      isDismissable
      isOpen={isOpen}
      onOpenChange={(o) => !o && onClose()}
    >
      <Modal className="modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {t.home.storageTitle}
          </Heading>
          <StorageLocation onDone={onClose} />
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** The folder, and changing it: in its own dialog (with Close) or in Settings › Projects (without). */
export function StorageLocation({ onDone }: { onDone?: () => void }) {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const [editing, setEditing] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (storage_location: string | null) =>
      unwrap(await api.PUT("/api/app-settings/storage-location", { body: { storage_location } })),
    onSuccess: (data) => {
      queryClient.setQueryData(["app-settings"], data);
      setEditing(null);
    },
  });
  const pick = async () => {
    const folder = await desktop.pickFolder();
    if (folder) setEditing(folder);
  };
  if (!settings.data) return null;
  const isDefault = settings.data.storage_location === settings.data.default_storage_location;
  return (
    <div className="settings-body">
      {editing === null ? (
        <div className="setting-line">
          <span className="mono">{settings.data.storage_location}</span>
          <Button className="button" onPress={() => setEditing(settings.data.storage_location)}>
            {t.home.change}
          </Button>
          {!isDefault && (
            <Button className="button" onPress={() => save.mutate(null)}>
              {t.home.useDefault}
            </Button>
          )}
        </div>
      ) : (
        <div className="setting-line">
          <Field label={t.home.folderLabel} value={editing} onChange={setEditing} width="long" autoFocus />
          {desktop.canPickFolder() && (
            <Button className="button" onPress={() => void pick()}>
              <FolderOpen aria-hidden="true" size="1em" />
              {t.home.change}
            </Button>
          )}
          <Button
            className="button button-primary"
            isDisabled={!editing.trim() || save.isPending}
            onPress={() => save.mutate(editing.trim())}
          >
            {t.home.save}
          </Button>
          <Button className="button" onPress={() => setEditing(null)}>
            {t.home.cancel}
          </Button>
        </div>
      )}
      <p className="row-meta">{t.home.storageNote}</p>
      {save.error && (
        <p className="error" role="alert">
          {save.error.message}
        </p>
      )}
      {onDone && (
        <div className="form-actions">
          <Button className="button" onPress={onDone}>
            {t.about.close}
          </Button>
        </div>
      )}
    </div>
  );
}
