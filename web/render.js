// Tick-time drawing: the day/night terminator overlay + the city clocks.
// Ports render.py:_overlay_night, _place_labels, and the clock-drawing loop.
import { subsolarPoint, boundaryLat, nightIsSouth } from "./sun.js";
import { rgb, rgba, labelLines } from "./config.js";

const TWILIGHT = [0.0, -6.0, -12.0, -18.0];

function polyPath(ctx, pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
}

function terminatorPolygon(elev, sublat, sublon, proj, w, h, daySide = false, step = 3) {
  const pts = [];
  for (let x = 0; x <= w; x += step) {
    const lat = boundaryLat(proj.xToLon(x), sublat, sublon, elev);
    pts.push([x, Math.max(0, Math.min(h, proj.latToY(lat)))]);
  }
  const closeBottom = nightIsSouth(sublat) !== daySide;
  if (closeBottom) pts.push([w, h], [0, h]);
  else pts.push([w, 0], [0, 0]);
  return pts;
}

export function overlayNight(ctx, date, theme, bands, alpha, proj, w, h) {
  const [sublat, sublon] = subsolarPoint(date);
  const elevations = bands ? TWILIGHT : [0.0];

  const dw = theme.day_wash;
  if (dw) {
    const a = dw.length > 3 ? dw[3] : 255;
    ctx.globalCompositeOperation = "screen";
    ctx.fillStyle = rgb([Math.round(dw[0] * a / 255), Math.round(dw[1] * a / 255), Math.round(dw[2] * a / 255)]);
    for (const e of elevations) { polyPath(ctx, terminatorPolygon(e, sublat, sublon, proj, w, h, true)); ctx.fill(); }
  }
  const night = theme.night;
  if (alpha > 0 && night) {
    const t = alpha / 255;
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = rgb(night.map((c) => Math.round(255 - (255 - c) * t)));
    for (const e of elevations) { polyPath(ctx, terminatorPolygon(e, sublat, sublon, proj, w, h, false)); ctx.fill(); }
  }
  ctx.globalCompositeOperation = "source-over";
}

const rectOverlap = (a, b) =>
  Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
  Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));

function placeLabels(items, obstacles, bounds, scale) {
  const gap = Math.round(6 * scale);
  const placed = obstacles.slice();
  const order = items.map((_, i) => i).sort((i, j) =>
    items[i].isHome !== items[j].isHome ? (items[i].isHome ? -1 : 1) : items[i].px - items[j].px);
  const defaults = ["right", "left", "below", "above", "below-right", "below-left"];
  for (const i of order) {
    const it = items[i];
    const g = it.dotr + gap;
    const anchors = {
      right: [it.px + g, it.py - it.h / 2], left: [it.px - g - it.w, it.py - it.h / 2],
      below: [it.px - it.w / 2, it.py + g], above: [it.px - it.w / 2, it.py - g - it.h],
      "below-right": [it.px + g, it.py + g], "below-left": [it.px - g - it.w, it.py + g],
    };
    const sides = anchors[it.side] ? [it.side, ...defaults.filter((s) => s !== it.side)] : defaults;
    let best = null, bestPen = null;
    for (const s of sides) {
      const [bx, by] = anchors[s];
      const box = [bx, by, bx + it.w, by + it.h];
      let pen = 0;
      for (const o of placed) pen += rectOverlap(box, o);
      const off = Math.max(0, bounds[0] - bx) + Math.max(0, bx + it.w - bounds[2])
        + Math.max(0, bounds[1] - by) + Math.max(0, by + it.h - bounds[3]);
      pen += off * (it.w + it.h) * 3;
      if (bestPen === null || pen < bestPen) { best = box; bestPen = pen; }
      if (pen === 0) break;
    }
    it.box = best;
    placed.push(best);
  }
}

export function drawClocks(ctx, w, h, opts) {
  const { date, theme, fmt, cities, scale, proj, labelBgAlpha, obstacles, isHome } = opts;
  const fs = Math.max(8, Math.round(16 * scale));
  const fsHome = Math.max(10, Math.round(20 * scale));
  const font = (bold, px) => `${bold ? "600 " : ""}${px}px system-ui, "Segoe UI", sans-serif`;

  const items = [];
  for (const c of cities) {
    const [px, py] = proj.toPx(c.lon, c.lat);
    if (px < -40 || px > w + 40 || py < -40 || py > h + 40) continue;
    const home = isHome(c);
    const px_ = home ? fsHome : fs;
    const lines = labelLines(c, date, fmt);
    ctx.font = font(home, px_);
    const lineH = Math.round(px_ * 1.18);
    const wid = Math.max(...lines.map((l) => ctx.measureText(l).width));
    items.push({
      c, isHome: home, lines, fontPx: px_, lineH,
      px, py, w: wid, h: lineH * lines.length + 2,
      dotr: Math.round((home ? 6 : 4) * scale), side: c.label_side,
    });
  }

  const dotBoxes = items.map((it) => [it.px - it.dotr, it.py - it.dotr, it.px + it.dotr, it.py + it.dotr]);
  const m = Math.round(10 * scale);
  placeLabels(items, obstacles.concat(dotBoxes), [m, m, w - m, h - m], scale);

  // backplates
  if (labelBgAlpha > 0) {
    const padX = Math.max(4, Math.round(10 * scale)), padY = Math.max(3, Math.round(7 * scale));
    const rad = Math.max(3, Math.round(7 * scale));
    // Black on a dark map; light themes carry a label_bg so the plate doesn't
    // fight the dark label text drawn on top of it (render.py does the same).
    const plate = theme.label_bg ?? [0, 0, 0];
    ctx.fillStyle = `rgba(${plate[0]},${plate[1]},${plate[2]},${labelBgAlpha / 255})`;
    for (const it of items) {
      const [x0, y0, x1, y1] = it.box;
      ctx.beginPath();
      ctx.roundRect(x0 - padX, y0 - padY, (x1 - x0) + 2 * padX, (y1 - y0) + 2 * padY, rad);
      ctx.fill();
    }
  }

  // dots + labels
  const lw = Math.max(1, Math.round(scale));
  ctx.textAlign = "left"; ctx.textBaseline = "top";
  for (const it of items) {
    const dot = it.isHome ? theme.home : theme.dot;
    const txt = it.isHome ? theme.home : theme.text;
    const stroke = it.isHome ? theme.home_stroke : theme.text_stroke;
    const r = it.dotr;
    ctx.beginPath(); ctx.arc(it.px, it.py, r, 0, 2 * Math.PI);
    ctx.fillStyle = rgba(dot); ctx.fill();
    ctx.lineWidth = lw; ctx.strokeStyle = rgba(theme.dot_outline); ctx.stroke();

    ctx.font = font(it.isHome, it.fontPx);
    ctx.lineJoin = "round"; ctx.lineWidth = lw * 2;
    ctx.strokeStyle = rgba(stroke); ctx.fillStyle = rgba(txt);
    it.lines.forEach((line, k) => {
      const ly = it.box[1] + k * it.lineH;
      ctx.strokeText(line, it.box[0], ly);
      ctx.fillText(line, it.box[0], ly);
    });
  }
}
