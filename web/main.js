// Live demo driver: set up the canvas, load the map data once, cache the static base
// layer, and re-render the terminator + clocks on a ticking loop.
import { makeProjection } from "./geo.js";
import { loadGeo, buildBase } from "./vectormap.js";
import { overlayNight, drawClocks } from "./render.js";
import { THEMES, THEME_LABELS, THEME_ORDER, DARKNESS_ALPHA, CITIES, tzOffsetHours, labelLines }
  from "./config.js";

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
  describe(now);
}

// The canvas is the entire page. Its label has to carry what the picture says — the
// clocks and which one is home — or a screen reader gets a heading and nothing else.
function describe(now) {
  const times = CITIES.map((c) => labelLines(c, now, state.fmt).join(" ")).join(", ");
  canvas.setAttribute(
    "aria-label",
    `World map with the day and night terminator. Local times: ${times}. ` +
    `Your timezone, ${viewerTz}, is highlighted.`,
  );
}

function bindControls() {
  // The theme list is generated (three dozen palettes), so the picker is filled in
  // here rather than spelled out in the markup.
  const picker = document.getElementById("theme");
  picker.append(...THEME_ORDER.map((name) => new Option(THEME_LABELS[name], name)));
  picker.value = state.theme;
  picker.addEventListener("change", () => {
    state.theme = picker.value;
    base = null;
    render();
  });

  document.querySelectorAll("[data-set]").forEach((el) => {
    el.addEventListener("click", () => {
      const [k, v] = el.dataset.set.split(":");
      state[k] = v === "true" ? true : v === "false" ? false : v;
      const group = el.dataset.group;
      if (group) document.querySelectorAll(`[data-group="${group}"]`).forEach((b) => {
        b.classList.toggle("on", b === el);
        b.setAttribute("aria-pressed", String(b === el));
      });
      base = null;  // theme/darkness change invalidates the cached base
      render();
    });
  });
}

// A clock accurate to the minute is the contract greyline makes, on the desktop and
// here — so redraw on the minute boundary rather than every second. Rebuilding the
// overlay and the clocks 60x more often than the display can change costs battery and
// buys nothing anyone can read.
function scheduleTick() {
  // +50ms of slack so a timer that fires a hair early still lands in the new minute.
  setTimeout(() => { render(); scheduleTick(); }, 60000 - (Date.now() % 60000) + 50);
}

// Every resize throws away the cached base and redraws the map, which is ~110ms of
// main thread. Dragging a window edge fires it continuously, and on a phone so does
// the URL bar sliding away; wait for it to settle instead.
let resizePending = null;
function onResize() {
  clearTimeout(resizePending);
  resizePending = setTimeout(resize, 150);
}

async function start() {
  bindControls();
  window.addEventListener("resize", onResize);
  resize();
  try {
    geo = await loadGeo();
    document.getElementById("loading").remove();
    resize();
    scheduleTick();
  } catch (e) {
    document.getElementById("loading").textContent = "Failed to load map data: " + e.message;
  }
}
start();
