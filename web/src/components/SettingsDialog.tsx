/** Settings (SPEC §5, §3.14): OAK box's own settings on this computer, in one place. Opened from the plate's gear,
 * File › Settings… (Ctrl+,) and a waiting map's note. Performance first: what the computer check found, and each
 * performance setting, Recommended (what the check chose) or the user's own choice. Then Display, Projects (where
 * they're kept) and Data keys. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Dialog,
  Heading,
  Modal,
  ModalOverlay,
  Tab,
  TabList,
  TabPanel,
  Tabs,
} from "react-aria-components";
import { api, type Performance, type Resolved, unwrap } from "../api/client";
import { type SettingsSection, useMachine, useSetPerformance } from "../lib/machine";
import { say, t } from "../wording";
import { CensusKey } from "./CensusKey";
import { Choice } from "./Form";
import { Seg } from "./Seg";
import { StorageLocation } from "./StorageLocation";

const s = t.settings;
const ZOOMS = [67, 75, 80, 90, 100, 110, 125, 150, 175, 200] as const;

type Kind = keyof Performance;

/** The tier as a pill: Light amber (it holds back), Standard blue, Strong green. */
export const TIER_PILL = { light: "pill-warn", standard: "pill-info", strong: "pill-ok" } as const;

/** A performance setting's value in words (Settings, and the check's result). */
export function choiceLabel(kind: Kind, value: string, cores = 1): string {
  switch (kind) {
    case "fold_workers":
      return value === "one" ? s.foldsOne : value === "two" ? s.foldsTwo : s.foldsCores({ n: cores });
    case "maps":
      return value === "now" ? s.mapsNow : s.mapsClick;
    case "map_detail":
      return value === "parcels" ? s.detailParcels : value === "squares" ? s.detailSquares : s.detailAuto;
    case "street_map":
      return value === "on" ? s.streetOn : s.streetOff;
  }
}

const CHOICES: Record<Kind, readonly string[]> = {
  fold_workers: ["one", "two", "cores"],
  maps: ["now", "click"],
  map_detail: ["auto", "squares", "parcels"],
  street_map: ["on", "off"],
};

export function SettingsDialog({
  section,
  onSection,
  onClose,
  onCheck,
}: {
  /** Open at this section; null: closed. */
  section: SettingsSection | null;
  onSection: (s: SettingsSection) => void;
  onClose: () => void;
  /** Check the computer again (the check screen takes over). */
  onCheck: () => void;
}) {
  return (
    <ModalOverlay
      className="modal-overlay"
      isDismissable
      isOpen={section !== null}
      onOpenChange={(o) => !o && onClose()}
    >
      <Modal className="modal settings-modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {s.title}
          </Heading>
          <Tabs
            className="st-tabs"
            orientation="vertical"
            selectedKey={section ?? "performance"}
            onSelectionChange={(k) => onSection(k as SettingsSection)}
          >
            <TabList className="st-list" aria-label={s.sections}>
              <Tab id="performance" className="st-tab">
                {s.performance}
              </Tab>
              <Tab id="display" className="st-tab">
                {s.display}
              </Tab>
              <Tab id="projects" className="st-tab">
                {s.projects}
              </Tab>
              <Tab id="keys" className="st-tab">
                {s.keys}
              </Tab>
            </TabList>
            <TabPanel id="performance" className="st-panel">
              <PerformancePane onCheck={onCheck} />
            </TabPanel>
            <TabPanel id="display" className="st-panel">
              <DisplayPane />
            </TabPanel>
            <TabPanel id="projects" className="st-panel">
              <h3 className="st-h">{s.where}</h3>
              <StorageLocation />
            </TabPanel>
            <TabPanel id="keys" className="st-panel">
              <KeysPane />
            </TabPanel>
          </Tabs>
          <div className="form-actions">
            <Button className="button" onPress={onClose}>
              {s.close}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function PerformancePane({ onCheck }: { onCheck: () => void }) {
  const machine = useMachine();
  const set = useSetPerformance();
  const v = machine.data;
  if (!v) return null;
  const m = v.machine;
  const row = (kind: Kind, label: string, note: string) => {
    const rec = v.recommended[kind as keyof Resolved] as string;
    const options = [
      ["recommended", s.recommended({ choice: choiceLabel(kind, rec, v.cores_workers) })] as const,
      ...CHOICES[kind].map((c) => [c, choiceLabel(kind, c, v.cores_workers)] as const),
    ];
    return (
      <>
        <Choice
          label={label}
          value={v.performance[kind] as string}
          options={options}
          onChange={(value) => set.mutate({ ...v.performance, [kind]: value } as Performance)}
        />
        <span className="set-note">{note}</span>
      </>
    );
  };
  return (
    <>
      <div className="st-machine">
        <div className="st-machine-head">
          <b>{s.thisComputer}</b>
          {m && <span className={`pill ${TIER_PILL[m.tier]}`}>{t.machine.tier({ tier: m.tier })}</span>}
          <Button className="button" onPress={onCheck}>
            {t.machine.again}
          </Button>
        </div>
        <p className="row-meta">
          {m
            ? `${say.machineSpecs(m)} · ${t.machine.checked({ date: m.checked_at.slice(0, 10) })}`
            : s.notChecked}
        </p>
      </div>
      <div className="set-grid st-grid">
        {row("fold_workers", s.folds, s.foldsHint)}
        {row("maps", s.maps, s.mapsHint)}
        {row("map_detail", s.detail, s.detailHint)}
        {row("street_map", s.street, s.streetHint)}
      </div>
    </>
  );
}

function DisplayPane() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  const put = useMutation({
    mutationFn: async (display: { density: "default" | "compact" | null; zoom: number }) =>
      unwrap(await api.PUT("/api/app-settings/display", { body: display })),
    onSuccess: (view) => queryClient.setQueryData(["app-settings"], view),
  });
  const d = settings.data?.display;
  if (!d) return null;
  const density = d.density === "compact" ? "compact" : "default";
  return (
    <div className="set-grid st-grid">
      <span className="field-label">{s.density}</span>
      <span className="set-cell">
        <Seg
          label={s.density}
          value={density}
          options={[
            ["default", s.densityDefault],
            ["compact", s.densityCompact],
          ]}
          onChange={(v) => put.mutate({ density: v === "compact" ? "compact" : null, zoom: d.zoom })}
        />
      </span>
      <Choice
        label={s.zoom}
        value={String(d.zoom)}
        options={ZOOMS.map((z) => [String(z), s.zoomLevel({ percent: z })] as const)}
        onChange={(v) => put.mutate({ density: d.density ?? null, zoom: Number(v) })}
      />
      <span className="set-note">{s.displayHint}</span>
    </div>
  );
}

function KeysPane() {
  const settings = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
  return (
    <>
      <h3 className="st-h">{s.census}</h3>
      <CensusKey saved={settings.data?.census_key_end} />
      <p className="row-meta">{s.censusHint}</p>
    </>
  );
}
