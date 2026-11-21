#!/usr/bin/env python3
"""Text-box defect detector for card-style UI images.

Scores an image for three text-box defects (0.0-1.0 each):

  (a) overflow_right   Text clipped at, or spilling past, the text box's
                       right edge: glyph strokes sliced just inside the box
                       border (CSS overflow:hidden clips at the padding-box
                       edge), or stroke ink continuing outside the box
                       border (overflow:visible).
  (b) overflow_bottom  Same two forms against the box's bottom edge.
  (c) overlap          Text occluded by a solid foreground element (badge,
                       ribbon, button) painted over part or all of a text
                       line, hiding the strokes underneath.

Pipeline: find the card panel (thin solid border rectangle) -> extract text
strokes by local contrast -> group into line bands -> per band measure
boundary fill (clip) and outside ink (spill) -> find solid foreign-colour
elements inside the panel and measure how much of a line they cover,
including lines that vanished entirely (rhythm gap). No OCR is used; the
judgement is purely geometric/photometric.

Dependencies: Pillow, numpy.

CLI:
    python text_box_detector.py IMAGE [IMAGE ...] --json report.json [--threshold 0.5]

Library:
    from text_box_detector import score_image
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

# --------------------------------------------------------------------------
# criteria constants
# --------------------------------------------------------------------------

EDGE_T = 30.0            # luminance step that counts as a hard edge
BOX_MIN_SIDE_FRAC = 0.25 # candidate box sides must span >= this of the image
BOX_SIDE_COVER = 0.55    # fraction of a rect side that must be edge pixels

STROKE_DELTA = 40.0      # local-contrast threshold for text strokes
STROKE_BLUR = 1.5        # gaussian radius for the local background estimate
MIN_LINE_AREA = 24       # strokes below this in a band are treated as noise
BORDER_FILL_FRAC = 0.80  # a row/column this full of strokes is a border line

INK_COL_MIN = 2          # strokes in a column for it to count as inked
INK_COLOR_TOL = 60.0     # RGB distance within which strokes are the line's ink
FOREIGN_TOL = 30.0       # RGB distance from box bg that marks a foreign fill

CLIP_WIN = 6             # inner px before the border checked for sliced ink
CLIP_FILL_MIN = 0.20     # fraction of band rows with boundary ink = clipped
CLIP_REACH = 10          # band's last ink must come within this of the border
SPILL_SCAN_MULT = 4.0    # scan this many band heights outside the box

ELEM_MIN_AREA = 40       # a solid occluder element is at least this big
ELEM_MIN_W = 12
ELEM_MIN_H = 8
VERT_OCC_MIN = 0.5       # element must cover this fraction of the line height


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _to_gray(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)


def _blur_gray(gray: np.ndarray, radius: float = STROKE_BLUR) -> np.ndarray:
    img = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        if v:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _group_positions(pos: list[int], gap: int = 3) -> list[int]:
    if not pos:
        return []
    groups = [[pos[0]]]
    for p in pos[1:]:
        if p - groups[-1][-1] <= gap:
            groups[-1].append(p)
        else:
            groups.append([p])
    return [int(round(sum(g) / len(g))) for g in groups]


def find_box(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find the best bordered-panel rectangle (x0, y0, x1, y1) or None."""
    h, w = gray.shape
    ex = np.zeros_like(gray)
    ey = np.zeros_like(gray)
    ex[:, :-1] = np.abs(gray[:, 1:] - gray[:, :-1])
    ey[:-1, :] = np.abs(gray[1:, :] - gray[:-1, :])
    exb = ex > EDGE_T
    eyb = ey > EDGE_T

    vpos = [x for x in range(w) if _longest_run(exb[:, x]) >= BOX_MIN_SIDE_FRAC * h]
    hpos = [y for y in range(h) if _longest_run(eyb[y, :]) >= BOX_MIN_SIDE_FRAC * w]
    xs = _group_positions(vpos)
    ys = _group_positions(hpos)

    best = None
    best_score = 0.0
    for i, xl in enumerate(xs):
        for xr in xs[i + 1:]:
            if xr - xl < BOX_MIN_SIDE_FRAC * w:
                continue
            for j, yt in enumerate(ys):
                for yb in ys[j + 1:]:
                    if yb - yt < BOX_MIN_SIDE_FRAC * h:
                        continue
                    # a 2-4 px border spreads its edges over several
                    # columns/rows, so test a small window around each side
                    cov = min(
                        exb[yt:yb + 1, max(0, xl - 2):xl + 3].any(axis=1).mean(),
                        exb[yt:yb + 1, max(0, xr - 2):xr + 3].any(axis=1).mean(),
                        eyb[max(0, yt - 2):yt + 3, xl:xr + 1].any(axis=0).mean(),
                        eyb[max(0, yb - 2):yb + 3, xl:xr + 1].any(axis=0).mean(),
                    )
                    if cov < BOX_SIDE_COVER:
                        continue
                    score = cov * (xr - xl) * (yb - yt)
                    if score > best_score:
                        best_score = score
                        best = (xl, yt, xr, yb)
    return best


