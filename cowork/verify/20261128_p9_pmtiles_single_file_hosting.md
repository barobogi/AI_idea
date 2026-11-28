# P9. 단일 파일 타일(PMTiles)의 GitHub Pages·Cloudflare R2 동작 근거 (만복 @PO 과제, 기한 2026-11-28 15:00 KST)

작성: Fo (for barobogi) <barobogi79@fo.wajo.ai> · 2026-11-28

## 3줄 요약
1. PMTiles는 "단일 파일 타일 아카이브 형식"으로, HTTP Range Requests로 접근하는 형식이다(protomaps 공식 문서). 브라우저에서는 npm `pmtiles`(현재 4.5.0, BSD-3-Clause)로 MapLibre GL JS 데모 기준 v1.15 이상과 함께 읽는다. PMTiles 자체가 별도 서버를 요구하지 않는다(별도 타일 백엔드 불필요가 공식 소개 문구).
2. Cloudflare R2는 공식 문서로 두 조건이 확인된다: 객체 하나 최대 5 TiB, GetObject의 Range 요청 구현(✅). GitHub Pages는 게시 사이트 1GB 상한과 저장소 파일 100MiB 하드 블록이 공식 문서로 확인되고, Range 요청 지원은 공식 문서 명시를 찾지 못했다(?).
3. 결론(긴장점 나열, 단정 없음): P8 중간 시나리오(전국 약 6.6GB)는 Pages의 사이트 1GB·파일 100MiB 한도를 모두 넘는 반면, R2는 5TiB 객체 한도 안에 들어간다. 다만 R2·Pages 모두 해외 인프라라 공간정보관리법 제16조 국내 호스팅 제약과 충돌한다(법적 결론 단정 없음).

## 1. PMTiles (공식 근거)

| 항목 | 확인 내용 | 출처 |
|---|---|---|
| 형식 성격 | "PMTiles is a single-file archive format for tiled data. ... hosted on a commodity storage platform such as S3, ... free of a custom tile backend or third party provider" | protomaps/PMTiles README (열람 2026-11-28) |
| 접근 방식 | "PMTiles, an open archive format for pyramids of tile data, accessible via HTTP Range Requests" | protomaps.com 문서 "What is Protomaps?" (열람 2026-11-28) |
| 사양 버전 | 현재 사양 Version 3 (spec/v3/spec.md, 저장소에 v2·v3 병존) | protomaps/PMTiles 저장소 (열람 2026-11-28) |
| 브라우저 라이브러리 | npm `pmtiles` 4.5.0, 라이선스 BSD-3-Clause, 설명 "PMTiles archive decoder for browsers" | npm registry (열람 2026-11-28 10:0x KST) |
| 읽는 방식 | `new PMTiles('url')` 로 인스턴스 생성, MapLibre에서는 `const protocol = new Protocol(); maplibregl.addProtocol("pmtiles", protocol.tile);` 후 스타일 소스 URL을 `pmtiles://https://…/파일.pmtiles` 로 지정 | PMTiles js/README (열람 2026-11-28) |
| 지도 라이브러리 | 공식 데모는 MapLibre GL JS v1.15 이상 요구. maplibre-gl npm 최신 6.20.0, BSD-3-Clause | PMTiles README·npm registry (열람 2026-11-28) |
| CORS | "Archives on cloud storage may require CORS"(README), js/README의 CORS 절은 R2·S3·GCS 등 Cloud Storage CORS 설정 문서로 연결. 호스팅 쪽 CORS 설정이 필수 조건 | PMTiles README·js/README (열람 2026-11-28) |
| 변환·생성 | go-pmtiles 바이너리로 `pmtiles convert INPUT.mbtiles OUTPUT.pmtiles` | PMTiles README (열람 2026-11-28) |

- 보조 도구 라이선스: tippecanoe(Apache-2.0, P7 확인)·go-pmtiles(MIT, P7 문서 확인) — P8 문서 5절에서 제안했던 PMTiles 변환 검증에 이들이 쓰인다.

## 2. Cloudflare R2 (공식 근거)

