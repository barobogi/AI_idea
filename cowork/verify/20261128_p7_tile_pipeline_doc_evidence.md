# P7 검증 문서: 좌표 변환·타일 파이프라인 공식 문서 근거

- 작성: Fo (for barobogi) <barobogi79@fo.wajo.ai> / 2026-11-28 15:0x KST
- 배정: 만복 세톡 id 733 (2026-11-28 14:58, 기한 11/29 12:00)
- 범위: GDAL/ogr2ogr·PROJ·PMTiles·MBTiles 공식 문서와 공개 저장소 스펙 문서만 열람. 데이터 내려받기·변환 실행·로그인·결제 없음. 법적 판정 없음. 확인 못 한 것은 (?) 표기.
- 관련 문서: PR #167(같은 주제의 실측 중심 문서, 만복 검증 완료). 본 문서는 공식 문서 근거 중심 별도 문서.

## 1. EPSG:5186 → 4326 변환: 명령 예시와 근거

명령 예시:

```
ogr2ogr -s_srs EPSG:5186 -t_srs EPSG:4326 out_4326.shp in_5186.shp
```

문서 근거:

- EPSG:5186 = KGD2002 / Central Belt 2010 (epsg.io/5186, 열람 2026-11-28 15:01 KST). Transverse Mercator, 위도 원점 38, 중앙경선 127, 축척계수 1, false_easting 200,000 m, false_northing 600,000 m, 타원체 GRS 1980. 좌표축 순서는 "Cartesian 2D CS. Axes: northing, easting (X,Y)" — 북쪽(northing)이 앞. 2010-01-01부터 법정 좌표계이고 정보원은 국토지리정보원(NGII).
- 변환 경로는 EPSG:15831 "KGD2002 to WGS 84 (1)" (epsg.io/15831, 열람 2026-11-28 15:01 KST). 방법: Geocentric translations (geog2D domain), 이동값 (0,0,0,0,0,0,0), 공표 정확도 1.0 m. 비고: "Approximation at the +/- 1m level assuming that ITRF2000 is equivalent to WGS 84" (EPSG 원문 13단어). 정보원: OGP.
- 해석: 문서상 공표 오차는 ±1.0 m 수준이고, 이 연산은 0 이동 근사이므로 별도 그리드(격자) 파일이 필요 없다. 등기·측량 수준의 정밀도가 필요한 용도에는 이 근사로 충분한지 별도 판단이 필요하다 (?) — 본 문서는 판단하지 않음.
- 축 순서 주의 (GDAL 3.0+): gdal.org osr_api_tut 문서는 "Starting with GDAL 3.0, the axis order mandated by the authority defining a CRS is by default honoured"라고 밝힌다. EPSG:4326 정의축은 위도(Lat) 우선. ogr2ogr가 shapefile 출력에 쓰는 x/y 기본 순서(경도,위도)에 대한 직접 문서 확인은 못 했다 (?) — 실제 변환 1회 검증 권고. (인용은 검색 스니펫 발췌, 본문 전체 열람 아님 (?))
- 웹 지도 투영: EPSG:3857 (WGS 84 / Pseudo-Mercator). MapLibre GL JS·Leaflet 기본 투영.
- 실측 보강: PR #167에서 pyproj 3.7.2(PROJ 9.5.1)로 5186↔4326 왕복 오차 ≤3.6e-9 m, 10만 점 0.020초 확인. 본 문서는 문서 근거만 다루고 실측은 PR #167을 인용한다.

## 2. 타일 형식 비교: PMTiles / MBTiles / 개별 파일

정적 호스팅(HTTP만으로 서빙) 관점 비교. 근거: docs.protomaps.com/pmtiles (열람 2026-11-28 15:02 KST), mapbox/mbtiles-spec 1.3 (열람 2026-11-28 15:02 KST).

| 형식 | 구조 | 정적 호스팅 적합성 | 근거 |
|---|---|---|---|
| PMTiles (v3) | 단일 파일 아카이브 | 적합. "readers use HTTP Range Requests to fetch only the relevant tile or metadata". 최대 2개의 캐시 가능한 중간 요청. 읽기 전용(부분 갱신 불가) | docs.protomaps.com/pmtiles |
| MBTiles 1.3 | SQLite 3.0.0+ 데이터베이스 | 부적합/조건부. protomaps 비교: "MBTiles are designed to be accessed on disk from a running server process". 서버 프로세스 또는 파일 전체 다운로드 필요 | mbtiles-spec 1.3 + protomaps |
| 개별 파일 /Z/X/Y | 디렉터리 트리 타일 파일 | 소형 타일셋 적합. 전역 피라미드(예: 3억 타일)는 업로드 비용·시간이 크고, 타일 중복 제거 없음 | docs.protomaps.com/pmtiles |

- HTTP Range 지원은 스토리지 쪽 조건이다. Cloudflare R2의 GetObject Range 지원은 P9(PR #170)에서 공식 문서로 확인. GitHub Pages의 Range 지원은 P9에서도 미확인 (?) — 본 런에서도 미확인 (?).
- MBTiles를 정적 HTTP에서 Range 요청으로 읽는 표준 방법의 존재 여부는 확인 못 했다 (?) — MBTiles 스펙 자체는 온디스크 SQLite 사용을 전제로 기술되어 있다.

## 3. 도구별 라이선스

| 도구 | 라이선스 | 확인 출처 |
|---|---|---|
| PROJ 9.x | MIT | PR #167 열람 (2026-11-28) |
| GDAL 3.x | MIT/X11 | PR #167 열람 (2026-11-28) |
| pyproj | MIT | PR #167 열람 (2026-11-28) |
| npm pmtiles 4.5.0 | BSD-3-Clause | PR #170(P9) 열람 (2026-11-28) |
| go-pmtiles | MIT | PR #170(P9) 열람 (2026-11-28) |
| tippecanoe | Apache-2.0 | PR #170(P9) 열람 (2026-11-28) |
| MapLibre GL JS | BSD-3-Clause | PR #170(P9) 열람 (2026-11-28) |

## 4. 미확인 (?)

1) ogr2ogr의 shapefile 출력에서 EPSG:4326 기본 x/y 순서 (경도,위도) — 문서 직접 확인 못 함
2) MBTiles의 정적 HTTP Range 기반 읽기 표준 방법 존재 여부
3) GitHub Pages의 HTTP Range 지원 여부 (P9에 이어 재확인 필요)
4) PROJ·GDAL 최신 릴리스 버전 번호 — 공식 릴리스 페이지 본 런 미열람 (PR #167 시점 실측은 9.5.1)
5) 5186→3857 직접 변환 시 PROJ가 선택하는 중간 연산 체인 — projinfo 출력 미열람

## 5. 참조 URL·열람 시각 (2026-11-28 KST)

- https://epsg.io/5186 (15:01)
- https://epsg.io/15831 (15:01)
- https://gdal.org/en/stable/programs/ogr2ogr.html (15:05)
- https://docs.protomaps.com/pmtiles/ (15:02)
- https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md (15:02)
- 기존 문서: PR #167 (실측), PR #169 (P8 용량), PR #170 (P9 PMTiles)
