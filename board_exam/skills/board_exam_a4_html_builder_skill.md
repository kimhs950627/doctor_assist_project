---
name: board_exam_a4_html_builder
description: 가정의학과 전문의 시험 대비용 docx 요약본을 A4 인쇄 최적화 HTML(단원별, 예 im_cv_a4.html)로 변환하는 절차. 단원명(순환기, 소화기, 호흡기 등)만 지정하면 이 절차를 그대로 적용해 결과물을 만든다.
---

## 목적

프로젝트 파일 중 "N권 ○○.docx" 안의 특정 단원(예: 순환기, 소화기, 호흡기, 내분비 등) 기출 정리 내용을,
A4 인쇄 시 잘리지 않고 클릭 목차가 있는 HTML로 재구성함. 원문은 최대한 보존함.
파일명 규칙: `im_<단원약칭>.html` (예: im_cv.html, im_gi.html) → 인쇄용 버전은 `im_<단원약칭>_a4.html`.

## 트리거

사용자가 "○○ 단원 A4 html 만들어줘" / "○○ 인쇄용 html로 재작성" 같은 요청을 하면 이 skill을 따른다.
Task A(시험 통과) 계열 작업이므로 family_medicine_exam_note_builder_skill.md와 함께 참조함.
말투는 caveman 원칙(~음, ~함체)을 적용하되, 환자용 자료가 아니므로 적용 대상임.

## 절차

### 1단계 — 원문 확보 및 구조 파악
- file_explore로 해당 단원이 들어있는 docx(N권 ○○.docx)를 찾아 원문 텍스트를 읽음.
- docx 안의 이미지(그림, 표, EKG 등)를 별도로 추출해야 함 → bash에서 `unzip -o "*.docx" -d tmp_extract` 형태로 압축 풀어서 `word/media/imageN.png` 경로에서 이미지 원본을 가져옴.
- 추출한 이미지는 `board_exam/assets/<단원약칭>_media/`에 저장함 (예: cv_media, gi_media).
- docx 텍스트에서 각 이미지가 어떤 소제목/문단 아래에 있었는지 대응관계를 기록해둠(원문 배치 참고용, 완전 1:1 복제는 아님).

### 2단계 — HTML 초안 작성 (im_<단원약칭>.html)
- 기존에 만든 im_gi.html / im_cv.html 스타일을 그대로 재사용함 (CSS 톤: 파란 계열 헤더, exam-source 라벨박스, danger-box, note, exam-tip 등).
- 구조: `<div class="page cover">` 표지 1장 + 이후 `<div class="page">` 여러 장, 각 장 안에 `<h2 id="...">소단원명</h2>` 로 섹션 구분.
- 원문 표/분류/약물명/기전은 원문 표현을 최대한 보존(볼드, 밑줄, 강조 표시 등도 최대한 살림).
- 이미지는 `<figure><img src="assets/<단원약칭>_media/imageN.png" alt="..."><figcaption>...</figcaption></figure>` 형태로 삽입. 관련 있는 그림 2개는 `.img-row`로 나란히 배치.

### 3단계 — 이미지 base64 인라인화
- 배포/공유 시 이미지 경로가 깨지는 문제를 막기 위해, 완성된 HTML의 `src="assets/.../imageN.png"` 전부를 base64 data URI로 치환함.
- Python으로 처리: 정규식 `src="(assets/[^"]+)"` 매칭 → 해당 파일을 base64 인코딩 → `src="data:image/png;base64,..."`로 교체.
- 이 단계는 im_<단원약칭>.html 자체에 적용(원본 파일 갱신).

### 4단계 — A4 인쇄 최적화 버전 제작 (im_<단원약칭>_a4.html)
이 단계에서 다음 3가지를 반드시 처리함:

1. **클릭 목차 페이지**
   - 원본의 `<div class="page cover">`를 표지+목차 통합 페이지로 교체.
   - `<h2 id="...">` 전체를 정규식으로 스캔해서 `<ul class="toc-box"><li><a href="#id">제목</a></li>...</ul>` 생성.
   - 목차 페이지는 `page-break-after:always`로 항상 첫 페이지로 고정.

