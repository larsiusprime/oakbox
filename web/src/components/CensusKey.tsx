import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { t } from "../wording";
import { DeleteButton } from "./Buttons";
import { ExternalLink } from "./ExternalLink";

const e = t.wizard.enrich;
const KEY_URL = "https://api.census.gov/data/key_signup.html";

/** The Census API key: kept in OAK box's settings on this computer, never in the project. */
export function CensusKey({ saved }: { saved: string | null | undefined }) {
  const queryClient = useQueryClient();
  const [key, setKey] = useState("");
  const put = useMutation({
    mutationFn: async (k: string) => unwrap(await api.PUT("/api/census-key", { body: { key: k } })),
    onSuccess: async () => {
      setKey("");
      // The key is this computer's, not a project's: every project's census card and marks change.
      await queryClient.invalidateQueries({ queryKey: ["enrich"] });
      await queryClient.invalidateQueries({ queryKey: ["wizard"] });
      await queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
  });
  return (
    <div className="en-row">
      <span className="en-lab">{e.key}</span>
      {saved ? (
        <>
          <span className="wiz-ok">✓ {e.keySaved({ end: saved })}</span>
          <DeleteButton confirm={e.keyForgetConfirm} onDelete={() => put.mutate("")}>
            {e.keyForget}
          </DeleteButton>
        </>
      ) : (
        <>
          <TextField aria-label={e.key} value={key} onChange={setKey} type="password" className="en-key">
            <Input className="input en-key-input" placeholder={e.keyPlaceholder} />
          </TextField>
          <Button className="button" isDisabled={!key.trim()} onPress={() => put.mutate(key)}>
            {e.keySave}
          </Button>
          <ExternalLink className="en-link" href={KEY_URL}>
            {e.keyGet}
          </ExternalLink>
        </>
      )}
    </div>
  );
}
