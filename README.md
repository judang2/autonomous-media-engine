# Instagram 자율 에이전트 실험

GPT가 계정 입력을 읽고 **한 번에 행동 하나를 선택**하는 로컬 Python 프로토타입입니다. 기본 실행은 계정·API 키·추가 패키지 없이 작동하는 오프라인 데모입니다. 실제 연결은 공식 Graph API / 비공식 일반 계정 경로로 나눴습니다.

```text
Mock / Graph / Private → 제한된 관찰 → GPT의 구조화된 행동 제안
                                         ↓
친구 ID · 기능 · 시간창 · 중복 · 빈도 검증 → dry-run 미리보기 또는 실행
                                         ↓
                                SQLite 상태 + JSONL 행동 로그
```

**실험용입니다. 비공식 private API는 읽기만 하거나 낮은 빈도로 사용해도 계정 제한·인증 요구·영구 정지가 발생할 수 있습니다. low-risk는 이 프로그램의 보수적인 설정 이름이며 안전 보장이 아닙니다.** 중요한 계정이나 다른 사람의 계정을 사용하지 마세요. 친구들에게 AI 운영 실험임을 알리고 참여한 사람의 ID만 등록하세요. 계정 소개에도 AI 운영 사실을 표시하는 것을 권합니다.

## 1. 바로 실행: 계정 없이 데모

Python 3.10 이상이 필요합니다. 이 폴더에서 실행하세요. PowerShell 기준:

```powershell
Copy-Item .env.example .env
python -m igagent
python -m unittest discover -s tests -v
```

`python`이 없다면 Python을 설치하거나 사용 중인 Python 실행 파일의 전체 경로로 실행하세요. 데모·공식 API·GPT 경로는 Python 표준 라이브러리만 사용하므로 pip 설치가 필요 없습니다. macOS/Linux에서는 `cp .env.example .env`, `python3`를 사용하면 됩니다.

예상 출력:

```json
{
  "status": "dry_run",
  "action": "reply_dm",
  "event_id": "dm:demo-1",
  "mode": "dry-run",
  "preview": {
    "kind": "reply_dm",
    "event_id": "dm:demo-1",
    "text": "안녕! 나는 실험 중인 AI 계정이야. 반가워!",
    "reason": "오프라인 데모 답장"
  }
}
```

`PLANNER=demo`는 고정된 샘플 답장을 만드는 테스트용입니다. GPT가 판단하는 모드는 아래처럼 별도로 켭니다. 샘플 데이터도 DM·댓글·피드를 포함합니다.

## 2. GPT 판단 연결

### Codex 구독 연결 — GPT-5.5 / low

2026-09-09 추가: API 키 없이 ChatGPT에 로그인한 Codex CLI를 호출할 수 있습니다. 구독 사용 한도를 소비합니다. 이 경로는 현재 `gpt-5.5`, `low` 조합으로 제한하며 다른 모델로 자동 전환하지 않습니다.

```dotenv
PLANNER=codex
CODEX_MODEL=gpt-5.5
CODEX_REASONING_EFFORT=low
ENABLE_LIVE=false
```

