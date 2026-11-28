# P16 검토서: 모바일 브라우저에서 3D 지도가 안 죽는 조건 (공식 문서 근거)

- 작성: Fo (for barobogi) <barobogi79@fo.wajo.ai>
- 만복 배정: 세톡 id 765 (2026-11-28 18:05 KST), 기한 2026-11-29 21:00
- 목적: 12/6 전국 공개 때 폰에서 검은 화면·튕김이 없게 하려면 모바일 WebGL의 메모리·텍스처 한계를 문서 근거로 정리한다(광진 페이지 REQ171 때 검은 화면 사례).
- 방법: three.js 공식 문서, Khronos glTF 확장·Basis Universal, MDN WebGL 문서 열람만. 기기 실측, 로그인·결제 없음. 우열 단정 없음.
- 열람 시각: 2026-11-28 17:4x~18:1x KST

## 0. 요약: 문서 근거가 있는 "안 죽는 조건"

1. VRAM을 보수적으로 예산화하고 webglcontextlost 이벤트를 반드시 처리한다(MDN: GPU 메모리 부족이 context lost 발화 이유 중 하나).
2. 텍스처를 압축 텍스처(KTX2/Basis Universal)로 쓴다 — GPU 메모리 축소 + 샘플링 빠름(모바일 대역폭 절약).
3. 쓸모없어진 텍스처·지오메트리는 GC 대기 없이 즉시 dispose한다(three.js 각 객체 dispose 문서).
4. InstancedMesh·mergeGeometries로 드로우콜 수를 줄인다.
5. 텍스처 크기는 renderer.capabilities.maxTextureSize 이하로 맞춘다.
6. WebGL 2에서는 texStorage로 mip 체인 할당을 직접 제어한다(MDN: 드라이버가 mip 체인 전체를 무조건 할당해 정사각 텍스처 기준 +33% 메모리).
7. 품질(텍스처 해상도·지오메트리 레벨) 옵션을 둔다(MDN 권고).

## 1. 모바일 GPU 텍스처 메모리 계산법과 KTX2가 줄이는 이유

- 텍셀 크기: MDN texImage2D의 입력 바이트 표에서 RGBA/UNSIGNED_BYTE는 "Input bytes per pixel 4"다(RGB/UNSIGNED_BYTE 3, RGBA/UNSIGNED_SHORT_4_4_4_4 2 등). 즉 RGBA 8비트 텍스처 1장은 가로×세로×4바이트. (만복 프롬프트의 "해상도×4바이트"는 이 표와 일치.)
- 밉맵: MDN best practices — 일부 드라이버는 mip 체인 전체를 무조건 할당한다("+33% memory for square textures!"). 정사각 텍스처에서 밉 체인 총량은 원본의 1/3 더하기(1/4+1/16+…)라는 산술과 문서 명시 수치가 일치한다. three.js Texture.generateMipmaps는 기본 true라 밉 체인이 기본 생성된다.
- 깊이·스텐실 함정: MDN best practices — 깊이·스텐실은 많은 기기에서 실제로 32bpp로 올려 저장된다(DEPTH_COMPONENT16이 32비트 포맷으로 저장될 수 있어 작은 포맷이 메모리를 아끼지 못할 수 있음). 스텐실 버퍼는 쓸 때만 요청하라.
- 압축 텍스처가 줄이는 이유: MDN best practices — "GPU compressed texture formats are smaller in GPU memory, and are faster to sample from. (This reduces texture memory bandwidth, which is precious on mobile.)" 보편 지원 포맷은 없고, s3tc(데스크톱)·etc1(Android)·pvrtc(iOS) 중 각 기기에 하나는 있다. WebGL 2는 s3tc+etc 조합으로 보편화되고, astc는 더 좋은 품질·압축을 제공한다.
- Basis Universal / KTX2: KHR_texture_basisu(glTF 확장, Ratified) — KTX v2 이미지에 Basis Universal supercompression을 얹어 "more efficient asset transmission and reducing GPU memory footprint"을 이루고 밉 레벨 지정도 가능하다. "At runtime, engines are expected to transcode a universal texture format into some block-compressed texture format supported by the platform." basis_universal README(v2.5) — "rapid transcoding to virtually any compressed GPU texture format", KTX2·.basis·DDS 지원. MDN도 Basis Universal을 "단일 압축 파일로 모든 주요 압축 포맷 지원 + 전송 크기는 JPEG 급"으로 소개한다.
- three.js 쪽: KTX2Loader 소스는 ASTC·BPTC·ETC2/EAC·PVRTC·S3TC(DXT)·RGTC 등 플랫폼 포맷으로 트랜스코딩하고 WorkerPool로 디코딩한다. GLTFLoader 문서의 지원 확장 목록에 KHR_texture_basisu가 있다.
- (?) 포맷별 정량 배율(ASTC/ETC2가 RGBA8 대비 몇 배 작은지)은 개별 확장·포맷 스펙을 이번에 열람하지 않아 수치 확정 불가. 전송 크기와 GPU 메모리 크기는 별개 개념이고(MDN), REQ171 광진 사이트에서 KTX2 사용 여부도 미확인.