2. **이미지 크기·불필요 이미지 정리**
   - 사용자가 지정한 "없어도 되는" 이미지(예: 해부도처럼 시험 포인트와 무관한 그림)는 정규식으로 figure 블록 자체를 삭제.
   - 남긴 이미지는 `figure img{max-width:52%;max-height:60mm;display:block;margin:0 auto}`로 축소해서 텍스트 대비 과도하게 크지 않게 함.
   - `.img-row` 안 이미지는 `max-height:52mm`로 별도 조정(2열 배치이므로 개별 이미지는 더 작게).

3. **인쇄 시 의미론적 비분절 처리**
   - 기존 `<div class="page">` 고정 페이지 분할(강제 페이지 분리)을 제거하고, 전체를 하나의 연속 흐름(`<div class="wrap">`)으로 바꿈. 즉, 컨텐츠 내부를 감싸던 div wrapper를 벗겨내되 태그 밸런스(open/close 개수)를 반드시 재검증함.
   - `break-inside:avoid` / `page-break-inside:avoid`를 아래 요소에 적용:
     - `table`, `figure`, `.img-row`
     - `.danger-box`, `.note`, `.exam-tip`, `.topic-block`
   - `h2`, `h4`에는 `break-after:avoid`를 적용해서 제목만 페이지 끝에 남고 본문이 다음 페이지로 넘어가는 상황을 방지함.
   - `.footer`(페이지 번호 등 고정 요소)는 연속 흐름에서는 의미 없으므로 제거함.

### 5단계 — 구조 검증 (필수)
- `html.parser.HTMLParser`로 open/close 태그 짝이 맞는지 검증하는 스크립트를 항상 실행함(사람이 눈으로 div 개수 세는 것보다 신뢰도 높음).
- 검증 실패 시 어디서 태그가 어긋났는지 stack 잔여물로 확인 후 수동 보정.

### 6단계 — 저장 위치 및 파일명
- `board_exam/im_<단원약칭>.html` (base64 인라인 원본)
- `board_exam/im_<단원약칭>_a4.html` (목차+인쇄 최적화 버전)
- 이미지 원본은 `board_exam/assets/<단원약칭>_media/imageN.png`로 보관(재사용/재편집 대비, git에도 커밋).

### 7단계 — Git 커밋 및 push (자동 규칙)
- 코드/HTML 파일을 만들거나 수정했으면 별도 지시 없이 항상:
  1. `git config --global user.name kimhs950627` / `user.email kimhs950627@knou.ac.kr`
  2. 파일 저장
  3. `git remote set-url origin https://kimhs950627:<PAT>@github.com/kimhs950627/doctor_assist_project.git`로 PAT 임베드 후 `git add` → `git commit` → `git push`
  4. push 성공 확인 후 `git remote set-url origin https://github.com/kimhs950627/doctor_assist_project.git`로 원복(PAT 노출 방지)
  5. 403 에러 발생 시 즉시 재시도(1~2회, 몇 초 대기 후) — GitHub 쪽 일시적 오류인 경우가 많음.
  6. commit ID, branch, 변경 파일 목록을 사용자에게 보고함. PAT 전체 값은 절대 노출하지 않음.

## 재사용 시 입력값

사용자가 아래만 지정하면 이 skill을 바로 적용 가능함:
- 단원명 (예: 순환기, 소화기, 호흡기, 내분비, 신장/요로생식 등)
- (선택) 제외할 이미지 지정 (예: "해부도는 빼라")
- (선택) 목차 세분화 수준 (h2만 vs h2+h4까지)

## 참고 스타일 원칙 (caveman)

이 skill로 만드는 산출물은 시험공부용 자료(Task A)이므로, 작업 중 사고 과정과 사용자 보고는 caveman 말투(~음, ~함체)를 씀.
단, HTML 안의 실제 의학 내용(시험 정리 문구)은 원문 보존이 원칙이라 caveman체로 바꾸지 않음.