`codex login status`가 ChatGPT 로그인을 표시해야 합니다. 필요하면 `codex login`으로 로그인하세요. CLI를 찾지 못하면 `.env`의 `CODEX_EXECUTABLE`에 실행 파일 전체 경로를 설정하세요. API 키 로그인은 거부하며 API 과금으로 자동 전환하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m igagent.benchmark
```

가짜 DM 10개를 GPT에 각각 전달합니다. **Instagram에 접속하지 않습니다.** 결과는 `local/benchmark/실행번호/`의 `answers.json`, `model-usage.jsonl`, `summary.json`에 저장됩니다. 100회 예상치는 이 표본의 10배로 계산하며, 구독 한도 비율로 환산하지 않습니다. 캐시 입력은 전체 입력에 포함될 수 있으므로 이중 합산하면 안 됩니다. 모델별 추론 토큰이 따로 보고되지 않으면 추론량을 별도로 알 수 없습니다. 10개 답변을 얻었다는 것만으로 답변 내용의 안전성이 검증되지는 않습니다.

실제 계정 DM으로 초안 하나를 만들려면 기존 명령을 그대로 사용합니다:

```powershell
.\.venv\Scripts\python.exe -m igagent
```

이 명령은 실제 provider에서 Instagram을 조회하고 등록한 친구의 텍스트를 Codex로 보냅니다. `.env`와 Instagram 자격 증명은 자식 프로세스 환경에서 제외합니다. 별도의 임시 폴더에서 읽기 전용·도구 제한으로 실행하고 개인 Codex 설정/프로젝트 지침은 로드하지 않습니다. 이 대화의 기억을 자동 상속하지 않습니다. 응답과 요청은 임시 세션으로 처리하지만 서비스 측 보존 정책과 Codex 자체 진단 로그까지 무보존을 보장하는 것은 아닙니다.

오류가 나면 API 경로로 넘어가지 않고 중단합니다. 앱 내부 실행에서 `Access denied`가 나면 일반 PowerShell에서 실행해 보세요. 내부 CLI 버전이 필요한 옵션을 지원하지 않거나 GPT-5.5 사용 권한이 없을 때도 중단합니다. 실제 전송은 기존 두 단계 live 설정과 정책 검사를 통과해야 합니다.

### 별도 OpenAI API 키 연결

`.env`에서 다음을 지정하고 다시 실행하세요.

```dotenv
PLANNER=openai
OPENAI_API_KEY=여기에_로컬에서만_입력
OPENAI_MODEL=내_API_계정에서_사용할_Responses_지원_모델_ID
```

모델 이름은 자동으로 추정하지 않습니다. 본인의 API에서 사용할 수 있고 Structured Outputs를 지원하는 GPT 모델 ID를 지정하세요. `IG_PROVIDER=mock`을 유지하면 샘플 입력으로 GPT 판단만 실험합니다. OpenAI API 호출에는 비용이 발생하며, 허용한 친구의 입력 텍스트와 계정 ID·이름이 OpenAI로 전송됩니다. Instagram 토큰, 세션, 비밀번호, 게시 이미지 파일 경로는 모델 입력에 넣지 않습니다. `store=false`를 사용하지만 이것이 모든 서버 로그의 무보존을 의미하지는 않습니다.

실제 계정 내용을 GPT로 전송하기 전에 참여자에게 이 흐름을 알려 주세요. 현재 텍스트만 처리하며 사진·영상 자체를 시각적으로 이해하거나 생성하지 않습니다.

## 3. 공식 Graph API 경로

이번 구현은 **Instagram API with Instagram Login**입니다. Facebook Login 경로의 `graph.facebook.com` 토큰과 섞으면 안 됩니다. Business/Creator 계정, Meta 개발자 앱, 해당 계정의 Instagram User access token과 권한이 필요합니다. OAuth 화면·토큰 교환 서버는 이 최소 버전에 포함하지 않았습니다. Meta 앱의 Instagram 설정에서 로그인 및 권한 부여를 완료하고 토큰을 로컬 `.env`에 넣으세요.

```dotenv
IG_PROVIDER=graph
IG_GRAPH_TOKEN=로컬에서_설정
IG_GRAPH_USER_ID=내_Instagram_계정의_숫자_ID
IG_GRAPH_VERSION=내_Meta_앱이_지원하는_버전
GRAPH_ENABLE_DM=false
ALLOWED_USER_IDS=
```

`IG_GRAPH_VERSION`은 `v숫자.숫자` 형태입니다. 예: `v25.0`. 예시 버전을 그대로 고정하기보다 Meta 앱에서 지원 여부를 확인하세요.

권한은 기능에 맞게 부여합니다: `instagram_business_basic`, `instagram_business_manage_comments`, 게시용 `instagram_business_content_publish`, DM용 `instagram_business_manage_messages`. 개발 모드 테스트 역할, 접근 수준 및 운영 대상에 따라 App Review 등이 필요합니다. 앱 권한이 있다고 모든 계정에 접근할 수 있는 것은 아닙니다. 실제 설정 절차와 요구 조건은 [Meta 공식 Instagram Login 문서](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)를 확인하세요.

```powershell
python -m igagent observe
```

실제 조회를 수행하고 본문 없이 계정·기능·이벤트 ID·발신자 ID를 표시합니다. 참여한 친구의 `actor` 값을 `ALLOWED_USER_IDS`에 쉼표로 등록하세요. ID가 누락된 댓글은 처리하지 않습니다. 권한 준비 후 `GRAPH_ENABLE_DM=true`를 켜야 DM도 조회·답장 후보가 됩니다.

구현 범위:

| 기능 | Graph 경로 |
|---|---|
| 계정 상태 | ID·사용자 이름 |
| 내 게시물 댓글 읽기·답글 | 최신 게시물 최대 3개, 각 댓글 5개 |
| DM 읽기·답장 | 옵션 활성화 시 최근 대화 최대 3개, 각 최신 메시지 1개 |
| 사진 게시 | 운영자가 준비한 공개 HTTPS JPEG URL로 컨테이너 생성 → 준비 상태 확인 → 게시 |
| 개인 홈 피드·임의 좋아요 | 지원하지 않음 |

DM은 상대가 시작한 대화의 관찰된 최신 메시지에만 답장합니다. 프로그램은 메시지 생성 시각부터 23시간 미만만 허용하는 보수적인 조건을 둡니다. 실제 Meta의 메시징 규칙과 수신자 자격은 서버에서도 적용됩니다. 새로운 상대에게 먼저 보내는 기능은 없습니다. [Meta 공식 API 컬렉션](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api) 참고.

## 4. 비공식 일반 계정 경로

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install ".[private]"
```

