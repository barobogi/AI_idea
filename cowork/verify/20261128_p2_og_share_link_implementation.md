# P2. OG·공유 링크 구현안 (만복 @PO 과제, 기한 2026-11-28 18:00 KST)

작성: Fo (for barobogi) <barobogi79@fo.wajo.ai> · 2026-11-28

## 3줄 요약
1. 실측(2026-11-28): 포털(index.html)과 26개 구 페이지(b/11110/index.html 등)의 head에 OG 태그와 meta description이 전무하다. og:image로 쓸 이미지 파일도 저장소에 없다.
2. 구현안: 구 단위 고정 OG 태그 1세트(og:title·og:description·og:url·og:image 1200×630·twitter:card)를 페이지별로 넣고, 공유 버튼은 Web Share API + URL 복사 폴백으로 구현한다. og:image는 새로 제작해 /assets/에 둔다.
3. 주의: 두 페이지 모두 robots noindex,nofollow가 걸려 있다. 일부 공유 크롤러가 robots를 존중할 수 있어(?) 12/6 오픈 시점의 robots 정책 변경과 함께 결정해야 한다.

## 1. 현재 상태 실측 (2026-11-28 KST, GitHub API)
- 포털 index.html: charset·viewport·robots(noindex, nofollow)·title("대한민국 3D 지도 · 비공개 베타")만 있음. OG 태그 0건, meta description 없음.
- 구 페이지 b/11110/index.html(종로구): robots(noindex, nofollow)·viewport·manifest·theme-color·PWA 관련 메타·title("서울특별시 종로구 v3 · block.json 6탭")만 있음. OG 태그 0건, meta description 없음. title에 내부 용어(block.json 6탭)가 포함되어 공유 카드 문구로는 부적합.
- b/ 디렉터리에 구 페이지 26곳(11110~28185). 저장소에 이미지 파일 없음 → og:image 파일 신규 제작 필요.
- 포털은 모바일 UA를 b/11110/로 자동 라우팅(DEF-001).

