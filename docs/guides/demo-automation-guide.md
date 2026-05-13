# 시연 자동화 스크립트 작성 가이드

매듭 시연 자동화 스크립트(`.gstack-demo*.py`)를 만들거나 수정할 때 참고. D-day 2026-05-13 통합 시나리오 자동화(`.gstack-demo-integrated.py`) 만들면서 헤맸던 함정과 패턴을 모은 문서.

대상: 다음 시연/QA/E2E 자동화를 만들 사람(future-self 포함).

---

## 0. 전체 구조 — 무엇이 어디에 있나

```
.gstack-browser-launch.py     # 터미널 1: chromium CDP 9222 + 토큰 주입
.gstack-demo-token            # JWT 평문 (gitignore)
.gstack-demo.py               # 터미널 2 (v2, 3명 시나리오)
.gstack-demo-integrated.py    # 터미널 2 (v3 통합, 4명, ACT 0~6)
.rehearsal-*                  # 리허설용 임시 helper (gitignore, 시연 안 씀)
backend/scripts/seed_demo_personal_data.py  # docker exec로 호출하는 시드
backend/data/demo_extraction_canned.json    # ACT 6 학습 fallback
```

핵심 의존성:
- `playwright` (CDP attach)
- `websockets` (직접 WS 송신)
- `urllib.request` (HTTP — 외부 라이브러리 의존 줄임)

---

## 1. 환경 사전 점검 — 자동화 돌리기 전

| 항목 | 명령 | 정상값 |
|---|---|---|
| Docker 컨테이너 4개 healthy | `docker ps` | api/frontend/postgres/redis 모두 `(healthy)` |
| Backend health | `curl http://localhost:8000/health` | `{"status":"ok"}` |
| Frontend reachable | `curl -o /dev/null -w "%{http_code}" http://localhost:3000/` | `200` |
| CDP 9222 활성 | `curl http://localhost:9222/json/version` | `Chrome/X.X.X.X` JSON |
| 호스트 JWT 유효 | `curl -H "Authorization: Bearer $(cat .gstack-demo-token)" http://localhost:8000/api/v1/users/me` | 200 + name |

**JWT 만료 시** (401) — 정상 Chrome으로 로그인 → `localStorage.getItem('auth_token')` → `.gstack-demo-token` 갱신(ASCII 인코딩, `Set-Content -Encoding ascii`). 자동화 chromium에선 Google OAuth 거부됨.

---

## 2. 함정과 해결책

### 2.1 WebSocket `time_selection` slot 단위

**함정**: slot이 hour 인덱스(0~23)인지 30분 인덱스(0~47)인지 코드만 보고 불분명.

**진실**: backend는 **30분 슬롯 인덱스 (HOUR_START=9 ~ HOUR_END=22, SLOT_MINUTES=30 → TOTAL_SLOTS=26)**. 즉 `slot 0 = 09:00`, `slot 18 = 18:00`, `slot 19 = 18:30`.

**검증 권위 helper**:
- frontend: `TimeBarSelector.tsx:51` `slotToTime(slotIndex)`
- backend: `scheduling_round.slot_idx_to_time(idx)`
- 검증 스크립트: `.gstack-act3-verify.py`의 `SLOT_START=18, SLOT_END=19` (18:00 시작 + 18:30 종료, inclusive)

**규칙**:
- `start`는 시작 슬롯 인덱스 (inclusive)
- `end`는 종료 슬롯 인덱스 (inclusive) — `slotToTime(end + 1)`로 종료 시각 표시

### 2.2 `schedule_consensus_ready` 발화 조건

**함정**: 4명 다 `time_selection` 보냈는데 consensus_ready 안 옴.

**원인**: `_maybe_emit_proposal` (backend/app/api/ws/social.py:82) 조건 `len(availability) >= member_count`. 게스트 중복 join으로 `RoomMember`가 부풀면 member_count > availability → 영구 실패.