macOS/Linux에서는 `.venv/bin/python`을 사용하세요. 다음 설정 후 **로그인은 사용자가 로컬 터미널에서 직접** 수행합니다.

```dotenv
IG_PROVIDER=private
ACK_PRIVATE_API_RISK=true
IG_SESSION_FILE=local/instagram-session.json
IG_USERNAME=실험용_계정명
PRIVATE_ENABLE_FEED=false
ALLOWED_USER_IDS=
```

```powershell
.venv/Scripts/python.exe -m igagent login-private
.venv/Scripts/python.exe -m igagent observe
```

비밀번호와 2FA 코드는 숨김 입력입니다. 비밀번호를 채팅이나 코드에 넣지 마세요. 환경변수 `IG_PASSWORD`도 지원하지만 숨김 입력을 권합니다. 세션은 **암호화되지 않은 로컬 JSON**이며 비밀번호와 같은 수준으로 보호해야 합니다. `.gitignore`만으로 파일 접근이 차단되는 것은 아닙니다. Windows에서는 해당 폴더 접근 권한을 본인 계정으로 제한하고 공유·동기화 대상에 넣지 마세요. 세션이 만료되면 자동 재로그인하지 않고 중단합니다.

이 경로는 `instagrapi`를 사용합니다. 1:1 DM, 내 게시물 댓글, 선택적 홈 피드 조회와 DM 답장·댓글 답글·피드 댓글·좋아요·JPEG 게시를 연결했습니다. 그룹 DM은 제외합니다. `PRIVATE_ENABLE_FEED=true`에서만 피드 한 페이지를 가져옵니다. 라이브러리 내부의 요청·인증 동작 때문에 조회도 완전히 무해한 동작이라고 보장할 수 없습니다. 로그인 과정은 라이브러리의 기본 인증 절차를 사용하며, 실행 루프는 비밀번호를 전달하지 않습니다. 인증 확인이 나오면 공식 앱에서 직접 해결한 후 세션을 다시 만드세요. CAPTCHA 우회·프록시 회전·대량 팔로우는 구현하지 않았습니다.