## 2. 드로우콜·지오메트리 병합·instancing 권고 (three.js 문서 근거)

- InstancedMesh 문서: "Use this class if you have to render a large number of objects with the same geometry and material(s) but with different world transformations. The usage of 'InstancedMesh' will help you to reduce the number of draw calls and thus improve the overall rendering performance in your application." — 같은 지오메트리·재질을 다른 변환으로 대량 렌더링할 때 인스턴싱.
- BufferGeometryUtils.mergeGeometries(JSDoc): 여러 BufferGeometry를 하나로 병합한다. 모든 지오메트리가 호환 속성(index 유무·속성 이름)을 가져야 하고 실패 시 null을 반환한다.
- GLTFLoader 지원 확장 목록에 EXT_mesh_gpu_instancing이 있다.
- 모니터링: WebGLRenderer.info — "Holds a series of statistical information about the GPU memory and the rendering process. Useful for debugging and monitoring." post-processing 등으로 프레임당 여러 렌더 패스를 돌릴 때 autoReset=false + reset() 패턴이 문서에 있다.
- 업로드 타이밍: WebGLRenderer.initTexture — 첫 렌더 시점의 디코드·GPU 업로드 지연("noticeable lags")을 피하려면 텍스처를 미리 초기화한다.
- MDN 런타임 권고(렌더러 레벨): VAO 첨부 변경(vertexAttribPointer 등)을 피하고 정적 VAO를 재사용하라. three.js 문서에 대응 권고 표기는 없음 (?).

## 3. WebGL 컨텍스트 손실(context lost) 처리

- 이벤트: MDN webglcontextlost — 사용자 에이전트가 드로잉 버퍼 상실을 감지하면 발화한다. WebGLContextEvent 타입, 버블 안 됨, Baseline Widely available(2015-07부터), 스펙 참조는 WebGL Specification 5.15.2. 짝인 webglcontextrestored 이벤트도 있다.
- MDN best practices: "Handle webglcontextlost events, which can be emitted when the GPU runs out of memory, among other reasons." — GPU 메모리 부족이 발화 이유 중 하나로 명시. "The only errors a well-formed page generates are OUT_OF_MEMORY and CONTEXT_LOST_WEBGL."
- 테스트·정리 도구: MDN WEBGL_lose_context — loseContext()/restoreContext()로 상실·복구를 시뮬레이션한다(WebGL1·2 모두, Web Worker 포함, Baseline 2018-04). WebGLRenderingContext.isContextLost()로 상태 확인.
- three.js: WebGLRenderer.dispose()는 "Frees the GPU-related resources allocated by this instance"; forceContextLoss()/forceContextRestore()가 있고 forceContextLoss는 "requires support for the WEBGL_lose_context extension"이라고 문서에 명시돼 있다.
- 스펙 원문: WebGL 스펙 저장소(KhronosGroup/WebGL specs/latest/2.0)에서 "Each WebGLRenderingContext and WebGL2RenderingContext has a webgl context lost flag" 정의 일부를 열람했다. registry.khronos.org 페이지는 이번 열람에서 본문을 반환하지 않았다 (?).
- 긴장점: three.js 문서 원문에는 context lost 이벤트 수신 후 렌더러를 어떻게 복구하는지(재생성 여부, 자동 복구 여부) 표기가 없다 (?) — 복구 절차는 앱 레벨 구현 사안으로 문서 근거 밖이다.

