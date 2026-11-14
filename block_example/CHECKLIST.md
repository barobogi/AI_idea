# 블록 제작 체크리스트 (측정기 번호와 같음)

제출 전에 위에서부터 하나씩 확인한다. 측정기가 자동으로 보는 것은 "자동"으로 표시했다.

## 1. 파일 (자동 F01~F03)
- [ ] 폴더명 `<5자리코드>_B<번호>_<이름>`
- [ ] 4종만 있음: `model_lod3.gltf`, `model_lod2.gltf`, `texture_atlas.webp`, `block_manifest.json`
- [ ] 스크립트·소스 파일 없음 (.py .sh .js .html .blend 등)

## 2. 모델 품질 (자동 Q01~Q10)
- [ ] Q01 LOD3 삼각형 10,000~14,000
- [ ] Q02 LOD2 삼각형 1,200~1,800
- [ ] Q03 LOD3 768,000B 이하 / Q04 LOD2 71,680B 이하
- [ ] Q05 접지: LOD3·LOD2 최저점 Y=0.000(±0.005), **실제 정점 데이터로** 확인. 사각 바닥판 없음
- [ ] Q06 인덱스 uint16, 법선 버퍼 없음
- [ ] Q07 텍스처 참조 `texture_atlas.webp` 하나, 버퍼 내장
- [ ] Q08 1024×1024 WebP / Q09 102,400B 이하
- [ ] Q10 패키지 합계 972,800B 이하
- [ ] Q11 재질 11종 / Q12 UV uint16 normalized / Q13 전 노드 name / Q14 앵커 night_light 4 + hotspot 5
- [ ] **Q15 접근자 min/max가 실제 데이터와 일치 / Q16 scene.nodes 유효**
- [ ] **Khronos 검증기: WebP MIME 확장 미선언 2건 외 오류 0** (`node tools/khronos_validate.mjs`, LOD3·LOD2 모두)
- [ ] 뷰어(three.js 등)에서 LOD3·LOD2 둘 다 열림 확인, 렌더 캡처 3장(`{슬롯}_front.png`, `_bird.png`, `_eye.png`, 1400×980)을 `evidence/`에 저장

## 3. 시각 체크리스트 (제미나이가 8항목으로 판정, 제출 전 자기 점검)
수치로 재는 것(접지, 접근자, 재질 수 등)은 측정기가 하고, 여기서는 **눈으로 본 결과**만 판정한다. 통과/전체 분수로 채점한다.
- [ ] V1 대상 건물을 알아볼 수 있다(공식 사진·자료의 형태와 비례)
- [ ] V2 핵심 부재가 빠지지 않았다(출입구, 지붕, 탑, 아치 등)
- [ ] V3 지붕·입면 비례와 층수가 제원과 맞다
- [ ] V4 공중에 뜬 부재, 겹침, 뚫림, 뒤집힌 면이 없다
- [ ] V5 단색 상자화나 텍스처 깨짐이 없다(아틀라스가 정상으로 입혀짐)
- [ ] V6 LOD2가 LOD3의 윤곽을 유지한다(전환 시 튀지 않음)
- [ ] V7 글자·간판 깨짐, 워터마크, 제3자 이미지·화면이 없다
- [ ] V8 눈높이(보행자) 조망이 자연스럽고, 표준 예제와 같은 지도에 놓아도 이질감이 없다(재질, 색 계열, 바닥 처리)

## 4. 매니페스트 (자동 M01~M07)
- [ ] M01 필수 키: `task_slot_id`, `block_id`, `name`, `category`, `district`, `road_address`, `coordinates`, `orientation_deg`, `reference_url`, `verified_at`, `verification_evidence`, `lod_budget`, `files`, `package_total_bytes`
- [ ] M02 좌표는 경도, 위도 순서로 한반도 안
- [ ] M03 공식 출처(go.kr/or.kr 등) 1건 이상
- [ ] M04 열람 시각은 KST(`+09:00`)
- [ ] M05 전화번호·키·서명 URL 없음
- [ ] M06 슬롯 번호가 폴더명과 일치
- [ ] M08 `lod_switch_distance` 200, `ground.mode`=snap_to_terrain, `origin_y_m`=0, ASL 필드 없음, `generation.execution_code_in_package`=false
- [ ] M09 `references` 4건 이상
- [ ] M07 "V-World 풋프린트 참조" 같은 문구 없음, 공공누리 2유형을 "출처표시"라고 쓰지 않음

## 5. 사실·출처 (사람이 확인)
- [ ] 씨앗 좌표·설명을 공식 출처로 확인하고 다른 점을 REPORT 3절에 적음
- [ ] 높이·층수·치수·준공 연도마다 출처와 열람 시각이 있다
- [ ] 위키·블로그·지도 앱만 근거로 삼은 수치가 없다
- [ ] 확인하지 못한 값은 "미확인"으로 적었고 지어내지 않았다
- [ ] 이용 조건(공공누리 유형, ODbL 등)을 정확히 적었다

## 6. 시간 기록 (자동 T01 + 사람 확인)
- [ ] 읽기 시작 전에 `timing/STARTED.md`를 커밋·푸시했다
- [ ] `GUIDE_3TEAM_BLOCK_TECH_20261114.md` 전문을 읽고 `timing/READ_CONFIRM.md`(10문항)를 커밋·푸시했다(이 시각이 제작 시작 기준)
- [ ] 블록마다 `timing_<슬롯>.json`을 채웠다(필수 키 전부, `read_min`·`wall_clock_min` 구분)
- [ ] 처음 통과까지 시간, 측정기 실행 횟수, 중단·재개, 한도 체계를 적었다
- [ ] 보고서의 시간이 timing 파일과 같다

## 7. 제출
- [ ] 블록마다 `reports/<폴더명>_check.json`이 있다(제출 직전 실행값, 블록 폴더 안이 아님)
- [ ] `REPORT.md`를 채웠다
- [ ] PR 본문 표에 삼각형·용량·접지·출처 URL이 있다(3AI 자동 점검용)
- [ ] 자기 폴더 밖 파일을 건드리지 않았다