실행용 클라이언트는 확인한 `instagrapi==2.18.18`에 고정했습니다. 내부 타임아웃 재시도·자동 challenge 처리를 우회하고 HTTP 재시도를 0으로 설정합니다. 관찰당 private 요청은 최대 20회, 실행당 최대 10회로 제한합니다. 사진도 라이브러리의 반복 configure 도우미 대신 업로드와 configure를 각 한 번 호출합니다. 버전 변경 시 `tests/test_private_contract.py`와 내부 전송 함수를 재검토해야 합니다. 별도 로그인 명령만 기본 로그인 흐름을 사용합니다.

## 5. 실제 행동 켜기

먼저 `python -m igagent`로 dry-run을 검토하세요. 실제 provider를 선택한 dry-run은 **Instagram 조회는 수행**하며, `PLANNER=openai`이면 GPT도 호출합니다. 게시·답장·좋아요 실행 함수는 호출하지 않습니다. 완전히 오프라인인 것은 `mock + demo`뿐입니다. `observe` 역시 실제 provider에서는 네트워크를 사용합니다. `login-private`는 인증용 별도 명령으로 dry-run이 아닙니다.

실행을 켜려면 `.env`의 `ENABLE_LIVE=true`, `PLANNER=openai`, 올바른 provider·친구 ID와 CLI의 `--live`가 모두 필요합니다.

```powershell
python -m igagent run --live
python -m igagent run --live --cycles 6 --interval 1800
```

매 회차 다시 관찰하고 최대 한 행동을 결정합니다. 기본 최근 24시간 최대 3회, 행동 사이 30분입니다. 설정의 상한은 최근 24시간 100회이며 최소 간격은 10분입니다. 이는 Instagram이 공인한 안전 한도가 아닙니다. 폴링은 최대 48회로 제한하고 프로세스 종료 시 멈춥니다. 별도 예약 작업이나 백그라운드 서비스는 설치하지 않습니다. 같은 계정을 여러 폴더·여러 컴퓨터에서 동시에 실행하지 마세요.

기본 `ALLOWED_ACTIONS=reply_dm,reply_comment`입니다. 확장하려면 `comment`, `like`, `publish_photo`를 쉼표로 추가하세요. 실제 API가 지원하지 않는 행동은 차단됩니다. 피드 댓글·좋아요도 등록한 친구의 관찰된 게시물에만 적용됩니다. 링크·@멘션, 빈 답장, 500자를 넘는 출력, 임의 대상 ID를 차단합니다. 팔로우·삭제·차단·외부 URL 탐색은 행동 목록에 없습니다.

사진 게시는 `assets.example.json`을 `assets.json`으로 복사해 준비합니다. `description`은 실제 사진을 설명하도록 바꾸세요. Graph용 `image_url`은 Meta가 접근할 수 있는 공개 HTTPS JPEG URL, private용 `file`은 `media/` 안의 JPEG 파일 이름입니다. `YOUR-PUBLIC-HOST.example`은 동작하지 않는 자리표시자입니다. GPT는 설명과 자산 ID만 보고 선택하며 이미지 경로나 URL을 만들어낼 수 없습니다. 같은 자산 ID는 한 번만 게시합니다. 이 버전은 사진 생성, 릴스, 스토리, OAuth UI를 구현하지 않았습니다.

## 6. 기록·중지·복구

### 주인 지정과 첫 DM 전송

`.env`에 `OWNER_USERNAME=example_owner`을 지정한 후 `python -m igagent bind-owner`를 실행하면 Instagram에서 해당 사용자 이름의 숫자 ID를 조회해 `local/owner.json`에 저장합니다. 이것은 운영자가 지정한 계정 연결이며 실제 사람이 그 계정을 소유하는지 인증하는 절차는 아닙니다. 주인과 실험 계정은 달라야 합니다. 실험 계정별로 묶이고 사용자 이름 설정을 바꾸면 다시 연결해야 합니다. 주인의 DM으로 실행 권한을 바꾸거나 비밀을 읽는 기능은 제공하지 않습니다.

