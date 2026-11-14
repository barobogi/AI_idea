# -*- coding: utf-8 -*-
# 블록 1개(폴더)의 규격을 숫자로 측정한다. 표준 라이브러리만 사용.
# 사용: python check_example_block.py <블록폴더> [--timing <timing.json>]
# 결과: 항목별 PASS/FAIL 표 + 같은 폴더의 check_report.json. FAIL이 하나라도 있으면 종료코드 1.
import sys, os, re, json, struct
sys.stdout.reconfigure(encoding="utf-8")
BUDGET = {"lod3_tri": (10000, 14000), "lod2_tri": (1200, 1800), "lod3_bytes": 768000, "lod2_bytes": 71680,
          "tex_bytes": 102400, "pkg_bytes": 972800}
FILES = ("model_lod3.gltf", "model_lod2.gltf", "texture_atlas.webp", "block_manifest.json")
BAD_EXT = {".py", ".sh", ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".html", ".htm", ".dll", ".so", ".js", ".blend"}
REQ_KEYS = ["task_slot_id", "block_id", "name", "category", "district", "road_address", "coordinates",
            "orientation_deg", "reference_url", "verified_at", "verification_evidence", "lod_budget", "files",
            "package_total_bytes"]
OFFICIAL = (".go.kr", ".or.kr", ".ac.kr", ".re.kr")
res = []


def chk(cid, ok, msg):
    res.append({"id": cid, "pass": bool(ok), "msg": msg})


