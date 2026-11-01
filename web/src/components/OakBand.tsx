/** The top of every screen (SPEC D21): the box's lid, polished oak with the brass plate on it, which says where you
 * are and takes you home. It stays at the top as the page scrolls, so the box's frame is always whole (the frame's
 * sides butt flat against its underside). No text sits on the bare wood: what's said is on the plate. */
import { t } from "../strings";

export function OakBand({ here }: { here: React.ReactNode }) {
  return (
    <header className="oak-nav">
      <a className="plate" href="#/" title={t.nav.home}>
        <span className="wordmark">
          <span className="wordmark-strong">OAK</span>
          <span className="wordmark-light">box</span>
        </span>
        <span className="plate-rule" aria-hidden="true" />
        <span className="plate-here">{here}</span>
      </a>
    </header>
  );
}