## 4. dispose와 메모리 정리 (three.js 문서 근거)

- WebGLRenderer.dispose() / Texture.dispose() / BufferGeometry.dispose(): 셋 모두 "Frees the GPU-related resources allocated by this instance. Call this method whenever this instance is no longer used in your app."
- Texture.dispose 주의: 렌더 타깃에 속한 텍스처는 렌더 타깃이 관리하므로 RenderTarget.dispose()를 써야 한다.
- GLTFLoader 문서: "image bitmaps are not automatically GC-collected when they are no longer referenced, and they require special handling during the disposal process" — 블록을 갈아끼울 때 이미지 비트맵까지 수동 정리가 필요하다.
- MDN best practices: "Delete objects eagerly" — API 레벨의 delete는 핸들만 놓아줄 뿐, 구현 내부에서 쓰이지 않게 될 때 실제로 해제된다. "Lose contexts eagerly" — 더는 필요 없는 컨텍스트는 WEBGL_lose_context로 능동적으로 놓아주되, 페이지 이탈 시 unload 핸들러로 할 필요는 없다.

## 5. 미확인 (?) 목록

1. 모바일 실제 VRAM 한계와 "안 죽는" 구체 수치는 기기 실측 없이 문서로 확인 불가(MDN: 비디오 메모리 최대량 조회 API는 이식성 문제로 제공되지 않음).
2. ASTC/ETC2 등 포맷별 압축 배율 정량값 미확인(개별 포맷 스펙 미열람).
3. context lost 이후 three.js 렌더러의 정확한 복구 절차(재생성 여부) 문서 표기 없음.
4. Khronos WebGL 스펙 registry 페이지 본문 미반환 — 스펙 정의는 저장소 원문 일부와 MDN으로 대체 열람.
5. REQ171 광진 검은 화면의 정확 원인(텍스처 언더런인지 컨텍스트 lost인지)은 미판명 — 본 문서는 문서 근거만 다룬다.
6. 요청 사이트(glTF 블록)에서 현재 KTX2·instancing 사용 여부 미확인.

## 6. 12/6 전국 공개와의 연결

- P15(#187)에서 현재 공개 구조는 three.js glTF 블록(만복 열람, 세톡 id 765)으로 정정됐다. 본 문서의 조건은 그 구조 기준이다.
- KTX2 도입, dispose 체계, context lost 처리, 품질 옵션은 안티 구현 지시서(안티 PR) 단계에서 실측과 함께 설계되어야 한다. 본 문서는 그때 인용할 문서 근거 장이다.

## 7. 문서 목록 (열람 시각 2026-11-28 17:4x~18:1x KST)

- MDN WebGL best practices: https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices
- MDN WEBGL_lose_context: https://developer.mozilla.org/en-US/docs/Web/API/WEBGL_lose_context
- MDN webglcontextlost event: https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/webglcontextlost_event
- MDN texImage2D(입력 바이트/픽셀 표): https://developer.mozilla.org/en-US/docs/Web/API/WebGLRenderingContext/texImage2D
- three.js docs(WebGLRenderer·Texture·BufferGeometry·InstancedMesh·GLTFLoader, dev 브랜치 docs/pages/): https://github.com/mrdoob/three.js/tree/dev/docs/pages
- three.js 소스 JSDoc: examples/jsm/loaders/KTX2Loader.js, examples/jsm/utils/BufferGeometryUtils.js
- glTF KHR_texture_basisu: https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_texture_basisu/README.md
- basis_universal README(v2.5): https://github.com/BinomialLLC/basis_universal/blob/master/README.md
- WebGL 스펙 저장소(KhronosGroup/WebGL, specs/latest/2.0): https://github.com/KhronosGroup/WebGL/tree/main/specs/latest/2.0
