# kospimap 운영자 진술 기술 검증 가능성 검토 (만복 @PO 의뢰, 셋톡 #330)

- 의뢰: 공개 3D 드론 지도 사이트 운영자의 진술 "서버에 데이터를 저장하지 않고 요청마다 실시간 렌더링한다"를 바깥에서 어디까지 기술적으로 확인할 수 있는지 **가능 여부 검토** (판정 아님)
- 대상: https://kospimap.com/drone-explore (공개 페이지만)
- 기한: 2026-11-27 12:00 KST / 산출: 검토서(마크다운), Draft PR, 확인 못 한 것 (?)
- 관찰 일시: 2026-11-26 19:40~19:55 KST

## 3줄 요약

1. 페이지 코드(배포된 JS 번들) 수준에서는 **건물·지형 데이터가 kospimap.com 자체 서버가 아니라 외부 VWorld API에서 브라우저로 직접 들어오는 구조**로 보인다 → "서버 저장 없음" 진술과 일치하는 방향의 관찰 결과(확인).
2. 같은 도메인 `/3d/*` 정적 파일(차량·나무·음향 등 게임 에셋)은 kospimap.com에서 302로 **GitHub Pages(fdx5.github.io/kospimap-assets)** 콘텐츠 해시 파일로 우회된다(확인). 건물 데이터가 아니라 에셋이며, 자체 서버 저장도 아니다.
3. 실시간 브라우저 네트워크 로그와 서버 내부(캐시·DB)는 이번 관찰 환경에서 볼 수 없었다 (?). 런타임 요청 목록은 브라우저 DevTools로만 확정 가능하므로 절차와 해석표를 아래에 둔다.

## 관찰 방법의 한계 명시

- 이번 관찰은 ①페이지·배포 JS 번들 소스 분석(정적), ②개별 URL 요청 시 응답 헤더 확인의 조합이다. 실제 브라우저 세션의 **네트워크 요청 목록은 캡처하지 못했다** (?) — 스크린샷 도구로는 요청 로그·콘솔이 나오지 않았고, 페이지는 "건물 윤곽 불러오는 중..." 단계에서 머무는 화면이 확인됐다(확인).
- 번들에 데이터 요청 코드가 있어도 실제 로드 시 그 요청이 나가는지, 실패하는지는 런타임 로그가 있어야 확정된다.

## 무엇을 관찰했는가 (공개 화면·공개 자원만 사용)

### 1) 페이지 셸·호스팅 구조
- `https://kospimap.com/drone-explore` HTML: `x-render-origin-server: uvicorn`, `server: cloudflare`, `cache-control: no-store, no-cache, must-revalidate` (확인). HTML 셸은 캐시 금지.
- SPA(Vite 빌드)이며 지연 로딩 청크 구조. 드론 탐험 페이지 청크 `DroneExplorePage-P3hkSGN-.js`가 의존 청크 목록에 `vworldBuildings-BEhMJeoj.js`(VWorld 건물 로더)를 포함(확인).

### 2) 건물·지형 데이터의 출처 (번들 소스 기준, 확인)
- `vworldBuildings` 청크 내 요청 대상:
  - `https://map.vworld.kr/dtkmap/selectApiKeyJson.do?apiKey=<클라이언트 코드에 삽입된 값>` → 응답의 apiKey로 "VWorld 3D token"을 얻는 코드. 키 값은 기록·재사용하지 않았다(의뢰 금지 항목).
  - 데이터 서버: `https://xdworld.vworld.kr`, `xdworld1~3.vworld.kr` (XDWorld 3D 데이터)
  - 주소 검색/데이터 API: `https://api.vworld.kr/req/address?`, `https://api.vworld.kr/req/data?`
- 즉 브라우저가 **VWorld(공공 지도 API)를 직접 호출**하는 구조로, kospimap 자체 도메인의 데이터 응답 경로는 번들에서 보이지 않았다.
- 참고: 별도 호스트 `voltaris-nyyo.onrender.com`은 링크(외부 사이트 이동) 용도로만 보였고 데이터 경로 아님(확인).

