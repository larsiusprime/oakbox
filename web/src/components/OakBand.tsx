/** The top of every screen (SPEC D21): an oak band with the brass plate, which says where you are and takes you
 * home; inside a project, the folder tabs stand on its bottom edge and the open one runs into the page. No text
 * sits on the bare wood: what's said is on the plate. */
import { t } from "../strings";

export function OakBand({ here, children }: { here: React.ReactNode; children?: React.ReactNode }) {
  return (
    <header className={children ? "oak-nav" : "oak-nav oak-nav-bare"}>
      <a className="plate" href="#/" title={t.nav.home}>
        <span className="wordmark">
          <span className="wordmark-strong">OAK</span>
          <span className="wordmark-light">box</span>
        </span>
        <span className="plate-rule" aria-hidden="true" />
        <span className="plate-here">{here}</span>
      </a>
      {children}
    </header>
  );
}