**예방**:
- 자동화 스크립트가 같은 게스트 이름으로 두 번 join하면 안 됨. token 캐시 사용 (`.rehearsal-tokens.json`).
- 백엔드는 `commit 3eef0d3`로 중복 방지 추가됨 (같은 방·같은 display_name이면 기존 user 토큰 재발급).

**우회**: 만약 카운트가 꼬였으면 SQL로 직접 정리:
```sql
DELETE FROM room_members WHERE room_id=<X> AND user_id IN (<중복 id들>);
```

### 2.3 `/schedule-confirm` API의 snapshot race

**함정**: consensus_ready 받은 직후 `POST /rooms/{id}/schedule-confirm`에 `snapshot_hash` 넣으면 `snapshot_outdated` 응답. 한 게스트가 늦게 send해서 snapshot이 다시 바뀐 거.

**해결**: HTTP 직접 호출 대신 **호스트 chromium UI의 `[✅ 추천 시간 그대로 확정]` 버튼 클릭**. UI는 frontend가 최신 snapshot으로 보내므로 race 없음.

### 2.4 게스트 토큰 라이프사이클

**함정**: `guest-join` 응답의 token을 잃으면 그 user로 더 발화 못함. 새로 join하면 user_id 새로 생성 → RoomMember 누적.

**예방**: `.rehearsal-tokens.json` 같은 캐시 파일 사용 (gitignore). 매 실행마다 새 방이라면 새 토큰. 같은 방 재진입은 캐시.

```python
import json, os
TOKEN_CACHE = ".rehearsal-tokens.json"

def load_tokens():
    return json.load(open(TOKEN_CACHE)) if os.path.exists(TOKEN_CACHE) else {}

def save_tokens(d):
    json.dump(d, open(TOKEN_CACHE, "w"))
```

### 2.5 Docker env_file 재로드

**함정**: `.env` 수정 후 `docker restart maedeup-api` → 환경변수 안 보임.

**원인**: `docker restart`는 컨테이너 프로세스만 재시작. `env_file`은 컨테이너 생성 시점 한 번만 로드.

**해결**: `docker compose up -d --force-recreate <service>` — 컨테이너 재생성 + env 재로드.

검증: `docker exec maedeup-api env | grep <KEY>`.

### 2.6 Backend volume mount vs Frontend image build

**Backend (volume mount)**: 코드 변경은 디스크 → 컨테이너 자동 반영. **Python import 캐시는 process 재시작 의존** → `docker restart maedeup-api` 또는 `compose up --force-recreate`로 reload.

**Frontend (image build)**: Next.js production build artifact. 코드 변경은 **`docker compose build frontend` + `up -d --no-deps frontend`** 필요. `docker restart`나 단순 `up`은 옛 이미지 그대로.

**주의**: `--no-deps` 플래그는 `up`에는 있고 `build`에는 없음 (compose v2). `docker compose build --no-deps frontend` → `unknown flag` 오류.

### 2.7 PowerShell / Git Bash path 변환

**함정 1 — Git Bash**: `docker cp` 또는 `docker exec` 인자에 `/app/foo`를 주면 `/C:/Program Files/Git/app/foo`로 변환되어 `No such file`.

**해결**: `//app` (double slash) 또는 `MSYS_NO_PATHCONV=1` 환경변수.
```bash
docker exec -w //app maedeup-api python rehearsal_test.py
```

**함정 2 — PowerShell**: `vi`, `head`, `tail` 등 Unix 명령 없음. `Set-Content -Encoding ascii`로 토큰 저장 (UTF-16 BOM 방지).

### 2.8 Python f-string + JS regex `\s`

**함정**: f-string 안에 JS regex `/(오전|오후)\s*\d/` 적으면 `SyntaxWarning: invalid escape sequence '\s'`.

**해결**: backslash 이중화 → `/(오전|오후)\\s*\\d/`. JS에선 escape 한 단계만 풀려 regex가 정상 작동.

### 2.9 docker cp가 volume mount면 양방향

**함정**: `docker cp foo.py maedeup-api:/app/foo.py` 후 `docker exec maedeup-api rm /app/foo.py`로 지웠는데 호스트 `backend/foo.py`가 남아있음.

