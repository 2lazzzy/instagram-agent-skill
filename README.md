# Instagram Agent Skills

[English](README.en.md) | **한국어**

인스타그램 콘텐츠를 기획하고, 초안을 만들고, 게시 후 성과를 돌아보는 **Claude Code 스킬 14개**입니다.
릴스 대본, 피드 캐러셀, 설명글, 스토리, 댓글과 DM을 영어와 한국어로 작성합니다.
어디서 시작할지 모르겠다면 **`/ig-help`**로 현재 사용할 수 있는 스킬과 역할부터 확인하세요.

이 저장소는 [Jake Schincariol의 원작](https://github.com/Jakeschincariol/instagram-agent-skill)을
바탕으로 [2lazzzy](https://github.com/2lazzzy)가 한국어 처리, 도움말, 검증을 보완한 포크입니다.

## 빠른 시작

Claude Code가 필요합니다. 함께 제공하는 텍스트 검사 도구는 **Python 3.9 이상**에서 실행하며,
외부 Python 패키지를 요구하지 않습니다. 모델 사용과 웹 조사는 사용 중인 Claude 환경에 따릅니다.

설치는 아래 두 방법 중 하나를 선택하세요.

### 스킬 폴더 복사

터미널에서 실행합니다.

```bash
git clone https://github.com/2lazzzy/instagram-agent-skill.git
mkdir -p ~/.claude/skills
cp -r instagram-agent-skill/skills/ig-* ~/.claude/skills/
```

Claude Code에서 `/ig-help`를 실행하세요. 현재 프로젝트에서만 사용하려면 같은 폴더들을
프로젝트의 `.claude/skills/`에 복사하면 됩니다.

`ig-i18n`은 한국어 처리와 언어 설정을 위한 공용 폴더입니다. 실행할 스킬만 골라 복사하지 말고
위 명령처럼 `ig-*` 폴더를 함께 가져오세요. `ig-i18n` 자체는 명령어로 표시되지 않습니다.

### 플러그인 설치

Claude Code 대화창에서 실행합니다.

```text
/plugin marketplace add 2lazzzy/instagram-agent-skill
/plugin install instagram-agent@instagram-agent-skill
```

설치 화면에서 적용 범위를 선택한 뒤 `/instagram-agent:ig-help`를 실행하세요.
플러그인으로 설치하면 명령어 앞에 `instagram-agent:`가 붙습니다. 아래 예시의
`/ig-reel`도 `/instagram-agent:ig-reel`로 바꿔 부르면 됩니다.
설치 방식은 [Claude Code 공식 안내](https://code.claude.com/docs/en/discover-plugins)를 참고하세요.

## 먼저 사용할 스킬 고르기

```text
/ig-help
/ig-help 릴스
/ig-help 캐러셀
/ig-help ig-caption
```

`/ig-help`는 전체 목록, 각 스킬의 역할, 필요한 입력, 결과물과 사용 예시를 보여 줍니다.
주제를 붙이면 관련 제작 순서를, 스킬 이름을 붙이면 그 스킬의 자세한 사용법을 안내합니다.
브랜드 프로필을 먼저 작성할 필요는 없습니다.

## 전체 스킬

| 스킬 | 하는 일과 결과물 | 준비할 것 |
| --- | --- | --- |
| `/ig-help` | 스킬 목록, 역할, 사용법, 제작 순서 안내 | 없어도 됨. 주제나 스킬 이름으로 좁히기 가능 |
| `/ig-profile` | 프로필 점검과 소개글, 링크, 하이라이트 등의 개선안 | 프로필 내용이나 화면, 계정 목표 |
| `/ig-viral` | 참고 게시물 조사, 계정의 평소 성과 대비 분석, 사례 모음 | 분야, 타깃, 참고 계정이나 게시물 |
| `/ig-plan` | 한 주의 주제, 게시 형식, 일정, 소통 계획 | 목표, 타깃, 다룰 주제, 실제 경험이나 소재 |
| `/ig-repurpose` | 기존 자료에서 소재를 뽑아 릴스와 캐러셀로 구성 | 글, 영상 자막, 녹취록, 메모 등 원본 |
| `/ig-reel` | 훅 후보와 점수, 말할 대본, 화면 문구, 구간별 시간표 | 주제, 타깃, 확인된 사실, 원하는 길이 |
| `/ig-carousel` | 장별 문구, 구성, 설명글과 제작 파일 준비 | 주제, 타깃, 전달할 핵심과 근거 |
| `/ig-human` | 반복 표현과 어색한 문장 점검, 초안 다듬기 | 다듬을 글, 원하는 말투 |
| `/ig-caption` | 게시물 설명글의 첫 줄, 본문, 행동 유도 문구, 해시태그 | 대본이나 슬라이드 문구, 목표, 키워드 |
| `/ig-story` | 스토리의 장면 순서, 문구, 참여 유도 구성 | 메시지, 목표, 활용할 소재 |
| `/ig-comment` | 다른 사람의 게시물에 남길 댓글 후보 | 상대 게시물, 보탤 경험이나 의견 |
| `/ig-reply` | 내 게시물에 달린 댓글의 답글 | 내 게시물, 받은 댓글, 원하는 말투 |
| `/ig-dm` | 문의 응대, 자료 전달, 협업 제안 등의 DM 초안 | 대화 상황, 상대와의 관계, 목적 |
| `/ig-audit` | 게시물 성과 분석과 다음에 시도할 개선안 | 게시물 기록, 목표, 확보한 인사이트 지표 |

캐러셀 파일 제작에는 사용 가능한 렌더링 도구가 필요하며, 문구를 승인받은 뒤 진행합니다.
릴스는 제작용 대본과 구성까지 제공하므로 촬영과 영상 편집은 별도로 진행합니다.
게시, 댓글 등록, DM 발송은 사용자가 합니다.

## 릴스와 피드 캐러셀에 사용하는 방법

### 릴스 만들기

1. `/ig-reel`에 주제, 타깃, 실제 소재, 원하는 길이를 전달합니다.
2. 훅 후보와 대본을 확인합니다. 문장 점검은 릴스 작업에 포함됩니다.
3. `/ig-caption`으로 게시물 아래에 붙일 설명글을 만듭니다.
4. 대본과 구간별 시간표를 바탕으로 촬영하고 편집합니다.

```text
/ig-reel --locale ko-KR 회의록 정리 과정을 소개하는 30초 릴스를 만들고 싶어. 타깃은 1인 개발자야. 아래 실제 작업 메모를 바탕으로 구성해 줘. [메모 붙여넣기]
/ig-caption --locale ko-KR 위 릴스의 설명글을 써 줘. 목표는 저장이고 검색어는 회의록 정리야.
```

`ig-caption`의 캡션은 **게시물 아래 설명글**입니다. 영상 안에 들어갈 자막 문구는 릴스 작업에서 다룹니다.

### 피드 캐러셀 만들기

1. `/ig-carousel`에 전달할 핵심과 원본 자료를 전달합니다.
2. 표지, 장별 문구, 설명글을 검토합니다. 캡션 작성과 문장 점검이 이 작업에 포함됩니다.
3. 문구를 승인한 뒤 사용 가능한 도구로 이미지를 만듭니다.

```text
/ig-carousel --locale ko-KR 아래 회의록 정리 가이드를 피드 캐러셀로 구성해 줘. 타깃은 1인 개발자고, 따라 할 순서가 잘 보이면 좋겠어. 먼저 장별 문구부터 보여 줘. [가이드 붙여넣기]
```

이미 완성한 초안의 표현만 고치려면 `/ig-human`, 설명글만 다시 만들려면 `/ig-caption`을 따로 사용하세요.

| 상황 | 함께 쓸 스킬 |
| --- | --- |
| 무엇을 만들지 아직 못 정했을 때 | `/ig-plan` |
| 참고 사례를 찾아보고 싶을 때 | `/ig-viral` |
| 기존 글이나 영상을 재활용할 때 | `/ig-repurpose` |
| 게시물을 스토리로도 알리고 싶을 때 | `/ig-story` |
| 내 게시물에 댓글이 달렸을 때 | `/ig-reply` |
| 성과 자료가 쌓여 다음 방향을 정할 때 | `/ig-audit` |

## 언어와 말투 설정

영어 `en-US`와 한국어 `ko-KR`을 지원합니다. 한 번만 언어를 바꾸려면 명령에 지정하세요.

```text
/ig-help --locale ko-KR
/ig-caption --locale en-US [영어로 쓸 게시물 내용]
```

언어는 다음 순서로 정합니다. 먼저 지정된 값이 우선합니다.

1. 명령의 `--locale`
2. 환경 변수 `IG_LOCALE`
3. `~/.claude/instagram/config.json`의 `locale`
4. `~/.claude/instagram/voice.md`의 `Locale:` 줄
5. 요청이나 입력 글의 언어
6. 기본값 `en-US`

반복해서 쓸 계정이라면 [한국어 말투 템플릿](templates/voice.ko-KR.md)을
`~/.claude/instagram/voice.md`로 복사해 타깃, 말투, 실제 사례를 채우세요.
영어 템플릿은 [templates/voice.md](templates/voice.md)에 있습니다.
기존 파일이 있다면 필요한 항목만 옮겨 넣으세요.

선택적으로 [설정 예시](templates/config.example.json)를 참고해
`~/.claude/instagram/config.json`을 만들 수 있습니다.
예시의 `locale`은 `ko-KR`이므로 영어를 기본으로 쓰려면 `en-US`로 바꾸세요.

한국어는 별도 훅 공식 26개, 음절 기반 대본 시간 추정, 한글 해시태그와 표시 폭 검사,
한국어 표현 점검 규칙을 사용합니다. 자세한 구성은 [언어 지원 문서](docs/i18n.md)를 참고하세요.

## 로컬 텍스트 도구

아래는 저장소 폴더 안에서 직접 실행하는 예시입니다. 입력 파일은 직접 준비하세요.
이 Python 도구들은 텍스트를 로컬에서 처리하며 네트워크에 업로드하지 않습니다.

```bash
python3 skills/ig-reel/hookscore.py hooks.txt --locale ko-KR
python3 skills/ig-reel/beats.py script.txt --locale ko-KR --target 30
python3 skills/ig-caption/caption.py caption.txt --locale ko-KR --keywords "회의록 정리,업무 자동화"
python3 skills/ig-human/humanize.py draft.txt --locale ko-KR -o clean.txt --report
python3 skills/ig-human/detect.py draft.txt clean.txt --locale ko-KR
python3 skills/ig-viral/swipe.py captured.tsv --locale ko-KR
```

| 도구 | 확인하는 것 |
| --- | --- |
| `hookscore.py` | 훅의 길이, 구체성, 도입 표현 등 |
| `beats.py` | 대본의 예상 길이와 구간별 시간 |
| `caption.py` | 설명글 길이, 해시태그, 행동 유도 문구, 검색어, 첫 화면 추정 |
| `humanize.py` | 자동 수정 가능한 표현과 별도로 검토할 표현 |
| `detect.py` | 문체 점검 결과와 수정 전후 차이 |
| `swipe.py` | 수집한 사례의 계정별 중앙값 대비 성과와 훅 분류 |

`swipe.py` 입력은 `account`, `followers`, `median`, `views`, `hook` 열을 가진 TSV입니다.
최근 조회수 중앙값 `median`이 없는 행은 별도 참고 목록에 남기고 주 순위와 통계에서는 제외합니다.
한국어 조회수 표기(`41.2만`, `1.5천`)와 `41.2K`, `1.2M`도 읽습니다.

## 검증과 결과 해석

```bash
python3 -m unittest discover -s tests -t tests
```

영어 기준 출력, 한국어 처리, 언어 설정, 스킬 구조, 설치 명령, 통합 검사 자체의 실패 처리를 검사합니다.
실제 Claude 모델을 호출하는 검사는 별도입니다. Claude CLI 인증과 네트워크가 필요하고 사용량이 발생합니다.

```bash
bash tests/integration/claude_cli.sh
```

- **훅 점수는 문장 점검 기준입니다.** 조회수나 바이럴 확률을 예측하지 않습니다. 한국어 기준값은 실제 성과 데이터로 검증하지 않았습니다.
- **문체 점수는 작성자를 판별하지 않습니다.** 짧은 글은 `INSUFFICIENT`(판정 보류)로 처리하고, 점수를 받기 위해 글을 늘리지 않습니다.
- **대본 시간과 피드 잘림은 추정치입니다.** 실제 녹음 길이로 시간을 보정할 수 있으며, 잘림은 기기와 글꼴 등에 따라 달라집니다.
- **설명글 길이와 해시태그 수는 설정값입니다.** 기본값을 모든 화면과 향후 정책에 적용되는 보장으로 해석하지 마세요. 필요하면 옵션이나 설정 파일에서 조정할 수 있습니다.
- **콘텐츠 계획은 예약 게시가 아닙니다.** 결과물 검토와 실제 업로드, 댓글 등록, DM 발송은 사용자가 진행합니다.

## 출처와 라이선스

원작: Jake Schincariol, [opusjake.ai](https://opusjake.ai),
[instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill).

한국어 지원, 도움말과 검증 보완: [2lazzzy](https://github.com/2lazzzy).
라이선스: [MIT](LICENSE).
