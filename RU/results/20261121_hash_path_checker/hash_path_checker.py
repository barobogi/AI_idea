#!/usr/bin/env python3
"""해시/경로 문자열 추출 + 형식 검사 + '가짜 의심' 점수 (hash_path_checker)

요청: 만복 (2026-11-21, id59) — 텍스트에서 해시 형식 문자열과 파일 경로
형식 문자열을 추출하고, 형식이 맞는지 + 얼마나 '지어낸 값'처럼 보이는지
0.0-1.0 의심 점수를 매긴다. 실제 값의 진위 대조는 요청자 쪽에서 한다.

표준 라이브러리만 사용. 외부 API/네트워크 없음.

  python3 hash_path_checker.py 문서.txt [문서2.md ...] [--json report.json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# 추출 정규식
# ---------------------------------------------------------------------------

# 특수 형식 먼저, 일반 hex 는 마지막에 (긴 것부터 매칭)
RE_BCRYPT = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")
RE_SHA_CRYPT = re.compile(r"\$(?:5|6)\$(?:rounds=\d+\$)?[./A-Za-z0-9]{4,}\$?"
                          r"[./A-Za-z0-9]{20,}")
RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
RE_HEX = re.compile(r"\b[0-9a-fA-F]{8,}\b")

# 경로: POSIX 절대/상대, Windows 드라이브/UNC
# 세그먼트로 <username> 같은 템플릿 토큰도 허용한다 (의심 점수에서 잡음)
RE_PATH_POSIX = re.compile(
    r"(?<![\w/.-])(?:~|\.{1,2})?(?:/(?:[A-Za-z0-9._+@-]+|<[^>/]*>(?:\.[A-Za-z0-9]+)?)){1,}/?")
# 세그먼트 안의 공백은 ASCII 단어가 이어질 때만 허용한다 (Program Files).
# 한국어 조사가 붙은 문장("daily\ 로")을 경로로 삼키지 않기 위해서다.
_WIN_SEG = r"[A-Za-z0-9._+@(),-]+(?: [A-Za-z0-9._+@(),-]+)*"
RE_PATH_WIN = re.compile(
    rf"\b[A-Za-z]:[\\/](?:{_WIN_SEG}[\\/])*{_WIN_SEG}?[\\/]?"
    rf"|\\\\{_WIN_SEG}(?:\\{_WIN_SEG})+")

HASH_LENGTH_KINDS = {
    32: "md5", 40: "sha1", 56: "sha224", 64: "sha256",
    96: "sha384", 128: "sha512",
}

# 흔한 플레이스홀더/더미 패턴 (소문자 비교)
PLACEHOLDER_TOKENS = (
    "deadbeef", "cafebabe", "feedface", "deadc0de", "0badf00d",
    "abcdef0123456789", "0123456789abcdef",
)
PLACEHOLDER_SEGMENTS = {
    "foo", "bar", "baz", "qux", "test", "example", "sample", "dummy",
    "demo", "xxx", "aaa", "temp", "tmp", "placeholder", "something",
    "your", "path", "to", "file", "dir", "folder", "name", "here",
    "myfile", "my", "some", "any",
}
RE_TEMPLATE = re.compile(r"[<{(\[][^>}\])]{1,30}[>}\])]|%[sd]")
WIN_RESERVED = {"con", "prn", "aux", "nul",
                *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}


# ---------------------------------------------------------------------------
# 해시 형식 검사
# ---------------------------------------------------------------------------

def classify_hash(value: str) -> dict:
    """형식 검사 결과: kind, 형식 유효성, 형식 문제 목록."""
    problems: list[str] = []
    v = value
    if RE_BCRYPT.fullmatch(v):
        cost = int(v[4:6])
        if not (4 <= cost <= 31):
            problems.append(f"bcrypt cost {cost} out of range 4..31")
        return {"kind": "bcrypt", "valid": not problems, "problems": problems}
    if RE_SHA_CRYPT.fullmatch(v):
        return {"kind": "sha-crypt", "valid": True, "problems": problems}
    if RE_UUID.fullmatch(v):
        ver = v[14].lower()
        var = v[19].lower()
        if ver not in "12345678":
            problems.append(f"UUID version nibble '{ver}' not in 1..8")
        if var not in "89ab":
            problems.append(f"UUID variant nibble '{var}' not in 8/9/a/b")
        return {"kind": "uuid", "valid": not problems, "problems": problems}
    if RE_HEX.fullmatch(v):
        n = len(v)
        if n % 2:
            problems.append(f"odd hex length {n}")
        kind = HASH_LENGTH_KINDS.get(n, f"hex-{n}")
        return {"kind": kind, "valid": not problems, "problems": problems}
    return {"kind": "unknown", "valid": False,
            "problems": ["matches no known hash format"]}


# ---------------------------------------------------------------------------
# 의심 점수: 해시
# ---------------------------------------------------------------------------

def _max_char_run(s: str) -> int:
    best = run = 1
    for i in range(1, len(s)):
        run = run + 1 if s[i] == s[i - 1] else 1
        best = max(best, run)
    return best


def _max_seq_run(s: str) -> int:
    """0123... / fedc... 식 연속 증감 런의 최대 길이."""
    best = run = 1
    for i in range(1, len(s)):
        d = ord(s[i]) - ord(s[i - 1])
        run = run + 1 if d in (1, -1) else 1
        best = max(best, run)
    return best


def _max_block_repeat(s: str) -> int:
    """ababab / aabbccdd 같은 반복 블록이 덮는 최대 길이."""
    best = 0
    for w in (2, 4, 8, 16):
        i = 0
        while i + 2 * w <= len(s):
            if s[i:i + w] == s[i + w:i + 2 * w]:
                j = i + 2 * w
                while j + w <= len(s) and s[j:j + w] == s[i:i + w]:
                    j += w
                best = max(best, j - i)
                i = j
            else:
                i += 1
    return best


def _max_freq_z(s: str, alphabet: int = 16) -> float:
    """가장 많이 나온 문자의 z-점수 (균등 기대 대비). 랜덤 해시는 ~3 이하."""
    n = len(s)
    if n == 0:
        return 0.0
    exp = n / alphabet
    var = n * (1 / alphabet) * (1 - 1 / alphabet)
    if var <= 0:
        return 0.0
    return (max(Counter(s).values()) - exp) / math.sqrt(var)


def hash_suspicion(value: str) -> tuple[float, list[str]]:
    """0.0 (자연스러움) ~ 1.0 (거의 확실히 지어낸 값) + 근거 목록."""
    cls = classify_hash(value)
    reasons: list[str] = []
    if not cls["valid"]:
        reasons.extend(cls["problems"])
        return 1.0, reasons          # 형식 자체가 틀리면 최대 의심

    v = value.lower()
    score = 0.0

    for tok in PLACEHOLDER_TOKENS:
        if tok in v:
            score = max(score, 0.95)
            reasons.append(f"known placeholder token '{tok}'")
            break

    run = _max_char_run(v)
    if run >= 8:
        score = max(score, 0.9)
        reasons.append(f"same character repeated x{run}")
    elif run >= 5:
        score = max(score, 0.55)
        reasons.append(f"same character repeated x{run}")
    elif run >= 4:
        # 4연속은 진짜 해시에서도 종종 나온다 (128자 기준 수 %): 낮게만
        score = max(score, 0.45)
        reasons.append(f"same character repeated x{run}")

    seq = _max_seq_run(v)
    if seq >= 8:
        score = max(score, 0.85)
        reasons.append(f"sequential characters x{seq}")
    elif seq >= 6:
        score = max(score, 0.5)
        reasons.append(f"sequential characters x{seq}")

    blk = _max_block_repeat(v)
    if blk >= max(16, len(v) // 2):
        score = max(score, 0.9)
        reasons.append(f"repeating block covers {blk}/{len(v)} chars")
    elif blk >= 12:
        score = max(score, 0.45)
        reasons.append(f"repeating block covers {blk} chars")

    if cls["kind"] not in ("bcrypt", "sha-crypt"):
        hexpart = v.replace("-", "")
        z = _max_freq_z(hexpart)
        # 균등 랜덤 32/40/64/128자 hex 의 최다 문자 z 는 거의 4 미만이다.
        if z >= 6:
            score = max(score, 0.85)
            reasons.append(f"character distribution heavily skewed (z={z:.1f})")
        elif z >= 4:
            score = max(score, 0.5)
            reasons.append(f"character distribution skewed (z={z:.1f})")

    return min(1.0, score), reasons


# ---------------------------------------------------------------------------
# 의심 점수: 경로
# ---------------------------------------------------------------------------

def classify_path(value: str) -> dict:
    problems: list[str] = []
    kind = "windows" if re.match(r"^(?:[A-Za-z]:|\\\\)", value) else "posix"
    segs = [s for s in re.split(r"[/\\]", value) if s not in ("", ".")]
    if kind == "windows":
        for seg in segs[1:] if value.startswith("\\\\") else segs[1:]:
            base = seg.split(".")[0].lower().rstrip()
            if base in WIN_RESERVED:
                problems.append(f"reserved device name '{seg}'")
            if re.search(r"[<>:\"|?*\x00-\x1f]", seg):
                problems.append(f"illegal character in '{seg}'")
            if seg.endswith((" ", ".")):
                problems.append(f"segment ends with space/dot: '{seg}'")
    if "/" in value and "\\" in value:
        problems.append("mixed / and \\ separators")
    if "//" in value[1:] and kind == "posix":
        problems.append("double slash")
    return {"kind": kind, "valid": not problems, "problems": problems}


def path_suspicion(value: str) -> tuple[float, list[str]]:
    cls = classify_path(value)
    reasons: list[str] = []
    if not cls["valid"]:
        reasons.extend(cls["problems"])
        return 1.0, reasons

    score = 0.0
    raw_segs = [s for s in re.split(r"[/\\]", value) if s not in ("", ".")]
    segs = [s.lower().split(".")[0] for s in raw_segs if s != ".."]
    hits = [s for s in segs if s in PLACEHOLDER_SEGMENTS]
    if RE_TEMPLATE.search(value):
        score = max(score, 0.9)
        reasons.append("template token like <name> or %s")
    if len(hits) >= 2:
        score = max(score, 0.85)
        reasons.append(f"placeholder segments: {hits}")
    elif hits:
        score = max(score, 0.45)
        reasons.append(f"placeholder segment: {hits}")
    if ".." in raw_segs:
        score = max(score, 0.3)
        reasons.append("parent-directory traversal '..'")
    return min(1.0, score), reasons


# ---------------------------------------------------------------------------
# 문서 스캔
# ---------------------------------------------------------------------------

def _dedup_spans(items: list[dict]) -> list[dict]:
    """같은 구간을 덮는 중복 추출 제거 (긴 것/특수 형식 우선)."""
    items.sort(key=lambda it: (it["span"][0], -(it["span"][1] - it["span"][0])))
    out: list[dict] = []
    last_end = -1
    for it in items:
        if it["span"][0] >= last_end:
            out.append(it)
            last_end = it["span"][1]
    return out


def scan_text(text: str) -> dict:
    findings: list[dict] = []

    hashes: list[dict] = []
    for regex, kind in ((RE_BCRYPT, "bcrypt"), (RE_SHA_CRYPT, "sha-crypt"),
                        (RE_UUID, "uuid"), (RE_HEX, None)):
        for m in regex.finditer(text):
            val = m.group(0)
            cls = classify_hash(val)
            score, reasons = hash_suspicion(val)
            hashes.append({"type": "hash", "value": val,
                           "kind": cls["kind"], "valid": cls["valid"],
                           "suspicion": round(score, 3), "reasons": reasons,
                           "span": list(m.span())})
    for h in _dedup_spans(hashes):
        findings.append(h)

    paths: list[dict] = []
    for regex in (RE_PATH_WIN, RE_PATH_POSIX):
        for m in regex.finditer(text):
            val = m.group(0)
            # 문장 끝 마침표가 세그먼트에 붙는 것 정리
            stripped = val.rstrip(".")
            if stripped and not stripped.endswith(("/", "\\")):
                val = stripped
            # 경로처럼 보이려면 최소한 세그먼트 하나는 있어야 한다
            if val in ("/", "./", "../", "~/") or len(val) < 3:
                continue
            cls = classify_path(val)
            score, reasons = path_suspicion(val)
            paths.append({"type": "path", "value": val,
                          "kind": cls["kind"], "valid": cls["valid"],
                          "suspicion": round(score, 3), "reasons": reasons,
                          "span": list(m.span())})
    findings.extend(_dedup_spans(paths))

    findings.sort(key=lambda f: f["span"][0])
    n_sus = sum(1 for f in findings if f["suspicion"] >= 0.5)
    top = max((f["suspicion"] for f in findings), default=0.0)
    mean = (sum(f["suspicion"] for f in findings) / len(findings)
            if findings else 0.0)
    # 문서 점수: 최고 의심 70% + 평균 30% (한 개의 뻔한 가짜만으로도 높게)
    doc_score = round(0.7 * top + 0.3 * mean, 3)
    return {"findings": findings, "n_findings": len(findings),
            "n_suspicious": n_sus, "doc_suspicion": doc_score}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--json", dest="json_path")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    report = {}
    for path in args.docs:
        with open(path, encoding="utf-8") as f:
            report[path] = scan_text(f.read())
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    n_flag = 0
    for path, r in report.items():
        flag = r["doc_suspicion"] >= args.threshold
        n_flag += flag
        print(f"{path}: findings={r['n_findings']} "
              f"suspicious={r['n_suspicious']} "
              f"doc_suspicion={r['doc_suspicion']:.2f} "
              f"{'FLAG' if flag else 'ok'}")
        for f_ in r["findings"]:
            if f_["suspicion"] >= args.threshold:
                print(f"   [{f_['type']}] {f_['value'][:60]!r} "
                      f"-> {f_['suspicion']:.2f} ({'; '.join(f_['reasons'])})")
    print(f"scanned={len(report)} flagged={n_flag}")
    sys.exit(1 if n_flag else 0)


if __name__ == "__main__":
    main()
