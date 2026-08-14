// Live demo driver: set up the canvas, load the map data once, cache the static base
// layer, and re-render the terminator + clocks on a ticking loop.
import { makeProjection } from "./geo.js";
import { loadGeo, buildBase } from "./vectormap.js";
import { overlayNight, drawClocks } from "./render.js";
import { THEMES, DARKNESS_ALPHA, CITIES, tzOffsetHours } from "./config.js";

const canvas = document.getElementById("wt");
const ctx = canvas.getContext("2d");
const viewerTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

const state = { theme: "modus", fmt: "24h", bands: true, darkness: "subtle" };
let geo = null, proj = null, base = null, baseKey = "", W = 0, H = 0, dpr = 1;

function resize() {
  dpr = Math.min(2, window.devicePixelRatio || 1);
  W = Math.round(window.innerWidth);
  H = Math.round(window.innerHeight);
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
  canvas.style.width = W + "px"; canvas.style.height = H + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  proj = makeProjection(W, H);
  base = null;
  render();
}

function render() {
  if (!geo || !proj) return;
  const now = new Date();
  const theme = THEMES[state.theme];
  const scale = proj.scale;
  const homeOffset = tzOffsetHours(viewerTz, now);
  const alpha = theme.night_alpha ?? DARKNESS_ALPHA[state.darkness];

  const key = `${W}x${H}:${state.theme}:${homeOffset}`;
  if (key !== baseKey || !base) {
    base = document.createElement("canvas");
    base.width = Math.round(W * dpr); base.height = Math.round(H * dpr);
    const bctx = base.getContext("2d");
    bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildBase(bctx, W, H, theme, proj, geo, homeOffset, Math.max(8, Math.round(11 * scale)));
    baseKey = key;
  }

  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(base, 0, 0, W, H);
  overlayNight(ctx, now, theme, state.bands, alpha, proj, W, H);
  const isHome = (c) => Math.abs(tzOffsetHours(c.tz, now) - homeOffset) < 0.01;
  drawClocks(ctx, W, H, {
    date: now, theme, fmt: state.fmt, cities: CITIES, scale, proj,
    labelBgAlpha: 130, obstacles: [], isHome,
  });
}

function bindControls() {
  document.querySelectorAll("[data-set]").forEach((el) => {
    el.addEventListener("click", () => {
      const [k, v] = el.dataset.set.split(":");
      state[k] = v === "true" ? true : v === "false" ? false : v;
      const group = el.dataset.group;
      if (group) document.querySelectorAll(`[data-group="${group}"]`)
        .forEach((b) => b.classList.toggle("on", b === el));
      base = null;  // theme/darkness change invalidates the cached base
      render();
    });
  });
}

async function start() {
  bindControls();
  window.addEventListener("resize", resize);
  resize();
  try {
    geo = await loadGeo();
    document.getElementById("loading").remove();
    resize();
    setInterval(render, 1000);
  } catch (e) {
    document.getElementById("loading").textContent = "Failed to load map data: " + e.message;
  }
}
start();