**원인**: backend 폴더가 호스트 ↔ 컨테이너 volume mount. cp는 호스트에도 영향. exec rm은 컨테이너 내 unlink이지만 mount 매핑상 호스트도 영향.

**예방**: 일회성 테스트 스크립트는 `.rehearsal-*` 이름 + 호스트 루트에. docker는 cp 없이 `python -c "..."` 또는 `python <(cat script.py)` 같은 stdin 패턴.

---

## 3. Chromium 조작 (CDP via Playwright)

### 3.1 CDP attach

```python
browser = await p.chromium.connect_over_cdp("http://localhost:9222")
ctx = browser.contexts[0]
page = ctx.pages[0] if ctx.pages else await ctx.new_page()
```

`.gstack-browser-launch.py`로 띄운 chromium은 종료 안 됨 (Ctrl+C 전까지). 자동화 스크립트는 attach만.

### 3.2 JS locator 패턴 — 권장

**버튼 텍스트로 찾기**:
```js
Array.from(document.querySelectorAll('button')).find(
  b => b.innerText && b.innerText.includes("확정") && b.offsetParent
);
```

- `b.offsetParent` 체크 — 화면에 보이는 것만 (`display: none` 제외)
- `b.disabled` 체크 — 활성 버튼만 (선택)
- 매칭 우선순위: `===` exact > `.includes()` > regex

**input 채우기 (React)**:
```js
const inp = document.querySelector('input[placeholder*="모임명"]');
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
setter.call(inp, "value");
inp.dispatchEvent(new Event('input', {bubbles: true}));
```

이유: React가 자체 state로 input value를 관리 → 단순 `inp.value = "x"`는 무시됨. native setter 호출 + input 이벤트로 React state 트리거.

**ID로 정확 매칭** (TimeBar 같은 정형 UI):
```js
document.getElementById(`timebar-${date.replace(/-/g, "")}-mine-${slotIdx}`)
```

### 3.3 화면 캡쳐 폴링 패턴

비동기 UI 변화 기다릴 때:
```python
async def wait_for_text(page, contains, timeout_s=30.0, poll=0.5):
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        found = await page.evaluate(
            f"Array.from(document.querySelectorAll('*')).some(e => "
            f"  e.children.length === 0 && e.innerText && "
            f"  e.innerText.includes({json.dumps(contains)}) && e.offsetParent)"
        )
        if found:
            return True
        await asyncio.sleep(poll)
    return False
```

`children.length === 0` — 리프 노드만 (조상까지 잡으면 noise).

---

## 4. 시연용 데이터 시드 패턴

### 4.1 Personal Data 시드

`backend/scripts/seed_demo_personal_data.py` — `--room <id>`로 호출. RoomMember를 `user.name`으로 매칭(SEED_MAP).

```python
# 시나리오 박힌 시드
SEED_MAP = {
    "지민": {"food_preferences": ["한식"], "liked_areas": ["강남"], "time_preference": "저녁형"},
    "수현": {"food_restrictions": ["채식"], "disliked_areas": ["홍대"]},
    "민수": {"transport_mode": "지하철"},
}
```

**주의**: 호스트는 SEED_MAP의 "지민"과 매칭돼야 ✨ 표시. 실 환경 호스트 `user.name`이 다르면(예: "김창윤") 호스트 skip → 호스트 ✨ 안 보임. 시연 시 호스트 name을 직접 DB 수정 또는 SEED_MAP에 추가.

호출:
```bash
docker exec maedeup-api python -m scripts.seed_demo_personal_data --room 60
```

### 4.2 ACT 6 학습 canned fallback

`backend/data/demo_extraction_canned.json` — `DEMO_FALLBACK_ENABLED=true`일 때만 사용. `user_email`로 매칭.

**용도**: 시연 transcript에 "비린 거 별로" 발화 → Gemini가 못 잡을 때 → canned가 박혀있어서 ACT 6 ✨ 임팩트 보장.

