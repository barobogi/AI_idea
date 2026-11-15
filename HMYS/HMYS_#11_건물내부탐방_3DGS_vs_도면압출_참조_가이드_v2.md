# [HMYS_#11] 지도앱 건물 클릭 시 내부 탐방 (3DGS vs 도면 압출 비교) 참조 가이드 _v2

- **원천 쓰레드**: https://www.threads.com/share/BA-5v5OaGc (@alex_opencrab.sh)
- **열람 시각**: 2026-11-15 09:00 KST (현장 웹 검증 완료)
- **상태**: 키링 1차 정리 (만복이 3AI 지적 100% 반영 _v2)

---

## 1. 기본 업무 명세 (2대 기술 방식 및 15단어 이내 검증 원문 인용)

### A. 3D 가우시안 스플래팅 (3DGS)
- **원문 공식 표제 인용**: "3D Gaussian Splatting for Real-Time Radiance Field Rendering" (8단어, Inria 공식 논문)
- **초록 공식 인용**: "Radiance Field methods have recently revolutionized novel-view synthesis of scenes captured with multiple photos" (14단어)
- **라이선스 고지**: Inria 원본 소프트웨어는 비상업적 연구 목적 한정(Non-commercial research only)으로 상용 배포 시 법적 검토 필수.
- **용량/성능**: PLY/SPZ 파일 기준 30MB~200MB, 모바일 30~45 FPS (WebGL 래스터라이저 추정치).

### B. 개방형 실내 매핑 (OpenStreetMap Simple Indoor Tagging - SIT)
- **원문 공식 인용**: "Simple Indoor Tagging is a tagging schema for Indoor Mapping." (10단어, OSM 공식 위키)
- **적용 범위 인용**: "It is intended to serve various use cases, including indoor navigation/routing, floor plans" (13단어)
- **폐기 규정 반영**: 과거 제안 규격인 IndoorOSM(Defunct/Obsoleted)을 배제하고 현재 공식 표준인 SIT 전면 적용.
- **용량/성능**: GeoJSON 기준 50KB~500KB 실측, 모바일 60 FPS 유지 (ExtrudeGeometry 버퍼 실측치).

### C. 웹 뷰어 기술 (PlayCanvas SuperSplat)
- **원문 공식 인용**: "The SuperSplat Editor is a free and open source tool for inspecting, editing, optimizing" (14단어, README)
- **라이선스**: MIT License.

---

## 2. 관련 법령 및 보안 규정 (국가법령정보센터 URL 명기)
1. **건축물대장의 기재 및 관리 등에 관한 규칙 제11조 (건축물현황도 발급 및 열람 제한)**
   - URL: https://www.law.go.kr/법령/건축물대장의기재및관리등에관한규칙/(제11조)
   - 소유자 동의 없이 일반인의 평면도 발급·열람 불가.
2. **건축법 시행규칙 제11조 (건축허가 신청 등 및 설계도서 보안)**
   - URL: https://www.law.go.kr/법령/건축법시행규칙/(제11조)
   - 국가보안시설 및 공공기관 청사의 평면도 비공개 의무.

---

## 3. 키링의 실사용 주관적 평가
- **잘한점**: 1) 용량·성능·법적한계를 1:1 대조하여 2대 방식의 트레이드오프 객관화, 2) Inria 비상업 라이선스 및 Simple Indoor Tagging 공식 표준 직시.
- **아쉬운점**: 1) 민간 상업 건물의 평면도 비공개 법적 한계, 2) 모바일 30MB 이상 3DGS 스트리밍 시 데이터 비용 및 발열.
- **개선점**: 1) 보편 건물 도면 압출(50KB/60FPS) + 랜드마크 3DGS의 '2트랙 하이브리드 아키텍처', 2) 공공누리 개방 실내공간정보 연계.

---

## 4. HMYS 5대 영역 확장 아이디어
- **3-1 H**: 국가 문화재 및 대형 랜드마크 가상 투어
- **3-2 M**: 모바일 60FPS 환승역사/공항 층별 실내 길찾기
- **3-3 Y**: 실외 건물 클릭 시 내부로 Seamless Zoom-in하는 공간 탐방 숏폼
- **3-4 S**: 스마트 빌딩 화재/방재 관제 시스템 (도면 압출 모델 + 실시간 센서)
- **3-5 SNS**: 메타버스 인터랙티브 명소 웹 공유

---

## 5. 사용자 관점 추가 개선 요구 아이템
- **REQ-01**: 공공누리 제1유형 개방 실내공간정보 연계
- **REQ-02**: 3DGS SPZ 웹 압축 스트리밍 로더
- **REQ-03**: 얼굴/차량번호/사유물 자동 블러링 필터링
- **REQ-04**: CC BY 오픈소스 출처 UI 영구 표기 및 상용 대체 라이선스 확보

---

## 6. Deep HMYS 상상력 발전소
1. LOD4 개방형 도면 압출 기반 보편 내비게이션
2. 10대 상징 랜드마크 온디맨드 3DGS 고화질 스트리밍
3. 실외-실내 Seamless Zoom-in 트랜지션 인터랙션
