# 1) HMYS_#9 ChetasLua/crimson-loong (赤龍) 에셋 제로 3D 시네마틱 심층 역공학 기술 가이드

## 2) 쓰레드 링크
- 쓰레드 원본 링크: https://www.threads.com/share/BAO7DaF0lv (포스트: https://www.threads.com/@aicoffeechat/post/DftAT3aCjL_)
- 원작 오픈소스 저장소: https://github.com/ChetasLua/crimson-loong
- 라이브 데모: https://chetaslua.github.io/crimson-loong/

## 3) 분석내용

### (1) 기본업무 (객관적 기능·풀코드·스키마 구현 명세)
- **Zero Assets & Zero Network 아키텍처**:
  - 외부 3D 모델(GLTF/OBJ), 텍스처 이미지(PNG/JPG), 폰트, 오디오 파일 일체 미사용.
  - `data:` URI 및 네트워크 로더 없이 100% 자바스크립트 + GLSL + Web Audio API 수학적 연산만으로 런타임 생성.
  - Python 빌드 스크립트(`tools/build.py`)를 통해 Three.js r180과 15개 모듈 소스를 단일 `index.html`(약 2.0MB)로 인라인 번들링하여 로컬 `file://` 오프라인 완벽 구동.
- **핵심 모듈 구조**:
  - `src/10_sdf.js`: 순수 수학 Signed Distance Field(SDF) 조각 키트(구체, 타원체, 가변 캡슐, 부드러운 불리언 `smin`) 및 Surface-Nets 메셔.
  - `src/15_tex.js`: 캔버스 및 FBO를 통한 로딩 타임 절차적 텍스처/법선 아틀라스 베이킹.
  - `src/20_sky.js`: 레이마칭(Ray-marching) 적운(Cumulus) 구름층 및 뇌우 셰이더.
  - `src/30_rock.js` / `src/35_arch.js`: 파라메트릭 카르스트 절벽 및 전통 누각/처마/제등 물리 연산.
  - `src/58_dlook.js` / `src/60_dragon.js`: 적룡/백룡 비늘 셰이더, 척추 스플라인 궤적 충돌 시퀀스.
  - `src/85_audio.js`: Web Worker 백그라운드 스레드에서 수학 함수로 합성된 국악 스코어 및 굉음 스트리밍.

### (2) 키링의 실사용 주관적 평가
- **잘한점**:
  1. 완전한 에셋 제로(Zero-Asset) 극한 경량화로 오프라인(`file://`) 60fps 구동 달성.
  2. 결정론적 시간 함수(Deterministic Film Time) 설계로 임의 프레임 독립 렌더링 및 디버깅 가능.
- **잘못한점 / 아쉬운점**:
  1. 소프트웨어 WebGL(CPU 에뮬레이션) 환경에서 `painting the sky` 레이마칭 베이킹 초기 지연 발생.
  2. 90초 고정 카메라 궤도로 인한 자유 인터랙티브 관찰(OrbitControls) 부재.
- **개선점**:
  1. GPU 하드웨어 사양별 계층적 LOD 베이킹 프리셋(Fast Bake) 제공.
  2. SDF 생성 메쉬의 바이너리 glTF/GLB 실시간 추출 브리지 구축.

### (3) HMYS 5대 영역 비즈니스 확장 아이디어 [제안]
- **3-1 H (Healthcare)**: 절차적 해부학 3D 시각화 엔진 (CT/MRI 없이 모바일 브라우저 0바이트 인체 척추/장기 실시간 시뮬레이션)
- **3-2 M (Manufacturing)**: 공장 설비 및 배관 디지털 트윈 (CAD 무거운 파일 대신 매개변수로 대역폭 극제한 현장 점검)
- **3-3 Y (Youth/Edu)**: 코딩으로 배우는 기하학 3D 수학 시뮬레이터 (smin, sphere 등 기초 수식 기반 초경량 그래픽 코딩 교육)
- **3-4 S (Senior)**: 저사양 실버 기기 맞춤형 전통 문화재 3D 감상실 (다운로드 지연 없이 국보급 건축물 60fps 감상)
- **3-5 SNS (Social Media)**: 단일 HTML 링크 3D 인터랙티브 카드 (1MB 미만 링크로 브라우저 즉시 3D 공간 연출)

### (4) 연동 웹/앱 실사용 심층 분석
- 라이브 데모 구동 및 `stills/` 고해상도 무손실 스틸컷 4종 매핑 검증 완료:
  - 캡처 1: 카르스트 협곡과 적룡 서식 씬 (파라메트릭 암벽 절벽과 전통 전각)
  - 캡처 2: 적룡 두상 클로즈업 (SDF 조각 및 비늘 셰이더, 동적 수염)
  - 캡처 3: 화염 브레스 및 절차적 FX 볼륨 (볼류메트릭 조명 방출)
  - 캡처 4: 폭풍 구름 속 백룡 격돌 결투 씬 (레이마칭 구름층 및 척추 스플라인 충돌)

### (5) 사용자 관점 추가 개선 요구 아이템
- REQ-01: 명시적 오디오 컨트롤 UI 오버레이 (음소거/볼륨 슬라이더 및 Seekbar)
- REQ-02: 스페이스바 일시정지 시 자유 궤도 카메라(Free Orbit) 모드 전환
- REQ-03: 단일 GLTF/GLB 파일 내보내기(Export) 스크립트 제공
- REQ-04: 모바일 터치 제스처 최적화 및 뷰포트 자이로스코프 연동

### (6) 웹사용 추가 고려 가능한 Deep HMYS 상상력 발전소
- Deep Idea 1: Prompt-to-SDF 텍스트 프롬프트 기반 3D 메쉬 자동 합성기
- Deep Idea 2: HMYS `block_example` 도심 블록 자동 절차화 셰이더 연계
- Deep Idea 3: Zero-Cost 클라우드 렌더링 대체 웹 네이티브 시네마틱 엔진