def _stroke_mask(gray: np.ndarray) -> np.ndarray:
    return np.abs(gray - _blur_gray(gray)) > STROKE_DELTA


def _clear_long_runs(stroke: np.ndarray, box: tuple[int, int, int, int]) -> None:
    """Remove border/ribbon edge lines from the stroke mask.

    A row (column) whose stroke pixels fill >= BORDER_FILL_FRAC of the box's
    width (height) is a straight drawn line, not text: dense text rows stay
    well below that fill. Fill fraction (not contiguity) keeps this robust
    to image grain breaking the line.
    """
    bx0, by0, bx1, by1 = box
    w_span = bx1 - bx0 + 1
    h_span = by1 - by0 + 1
    for y in range(max(0, by0 - 2), min(stroke.shape[0], by1 + 3)):
        row = stroke[y, bx0:bx1 + 1]
        if row.mean() >= BORDER_FILL_FRAC:
            stroke[y, bx0:bx1 + 1] = False
    for x in range(max(0, bx0 - 2), min(stroke.shape[1], bx1 + 3)):
        col = stroke[by0:by1 + 1, x]
        if col.mean() >= BORDER_FILL_FRAC:
            stroke[by0:by1 + 1, x] = False


def _line_bands(stroke: np.ndarray, ix0: int, iy0: int, ix1: int, iy1: int) -> list[tuple[int, int]]:
    """Row bands inside the inner rect that carry text strokes."""
    sub = stroke[iy0:iy1 + 1, ix0:ix1 + 1]
    rows = sub.any(axis=1)
    bands = []
    y = 0
    while y < len(rows):
        if rows[y]:
            y2 = y
            while y2 + 1 < len(rows) and rows[y2 + 1]:
                y2 += 1
            if sub[y:y2 + 1].sum() >= MIN_LINE_AREA:
                bands.append((iy0 + y, iy0 + y2))
            y = y2 + 1
        else:
            y += 1
    # merge bands separated by less than 40% of the median band height
    if not bands:
        return bands
    heights = sorted(b[1] - b[0] + 1 for b in bands)
    med = heights[len(heights) // 2]
    merged = [bands[0]]
    for b in bands[1:]:
        if b[0] - merged[-1][1] - 1 <= 0.4 * med:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(b)
    return merged


def _median_color(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray | None:
    pts = rgb[mask]
    if len(pts) == 0:
        return None
    return np.median(pts, axis=0)


def _dilate(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _components(mask: np.ndarray, offset: tuple[int, int]) -> list[tuple[int, int, int, int, int]]:
    """8-connected components of a boolean mask.

    Returns [(x0, y0, x1, y1, area)] in image coordinates (offset added)."""
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.where(mask & ~seen)
    for sy, sx in zip(ys, xs):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        x0 = x1 = sx
        y0 = y1 = sy
        area = 0
        while q:
            y, x = q.popleft()
            area += 1
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]
                            and mask[ny, nx] and not seen[ny, nx]):
                        seen[ny, nx] = True
                        q.append((ny, nx))
        out.append((x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1], area))
    return out


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def score_image(rgb: np.ndarray, threshold: float = 0.5) -> dict:
    h, w = rgb.shape[:2]
    gray = _to_gray(rgb)
    box = find_box(gray)
    if box is None:
        return {"box": None, "scores": {"overflow_right": 0.0, "overflow_bottom": 0.0,
                                        "overlap": 0.0},
                "flags": [], "bands": [], "note": "no bordered panel found"}
    bx0, by0, bx1, by1 = box
    ix0, iy0 = bx0 + 3, by0 + 3
    ix1, iy1 = bx1 - 3, by1 - 3

    stroke = _stroke_mask(gray)
    _clear_long_runs(stroke, box)
    # rounded-corner arcs are curves: they survive the straight-line clearing
    # and would look like sliced ink at the boundary. Text lines are never
    # wholly inside the 14 px corner squares (padding), so erase them there.
    R = 14
    stroke[max(0, by0 - 2):by0 + R, max(0, bx0 - 2):bx0 + R] = False
    stroke[max(0, by0 - 2):by0 + R, bx1 - R + 1:bx1 + 3] = False
    stroke[by1 - R + 1:by1 + 3, max(0, bx0 - 2):bx0 + R] = False
    stroke[by1 - R + 1:by1 + 3, bx1 - R + 1:bx1 + 3] = False

    interior_bg = _median_color(rgb[iy0:iy1 + 1, ix0:ix1 + 1],
                                ~stroke[iy0:iy1 + 1, ix0:ix1 + 1])
    if interior_bg is None:
        interior_bg = np.array([255.0, 255.0, 255.0])

    bands = _line_bands(stroke, ix0, iy0, ix1, iy1)
    band_infos = []
    band_heights = []
    for (ty0, ty1) in bands:
        stroke_band = stroke[ty0:ty1 + 1, ix0:ix1 + 1]
        counts = stroke_band.sum(axis=0)
        inked = counts >= INK_COL_MIN
        inked_idx = np.where(inked)[0]
        extent = (ix0 + int(inked_idx[0]), ix0 + int(inked_idx[-1])) if len(inked_idx) else None
        band_heights.append(ty1 - ty0 + 1)
        band_infos.append({"rows": (ty0, ty1), "stroke": stroke_band, "inked": inked,
                           "extent": extent})
    # merged bands (an element bridging lines) inflate the median, so the
    # typical line height comes from the smallest plausibly-tall band
    bh_typ = int(min([h for h in band_heights if h >= 7] or band_heights or [14]))

    # ---- solid foreign-colour elements inside the panel (occluder candidates)
    sx0, sy0, sx1, sy1 = bx0 + 4, by0 + 4, bx1 - 4, by1 - 4
    panel = rgb[sy0:sy1 + 1, sx0:sx1 + 1].astype(np.float32)
    dist_bg = np.linalg.norm(panel - interior_bg, axis=2)
    foreign = dist_bg > FOREIGN_TOL
    foreign &= ~_dilate(stroke[sy0:sy1 + 1, sx0:sx1 + 1])
    elems = [c for c in _components(foreign, (sx0, sy0))
             if c[4] >= ELEM_MIN_AREA and (c[2] - c[0] + 1) >= ELEM_MIN_W
             and (c[3] - c[1] + 1) >= ELEM_MIN_H]
    # merge pieces of one element split by its own label text (the label is
    # stroke-coloured and splits the foreign component): same row span,
    # horizontal gap small enough to be a label
    elems.sort(key=lambda c: (c[1], c[0]))
    merged: list[tuple] = []
    for c in elems:
        if (merged and c[1] <= merged[-1][3] + 2
                and c[0] - merged[-1][2] - 1 <= 24):
            p = merged[-1]
            merged[-1] = (min(p[0], c[0]), min(p[1], c[1]),
                          max(p[2], c[2]), max(p[3], c[3]), p[4] + c[4])
        else:
            merged.append(tuple(c))
    elems = merged

    band_results = []
    for info in band_infos:
        (ty0, ty1) = info["rows"]
        band_h = ty1 - ty0 + 1
        stroke_band = info["stroke"]
        inked_idx = np.where(info["inked"])[0]
        res = {"rows": [ty0, ty1],
               "x_extent": list(info["extent"]) if info["extent"] else None,
               "right_clip": 0.0, "right_spill": 0.0,
               "bottom_clip": 0.0, "bottom_spill": 0.0,
               "overlap": 0.0, "overlap_kind": None}

        # -- (a) right edge: clip (sliced-glyph ink just inside the border)
        # CSS overflow:hidden clips at the padding-box edge, so a clipped
        # line's ink reaches within a few px of the border; normal text stays
        # a padding width away. The sliced glyph's cut face is a solid run of
        # ink ending at the boundary; a corner arc is only 1-3 px thick per
        # row, so require a run of >= 4 px reaching the boundary zone.
        if len(inked_idx) and inked_idx[-1] >= bx1 - CLIP_REACH - ix0:
            x_lo = max(0, bx1 - 16 - ix0)
            x_hi = bx1 - 1 - ix0           # exclusive
            hit_rows_list: list[int] = []
            for r in range(stroke_band.shape[0]):
                row = stroke_band[r, x_lo:x_hi]
                # contiguous run of >=4 px whose RIGHTMOST column lands in
                # the boundary zone [bx1-9, bx1-2] (relative coords below)
                run = 0
                for x in range(len(row) - 1, -1, -1):
                    if row[x]:
                        run += 1
                    else:
                        # rightmost col of the run in absolute coords:
                        # ix0 + x_lo + x + run - 1
                        if run >= 4 and bx1 - 9 <= ix0 + x_lo + x + run - 1 <= bx1 - 2:
                            hit_rows_list.append(r)
                            break
                        run = 0
                else:
                    if run >= 4 and bx1 - 9 <= ix0 + x_lo + run - 1 <= bx1 - 2:
                        hit_rows_list.append(r)
            # a clipped line is a contiguous block of hit rows; score the
            # best block against the rows that reach the window in it, so
            # other lines of a merged band do not dilute the fill
            hit_set = set(hit_rows_list)
            best_fill = 0.0
            for r0 in sorted(hit_set):
                if r0 - 1 in hit_set:
                    continue
                r1 = r0
                while r1 + 1 in hit_set:
                    r1 += 1
                w_rows = sum(1 for r in range(r0, r1 + 1)
                             if stroke_band[r, x_lo:x_hi].any())
                best_fill = max(best_fill, (r1 - r0 + 1) / max(1, w_rows))
            if best_fill >= CLIP_FILL_MIN:
                res["right_clip"] = min(1.0, 1.5 * best_fill)

        # -- (a) right edge: spill (ink outside the border on band rows)
        xs0 = bx1 + 4
        xs1 = min(w, xs0 + int(SPILL_SCAN_MULT * band_h))
        if xs1 > xs0:
            out = stroke[max(0, ty0 - 2):ty1 + 3, xs0:xs1]
            spill_cols = int(out.any(axis=0).sum())
            if spill_cols:
                res["right_spill"] = min(1.0, spill_cols / (2.0 * band_h))

        # -- (b) bottom edge: clip (ink sliced just inside the bottom
        # border). Same solid-run rule, vertical: the sliced glyph bottom is
        # a contiguous column of ink ending at the boundary zone.
        if ty1 >= by1 - 8:
            ink_cols_band = np.where(stroke_band.sum(axis=0) >= 1)[0]
            if len(ink_cols_band):
                y_lo = max(by0, by1 - 16)
                hit_cols = 0
                for c in ink_cols_band:
                    col = stroke[y_lo:by1 - 1, ix0 + c]
                    run = 0
                    for y in range(len(col) - 1, -1, -1):
                        if col[y]:
                            run += 1
                        else:
                            if run >= 4 and by1 - 9 <= y_lo + y + run <= by1 - 2:
                                hit_cols += 1
                                break
                            run = 0
                    else:
                        if run >= 4 and by1 - 9 <= y_lo + run - 1 <= by1 - 2:
                            hit_cols += 1
                fill_b = hit_cols / len(ink_cols_band)
                if fill_b >= CLIP_FILL_MIN:
                    res["bottom_clip"] = min(1.0, 1.5 * fill_b)

        # -- (b) bottom edge: spill (ink below the border, under the band)
        ys0 = by1 + 4
        ys1 = min(h, ys0 + int(SPILL_SCAN_MULT * band_h))
        if ys1 > ys0 and len(inked_idx):
            cx0, cx1 = inked_idx[0], inked_idx[-1]
            out = stroke[ys0:ys1, ix0 + cx0:ix0 + cx1 + 1]
            spill_rows = int(out.any(axis=1).sum())
            if spill_rows:
                res["bottom_spill"] = min(1.0, 1.5 * spill_rows / band_h)

        band_results.append(res)

    # -- (c) overlap: solid elements over text. Each band is tested with
    # corrected rows (a thin sliver band is the uncovered bottom of a taller
    # line, so extend it upward); line positions with no band at all are
    # fully covered lines, found via the rhythm of the detected band tops.
    tops = [b["rows"][0] for b in band_results]
    if tops:
        leading = int(np.median(np.diff(tops))) if len(tops) >= 2 else bh_typ * 2
        candidates: list[tuple[tuple[int, int], tuple[int, int] | None, int]] = []
        for i, info in enumerate(band_infos):
            (ty0, ty1) = info["rows"]
            band_h = ty1 - ty0 + 1
            if band_h < 0.7 * bh_typ:      # sliver: extend to the full line
                rows = (ty1 - bh_typ + 1, ty1)
            else:
                rows = (ty0, ty1)
            candidates.append((rows, info["extent"], i))
        p = tops[0]
        while p <= iy1 - bh_typ // 2:
            if not any(abs(p - t0) <= 0.5 * leading for t0 in tops):
                candidates.append(((p, p + bh_typ - 1), None, -1))
            p += leading
        for rows, extent, bi in candidates:
            best = 0.0
            kind = None
            for (cx0, cy0, cx1, cy1, _a) in elems:
                vert = min(cy1, rows[1]) - max(cy0, rows[0]) + 1
                if vert < VERT_OCC_MIN * max(1, min(bh_typ, cy1 - cy0 + 1)):
                    continue
                vert_frac = min(1.0, vert / max(1, min(bh_typ, cy1 - cy0 + 1)))
                # the line's ink *within the element's row span*: a merged
                # band must not dilute the extent with other lines' ink
                ry0, ry1 = max(cy0, rows[0]), min(cy1, rows[1])
                # ink INSIDE any element is the element's own content (e.g.
                # a button label), never line text: drop it row-wise
                def _line_ink_cols(r: int) -> np.ndarray:
                    cols = np.where(stroke[r, ix0:ix1 + 1])[0]
                    if not len(cols):
                        return cols
                    abs_cols = cols + ix0
                    keep = np.ones(len(cols), dtype=bool)
                    for (ex0c, ey0c, ex1c, ey1c, _a) in elems:
                        if ey0c <= r <= ey1c:
                            keep &= (abs_cols < ex0c) | (abs_cols > ex1c)
                    return cols[keep]
                ink_cols = np.unique(np.concatenate(
                    [_line_ink_cols(r) for r in range(ry0, ry1 + 1)]))
                if len(ink_cols):
                    # per-row occupancy, max over rows: a neighbouring
                    # line's ink must not dilute the covered fraction
                    best_row = 0.0
                    hit = 0
                    ink_rows = 0
                    for r in range(ry0, ry1 + 1):
                        row_ink = _line_ink_cols(r)
                        if not len(row_ink):
                            continue
                        ink_rows += 1
                        ex0 = ix0 + int(row_ink[0])
                        ex1 = ix0 + int(row_ink[-1])
                        inter = max(0, min(cx1, ex1) - max(cx0, ex0) + 1)
                        # an overhang counts as hidden text only when the
                        # element touches the visible ink; a separate icon
                        # next to the line must not trigger it
                        over_l = max(0, ex0 - cx0) if cx1 >= ex0 - 3 else 0
                        over_r = max(0, cx1 - ex1) if cx0 <= ex1 + 3 else 0
                        covered = inter + over_l + over_r
                        if covered < 8:
                            continue
                        hit += 1
                        line_w = (ex1 - ex0 + 1) + covered
                        best_row = max(best_row, covered / line_w)
                    if not hit:
                        continue
                    occ = (best_row * vert_frac
                           * min(1.0, hit / max(1, 0.25 * ink_rows)))
                else:
                    # no visible ink where the element sits: fully covered
                    if (cx1 - cx0 + 1) < 24:
                        continue
                    occ = min(1.0, (cx1 - cx0 + 1) / (0.5 * (ix1 - ix0))) * vert_frac
                if 2.0 * occ > best:
                    best = 2.0 * occ
                    kind = "element" if len(ink_cols) else "covered_line"
            best = min(1.0, best)
            if best <= 0:
                continue
            if bi >= 0:
                if best > band_results[bi]["overlap"]:
                    band_results[bi]["overlap"] = best
                    band_results[bi]["overlap_kind"] = kind
            else:
                band_results.append({"rows": list(rows), "x_extent": None,
                                     "right_clip": 0.0, "right_spill": 0.0,
                                     "bottom_clip": 0.0, "bottom_spill": 0.0,
                                     "overlap": best, "overlap_kind": kind})

    def _round(v):
        return round(float(v), 3)

    # hard bottom clips can leave only a sliver of ink (< one band) at the
    # boundary: catch columns with >= 3 px of ink inside the boundary zone
    # [by1-9, by1-2] that no band claimed, spread over a text-like width
    # hard clips leave sparse glyph-top fragments: >= 2 px per column is
    # enough; skip 6 px at both sides where border anti-aliasing leaks in
    zone = stroke[by1 - 9:by1 - 1, ix0 + 6:ix1 - 5]
    col_hits = (zone.sum(axis=0) >= 2)
    band_cols = np.zeros(ix1 - ix0 - 11, dtype=bool)
    for r in band_results:
        if r["x_extent"]:
            band_cols[max(0, r["x_extent"][0] - ix0 - 6):
                      min(ix1 - ix0 - 12, r["x_extent"][1] - ix0 - 6) + 1] = True
    sliver_cols = int((col_hits & ~band_cols).sum())
    bottom_sliver = min(1.0, sliver_cols / 40.0) if sliver_cols >= 24 else 0.0

    overflow_right = max((max(r["right_clip"], r["right_spill"]) for r in band_results), default=0.0)
    overflow_bottom = max([max(r["bottom_clip"], r["bottom_spill"]) for r in band_results] + [bottom_sliver], default=0.0)
    overlap = max((r["overlap"] for r in band_results), default=0.0)

    scores = {"overflow_right": _round(overflow_right),
              "overflow_bottom": _round(overflow_bottom),
              "overlap": _round(overlap)}
    flags = [k for k, v in scores.items() if v >= threshold]
    for r in band_results:
        for k in ("right_clip", "right_spill", "bottom_clip", "bottom_spill", "overlap"):
            r[k] = _round(r[k])
    return {"box": [bx0, by0, bx1, by1], "inner": [ix0, iy0, ix1, iy1],
            "scores": scores, "flags": flags, "bands": band_results}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--json", dest="json_path")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    report = {}
    for path in args.images:
        rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
        report[path] = score_image(rgb, threshold=args.threshold)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    defective = 0
    for path, r in report.items():
        s = r["scores"]
        mark = " ".join(f"{k}={v:.2f}" for k, v in s.items())
        print(f"{path}: {mark} flags={r['flags'] or '-'}")
        if r["flags"]:
            defective += 1
    print(f"scanned={len(report)} defective={defective}")
    sys.exit(1 if defective else 0)


if __name__ == "__main__":
    main()