주인 계정에서 실험 계정으로 새로운 DM을 보낸 후 `python -m igagent --owner-only`로 초안을 확인하세요. 처음 실제 전송할 때 `.env`의 `ENABLE_LIVE=true`와 `python -m igagent --owner-only --live --cycles 1`을 사용하면 주인의 DM만 대상으로 최대 한 번 행동합니다. 모델이 noop을 고르거나 한도/중복 검사에 걸리면 보내지 않습니다. 이 명령은 **초안을 다시 생성**하므로 직전에 본 미리보기와 문장이 다를 수 있습니다. 완료 후 `ENABLE_LIVE=false`로 되돌리세요. 주인 정보가 연결되지 않으면 실행을 거부합니다.

`--owner-only` 없이 실행할 때는 기존 친구 허용 목록을 그대로 따르므로 주인 계정에도 답장을 허용하려면 그 숫자 ID를 `ALLOWED_USER_IDS`에 포함해야 합니다.

- `local/actions.jsonl`: 시각, 행동 종류, 이벤트 ID, 모드, 실행/차단 상태. DM 원문·답장 본문·토큰·원시 예외는 저장하지 않습니다. dry-run 답장 미리보기는 터미널에 표시되므로 터미널 기록 취급에 주의하세요.
- `local/state.sqlite`: 계정별 실행 예약과 결과. 같은 이벤트에 답장 문구만 바꿔 반복하는 것을 막습니다. 재실행해도 유지됩니다. dry-run은 실행 이력을 소비하지 않습니다.
- `local/STOP`: 이 파일이 있으면 조회/실행을 시작하지 않습니다. 대기 중에는 1초 단위로 확인합니다. 이미 진행 중인 HTTP 요청은 취소할 수 없으며 단일 요청의 제한 시간은 45초입니다.

```powershell
New-Item local/STOP -ItemType File -Force
```

Ctrl+C도 지원합니다. 실행 예약은 전송 전에 기록됩니다. 전송 중 타임아웃·오류·프로세스 종료가 발생하면 `pending` 또는 `unknown`이 남고 **그 계정의 다음 쓰기를 차단**합니다. 중복 전송을 피하려고 자동 재시도하지 않습니다. 이는 정확히 한 번 전송을 보장하는 분산 트랜잭션은 아닙니다.

복구: Instagram 앱에서 실제 결과를 직접 확인하고, SQLite 도구로 해당 `attempts` 행을 확인하세요. 전송됐으면 `status=success`, 전송되지 않았고 자동 재시도를 포기할 경우 `status=skipped`로 바꾸세요. 행을 지우지 않으면 해당 이벤트는 계속 제외됩니다. `pending/unknown`을 확인 없이 바꾸거나 DB 자체를 삭제하면 중복 방지가 깨집니다. `STOP`을 해제할 때는 파일만 수동으로 삭제하세요.

오류 메시지는 비밀 유출을 막으려고 예외 클래스만 표시합니다. `ValueError`: `.env` 값·동시 live 설정·필수 자격 확인. `HTTPError`: Graph 권한·토큰·버전 또는 OpenAI 모델·키 확인. `LoginRequired`/`ChallengeRequired`: 실행 중지 후 공식 앱 인증. `RuntimeError`: 모델 응답 거절/불완전 또는 전송 불확실성을 로그와 상태 DB로 구분하세요. 라이브러리 변경으로 응답 필드가 달라져도 중단하며 조용히 다른 API로 바꾸지 않습니다.

## 7. GitHub 비교 조사와 참고한 부분

조사일: **2026-09-08**. 공개 README와 아래 연결한 구현·문서를 비교했습니다. 전체 프로젝트의 보안 감사나 실계정 동작 검증은 아닙니다. 별·다운로드 수는 채택 근거로 쓰지 않았습니다. 아래 프로젝트 코드를 복사·벤더링하지 않고 공개 인터페이스와 설계를 참고해 별도 구현했습니다. 런타임의 선택적 외부 의존성은 `instagrapi`입니다.

