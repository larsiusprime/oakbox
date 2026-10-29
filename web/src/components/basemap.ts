import L from "leaflet";
import { t } from "../strings";

const KEY = "oakbox.basemap";

function wanted(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

/** OpenStreetMap under a map's shapes, with a "Street map" box in its corner to take it away (a blank background, to
 * see only the colours). The choice carries to every map. */
export function addBasemap(m: L.Map) {
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  });
  if (wanted()) tiles.addTo(m);
  L.control
    .layers(undefined, { [t.map.basemap]: tiles }, { collapsed: false, position: "topright" })
    .addTo(m);
  const remember = (on: boolean) => () => {
    try {
      localStorage.setItem(KEY, on ? "on" : "off");
    } catch {
      // Not remembered: the next map shows it again.
    }
  };
  tiles.on("add", remember(true));
  tiles.on("remove", remember(false));
}