### 3) 같은 도메인 정적 파일과 캐시 헤더 (확인)
- `/3d/*` 자산(cars.json, facades/manifest.json, trees.json/bin, plants, drone 사운드 `mini2-20261010-v2/*.wav`, `places-20261018-v2` 등)은 kospimap.com에서 **302 리다이렉트** → `https://fdx5.github.io/kospimap-assets/objects/<sha256>.json` 형태의 GitHub Pages 콘텐츠 주소 파일로 우회(확인).
- 리다이렉트 응답 캐시 헤더: `cache-control: public, max-age=3600`, `cf-cache-status: DYNAMIC` (확인). JS 청크: `cache-control: public, max-age=31536000, immutable`, `ETag: W/"..."` (확인). HTML: no-store(확인).
- `/3d/drone/mini2-20261010-v2` 경로 자체 단독 요청은 404(no-store)였다. 실제 파일은 `<base>/<이름>.wav` 조합이라고 추정되나 그 파일의 헤더는 미확인 (?).

### 4) 해석표 (의뢰서 기준 분류)

| 관찰 대상 | 관찰 결과 | 의뢰서 분류 기준 적용 |
|---|---|---|
| 건물·지형 데이터 경로 | 외부 VWorld API 직접 호출 구조(번들 소스 기준) | **"서버 저장 없음과 일치"** — 다만 런타임 요청 로그 미확인 (?) |
| 같은 도메인 정적 파일(geojson·pbf·pmtiles) | `/3d/*`는 자체 서버 파일처럼 보이나 302로 GitHub Pages 우회, 건물 데이터 아님(에셋) | "저장 가능성 높음"에 해당하는 증거 없음. 자체 서버 저장 시그널 미발견 |
| 캐시 헤더(Cache-Control·ETag) | HTML no-store, JS immutable+ETag, /3d/* 302 hop max-age=3600 | 정적 에셋은 CDN 캐시 정상. 건물 데이터 응답의 헤더는 미확인 (?) |
| 서버 내부(캐시·DB) | 바깥에서 볼 수 없음 | **확인 불가로 명시** (진술과 배반도, 뒷받침도 못 함) |

## 사람이 확인하는 관찰 절차 (3~5단계, 공개 화면만)

1. 데스크톱 브라우저에서 `https://kospimap.com/drone-explore` 열기 → F12 → Network 탭 → "Preserve log" 켜고 새로고침.
2. 도메인 필터: `vworld` (map/xdworld/api) → 요청 목록, 상태 코드, 응답 크기 기록.
3. 도메인 필터: `kospimap.com` → `/api/*`와 `/3d/*` 요청 구분 기록. `/api/*`가 있으면 응답 내용이 지도 데이터인지(예: geojson 좌표 다수) 메타 데이터인지 구분.
4. 건물 데이터로 보이는 요청 하나의 Headers 탭에서 `Cache-Control`, `ETag`, `Age`, `cf-cache-status` 확인 — CDN 캐시(Age>0)면 어떤 층에선 캐시가 돌고 있다는 뜻.
5. Console 탭에서 CORS/401/403 에러 유무 확인. 결과 해석은 아래 표.

### 예상 결과 해석표

| DevTools에서 보이는 것 | 해석 |
|---|---|
| 건물 데이터가 xdworld*.vworld.kr에서 200 | 외부 API 직접 호출 — "서버 저장 없음" 진술과 일치 |
| 건물 데이터가 kospimap.com/api/*에서 대량 좌표로 200 | 자체 서버가 데이터를 내보는 것 — "저장 없음"과 충돌 가능성, 응답 본문 확인 필요 |
| kospimap.com/api/* 응답이 CDN 캐시(Age>0, HIT) | 자체 인프라 어딘가에 캐시 존재 — 진술과 배반 가능성 |
| 요청 실패/CORS | 관찰만으로 판단 불가 (?) |

## 확인 못 한 것 (?)

- 실시간 브라우저 네트워크 요청 목록·콘솔 로그(캡처 도구 한계) — 위 절차로 사람이 확정 가능.
- `/3d/drone/*` 개별 파일의 캐시 헤더.
- VWorld API 응답에 붙는 캐시 헤더(키 재사용 금지로 단독 호출 안 함).
- 서버 내부 캐시·DB 존재 여부(바깥에서 원리적으로 확인 불가 — 진술 검증의 근본 한계).

## 금지 준수

- 로그인·가입·결제 없음, 인증키 추출·재사용 없음(코드 내 키 값 미기록), 대량 호출·크롤링·우회 없음(요청 총 10회 이내, 페이지/청크/헤더 확인), 약관 위반 판정·위법 단정 없음.