| 프로젝트 | 경로·성격 | 참고/채택 | 이번에 그대로 사용하지 않은 이유 |
|---|---|---|---|
| [official-Arvind/instagram-mcp](https://github.com/official-Arvind/instagram-mcp) | FastMCP + instagrapi, 광범위한 계정 조작 | 관찰/DM/댓글/미디어 기능 분류, 로컬 세션 개념 | 큰 쓰기 도구 집합을 모델에 직접 노출하지 않음. 비밀번호를 모델 도구 인자로 전달하는 예시는 채택하지 않음 |
| [adelaidasofia/instagram-mcp](https://github.com/adelaidasofia/instagram-mcp) | 공식 Graph API MCP, Business/Creator | [server.py](https://github.com/adelaidasofia/instagram-mcp/blob/main/instagram_mcp/server.py)의 DM 분리, 게시 컨테이너 확인, 오류·감사 로그 경계 | 이 프로젝트의 Facebook Login 설정 대신 Instagram Login 어댑터를 별도로 작성 |
| [subzeroid/instagrapi](https://github.com/subzeroid/instagrapi) | Python 비공식 API 라이브러리 | private 어댑터의 유일한 외부 실행 의존성. [Direct](https://subzeroid.github.io/instagrapi/usage-guide/direct.html), [Media](https://subzeroid.github.io/instagrapi/usage-guide/media.html), [댓글 구현](https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/comment.py), [인증·피드 구현](https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/auth.py) | 비공식 API의 불안정성을 제거할 수 없음. 세션 저장·제한된 함수만 사용 |
| [dilame/instagram-private-api](https://github.com/dilame/instagram-private-api) | TypeScript/Node 비공식 SDK | 상태·피드 추상화를 비교 | 최소 버전에서 Python/Node 런타임을 동시에 운영하지 않기 위해 미채택 |
| [instaloader/instaloader](https://github.com/instaloader/instaloader) | 사진·영상·캡션·메타데이터 수집 도구 | 관찰 기능과 행동 실행 도구의 차이를 비교 | DM 답장·게시 중심 실행 계층에 맞지 않음 |
| [InstaPy/InstaPy](https://github.com/InstaPy/InstaPy) | Instagram 상호작용 자동화 | 정해진 반복 작업과 모델 기반 결정 구조 비교 | 성장/반복 자동화를 이번 실험의 기본 정책으로 사용하지 않음 |
| [oliverames/meta-mcp-server](https://github.com/oliverames/meta-mcp-server) | Meta 비즈니스 플랫폼 통합 MCP | 공식 API 기능 경계 및 서비스 분리 비교 | Instagram 한 계정 실험에는 범위가 넓어 직접 의존하지 않음 |

추가 1차 자료: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Meta 공식 API 컬렉션](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api). Meta 개발자 사이트 직접 조회가 실패한 부분은 Meta가 운영하는 Postman 문서로 확인했습니다. 저장소의 “안전/production-ready” 홍보 표현을 검증된 보장으로 취급하지 않았습니다. 외부 코드를 향후 복사하거나 배포에 포함하면 해당 revision의 LICENSE와 고지 조건을 확인하세요.

## 8. 구현 경계와 검증

`igagent/core.py`: 설정, 구조화된 GPT 호출, 코드 수준 정책, 실행 저널.
`igagent/providers.py`: mock / Graph / private 관찰·실행 및 로컬 로그인.
`igagent/__main__.py`: 유한 반복 CLI. `tests/test_agent.py`: 외부 호출 없이 동작하는 안전·전송 계약 테스트.

MCP 서버 자체는 이번 산출물에 포함하지 않았습니다. 참고 MCP의 도구 분류를 로컬 어댑터로 줄여 자율 루프를 완성했습니다. 향후 MCP를 붙이더라도 반드시 `cycle`과 정책·저널을 통과하도록 연결해야 합니다.

프롬프트는 외부 텍스트를 지시로 취급하지 않도록 분리하고 코드에서 행동·대상을 재검증합니다. 이것이 모든 프롬프트 주입이나 부적절한 답장을 해결하는 것은 아닙니다. 특히 허용된 사람에게 보내는 답장 내용의 품질·개인정보 누출은 완전하게 검증하지 않습니다. 공개 답장에 사적 대화를 인용하지 말라는 지침이 있으나, 민감한 내용을 가진 실계정 운영에는 추가 콘텐츠 검증이 필요합니다.

최신 일부 입력만 관찰하며 전체 피드/대화 백필·webhook·읽음 표시·이전 수동 답장 동기화는 없습니다. 과거 댓글이 23시간 안이면 초기 실행의 답장 후보가 될 수 있습니다. 재시작 이후에는 이 프로그램이 기록한 이벤트만 중복 제거합니다. 단일 로컬 계정 실험이며 다중 프로세스 조회나 서로 다른 STATE_DIR 간 한도 공유를 지원하지 않습니다.

실제 Instagram/Meta/OpenAI 자격 증명이 제공되지 않아 라이브 인증·GPT 생성·게시 성공은 검증하지 않았습니다. 테스트의 API 응답은 대역이며 실제 API 호환성을 완전히 보장하지 않습니다. 자세한 로컬 검증 결과는 `VALIDATION.md`를 참고하세요.


## 짧은 실시간 DM 실험 (Windows)

`python -m igagent chat --live`를 실행하면 일시정지 상태로 시작합니다. 콘솔에서 S로 시작/재개, P로 일시정지, Q로 종료합니다. Enter는 필요 없습니다. 시작 후 전체 10분이 지나면 종료하며 .env의 기존 간격은 바꾸지 않습니다. `--live`를 생략하면 dry-run입니다.

이 모드에서만 전송 대기시간을 0으로 하고, 각 작업 완료 후 5초 뒤 DM을 확인합니다. 최근 24시간 행동 한도는 유지합니다. 기본 chat 모드는 주요(Primary) 탭의 1:1 및 단체 DM을 대상으로 합니다. 개인별 허용 목록 대신 primary 조회 결과와 folder=0, pending=false를 확인하며 자신이 보낸 메시지는 제외합니다. 한 번에 최신 최대 20개 방을 조회하므로 더 오래된 방까지 매번 전부 조회하지 않습니다. GPT에는 한 번에 한 방의 최신 텍스트 메시지만 전달합니다. 주요 탭에 추가한 방은 이후 조회부터 대상이고 일반 탭으로 이동한 방은 이후 조회에서 제외됩니다. 조회 이후 모델 처리 중 방을 이동한 경우 진행 중인 답장까지 취소되지는 않습니다. `--owner-only`를 추가하면 주인만 대상으로 합니다. 시작 이후 DM만 처리하고 대화별 최신 텍스트 한 개를 사용하므로 연속 메시지 전체의 보존이나 모든 DM 처리를 보장하지 않습니다. 새 대상 메시지가 없거나 미확정 전송·하루 한도가 있으면 모델을 호출하지 않습니다. noop 및 dry-run 입력은 해당 실행 동안 재생성하지 않습니다.

한 번의 확인이 여러 HTTP 요청일 수 있고, 예산은 조회당 3회입니다. 오류가 나면 종료하며 재로그인·자동 재시도하지 않습니다. 5초 조회는 Instagram이 보장한 안전 주기가 아닙니다. P/Q는 진행 중인 동기식 API·모델 호출이 끝난 후 처리되므로 이미 진행 중인 답장은 전송될 수 있습니다. STOP 파일은 새 전송 전에도 확인합니다. 제한시간도 진행 중인 호출을 강제 취소하지 않습니다. 단일 프로세스만 실행하세요.
