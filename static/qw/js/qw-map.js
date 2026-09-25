/* QuakeWatch map helpers (Leaflet + markercluster).
 *
 * The server decides between "points" (≤ 2000 events, clustered client-side by markercluster)
 * and "clusters" (server-side grid aggregation for dense viewports). Magnitude is shown by
 * marker size *and* colour; every map is paired with a text list elsewhere on the page, which
 * is the accessible equivalent of the markers.
 */
(function () {
  "use strict";
  const { h, fmt, band } = window.QW;

  const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Data: USGS';

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function color(mag) {
    const b = band(mag);
    return cssVar(`--qw-mag-${b === null ? 0 : b}`);
  }

  function radius(mag) {
    if (mag === null || mag === undefined) return 3;
    return Math.max(3, Math.min(22, 2 + Math.pow(Math.max(mag, 0), 1.6)));
  }

  function wrapLon(lon) {
    return ((((lon + 180) % 360) + 360) % 360) - 180;
  }

  /** Leaflet bounds → API bbox "south,west,north,east" (antimeridian-aware). */
  function bboxParam(map) {
    const b = map.getBounds();
    const south = Math.max(-90, b.getSouth());
    const north = Math.min(90, b.getNorth());
    if (b.getEast() - b.getWest() >= 360) return `${south.toFixed(4)},-180,${north.toFixed(4)},180`;
    return [south, wrapLon(b.getWest()), north, wrapLon(b.getEast())].map((v) => v.toFixed(4)).join(",");
  }

  function legendControl() {
    const control = L.control({ position: "bottomright" });
    control.onAdd = function () {
      const labels = ["< 2.5", "2.5 – 4.5", "4.5 – 6", "6 – 7", "≥ 7"];
      const div = h("div", { class: "qw-legend", role: "img", "aria-label": "Legend: circle size and colour grow with magnitude" },
        h("strong", {}, "Magnitude"),
        labels.map((label, i) => h("div", {}, h("i", { class: `l${i}` }), label)));
      L.DomEvent.disableClickPropagation(div);
      return div;
    };
    return control;
  }

  function create(el, { center = [20, 0], zoom = 2, legend = true, scrollWheelZoom = true } = {}) {
    const map = L.map(el, { center, zoom, minZoom: 1, maxZoom: 12, worldCopyJump: true, scrollWheelZoom });
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 18 }).addTo(map);
    if (legend) legendControl().addTo(map);
    el.setAttribute("role", "region");
    return map;
  }

  function popup(key, mag, depth, occurredAt, place) {
    return h("div", {},
      h("div", { class: "fw-semibold" }, `M ${fmt.mag(mag)}`, place ? ` — ${place}` : ""),
      h("div", { class: "small" }, fmt.utc(occurredAt), " · depth ", fmt.depth(depth)),
      h("a", { href: `/events/${encodeURIComponent(key)}/` }, "Event details →"));
  }

  /**
   * A layer that renders an /events/map response. onSelect(key) is called when a point is
   * clicked (e.g. to open a side panel).
   */
  function eventLayer(map, { onSelect } = {}) {
    const clusterGroup = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 40,
      chunkedLoading: true,
      iconCreateFunction: (cluster) => {
        const n = cluster.getChildCount();
        const size = n < 10 ? 30 : n < 100 ? 38 : 46;
        return L.divIcon({ html: `<span>${n}</span>`, className: "qw-cluster", iconSize: [size, size] });
      },
    });
    const gridGroup = L.layerGroup();
    map.addLayer(clusterGroup);
    map.addLayer(gridGroup);

    function render(data) {
      clusterGroup.clearLayers();
      gridGroup.clearLayers();
      if (data.mode === "points") {
        const markers = data.points.map(([key, lat, lon, mag, depth, occurredAt]) => {
          const marker = L.circleMarker([lat, lon], {
            radius: radius(mag),
            color: "#222",
            weight: 1,
            fillColor: color(mag),
            fillOpacity: 0.85,
          });
          marker.bindPopup(() => popup(key, mag, depth, occurredAt));
          if (onSelect) marker.on("click", () => onSelect(key));
          return marker;
        });
        clusterGroup.addLayers(markers);
      } else {
        for (const c of data.clusters) {
          const size = Math.max(26, Math.min(60, 18 + Math.log2(c.count) * 5));
          const marker = L.marker([c.lat, c.lon], {
            icon: L.divIcon({ html: `<span>${c.count}</span>`, className: "qw-cluster", iconSize: [size, size] }),
            keyboard: true,
            title: `${c.count} events, strongest M ${fmt.mag(c.max_magnitude)}`,
            alt: `${c.count} events`,
          });
          marker.on("click", () => map.setView([c.lat, c.lon], Math.min(map.getZoom() + 3, 12)));
          gridGroup.addLayer(marker);
        }
      }
    }

    return { render, clear: () => { clusterGroup.clearLayers(); gridGroup.clearLayers(); } };
  }

  window.QWMap = { create, eventLayer, bboxParam, color, radius };
})();
