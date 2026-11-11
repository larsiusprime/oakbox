/** A bug on OAK box's side (a request that failed with a 500): a bar in the corner with the error's reference and
 * what failed, Copy details (to paste into a message) and Open the log folder (the traceback). It stays until
 * dismissed; a later failure replaces it. */
import { useState } from "react";
import { Button } from "react-aria-components";
import { api } from "../api/client";
import { dismissFailure, failureText, useFailure } from "../lib/failures";
import { t } from "../wording";
import { CloseButton } from "./Buttons";

const f = t.failure;

export function FailureBar() {
  const { failure, count } = useFailure();
  const [copied, setCopied] = useState<string | null>(null);
  if (!failure) return null;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(failureText(failure));
      setCopied(failure.ref);
    } catch {
      // No clipboard (a page without the permission): the details are on screen to copy by hand.
      setCopied(null);
    }
  };
  return (
    <div className="failure-bar" role="alert">
      <div className="failure-text">
        <b>{f.title}</b> <span className="wiz-from">{f.more({ n: count })}</span>
        <div className="failure-what">{f.what({ ref: failure.ref, what: failure.what })}</div>
        <div className="wiz-from mono failure-req">{failure.request}</div>
      </div>
      <div className="failure-acts">
        <Button className="button button-small" onPress={copy}>
          {copied === failure.ref ? `✓ ${f.copied}` : f.copy}
        </Button>
        <Button className="button button-small" onPress={() => void api.POST("/api/log/open")}>
          {f.openLog}
        </Button>
      </div>
      <CloseButton label={f.dismiss} onPress={dismissFailure} />
    </div>
  );
}
