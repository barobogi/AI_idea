# P15 검토서: 전국 3D 표현 방식 비교 — 벡터 타일 extrusion(MapLibre fill-extrusion) vs glTF 블록(three.js)

- 작성: Fo (for barobogi) <barobogi79@fo.wajo.ai>
- 만복 배정: 세톡 id 762 (2026-11-28 17:28 KST), 기한 2026-11-29 18:00
- 방법: 공식 문서·스펙 원문 열람만. 데이터 내려받기·변환 실행, 로그인·결제 없음. 우열 결론 없이 비교표까지.
- 열람 시각: 2026-11-28 17:20~17:37 KST

## 0. 비교표 (문서 근거 기준)

| 항목 | 벡터 타일 extrusion (MapLibre fill-extrusion) | glTF 블록 (three.js GLTFLoader) |
|---|---|---|
| 지오메트리 | MVT 폴리곤(2D) + 높이 속성(height/base)으로 지면에서 돌출 | scene/node 계층 + mesh primitive, 원본 3D 지오메트리 |
| 색·재질 | fill-extrusion-color(베이스색) + 루트 light 설정에 따른 셰이딩, rgba 알파 무시 | 재질(material)·텍스처 전면, KHR_materials_* 확장 계열 존재 |
| 표면 질감 | sprite 패턴(fill-extrusion-pattern, 2의 거듭제곱 크기)이 유일, color와 병용 불가 | 이미지·샘플러·UV, KHR_texture_basisu(KTX2)·webp/avif 확장 |
| 로딩 단위 | 타일 단위 (PMTiles 스펙: 타일별 오프셋 + HTTP Range 전제 설계) | 파일(블록) 단위; GLB subset 읽기는 스펙 note 수준 (?) |
| 캐시 단위 | 타일 | 블록 파일 |
| 용량 수치 | 문서에 수치 없음 (?) | REQ171 실측(루, PR #289): 광진 첫 방문 약 0.3MB, 씬 정상화 후 0.6~0.7MB 예상 |
| 호스팅 검증 | 만복 curl 실측: NCP Global Edge Range 206·캐시 HIT (세톡 id 762) | 동일 정적 서빙 환경 (현 사이트는 GitHub Pages에서 운영 중) |

## 1. fill-extrusion: 표현 방식과 문서상 한계

출처: MapLibre Style Spec 소스 `src/reference/v8.json`(maplibre/maplibre-style-spec main 브랜치), 2026-11-28 열람. 스타일 스펙 문서 사이트(layers 페이지)는 스크립트 렌더링이라 원문 대신 스펙 소스 JSON을 직접 열람했다.

- 레이어 타입 정의: "An extruded (3D) polygon." 2D 폴리곤을 높이 값으로 지면에서 세우는 방식이다.
- 높이: `fill-extrusion-height`(number, 기본 0, 음수는 지하 표현), `fill-extrusion-base`(number, height 이하, 음수 허용). 둘 다 data-driven이므로 피처 속성·표현식으로 건물별 값을 넣는 구조다.
- 색: `fill-extrusion-color`는 "The base color of the extruded fill"이고, "The extrusion's surfaces will be shaded differently based on this color in combination with the root `light` settings" — 면 음영은 스타일 루트 light 설정에 의존한다. rgba 알파 성분은 무시되며 투명도는 `fill-extrusion-opacity`로만 설정한다.
- 겹침: "Where several extrusions overlap on screen, only the surface closest to the camera is drawn, so they don't show through each other."
- 표현 옵션: `fill-extrusion-vertical-gradient`(기본 true, 옆면이 아래로 갈수록 더 어둡게), layout `fill-extrusion-rounded-corner-distance`(모서리 둥글림), `fill-extrusion-translate`·`translate-anchor`.
- 텍스처(문서상 한계): 표면 질감은 `fill-extrusion-pattern`(sprite 이미지. "image width and height must be a factor of two (2, 4, 8, ..., 512)", 줌 의존 표현식은 정수 줌에서만 평가)이 유일한 옵션이고 `fill-extrusion-color`와는 병용 불가(requires: !fill-extrusion-color). PBR 재질·노멀·UV 매핑·개별 모델 형태는 스펙 어디에도 없다.
- 지오메트리 출처: Mapbox Vector Tile 스펙 2.1 — 지원 지오메트리는 UNKNOWN/POINT/LINESTRING/POLYGON뿐(3D 지오메트리 타입 없음). 높이·밑면은 피처의 tags(key-value) 속성으로 담는다(4.2 Features).
- 지원 시작: sdk-support js 0.27.0부터.

## 2. glTF 블록의 표현력

출처: glTF 2.0 Specification(AsciiDoc 원문, KhronosGroup/glTF main), glTF 확장 레지스트리 목록(extensions/2.0/Khronos), three.js GLTFLoader 문서(docs/pages/GLTFLoader.html.md, dev 브랜치) — 2026-11-28 열람. (Khronos registry 웹페이지는 Cloudflare 차단으로 원문 저장소를 열람했다.)

- 성격: "glTF is an API-neutral runtime asset delivery format... efficient, extensible, interoperable format for the transmission and loading of 3D content." 구성 단위: scene, node(계층·로컬 변환), mesh primitive, material("parametrized approximation of visual properties"), texture, skinning, animation, camera.
- 표현력: 재질·텍스처·UV·애니메이션까지 코어 스펙에 있고, 확장 레지스트리 목록에 KHR_draco_mesh_compression, KHR_mesh_quantization, KHR_meshopt_compression, KHR_texture_basisu(KTX2), KHR_materials_unlit 등 재질·압축 계열 확장이 실려 있다(개별 확장 스펙 원문은 미열람, 5 참고).
- 컨테이너: GLB는 "enables a glTF asset, including JSON, buffers, and images, to be stored in a single binary blob"(media type `model/gltf-binary`, 확장자 .glb). JSON chunk를 먼저 읽는 방식으로 "it is also possible to read only a selected subset of resources from a Binary glTF asset"라는 note가 있으나 informative다. GLB도 외부 리소스(예: 이미지 별도 파일) 참조는 가능하다.
- three.js 쪽: GLTFLoader는 "A loader for the glTF 2.0 format"이고 load(url)로 URL에서 로드해 gltf.scene을 씬에 넣는 사용법이 문서 전체다. Draco 쓰려면 DRACOLoader를 별도 등록한다. 지원 확장 목록: KHR_draco_mesh_compression, KHR_mesh_quantization, KHR_meshopt_compression, KHR_texture_basisu, KHR_texture_transform, EXT_mesh_gpu_instancing, EXT_texture_webp, EXT_texture_avif 등. "image bitmaps are not automatically GC-collected... require special handling during the disposal process" — 블록을 갈아끼울 때 dispose 주의가 문서에 명시돼 있다.
- 타일 스트리밍·LOD 로딩: three.js 문서 원문에서 타일 단위 로딩·스트리밍 지원 표기를 못 찾았다 (?) — 블록 파일 단위 로드가 기본 단위다.

## 3. 정적 호스팅(HTTP Range)에서 로딩 단위·캐시·용량 (문서 근거)

- PMTiles 스펙 v3: "single-file archive format for tiled data". 헤더 127바이트, 루트 디렉터리는 반드시 아카이브 첫 16,384바이트 안에 있어야 한다("so that latency-optimized clients can retrieve the root directory in advance"). 디렉터리 엔트리(TileID/Offset/Length/RunLength)로 타일별 바이트 오프셋에 접근하고, 타일별 압축(gzip/brotli/zstd), 타일 타입에 MVT 포함. README: S3 같은 "commodity storage" 위에서 커스텀 타일 백엔드 없이(serverless) 운영, 데모는 MapLibre GL JS v1.15 이상.
- 문서상 대비: 벡터 타일 쪽은 "타일 단위 요청 + HTTP Range"가 스펙 설계 전제다. glTF 쪽은 파일 단위 로드가 기본이고 GLB subset 읽기는 스펙 note 수준이라, Range 기반 부분 로딩을 런타임이 쓰는지는 문서로 확인되지 않는다 (?).
- 캐시 단위: 타일/블록 파일이 각각 캐시 단위가 되는 게 문서 구조상 자연스럽지만, 두 스펙 어디에도 직접 비교 구절은 없다 (?).
- 용량: 두 스펙 모두 수치를 제공하지 않는다 (?). 참고 실측(루 REQ171, PR #289): glTF 블록 사이트 광진구 첫 방문 약 0.3MB, 3D 씬 정상화 시 0.6~0.7MB 예상. fill-extrusion 전국 용량 실측은 아직 없다.
- 만복 실측(세톡 id 762, 17:28): NCP Global Edge에서 Range 206·캐시 HIT를 curl로 확인 — PMTiles 방식을 올릴 수 있는 환경이라는 사실 확인. GitHub Pages의 Range 지원 여부는 P9(#170)·P7(#182)에서 미확인(?)으로 남아 있다.

## 4. 전국 규모 혼합 구성 (문서에 있는 경우)

- 이번에 읽은 문서 어디에도 "fill-extrusion + glTF 블록을 한 장면에 섞는" 공식 구성 설명을 찾지 못했다 (?). MapLibre와 three.js는 각각 별도 렌더러라 화면 합성은 문서가 아니라 구현 과제(두 엔진 간 카메라 동기 등)가 된다.
- 프로젝트 배경(기존 검토 기준): 현재 사이트는 PMTiles + MapLibre fill-extrusion 구성이고, Muse 검수(PR #160, F4)에서 정밀 3D 화면에 대한 fill-extrusion→Three.js 전환 제안이 나온 상태다. 즉 "도심 원경은 fill-extrusion, 광진 등 주요 구는 glTF 블록"으로 역할을 나누는 방향은 이미 검토 이력에 있고, 본 문서는 그 판단의 문서 근거 자료다.
- (?) 혼합 시 카메라 동기·로딩 순서·라이트 일관성은 문서 근거가 없어 안티 구현 지시서 단계에서 실측이 필요하다.

## 5. 긴장점·미확인 (?)

1. `fill-extrusion-pattern`의 UV 매핑 규칙(지오메트리별 텍스처 배치)은 스펙에 상세가 없다 — 패턴 지원 자체는 확인했으나 건물 외벽 텍스처로 쓸 수 있는지는 문서만으로 단정 불가.
2. GLB "subset 읽기" note(informative)를 브라우저 런타임(three.js GLTFLoader)이 실제로 활용하는지 문서에 표기 없음.
3. fill-extrusion 전국 용량·요청 수 실측 없음(REQ171은 glTF 블록 사이트 대상).
4. 두 엔진 혼합 구성의 공식 문서 근거 미확인.
5. KHR 확장(Draco, quantization, basisu 등)은 레지스트리 목록까지 열람, 개별 확장 스펙 원문은 미열람.
6. GitHub Pages HTTP Range 지원 여부는 여전히 미확인(?) — P9(#170)·P7(#182)에서 상속.

## 6. 참고 문서 목록 (열람 시각 2026-11-28 17:20~17:37 KST)

- MapLibre Style Spec 소스: https://github.com/maplibre/maplibre-style-spec/blob/main/src/reference/v8.json
- Mapbox Vector Tile 스펙 2.1: https://github.com/mapbox/vector-tile-spec/blob/master/2.1/README.md
- PMTiles 스펙 v3: https://github.com/protomaps/PMTiles/blob/main/spec/v3/spec.md / README: https://github.com/protomaps/PMTiles/blob/main/README.md
- glTF 2.0 Specification(AsciiDoc 원문): https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc (registry 웹페이지는 Cloudflare 차단, 원문 저장소 열람)
- glTF 확장 레지스트리 목록: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos
- three.js GLTFLoader 문서: https://github.com/mrdoob/three.js/blob/dev/docs/pages/GLTFLoader.html.md