| 항목 | 확인 내용 | 출처 |
|---|---|---|
| 파일 하나 최대 크기 | 객체 크기 5 TiB/객체 (업로드는 단일 요청 5GiB, 멀티파트로 약 5TiB) | developers.cloudflare.com R2 limits (페이지 갱신 2026-10-30, 열람 2026-11-28) |
| Range 요청 지원 | S3 호환 API의 GetObject에서 Range ✅ 구현(HeadObject도 Range 파라미터 구현) | developers.cloudflare.com R2 S3 API compatibility (페이지 갱신 2026-11-10, 열람 2026-11-28) |
| 공개 제공 | 퍼블릭 버킷·r2.dev 하위도메인 제공. 단 r2.dev는 프로덕션 용도가 아니어서 수백 req/s 이상에서 429 스로틀, 실제 서비스는 커스텀 도메인 연결 권장 | R2 limits 문서 (열람 2026-11-28) |
| CORS | PutBucketCors·GetBucketCors 구현(✅)으로 버킷 단위 CORS 설정 가능 | R2 S3 API compatibility (열람 2026-11-28) |

- 결합 평가: P8 중간 시나리오 총량 약 6.6GB(시도별 분할이면 파일당 수백 MB 수준)는 R2 객체 한도 5TiB 안에 들어가고, Range가 공식 구현돼 있어 PMTiles 단일 파일(또는 시도별 단일 파일) 호스팅의 두 조건(용량·Range)을 문서로 만족한다. r2.dev 사용 시 스로틀은 긴장점으로 남는다(?).

## 3. GitHub Pages (공식 근거)

| 항목 | 확인 내용 | 출처 |
|---|---|---|
| 게시 사이트 크기 | "Published GitHub Pages sites may be no larger than 1 GB" | docs.github.com GitHub Pages limits (열람 2026-11-28, P8과 동일 출처) |
| 저장소 파일 크기 | 50MiB 초과 시 푸시 경고, 100MiB 초과 파일은 푸시 차단(브라우저 업로드는 25MiB) | docs.github.com About large files on GitHub (열람 2026-11-28) |
| 배포 | 배포 10분 타임아웃, 대역폭 월 100GB 소프트 한도 | GitHub Pages limits (열람 2026-11-28) |
| Range 요청 지원 | 공식 문서에서 Range/부분 요청 지원 여부를 확인하지 못했다(?) | 미확인(?) |

- 결합 평가: 전국 단일 PMTiles 파일은 중간 시나리오 6.6GB로 100MiB 파일 블록·1GB 사이트 상한 모두 초과한다. 시도별 분할 파일이라도 파일당 수백 MB~1GB 급이면 100MiB 블록에 걸리고, LFS는 파일당 플랜 한도(Free/Pro 2GB)가 있으나 Pages 게시와의 조합은 별도 검증이 필요하다(?). 즉 용량 기준으로만 보면 Pages는 전국 단일 파일 호스팅에 부적합하다(문서 근거 기준).

## 4. 긴장점·미확인 (단정 없음)
- GitHub Pages의 Range 요청 지원: 공식 문서 명시를 찾지 못했다(?). 실제 동작은 PMTiles 공식 예제 호스트가 R2임을 감안하면 확인 후 사용이 안전하다(?).
- R2·Pages 모두 해외 인프라: 공간정보관리법 제16조 국내 호스팅 요건(P5·P7·P8에서 유지 중)과 충돌한다(법적 결론 단정 없음). 국내 호스팅이 선행되면 두 후보 모두 참고용으로만 유효하다.
- r2.dev의 스로틀(429)과 커스텀 도메인 필요성(?): 커스텀 도메인 연결 절차는 이번 과제 범위 밖(가입·업로드 금지).
- R2 요금(저장·대역폭 무료 한도)은 이번 런에서 열람하지 않았다(?).
- PMTiles 사양 v3 자체는 저장소 내부 구조를 정의하며 Range·CORS 요구는 protomaps 문서·README 쪽에 있다(위 출처 구분 기준).

## 5. 근거·확인일
- protomaps/PMTiles README·js/README·spec 저장소 (https://github.com/protomaps/PMTiles, 열람 2026-11-28)
- protomaps.com "What is Protomaps?" 문서 (열람 2026-11-28)
- developers.cloudflare.com R2 limits / R2 S3 API compatibility (열람 2026-11-28)
- docs.github.com GitHub Pages limits / About large files on GitHub (열람 2026-11-28)
- npm registry: pmtiles 4.5.0(BSD-3-Clause), maplibre-gl 6.20.0(BSD-3-Clause) (열람 2026-11-28)
- 가입·업로드·실제 호스팅 테스트는 하지 않았다. 이 문서는 새 파일만 추가하며 기존 파일을 수정하지 않는다.
