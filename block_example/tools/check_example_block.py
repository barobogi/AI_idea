# -*- coding: utf-8 -*-
# 블록 1개(폴더)의 규격을 숫자로 측정한다. 표준 라이브러리만 사용.
# 사용: python check_example_block.py <블록폴더> [--timing <timing.json>]
# 결과: 항목별 PASS/FAIL 표 + 블록 폴더 옆 reports/<폴더명>_check.json (블록 폴더에는 4종만 둔다). FAIL이 하나라도 있으면 종료코드 1.
import sys, os, re, json, struct, base64
sys.stdout.reconfigure(encoding="utf-8")
BUDGET = {"lod3_tri": (10000, 14000), "lod2_tri": (1200, 1800), "lod3_bytes": 768000, "lod2_bytes": 71680,
          "tex_bytes": 102400, "pkg_bytes": 972800}
MATS = {"wall", "trim", "glass", "roof", "stone", "ground", "metal", "wood", "accent", "plaque", "misc"}
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


def read_vec3(g, ai):
    """접근자 ai(POSITION)의 실제 값을 버퍼에서 읽어 (min[3], max[3])를 돌려준다. 선언된 min/max를 믿지 않는다."""
    a = g["accessors"][ai]
    bv = g["bufferViews"][a["bufferView"]]
    uri = g["buffers"][bv.get("buffer", 0)]["uri"]
    raw = base64.b64decode(uri.split(",", 1)[1])
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or 12
    mn = [float("inf")] * 3
    mx = [float("-inf")] * 3
    for i in range(a["count"]):
        v = struct.unpack_from("<3f", raw, off + i * stride)
        for k in range(3):
            mn[k] = min(mn[k], v[k])
            mx[k] = max(mx[k], v[k])
    return mn, mx


def gltf_stats(path):
    g = json.load(open(path, encoding="utf-8"))
    acc = g["accessors"]
    st = {"tris": 0, "idx": set(), "normal": False, "min_y": None, "warn": set(), "real": {}, "acc_total": 0, "acc_bad": 0}
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
                ai = p["attributes"]["POSITION"]
                if ai not in st["real"]:
                    st["real"][ai] = read_vec3(g, ai)
                    d = acc[ai]
                    st["acc_total"] += 1
                    if any(abs(d["min"][k] - st["real"][ai][0][k]) > 1e-3 or abs(d["max"][k] - st["real"][ai][1][k]) > 1e-3 for k in range(3)):
                        st["acc_bad"] += 1
                y = ty2 + sy2 * st["real"][ai][0][1]
                st["min_y"] = y if st["min_y"] is None else min(st["min_y"], y)
        for c in n.get("children", []):
            walk(c, ty2, sy2)

    roots = g["scenes"][g.get("scene", 0)]["nodes"]
    bad_roots = [r for r in roots if r >= len(nodes)]
    has_parent = {c for n in nodes for c in n.get("children", [])}
    orphans = [i for i in range(len(nodes)) if i not in has_parent and i not in roots]
    for r in roots:
        if r < len(nodes):
            walk(r, 0.0, 1.0)
    uv_ok = True
    for ms in g.get("meshes", []):
        for pr in ms["primitives"]:
            ta = pr["attributes"].get("TEXCOORD_0")
            if ta is None or acc[ta].get("componentType") != 5123 or not acc[ta].get("normalized"):
                uv_ok = False
    names = [n.get("name", "") for n in nodes]
    imgs = [i.get("uri") for i in g.get("images", [])]
    ext = [b for b in g["buffers"] if not str(b.get("uri", "")).startswith("data:")]
    return {"acc_bad": st["acc_bad"], "acc_total": st["acc_total"], "bad_roots": len(bad_roots), "orphans": len(orphans), "mats": [m.get("name", "") for m in g.get("materials", [])], "uv_ok": uv_ok,
            "unnamed": sum(1 for x in names if not x), "night": sum(1 for x in names if x.startswith("night_light")),
            "hot": sum(1 for x in names if x.startswith("hotspot")),
            "tris": st["tris"], "idx": sorted(st["idx"]), "normal": st["normal"], "min_y": st["min_y"],
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
            tol = 0.005   # 3총사 v1.1 규격: LOD3·LOD2 모두 min.y=0.000 (허용 ±0.005)
            chk(f"Q05-{tag} 접지 min.y", s["min_y"] is not None and abs(s["min_y"]) <= tol,
                ("min.y=" + (str(round(s["min_y"], 4)) if s["min_y"] is not None else "측정 불가(장면에 연결된 메시 없음)") + f" 실측 (허용 ±{tol})") + (" 경고:" + ";".join(s["warn"]) if s["warn"] else ""))
            chk(f"Q06-{tag} 인덱스 uint16·법선 없음", s["idx"] == [5123] and not s["normal"],
                f"index={s['idx']} normal={s['normal']}")
            mset = {x.split("_")[-1] for x in s["mats"]}
            chk(f"Q11-{tag} 재질 11종", len(s["mats"]) == 11 and mset == MATS, f"{len(s['mats'])}종, 이름 접미 {sorted(mset)[:11]}")
            chk(f"Q12-{tag} UV uint16 normalized", s["uv_ok"], f"uv_ok={s['uv_ok']}")
            chk(f"Q13-{tag} 전 노드 name", s["unnamed"] == 0, f"이름 없는 노드 {s['unnamed']}개")
            if tag == "LOD3":
                chk("Q14-앵커 야간조명 4·핫스팟 5", s["night"] == 4 and s["hot"] == 5, f"night_light={s['night']} hotspot={s['hot']}")
            chk(f"Q15-{tag} 접근자 min/max가 실제 데이터와 일치", s["acc_bad"] == 0, f"불일치 {s['acc_bad']}/{s['acc_total']}개 (뷰어의 경계 상자·컬링에 쓰임)")
            chk(f"Q16-{tag} scene.nodes 유효", s["bad_roots"] == 0 and s["orphans"] == 0, f"범위 밖 루트 {s['bad_roots']}개, 어느 장면에도 안 걸린 노드 {s['orphans']}개")
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
        def _u(e):
            if isinstance(e, dict):
                return e.get("url", "")
            if isinstance(e, (list, tuple)) and e:
                return e[0]
            return e if isinstance(e, str) else ""
        urls = [m.get("reference_url", "")] + [_u(e) for e in (m.get("verification_evidence") or [])]
        urls = [u for u in urls if u]
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
        gd = m.get("ground") or {}
        gen = m.get("generation") or {}
        asl = [k for k in m if k in ("elevation_asl", "elevation_m")]
        chk("M08-뷰어 규약", m.get("lod_switch_distance") == 200.0 and gd.get("mode") == "snap_to_terrain" and gd.get("origin_y_m") == 0.0
            and not asl and gen.get("execution_code_in_package") is False,
            f"lod_switch={m.get('lod_switch_distance')} ground={gd.get('mode')},{gd.get('origin_y_m')} ASL필드={asl} 실행코드미포함={gen.get('execution_code_in_package')}")
        refs = m.get("references") or []
        chk("M09-출처 4건 이상", len(refs) >= 4, f"references {len(refs)}건")
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
    rep_dir = os.path.join(os.path.dirname(os.path.abspath(d)), "reports")
    os.makedirs(rep_dir, exist_ok=True)
    json.dump({"folder": name, "pass": n_pass, "total": len(res), "package_bytes": pkg, "items": res},
              open(os.path.join(rep_dir, f"{name}_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sys.exit(0 if n_pass == len(res) else 1)


if __name__ == "__main__":
    main()