**시연 후**: `.env`에서 `DEMO_FALLBACK_ENABLED` 줄 삭제/false + `docker compose up -d --force-recreate fastapi-app`.

---

## 5. 페이싱 (PACE_FAST vs PACE_DEMO)

```python
PACE_FAST = {  # 검증용
    "after_trigger": 14.0,    # LLM 응답 대기
    "after_act3": 12.0,       # all_members_selected pipeline
    "view_pause": 3.0,        # 사용자가 카드 볼 시간
    ...
}
PACE_DEMO = {  # 시연
    "after_trigger": 16.0,
    "after_act3": 16.0,
    "view_pause": 3.5,
    ...
}
```

**Gemini API rate limit 발생 시 fallback 패턴** 사용 → 응답 시간 변동성 큼. 폴링 deadline을 충분히 (예: `pace["after_trigger"] * 4` = 56s).

---

## 6. 디버그 시 체크리스트

| 증상 | 1차 확인 |
|---|---|
| `consensus_ready` 안 옴 | `room_members` 카운트 SQL 확인. 중복 게스트? |
| 추천 카드 안 뜸 | `docker logs maedeup-api \| grep TIMING` — pipeline 어느 노드까지 갔는지 |
| 카드 텍스트 이상 (영문 등) | `holidays.KR(language="ko")` 확인. label format 코드 검토 |
| 장소 카드 안 뜸 | `_ML_AVAILABLE` 플래그 + Gemini API key valid 확인 |
| ACT 6 학습 안 됨 | `DEMO_FALLBACK_ENABLED` 환경변수 + `ai_memories` 테이블 SQL 확인 |
| chromium 클릭 무반응 | `b.offsetParent` null? `display: none` 부모 있는지. iframe 안 element는 별도 frame() 필요 |

`docker logs --since 5m maedeup-api 2>&1 | grep -iE "TIMING|REJECTED|memory_ext|consensus"` 가 만능 디버그 명령.

---

## 7. 권장 작업 흐름

새 자동화 시나리오 만들 때:

1. **선행 — 수동 1회**: chromium으로 풀 흐름 직접 클릭. 어느 버튼이 어디 있고 어떤 텍스트인지 메모.
2. **API/WS 흐름 분리**: 게스트 시뮬은 WS 직송신이 빠름. 호스트 시각화는 chromium UI 클릭.
3. **단위 함수화**: `click_button_by_text(page, text)`, `fill_input(page, placeholder, value)`, `wait_for_button(page, contains)`. 자동화 스크립트 = 이 헬퍼 호출들의 시퀀스.
4. **PACE_FAST부터**: 빠른 검증 → 흐름 통과되면 PACE_DEMO로 페이스 조정.
5. **검증 후 v2 보존 + v3 추가**: 기존 자동화 스크립트는 건드리지 말고 새 파일. 회귀 대비.
6. **`.rehearsal-shots/` snapshot 임시 추가**: 디버그 끝나면 빼고, 시연용은 깔끔하게.

---

## 8. 알려진 한계 (2026-05-13 기준)

- **TimeBar mine row 잘림**: 1440px 폭에서 호스트 selection이 우측 잘림. 1920px 이상 권장.
- **호스트 GCal busy 영향 큼**: ACT 2 추천 후보가 호스트 일정과 충돌하면 제거됨. 시연 일정 정리 또는 멘트 우회.
- **`/place patch` 흐름이 LangGraph 우회**: ACT 5 장소 확정 후 `memory_extraction` 자동 호출되지 않음 → `meetings.py:patch_meeting_place` 끝에 `_spawn_personal_data_extraction` fire-and-forget으로 우회 (commit `3eef0d3`).
- **`quick_classify` 정규식 단축 안 잡힘**: "강남에서 다 같이 갈만한 한식집" 같은 자연어가 정규식에 안 잡혀 ~37초. 시연 멘트 "빠르게"로 모호.

새 한계 발견 시 이 섹션에 append. 자동화 작성 시 참고.