## 2. 설계 원칙
1. 구 단위 고정 OG: 크롤러는 JS를 실행하지 않으므로 D1 딥링크(#v=1&b=블록&t=시각)처럼 해시·쿼리로 바뀌는 값은 OG에 반영될 수 없다. 해시는 아예 크롤러에 안 보인다. 따라서 OG는 구 단위 고정값으로 두는 것이 현실적이다(제안).
2. 절대 URL 필수: og:url·og:image는 반드시 https://로 시작하는 절대 주소. 상대 경로는 플랫폼에 따라 무시된다.
3. 문구는 UX 문구 4종과 통일: og:title·og:description은 피망 PR #13346(UX 문구 4종)의 검증 문구 체계(해요체)와 같은 말투를 쓴다. 아래 예시 문구는 자리 표시값이며 만복 검수 확정 문구로 교체해 적용한다.
4. robots와의 관계: 현재 모든 페이지에 noindex, nofollow. 이는 검색 엔진용 지시이지만 공유 크롤러도 robots를 존중하는 경우가 있어(?) 오픈 전 카드가 안 만들어질 수 있다. 12/6 robots 정책(인덱스 허용 여부) 결정 시 함께 다룬다.

## 3. 구현 스니펫 (제안안, 적용은 운영자 결정)
구 페이지(b/<코드>/index.html)의 `<head>` 시작 직후에 삽입:

```html
<meta property="og:type" content="website">
<meta property="og:site_name" content="대한민국 3D 지도">
<meta property="og:title" content="서울 종로구 · 대한민국 3D 지도">
<meta property="og:description" content="종로구 건물을 3D로 둘러보세요.">
<meta property="og:url" content="https://barobogi.github.io/korea-3d-map-site/b/11110/">
<meta property="og:image" content="https://barobogi.github.io/korea-3d-map-site/assets/og_default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="대한민국 3D 지도 로고 이미지">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image">
```

포털(index.html)은 og:title·og:description만 서비스 소개용으로 바꿔 동일 세트를 쓴다. 구 이름은 템플릿의 유일한 치환값이므로 페이지별 고정 문구를 만들어 넣는다.

### og:image 제작 요건 (제안)
- 1200×630px, JPG 또는 PNG, 1MB 이하 권장(플랫폼별 상한은 카톡 5MB 등으로 알려져 있으나 개별 확인 필요(?))
- 콘텐츠: 텍스트 최소화, 서비스 로고 또는 3D 도시 실루엣. 실제 제작은 별도 과제로 제안(?)
- 경로: /assets/og_default.png (저장소에 assets 디렉터리 신규)

### 일괄 적용 방법 (제안)
수동 27개 파일 편집 대신, 정적 빌드 스크립트 1개(Python)로 26곳+포털 head를 주입·갱신한다. 구 코드→구 이름 매핑은 data/의 지역 데이터에서 읽어 자동 생성할 수 있다. 스크립트는 '실행 코드(.py/.sh)는 받지 않는다'는 CONTRIBUTING 규칙에 따라 운영자가 로컬에서 1회 실행하는 형태로 제안한다. 스니펫:

```python
# scripts/inject_og.py (운영자 로컬 1회 실행용 예시, 저장소 푸시 금지)
import json, pathlib
MAPPING = json.load(open("data/region_names.json"))  # {"11110": "종로구", ...} 운영자가 준비
TPL = pathlib.Path("templates/og_head.html").read_text()  # 위 스니펫을 {{CODE}}·{{NAME}} 치환 형태로
for code, name in MAPPING.items():
    p = pathlib.Path(f"b/{code}/index.html")
    html = p.read_text()
    head = TPL.replace("{{CODE}}", str(code)).replace("{{NAME}}", name)
    if 'property="og:title"' not in html:
        html = html.replace("<head>", "<head>\n" + head, 1)
        p.write_text(html)
```

(매핑 파일 위치·형식은 운영자 확인 필요(?) — 이 문서에서는 예시로 둔다.)

### 공유 링크(버튼) 구현 (제안)
- 모바일: `navigator.share({title, text, url})` (Web Share API) 1개 버튼으로 카톡·메시지·SNS 공유를 OS 시트에 맡긴다. 미지원 브라우저는 폴백으로 URL 복사.
- 데스크톱: URL 복사 버튼(클립보드) + 완료 토스트.
- 공유되는 URL은 og:url과 같은 구 단위 주소여야 카드가 일치한다. 딥링크 파라미터는 공유 직후 사용자가 붙여 쓰는 형태로 남긴다(D1 설계와 연계).

## 4. 적용 후 검증 방법
1. 페이스북 Sharing Debugger 등 OG 검사 도구로 카드 미리보기 확인(도구 접근 조건은 개별 확인 필요(?))
2. 카카오톡은 공유 캐시가 남아 변경이 늦게 반영될 수 있다(?) — 실기기 전송 테스트로 확인
3. 적용 커밋 1건 + 각 플랫폼 미리보기 스크린샷을 PR에 남겨 만복 검수 재현성 확보

## 5. 작업 분할 (제안)
- 운영자 확정 필요: og:image 디자인·제작, og:title/description 최종 문구(UX 문구 4종 확정 문구 연계), robots 정책(12/6 시점)
- 이 문서의 스니펫은 그대로 복사해 쓸 수 있는 형태. 적용 PR은 운영자 또는 4총사 몫으로 제안(?)

## 6. (?) 미확인·판단 보류
- 공유 크롤러별 robots noindex 존중 여부: 플랫폼별 개별 확인 필요(?)
- og:image 플랫폼별 상한·권장 사양: 개별 확인 필요(?)
- 카카오톡 캐시 갱신 방법: 확인 필요(?)
- OG 검사 도구의 접근 조건(로그인 등): 개별 확인 필요(?)
- 매핑 데이터의 실제 위치·형식(data/ 내 지역명 데이터): 저장소 내 확인 필요(?)

## 7. 근거·확인일
- 실측: GitHub API로 index.html·b/11110/index.html head 원문·b/ 디렉터리 목록·루트 파일 목록 확인 (2026-11-28 06:35~06:42 KST)
- 만복 주소 확정: 세톡 id 554 (약관/방침/제보/홈 경로)
- UX 문구 연계: 세톡 id 579 (만복 결정), 피망 PR #13346 (head 0b4e20a)
- 이 문서는 새 파일만 추가하며 기존 파일을 수정하지 않는다. 실제 저장소(korea-3d-map-site)에는 적용하지 않았다.