def webp_size(b):
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        return None
    t = b[12:16]
    if t == b"VP8X":
        return (1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little"))
    if t == b"VP8 ":
        return (struct.unpack("<H", b[26:28])[0] & 0x3FFF, struct.unpack("<H", b[28:30])[0] & 0x3FFF)
    if t == b"VP8L":
        bits = int.from_bytes(b[21:25], "little")
        return (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
    return None


def gltf_stats(path):
    g = json.load(open(path, encoding="utf-8"))
    acc = g["accessors"]
    st = {"tris": 0, "idx": set(), "normal": False, "min_y": None, "warn": set()}
    nodes = g.get("nodes", [])

    def walk(i, ty, sy):
        n = nodes[i]
        if "matrix" in n or "rotation" in n:
            st["warn"].add("노드 회전/행렬 있음: min.y 계산이 근사")
        t = (n.get("translation") or [0, 0, 0])[1]
        s = (n.get("scale") or [1, 1, 1])[1]
        ty2, sy2 = ty + sy * t, sy * s
        if "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                if p.get("mode", 4) == 4 and "indices" in p:
                    a = acc[p["indices"]]
                    st["tris"] += a["count"] // 3
                    st["idx"].add(a["componentType"])
                if "NORMAL" in p["attributes"]:
                    st["normal"] = True
                y = ty2 + sy2 * acc[p["attributes"]["POSITION"]]["min"][1]
                st["min_y"] = y if st["min_y"] is None else min(st["min_y"], y)
        for c in n.get("children", []):
            walk(c, ty2, sy2)

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, 0.0, 1.0)
    imgs = [i.get("uri") for i in g.get("images", [])]
    ext = [b for b in g["buffers"] if not str(b.get("uri", "")).startswith("data:")]
    return {"tris": st["tris"], "idx": sorted(st["idx"]), "normal": st["normal"], "min_y": st["min_y"],
            "images": imgs, "ext_buffers": len(ext), "warn": sorted(st["warn"])}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    d = sys.argv[1].rstrip("/\\")
    name = os.path.basename(d)
    chk("F01-폴더명", re.match(r"^\d{5}_B\d{2}_\S+$", name), f"폴더명 '{name}' (형식: 5자리코드_B번호_이름)")
    present = {f: os.path.isfile(os.path.join(d, f)) for f in FILES}
    chk("F02-4종 파일", all(present.values()), "없는 파일: " + (", ".join(f for f, v in present.items() if not v) or "없음"))
    extra = [f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in BAD_EXT]
    chk("F03-금지 확장자 없음", not extra, "금지 확장자: " + (", ".join(extra) or "없음"))
    sizes = {f: os.path.getsize(os.path.join(d, f)) for f in FILES if present[f]}
    pkg = sum(sizes.values())
    if present["model_lod3.gltf"] and present["model_lod2.gltf"]:
        s3 = gltf_stats(os.path.join(d, "model_lod3.gltf"))
        s2 = gltf_stats(os.path.join(d, "model_lod2.gltf"))
        a, b = BUDGET["lod3_tri"]
        chk("Q01-LOD3 삼각형", a <= s3["tris"] <= b, f"{s3['tris']:,}△ (기준 {a:,}~{b:,})")
        a, b = BUDGET["lod2_tri"]
        chk("Q02-LOD2 삼각형", a <= s2["tris"] <= b, f"{s2['tris']:,}△ (기준 {a:,}~{b:,})")
        chk("Q03-LOD3 용량", sizes["model_lod3.gltf"] <= BUDGET["lod3_bytes"],
            f"{sizes['model_lod3.gltf']:,}B (≤{BUDGET['lod3_bytes']:,})")
        chk("Q04-LOD2 용량", sizes["model_lod2.gltf"] <= BUDGET["lod2_bytes"],
            f"{sizes['model_lod2.gltf']:,}B (≤{BUDGET['lod2_bytes']:,})")
        for tag, s in (("LOD3", s3), ("LOD2", s2)):
            tol = 0.001 if tag == "LOD3" else 0.5   # LOD3는 정확히 0, 원거리용 LOD2는 0.5m까지 허용
            chk(f"Q05-{tag} 접지 min.y", s["min_y"] is not None and abs(s["min_y"]) <= tol,
                f"min.y={s['min_y']} (허용 ±{tol})" + (" 경고:" + ";".join(s["warn"]) if s["warn"] else ""))
            chk(f"Q06-{tag} 인덱스 uint16·법선 없음", s["idx"] == [5123] and not s["normal"],
                f"index={s['idx']} normal={s['normal']}")
            chk(f"Q07-{tag} 텍스처 참조", s["images"] == ["texture_atlas.webp"] and s["ext_buffers"] == 0,
                f"images={s['images']} 외부버퍼={s['ext_buffers']}")
    if present["texture_atlas.webp"]:
        wh = webp_size(open(os.path.join(d, "texture_atlas.webp"), "rb").read(64))
        chk("Q08-텍스처 1024x1024 WebP", wh == (1024, 1024), f"크기 {wh}")
        chk("Q09-텍스처 용량", sizes["texture_atlas.webp"] <= BUDGET["tex_bytes"],
            f"{sizes['texture_atlas.webp']:,}B (≤{BUDGET['tex_bytes']:,})")
    chk("Q10-패키지 총량", pkg <= BUDGET["pkg_bytes"], f"{pkg:,}B (≤{BUDGET['pkg_bytes']:,})")
    if present["block_manifest.json"]:
        m = json.load(open(os.path.join(d, "block_manifest.json"), encoding="utf-8"))
        miss = [k for k in REQ_KEYS if k not in m]
        chk("M01-매니페스트 필수키", not miss, "없는 키: " + (", ".join(miss) or "없음"))
        c = m.get("coordinates") or [0, 0]
        chk("M02-좌표 한반도 안", isinstance(c, list) and len(c) == 2 and 124 <= c[0] <= 132 and 33 <= c[1] <= 39,
            f"coordinates={c} (경도,위도)")
        urls = [m.get("reference_url", "")] + [e[0] for e in (m.get("verification_evidence") or []) if e]
        doms = [re.sub(r"^https?://([^/]+).*", r"\1", u) for u in urls if u]
        chk("M03-공식 출처 1건 이상", any(dm.endswith(OFFICIAL) for dm in doms),
            "도메인: " + ", ".join(sorted(set(doms))[:6]))
        chk("M04-열람 시각(KST)", bool(re.search(r"\+09:00$", str(m.get("verified_at", "")))),
            f"verified_at={m.get('verified_at')}")
        txt = json.dumps(m, ensure_ascii=False)
        chk("M05-개인정보·키 없음",
            not re.search(r"\b0\d{1,2}-\d{3,4}-\d{4}\b|AKIA[0-9A-Z]{12,}|X-Amz-|api[_-]?key\s*[:=]", txt, re.I),
            "전화번호·키 패턴 검사")
        chk("M06-슬롯 일치", str(m.get("task_slot_id", ""))[:5] == name[:5], f"task_slot_id={m.get('task_slot_id')}")
        chk("M07-V-World 풋프린트 참조·공공누리 오표기 없음",
            not re.search(r"(?i)v-?world[^\"]{0,12}풋프린트\s*참조", txt) and not re.search(r"제2유형\s*\(\s*출처표시", txt),
            "'V-World 풋프린트 참조' 문구 금지(약관 제19조 저장·복제 제한), 공공누리 제2유형은 비영리 전용이므로 '출처표시'로 쓰지 말 것")
    if "--timing" in sys.argv:
        tp = sys.argv[sys.argv.index("--timing") + 1]
        try:
            t = json.load(open(tp, encoding="utf-8"))
            need = ["agent", "model_or_tool", "block_slot", "started_at_kst", "finished_at_kst", "wall_clock_min",
                    "active_min", "retries", "steps", "commit_started", "commit_finished"]
            miss = [k for k in need if k not in t]
            chk("T01-시간 기록 필수키", not miss, "없는 키: " + (", ".join(miss) or "없음"))
        except Exception as e:
            chk("T01-시간 기록 필수키", False, f"읽기 실패: {e}")
    w = max(len(r["id"]) for r in res)
    for r in res:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"].ljust(w) + "  " + r["msg"])
    n_pass = sum(r["pass"] for r in res)
    print(f"\n합계 {n_pass}/{len(res)} 통과, 패키지 {pkg:,}B")
    json.dump({"folder": name, "pass": n_pass, "total": len(res), "package_bytes": pkg, "items": res},
              open(os.path.join(d, "check_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sys.exit(0 if n_pass == len(res) else 1)


if __name__ == "__main__":
    main()
