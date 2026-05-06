# 매듭 파이프라인 감사 — 확정 이슈 목록

작성 시작: 2026-05-05
상태: 진행 중 (감사 세션마다 누적)

## 사용 규칙

- **확정**: 코드/git/실측으로 검증 끝난 이슈만 등록. 추정·의심 단계 이슈는 본 문서 X, 다이어그램의 `[의심점 X]` 라벨로만 둠
- **수정 시점**: 즉시 고치지 않고 **누적** → 한번에 PR로 묶어서 수정
- **승격 경로**: 다이어그램 의심점 (A/B/C/D/E) → 코드 검증 → 본 문서 등록 → 일괄 수정

## 확정 이슈

### 해결점 A. judge_stalemate 과조기 발동 (임계값 over-correction)

- **상태**: 🔴 확정 (git + 코드 검증 완료)
- **위치**: `backend/app/api/ws/social.py:593`
- **증상**:
  - 채팅 3개만 모이면 LLM 교착 판정 호출 → 컨텍스트 부족
  - false positive 위험 → 의심점 E ("배너 뜨고 카드 미생성") 빈도 증가
  - 분당 최대 1회 LLM 호출 (옛날 5분/회 → 1분/회로 5x 증가 가능)
- **원인 (git 추적)**:
  - 커밋 `52c0559` (2026-04-20) "feat: LLM judge 기반 채팅방 자동간섭 탐지"
  - 두 가지를 동시에 변경:
    1. 카운팅 범위: meeting_schedule intent만 → **모든 user 메시지**
    2. 임계값: **5 → 3**
  - 원래 버그는 "intent 분류된 메시지만 세서 짧은 응답('안돼','그러게')이 누락 → threshold 5 도달 못함"
  - 카운팅 범위 확대만으로 옛 버그 해결됨. 임계값까지 낮춘 건 **over-correction**
- **결정 수정안**: **옵션 C (임계값 4)**
  - `if count < 3` → `if count < 4` (1줄 변경)
  - 카운팅은 전체 user 메시지 그대로 유지 (옛 버그 fix 보존)
  - 근거: 5는 보수적, 3은 공격적, 4가 균형. 옛 시연 시나리오 "5회"와 큰 괴리 없음
- **부수 작업**:
  - 시연 시나리오 문서 "5회" 표현 → "3~4번 대화 후" 같은 부드러운 표현으로
  - 다이어그램 `01-trigger-rules.mmd` 게이트 4 라벨에 해결점 A 표시 (완료)

---

### 해결점 B. 배너 시스템 재설계 (AI 패널 통합)

- **상태**: 🔴 확정 (방향 결정됨, 옵션 3)
- **위치**:
  - 백엔드 발행: `backend/app/api/ws/social.py:549~561` (`intent_detected` emit, 게이트 1)
  - 프론트 수신: `frontend/src/hooks/useSocialWebSocket.ts:511~513`
  - 외부 노출: `useSocialWebSocket.ts:835~836`
  - 데드 코드: `frontend/src/components/meeting/ChatPane.tsx:92~93` (destructure만, 사용 0회)
- **증상**:
  - 게이트 1만 `intent_detected` 발행 (백엔드 단일 지점)
  - 프론트는 수신·state 저장하나 **렌더 코드 없음** → 사용자가 못 봄
  - 게이트 2/4 (LLM 5~15초 대기 발생) 동안 UX 피드백 0
  - 비용만 발생, UX 효과 0
  - 설계 아이러니: 짧은 게이트(1, ~100ms)에만 배너, 긴 게이트(2/4, 5~15s)는 무음
- **원인**:
  - 옛 설계 잔재 — 배너 UI 만들다 만 흔적
  - 페이로드에 `trigger_reason`/`message_text` 없어 게이트별 차별화 불가
  - dismiss 콜백까지 정의돼 있으나 미사용
- **결정 수정안**: **옵션 3 — AI 패널 활용**
  1. **게이트 1 `intent_detected` 발행 제거** (`social.py:545~561` 삭제)
  2. **게이트 2/4 발화 시 AI 패널에 "분석 중" 메시지 즉시 추가**
     - `agent.py`에서 trigger 수신 직후 `_publish_agent_message` 호출
     - `trigger_reason`별 문구 차별화:
       - `conclusion_detected` → "결론이 나오는 것 같네요, 정리할게요"
       - `stalemate_judged` → "대화가 길어지네요, AI가 정리해볼게요"
       - `all_members_selected` → "모두 시간 선택 완료! 일정 확정할게요"
       - `direct_request` → 별도 메시지 불필요 (사용자 입력 자체가 표시됨)
  3. LangGraph 카드 발행 시 "분석 중" 메시지 위에 카드 자연스럽게 누적
  4. 프론트 `useSocialWebSocket.ts`의 `detectedIntent`·`dismissIntent`·`IntentDetectedPayload` 관련 코드 제거 (데드 코드 정리)
  5. `ChatPane.tsx` 92~93줄 destructure 제거
- **영향 범위**:
  - 백엔드: `social.py` (배너 emit 제거), `agent.py` (분석중 메시지 추가)
  - 프론트: `useSocialWebSocket.ts` (배너 state·payload 제거), `ChatPane.tsx` (destructure 제거)
- **시연 효과**: 5~15초 LLM 대기 동안 AI 패널에 진행 메시지 → 사용자가 "AI가 일하는 중"임을 인지, 신뢰 ↑
- **다이어그램**: `01-trigger-rules.mmd` 게이트 1 + BAN_OUT 라벨에 해결점 B 표시

---

## 진행 중 (의심 단계)

코드/git 검증 끝나면 본 문서 위쪽 "확정 이슈"로 승격. 수정 방향이 결정되면 해결점으로 변환.

| ID | 요약 | 다이어그램 위치 | 검증 상태 |
|---|---|---|---|
| A | `_analyze_conversation` 1+2회차 중복 호출 | 02-langgraph-flow.mmd 진입부 | 검증 완료 (해결점 D로 승격됨) |
| B | `date_hints` 3중 쓰기 (entity → slot → conflict) | 02-langgraph-flow.mmd 노드3·4 | 검증 완료 (보류 — 묵시적 컨벤션, 시연 영향 미미) |
| C | `_is_specific_iso_date` 자연어 거부 누락 | 02-langgraph-flow.mmd 노드3 | 검증 완료 (해결점 F로 승격됨) |
| D | fast-skip 짧은 명령 시 거부 정보 무시 | 02-langgraph-flow.mmd 노드3 | 검증 완료 (해결점 E로 승격됨) |
| E | stalemate=false 시 배너만 잔류 (사실 배너 자체가 안 뜸) | 01-trigger-rules.mmd 게이트 4 | 검증 완료 (해결점 B로 흡수됨) |
| G | trigger_reason 다운스트림 차별화 부재 | 01-trigger-rules.mmd PUB 이후 | 검증 완료 (해결점 C로 승격됨) |

**모든 의심점 검증 완료** (2026-05-06)

### 의심점 B 검증 결론 (보류)

- **실측 결과**: 진짜 버그가 아니라 **묵시적 컨벤션**
  - `state["date_hints"]` = 최종 vote_card 입력 후보 (top-level)
  - `extracted_entities["date_hints"]` = Gemini 1차 raw 데이터 (nested)
  - 두 필드가 의도적으로 분리돼 있으나 코드/주석에 명시 안 됨
- **싱크 동기화 포인트 1곳뿐**: `:2365~2367` (거부 날짜 필터 직후) — 거부 날짜 있을 때만 발동하는 비대칭
- **conflict 분기 덮어쓰기 (`:2628`)**: 의도적 (교착 옵션을 vote_card 후보로 강제) — 버그 아님
- **보류 이유**:
  - 해결점 E 적용 시 단축 경로는 slot_filling 자체 스킵 → W8 (`:2628`) 미발동
  - 채팅방 자동 트리거 경로에서만 잠재 위험, 시연 임팩트 낮음
  - 리팩터링 비용 (~30곳 수정) 대비 시연 효용 낮음
- **남은 미세 위험**: 미래 코드 변경 시 컨벤션 인지 실패로 인한 버그 가능성. 시급도 낮음

---

### 해결점 C. trigger_reason 기반 LangGraph 조건부 진입 (옵션 4)

- **상태**: 🔴 확정 (설계 원칙 결정됨, 02 감사 시 호환성 체크리스트로 활용)
- **원본 의심점**: G (trigger_reason 다운스트림 차별화 부재 — 지금은 인사말 차별화만)
- **위치 (영향 범위)**:
  - GraphState 정의 (`langgraph_pipeline.py:140`)
  - LangGraph 그래프 정의 (`langgraph_pipeline.py:run_pipeline 진입부`)
  - `agent.py:_run_auto_trigger_pipeline` 사전 처리
  - 노드별: entity_extraction, slot_filling, function_calling, supervisor_validation
- **증상 (수정 전)**:
  - `conclusion_detected`("콜!"): 이미 합의됐는데도 vote_card 생성 가능 → 모순
  - `all_members_selected`: TimeBar 데이터 완비됐는데도 vote 거쳐서 maedeup으로 감
  - 트리거별로 진입부터 `intent_detection`(Gemini), `entity_extraction`(Gemini)까지 다 돌아 헛수고 (~3~5초 낭비)
  - LangGraph의 진정한 강점(조건부 그래프) 미활용
- **결정 수정안**: **옵션 4 — entry conditional edge + supervisor 분기 확장**

  #### 1. GraphState 필드 추가
  ```python
  trigger_reason: Literal["conclusion_detected", "all_members_selected",
                          "stalemate_judged", "direct_request"]
  bypass_function_calling: bool  # supervisor가 활용
  ```

  #### 2. agent.py 사전 처리
  ```python
  state["trigger_reason"] = trigger_reason
  if trigger_reason == "conclusion_detected":
      state["intent"] = "meeting_schedule"
  elif trigger_reason == "all_members_selected":
      state["intent"] = "meeting_schedule"
      state["extracted_entities"] = build_entities_from_timebar(room_id)
  ```

  #### 3. LangGraph entry conditional edge (강화 2026-05-06)
  ```python
  graph.add_conditional_edges(START, route_by_trigger, {
      "entity_extraction": "entity_extraction",     # conclusion / stalemate (노드1 스킵)
      "slot_filling": "slot_filling",               # all_members (노드1+3 스킵)
      # unknown trigger_reason → 명시적 ValueError (dead path 방지)
  })
  ```
  - **노드1·2 완전 제거 (강화 결정)**:
    - 모든 자동 트리거 (stalemate/conclusion/all_members)가 노드1 스킵
    - direct_request는 quick_classify (해결점 E)에서 별도 처리 → 노드1 안 거침
    - 결과: 노드1·2가 어떤 트리거에서도 도달 불가 = dead code
    - **함수 정의 자체 제거** (`intent_detection`, `general_response`, `classify_intent` 호출 자리)
    - 미래 새 trigger_reason 추가 시 라우팅 매핑 누락이 명시적 ValueError로 발견됨 (silent fallback 위험 차단)
  - **stalemate_judged 노드1 스킵 (확장 결정)**:
    - judge_stalemate (Gemini)가 최근 10개 메시지 보고 이미 intent 분류 완료
    - 페이로드 `intent` 필드에 박혀 agent.py까지 흘러옴
    - 노드1의 classify_intent (RAG + Gemini fallback)는 같은 메시지 단일 단위로 재분류 → 중복
    - 0.7 임계 미만으로 떨어지면 judge "yes intervene"과 노드1 "general" 모순 위험
    - 노드1 스킵 시 ~1초 절약 + 모순 위험 제거
    - judge_stalemate 결과 신뢰 (이미 LLM이 컨텍스트 보고 판단)

  #### 4. supervisor_validation 분기 확장
  ```
  trigger_reason == "conclusion_detected"        → maedeup_card 직행 (vote+place 스킵)
  trigger_reason == "all_members_selected"        → place_recommendation
  vote 가능 (stalemate / direct)                  → vote_card_creation
  intent == "place_suggestion"                    → place_recommendation
  ```

  #### 5. 노드별 입력 계약 변경
  | 노드 | 변경 사항 |
  |------|---------|
  | entity_extraction | `state["intent"]` 없을 때 fallback (라우터에서 미리 주입하지만 안전망) |
  | slot_filling | `state["extracted_entities"]` 없을 때 라우터 주입값 사용 |
  | function_calling | `bypass_function_calling` 플래그 보고 GCal 스킵 가능 |
  | supervisor_validation | trigger_reason 4-way 분기 |
  | vote_card_creation | conclusion/all_members 시 진입 안 됨 |

- **시간 절약 (예상)**:
  - conclusion_detected: ~1초 (intent_detection 스킵)
  - **stalemate_judged: ~1초 (intent_detection 스킵, 확장 후)**
  - all_members_selected: ~3초 (intent + entity 스킵)
  - 추가로 function_calling 스킵 시 ~2초

- **02 감사에 미치는 영향 (체크리스트)**:
  의심점 A/B/C/D 검증 시 해결점 C 호환성 확인:
  - [ ] **A** (`_analyze_conversation` 중복): 라우터에서 호출 시점 흡수해 1회로
  - [ ] **B** (`date_hints` 3중 쓰기): entity vs slot 책임 재정의 (라우터 주입과 충돌 없게)
  - [ ] **C** (자연어 거부 누락): entity_extraction 헬퍼 문제, 해결점 C와 독립
  - [ ] **D** (fast-skip): entity_extraction 분기 — 라우터가 entity로 보낸 후 fast-skip 발동 시 거부 정보 누락 가능, 같이 봐야

- **작업 분량**: 150~200줄 (GraphState + 라우터 + 사전 처리 + 노드 fallback + 그래프 정의 + 테스트 4 케이스)
- **다이어그램**: `04-option-c-routing.mmd` (신규, 옵션 4 구조 시각화), `01-trigger-rules.mmd` WARN_G → 해결점 C 참조

---

### 해결점 E. direct_request 전용 단축 경로 신설

- **상태**: 🔴 확정 (설계 결정됨, 의심점 D 흡수)
- **원본 의심점**: D (fast-skip 짧은 명령 시 거부 정보 무시)
- **위치 (영향 범위)**:
  - `backend/app/services/langgraph_pipeline.py:2403~2435` (기존 fast-skip 블록 제거)
  - `backend/app/api/ws/agent.py` `_run_auto_trigger_pipeline` 진입부 (분기 신설)
  - LangGraph 그래프 정의 (단축 서브그래프 추가)
  - `quick_classify` 신규 함수 (정규식 + Gemini fallback)
- **증상 (수정 전)**:
  - "일정 추천해줘" 같은 짧은 명령형 입력 시 fast-skip 발동 → entity_extraction 자체 스킵
  - 직전 채팅의 거부 발언("토요일 안 돼") 무시 → 거부된 날짜가 vote_card에 그대로 노출
  - direct_request는 사용자가 명시적으로 AI를 부른 것 → intent 분류·slot 누적 불필요한데도 풀 7노드 풀체인 탐 (5~15초)
- **결정 수정안**: **단축 경로 신설 (B + C 옵션 결합)**

  #### 1. quick_classify 함수 신설
  ```python
  # 1차: 정규식 매칭 (~ms, 무료)
  SCHEDULE = r"(일정|날짜|언제|시간).*(추천|뽑|정리|제안|잡)"
  PLACE = r"(장소|어디|맛집|카페|식당|근처).*(추천|뽑|정리|제안)"
  # 2차: 정규식 모호 시 Gemini 1-shot 분류 (~1s)
  # 출력: {"schedule", "place", "schedule+place", "general"}
  ```

  #### 2. agent.py direct_request 분기
  ```python
  if trigger_reason == "direct_request":
      kind = await quick_classify(message)
      if kind == "general":
          await run_general_response(state)  # Gemini chat만, ~2s
          return
      state["direct_request_kind"] = kind  # "schedule" | "place" | "schedule+place"
      await run_shortcut_pipeline(state)
  ```

  #### 3. 단축 LangGraph 서브그래프
  ```
  schedule          → entity_extraction → vote_card_creation
  place             → entity_extraction → place_recommendation
  schedule+place    → entity_extraction → vote_card → place_recommendation → maedeup_card
  ```

  #### 4. 스킵되는 노드
  | 노드 | 이유 |
  |---|---|
  | intent_detection | direct_request는 의도 자명 |
  | slot_filling | 1-shot 작업, 슬롯 누적 불필요 |
  | function_calling | entity_extraction이 직접 처리 (또는 vote_card 안전망) |
  | memory_extraction | 응답 후 비동기로 분리 (또는 스킵) |

  #### 5. 기존 fast-skip 블록 제거
  - `langgraph_pipeline.py:2403~2435` 삭제
  - 단축 경로에서 entity_extraction은 항상 풀로 돌고, Gemini 호출은 패턴 매칭 1차로 충분하면 자동 스킵 (`_extract_entities_from_context:1001~1010`)

- **시간 절약 (예상)**:
  - 기존 5~15초 → **3~5초**
  - schedule: ~4s (entity ~3s + vote_card ~0.5s)
  - place: ~5s (entity ~3s + place_recommendation ~2s)
  - general: ~2s (Gemini chat만)

- **시연 효과 (ACT 2)**:
  - "토요일 안 돼" → "일정 추천해줘" → 토요일 제외된 vote_card
  - 해결점 F와 결합해야 자연어 거부도 반영됨 (단독으론 ISO 거부만 반영)

- **해결점 C와의 관계**:
  - 해결점 C (트리거별 진입): 채팅방 자동 트리거 (`stalemate`/`conclusion`/`all_members`)용
  - 해결점 E (단축 경로): AI 패널 명시 입력 (`direct_request`)용
  - **공존 가능**: 진입점이 다름 (자동 vs 명시). 두 경로가 LangGraph 그래프에 병렬 정의됨

- **작업 분량**: 150~200줄
- **다이어그램**: `02-langgraph-flow.mmd` 단축 경로 추가, `04-option-c-routing.mmd` 갱신 (E 경로 별도)

---

### 해결점 F. 자연어 거부 날짜 → ISO 변환 헬퍼

- **상태**: 🔴 확정 (설계 결정됨, 의심점 C 흡수)
- **원본 의심점**: C (`_is_specific_iso_date` 자연어 거부 누락)
- **위치**:
  - `backend/app/services/langgraph_pipeline.py:2351, 2486` (필터 로직 교체)
  - `_is_specific_iso_date` 호출 자리에 신규 헬퍼 `_resolve_rejected_date`
- **증상 (수정 전)**:
  - Gemini가 `rejected_dates`를 자연어로 반환 시 (`"금요일"`, `"다음 금요일"`, `"5월 9일"`) 모두 필터에서 드랍
  - 같은 자연어가 `conflict_options`엔 살아남아 모순
  - 시연 ACT 2 직격: 사용자 거부 발언이 카드에 무시됨
- **원인**:
  - LLM 응답이 ISO 형식 보장 안 됨 (프롬프트로 강제해도 불안정)
  - 필터가 "엄격한 YYYY-MM-DD만 통과" 정책 → 자연어 누락
- **결정 수정안**: **자연어→ISO 변환 헬퍼 추가**
  ```python
  def _resolve_rejected_date(raw: str, today_kst: date) -> str | None:
      # 1. 이미 ISO이면 그대로
      if _is_specific_iso_date(raw): return raw
      # 2. "금요일" / "다음 금요일" / "이번주 토요일" 처리
      # 3. "5월 9일" / "5/9" 처리 (연도 미지정 시 KST 오늘 기준)
      # 4. 기존 _pattern_extract_entities 로직 재활용
      # 5. 변환 실패 시 None 반환 → 드랍 (현재 동작 유지)
  ```
- **필터 자리 변경**:
  ```python
  # before
  if not _is_specific_iso_date(d): continue
  # after
  resolved = _resolve_rejected_date(d, today_kst)
  if not resolved: continue
  d = resolved
  ```
- **2351줄, 2486줄 두 군데 동시 수정** (entity 본 처리 + slot conflict 흡수 처리)
- **테스트 케이스**:
  - "금요일" → 다음 금요일 ISO
  - "다음 금요일" → 다음주 금요일 ISO
  - "5월 9일" → 2026-05-09
  - "5/9" → 2026-05-09
  - "잘 모르겠음" → None (드랍)
- **작업 분량**: 30~50줄 (헬퍼 + 필터 자리 교체 + 테스트)
- **시급도**: 높음 (해결점 E와 결합 필수, 둘 다 있어야 ACT 2 완성)
- **다이어그램**: `02-langgraph-flow.mmd` 노드3 라벨에 해결점 F 표시

---

### 해결점 G. trigger_message_text 앵커 (intent_detection race 방지)

- **상태**: 🔴 확정 (옵션 B 채택)
- **원본 의심점**: 본 세션 (2026-05-06) 신규 발견 — 의심점 ID 미부여
- **위치**:
  - `backend/app/api/ws/agent.py:108~194` (`_run_auto_trigger_pipeline` — `trigger_content` 받지만 미사용)
  - `backend/app/services/langgraph_pipeline.py:2235~2238` (intent_detection의 latest user message 추출)
  - `langgraph_pipeline.py:_initialize_state` (state 초기화 진입부)
- **증상 (수정 전)**:
  - 자동 트리거 발화 후 파이프라인 진입까지 ~2초 갭 존재 (analyze_conversation + DB 재read)
  - 그 사이 다른 user가 짧은 메시지("ㅇㅋ", "ㅋㅋ") 보내면 DB의 last user msg 바뀜
  - `MessageReader.load_agent_context` (`agent.py:184`)가 파이프라인 진입 직전 DB 재read → 새 메시지가 latest가 됨
  - intent_detection이 트리거 메시지가 아닌 새 메시지로 의도 분류
  - "ㅇㅋ" → general (신뢰도 낮음) → 0.7 임계 미달 → 노드2 general_response 분기 → 카드 안 만들어짐
- **타임라인 (실측 추정)**:
  ```
  T=0ms    유저A "토요일 안 돼" → DB INSERT
  T=10ms   social.py stalemate 판정 → ai_auto_trigger 발행
  T=50ms   _analyze_conversation 시작 (DB 1차 read, 트리거 메시지 포함)
  T=2000ms _analyze_conversation 종료
  T=2010ms MessageReader.load_agent_context (DB 2차 read)  ← 여기서 race
  T=2500ms intent_detection 노드 → message_records[-1] 읽음
  ```
- **NX lock 한계**:
  - lock은 같은 trigger 중복 처리만 막음 (60초 TTL)
  - 새 user 메시지의 DB INSERT는 못 막음 → race 가능
- **trigger_content는 이미 전달되지만 미사용**:
  - `agent.py:108`에서 `trigger_content: str` 인자로 받음
  - `agent.py:437~483`에서 trigger payload에서 추출해 _run_auto_trigger_pipeline에 넘김
  - 하지만 `_run_auto_trigger_pipeline` 내부에서 한 번도 안 읽음 → 데드 인자
- **결정 수정안**: **옵션 B — trigger_message_text를 state에 박아넣기**
  1. `_initialize_state`에 `trigger_message_text: str | None` 필드 추가
  2. `_run_auto_trigger_pipeline`이 `slot_context["trigger_message_text"] = trigger_content`로 주입
  3. `intent_detection`(`:2235~2238`)에서:
     ```python
     # before
     for message in reversed(state["message_records"]):
         if message.get("role") == "user" and message.get("content"):
             latest_user_message = message["content"]
             break
     # after
     latest_user_message = state.get("trigger_message_text") or ""
     if not latest_user_message:
         # fallback (직접 호출 케이스 등)
         for message in reversed(state["message_records"]):
             if message.get("role") == "user" and message.get("content"):
                 latest_user_message = message["content"]
                 break
     ```
- **다른 노드 영향 (의도적으로 변경 안 함)**:
  - entity_extraction, slot_filling 등은 여전히 message_records의 latest 사용
  - 이들 노드는 채팅 컨텍스트 전체를 보고 슬롯 채우므로 race 영향 적음
  - intent_detection만 "트리거 시점 의도가 무엇이었나"를 분류해야 하므로 앵커 필요
- **옵션 비교 (선택지)**:
  | 옵션 | 작업 | 효과 |
  |---|---|---|
  | A. trigger_message_id 앵커 (DB 재조회) | ~50줄 (모든 노드 변경) | 정확하지만 비용 큼 |
  | **B. trigger_content state 주입** | ~10줄 (intent_detection만) | 간단, race 영향 최대 노드만 보호 |
  | C. message_records 자체를 trigger 페이로드에 동봉 | ~30줄 + 페이로드 ↑ | DB read 절약 + 완벽 차단 |
- **direct_request 경로 (해결점 E)와의 관계**:
  - 단축 경로는 intent_detection 자체를 스킵 → race 영향 없음
  - 해결점 G는 **자동 트리거 경로 전용** 보호
- **작업 분량**: ~10~15줄 (state 필드 추가 + agent.py 주입 + intent_detection fallback)
- **시급도**: 중 (시연 직격은 아니나 우발적 터치 가능)
- **다이어그램**: `02-langgraph-flow.mmd` AUTO_RUN 박스 라벨에 "trigger_message_text 주입" 명시

---

### 해결점 H. _analyze_conversation 윈도우 확대 + 요약 prepend

- **상태**: 🟡 확정 (시급도 낮음, 운영 단계 risk)
- **원본 의심점**: 본 세션 (2026-05-06) 신규 발견
- **위치**:
  - `backend/app/services/langgraph_pipeline.py:3977` (`limit(20)` 매직 넘버)
  - `backend/app/services/langgraph_pipeline.py:3961~3990` (_analyze_conversation 본체)
  - `backend/app/api/ws/agent.py:646~661` (별도 conversation_summary 생성, 미활용)
- **증상 (수정 전)**:
  - DB에서 최근 20개만 로드 → 21번째 이전의 정보 사라짐
  - 시나리오: A가 메시지 11에서 "토요일 안 돼" → 12~31 추가 대화 → 31에서 "일정 추천해줘" 트리거
    → _analyze_conversation은 12~31만 보고 거부 발언 못 봄
    → vote_card에 토요일 들어갈 위험
  - **시연 영향 낮음** (시연 8턴 내외) / **운영 risk 명확** (실사용자 100+ 메시지 일상)
- **현재 부분 보완 (불완전)**:
  - `agent.py:646~661`이 메시지 10/20/30… 마다 `_build_conversation_summary` 호출
  - 결과를 `slot_context["conversation_summary"]`에 저장
  - **한계 4가지**:
    1. 요약 입력 윈도우도 `limit=10` (오히려 더 짧음)
    2. `_analyze_conversation`은 conversation_summary를 **읽지 않음**
    3. intent_detection (`:2267~2273`)에서만 prepend로 활용
    4. `_build_conversation_summary`는 자유 텍스트 생성 — `rejected_dates` 같은 구조화 신호 추출 안 함
- **결정 수정안**: **2단계 적용**

  #### Phase 1 — 윈도우 확대 (1줄 변경, 시급도 낮음)
  ```python
  # langgraph_pipeline.py:3977
  .limit(20)  →  .limit(50)
  ```
  - 비용: 토큰 ~600 추가 (Gemini 2.5 Flash 1M 컨텍스트 여유)
  - 효과: 50번째 이전까지는 안전. 일반 사용 패턴 대부분 커버

  #### Phase 2 — 요약 prepend (선택)
  - `_analyze_conversation`에 `conversation_summary` 인자 받기
  - 프롬프트 앞에 `[이전 대화 요약]: ...` 섹션 추가
  - LLM이 50개 윈도우 + 요약을 같이 보고 signals 추출
  - `slot_context["conversation_summary"]`를 agent.py가 _analyze_conversation 호출 시 전달

  #### Phase 3 (참고만, 작업 X) — 거부 발언 전용 캐시
  - 정규식 매칭("안 돼", "못 해" + 요일/날짜)으로 메시지마다 Redis hash 누적
  - _analyze_conversation 호출 시 캐시 데이터도 함께 LLM에 전달
  - 가장 robust하나 ~150줄 작업 — 시연/운영 직격 위험 발생 시에만 진행

- **시연 영향**: 거의 없음 (시나리오가 짧음)
- **운영 영향**: 메시지 100+ 누적 방에서 거부 정보 누락 빈도 증가
- **작업 분량**:
  - Phase 1: 1줄
  - Phase 2: ~30줄 (인자 추가 + 프롬프트 섹션 + agent.py 호출 시 전달)
- **시급도**: 낮음 (운영 단계에서 리포트 누적 후 판단)
- **다이어그램**: `02-langgraph-flow.mmd` A1 박스 라벨에 "윈도우 50개 (해결점 H)" 표시 가능

---

### 해결점 I. slot_filling 트리거별 분기 차별화

- **상태**: 🔴 확정 (설계 결정됨, 본 세션 2026-05-06 신규 발견)
- **위치**: `backend/app/services/langgraph_pipeline.py:2542~2780` (`slot_filling` 함수 본체)
- **증상 (수정 전)**:
  - 노드4 slot_filling이 trigger_reason 무관하게 통일된 흐름 처리
  - 트리거별 의미가 완전히 다른데 같은 분기 트리 사용
  - **conclusion_detected 어색 안내**: "콜!"만 보낸 케이스에서 슬롯 부족 시 `partial_info_acknowledged` 분기 → "장소 나오면 정리해드릴게요" 안내 → **결론 났는데 더 입력하라고 함 = 모순**
  - **all_members_selected 무의미 분기**: TimeBar는 합의 결과인데 conflict 체크 + 중복 DB 조회 발생
  - **stalemate_judged만 현재 conflict 분기에 최적화**: 다른 트리거는 우회/통과만
- **결정 수정안**: **옵션 A — trigger_reason 보고 분기 차별화**

  #### 분기표 (8가지)
  | trigger_reason | 슬롯 상태 | 처리 | 출력 status |
  |---|---|---|---|
  | stalemate_judged | conflict 있음 | 현재 conflict 분기 그대로 (중재 메시지 + conflict_options→date_hints 변환) | `multi_date_vote` |
  | stalemate_judged | conflict 없음 (드뭄) | 일반 슬롯 충족도 체크 fallback | (현재와 동일) |
  | conclusion_detected | `has_date && has_place` | 결론 확인 메시지 + 즉시 진행 | `slots_filled` |
  | conclusion_detected | `has_date xor has_place` (한쪽만) | 디폴트 채움 (headcount=4) + 진행 | `slots_filled_with_defaults` |
  | **conclusion_detected** | **슬롯 0** | **silent abort (정규식 false positive로 판정)** | `conclusion_false_positive` 신규 |
  | all_members_selected | `place_hint` 있음 | conflict 체크 스킵 + 즉시 진행 | `location_first_ready` |
  | all_members_selected | place 없음, 선호 `best_location` 있음 | 보강 + 진행 | `location_first_ready` |
  | **all_members_selected** | **place 없음, 선호 없음** | **maedeup_card 부분 발행 (시간만 확정, 장소 placeholder)** | `time_only_ready` 신규 |

  #### Q1 결정 — conclusion_detected 슬롯 0 = silent abort
  - **근거**: 슬롯 0 = `_is_conclusion` 정규식이 false positive로 발화했다는 신호
  - "결론 잘 들었어요" 같은 안내 발행하면 결론 아닌데 결론 났다고 우김 = 모순
  - 사용자에게 메시지 0건, 카드 0건. NX lock 해제 + 다음 트리거 정상 받기
  - **로그 카운트**: 정규식 false positive 빈도 추적 → 자주 발생하면 정규식 정밀화 신호
  - 비용: 분석 시간 ~5초 + LLM 1회 (sunk cost)

  #### Q2 결정 — all_members + 장소 없음 = maedeup_card 부분 발행
  - **근거**: TimeBar로 시간 확정됐으니 사용자 노력에 즉시 보상 가시화
  - 장소 영역만 비워두고 placeholder 표시 → 이후 장소 정해지면 카드 갱신
  - 페이로드 예시:
    ```json
    {
      "type": "maedeup_card",
      "date": "2026-05-09",
      "time": "19:00",
      "place": null,
      "place_pending": true,
      "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
      "headcount": 4,
      "meeting_type": null,
      "calendar_registered": false
    }
    ```
  - **프론트 변경 필요**: `MaedeupCard` 컴포넌트가 `place_pending=true` 케이스 렌더 지원

  #### 신규 status 라벨 2개
  - `conclusion_false_positive`: silent abort용. emit 단계에서 카드 발행 0건 처리
  - `time_only_ready`: 부분 maedeup_card 발행 분기

  #### 코드 구조 (제안)
  ```python
  async def slot_filling(state: GraphState) -> GraphState:
      _update_slot_state(state, state["extracted_entities"])
      pref_data = await _load_meeting_preferences(state)
      _enrich_with_preferences(state, pref_data)

      trigger = state.get("trigger_reason")

      if trigger == "stalemate_judged":
          return await _slot_filling_stalemate(state, pref_data)
      elif trigger == "conclusion_detected":
          return await _slot_filling_conclusion(state, pref_data)
      elif trigger == "all_members_selected":
          return await _slot_filling_all_members(state, pref_data)
      else:
          return await _slot_filling_default(state, pref_data)
  ```
  - 분기 함수 각 25~40줄 → 총 ~120~150줄

- **시연 임팩트**:
  - conclusion 어색 안내 해소 (시연 ACT 3 합의 단계)
  - all_members + 장소 없음 시 즉시 부분 카드 → 사용자 만족도 ↑

  #### 하류 노드 영향 (필수 동반 변경)

  새 status 라벨 (`conclusion_false_positive`, `time_only_ready`)을 후속 4개 노드가 인식해야 정상 동작.

  **노드5 function_calling**:
  ```python
  if state["status"] == "conclusion_false_positive":
      return state  # silent abort, GCal/Kakao 호출 0
  if state["status"] == "time_only_ready":
      state["calendar_free_slots"] = []
      state["place_search_results"] = []
      return state  # 외부 API 모두 스킵, ~2초 절약
  ```

  **노드6 supervisor_validation** (해결점 C 분기에 2갈래 추가):
  ```python
  if status == "conclusion_false_positive":
      return state  # 카드 생성 0건, END
  if status == "time_only_ready":
      state["next_node"] = "maedeup_card_creation"
      state["partial_mode"] = "time_only"
      return state
  # 기존 4-way 분기 (해결점 C) 그대로
  ```

  **노드9 maedeup_card_creation** (partial_mode 지원):
  ```python
  if state.get("partial_mode") == "time_only":
      payload = {
          "type": "maedeup_card",
          "date": state["date_hint"],
          "time": ...,
          "place": None,
          "place_pending": True,
          "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
          "headcount": state.get("headcount"),
          "calendar_registered": False,  # GCal 등록 보류 (장소 채워질 때)
      }
      state["maedeup_card_payload"] = payload
      return state
  # 기존: 정상 maedeup_card 발행 + GCal event INSERT
  ```

  **emit (agent.py)**:
  ```python
  if status == "conclusion_false_positive":
      logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
      return  # 카드/메시지 발행 0
  ```

  **프론트 MaedeupCard**:
  - `place_pending=true` 케이스 렌더 (장소 영역 placeholder "🔍 장소 정해지면...")
  - GCal 등록 안 됨 표시
  - 추후 장소 추가 시 카드 갱신 → **해결점 J 의존**

  #### 영향 받지 않는 노드
  - 노드7 vote_card_creation: 새 status에서 도달 안 함
  - 노드8 place_recommendation: 새 status에서 도달 안 함
  - 노드10 memory_extraction: 메시지 분석은 의미 있음, 그대로 실행

  #### 잠재 문제
  - **silent abort 시 부수 필드 정리**: `awaiting_user_reply=False`, `new_assistant_messages=[]` 명시 비우기
  - **카드 갱신 의존성**: time_only 카드가 한 번 발행된 후 장소 채워졌을 때 같은 카드 update 메커니즘 필요 → **해결점 J에서 처리**

- **작업 분량 (해결점 I 단독)**:
  - 백엔드 slot_filling 분기: ~120~150줄
  - 백엔드 하류 노드 (function_calling/supervisor/maedeup_card/emit): ~75줄
  - 프론트 MaedeupCard partial 렌더: ~30줄
  - **소계: ~225~255줄**
  - **+ 해결점 J (카드 갱신 메커니즘): 별도 ~60줄**
- **시급도**: 중-높 (시연 시나리오에 conclusion/all_members 케이스 포함됨)
- **의존성**: 해결점 J(카드 갱신)와 묶어야 time_only 후 장소 추가 시 UX 정상 동작
- **다이어그램**: `02-langgraph-flow.mmd` N4 박스를 4분기로 분해 (stalemate/conclusion/all_members/default), N5/N6/N9에 신규 status 라벨 추가

---

### 해결점 J. 카드 갱신 메커니즘 (meeting_id 기반 update)

- **상태**: 🔴 확정 (해결점 I 의존, 본 세션 2026-05-06 신규 발견)
- **위치**:
  - 백엔드: `backend/app/services/langgraph_pipeline.py` (maedeup_card_creation, vote_card_creation, place_recommendation 노드)
  - 백엔드: `backend/app/api/ws/agent.py` (emit 단계)
  - 프론트: `frontend/src/hooks/useAgentWebSocket.ts` (카드 state 관리)
  - 프론트: `frontend/src/components/meeting/MaedeupCard.tsx` (렌더)
- **증상 (수정 전)**:
  - 카드는 한 번 발행되면 끝. 같은 모임에 새 카드가 또 만들어지면 UI에 카드 2개 누적
  - 시나리오: TimeBar로 시간 확정(time_only_ready) → maedeup_card 부분 발행 → 채팅에서 장소 합의 → 새 maedeup_card 발행 (정상) → **두 카드가 동시에 보임 = 사용자 혼란**
  - 현재 시나리오에서도 부분 문제: vote_card 후 maedeup_card 발행 시 vote_card는 그대로 남음 (단, 이건 vote 결과 = 시간 확정 흐름이라 의도된 면이 있음)
- **결정 수정안**: **meeting_id 기반 카드 update**

  #### 1. 페이로드에 meeting_id 추가
  **모든 카드 페이로드** (`vote_card`, `place_recommendation`, `maedeup_card`)에 `meeting_id` 필드 신설:
  ```json
  {
    "type": "maedeup_card",
    "meeting_id": 142,  ← 새 필드
    "date": "...",
    ...
  }
  ```
  - 출처: `MeetingSchedule` DB pending row의 PK
  - vote_card / place_recommendation / maedeup_card 모두 같은 meeting_id 공유
  - place_recommendation도 meeting_id 포함 이유: 추후 사용자가 다른 장소 선택 시 같은 카드로 갱신 가능하도록 (해결점 K patch 엔드포인트 호환)

  #### 2. 프론트 카드 state 변경
  ```typescript
  // useAgentWebSocket.ts
  // before
  const [maedeupCards, setMaedeupCards] = useState<MaedeupCard[]>([]);
  setMaedeupCards(prev => [...prev, newCard]);  // append

  // after
  const [cardsByMeetingId, setCardsByMeetingId] = useState<Map<number, MaedeupCard>>(new Map());
  setCardsByMeetingId(prev => {
    const next = new Map(prev);
    next.set(newCard.meeting_id, newCard);  // upsert
    return next;
  });
  ```

  #### 3. 카드 라이프사이클 정의
  ```
  meeting_id=142
    ├─ T+0  vote_card 발행          → cardsByMeetingId[142] = vote_card
    ├─ T+30 vote 결과로 시간 확정    → maedeup_card (place_pending=true) 발행
    │                                 → cardsByMeetingId[142] = maedeup_card (vote_card 자동 대체)
    ├─ T+60 장소 합의               → maedeup_card (place 채워짐) 발행
    │                                 → cardsByMeetingId[142] = maedeup_card (place 갱신)
    └─ T+90 GCal 등록 완료          → maedeup_card (calendar_registered=true) 발행
                                      → cardsByMeetingId[142] = 최종 카드
  ```

  #### 4. 카드 type 전환 처리
  - vote_card → maedeup_card 전환: 같은 meeting_id면 type 변경 허용
  - place_recommendation은 별도 카드 (meeting_id 없거나 다른 ID) — 추천 후보 제시용

  #### 5. 메모리/cleanup
  - 모임 확정/취소 시 해당 meeting_id 카드 제거
  - WebSocket 재연결 시 백엔드에서 활성 카드 목록 재발행 (현재도 부분적으로 있음)

- **시연 효과**:
  - time_only 부분 카드 → 장소 채워지며 같은 카드 자연스러운 갱신 (UX 임팩트 큼)
  - 카드 누적 혼란 방지
  - 모임 진행 단계가 한 카드에 시각화 (vote → 부분 → 완전)

- **작업 분량**:
  - 백엔드 페이로드 meeting_id 추가: ~30줄 (3개 카드 노드)
  - 프론트 useAgentWebSocket Map 변환: ~20줄
  - 프론트 MaedeupCard 갱신 시 애니메이션 (선택): ~10줄
  - **총 ~60줄**

- **시급도**: 중 (해결점 I time_only_ready 동작 완성에 필수)
- **의존성**: 해결점 I 적용 시 같이 진행. 단독 가치도 있음 (vote → maedeup 전환 매끄러워짐)

---

### 해결점 K. partial 카드 장소 수동 입력 (UI 인터랙션)

- **상태**: 🔴 확정 (해결점 I·J 의존, 본 세션 2026-05-06 신규)
- **위치**:
  - 백엔드: 신규 엔드포인트 `PATCH /api/v1/meetings/{id}/place`
  - 백엔드: 갱신 로직 (DB MeetingSchedule UPDATE + maedeup_card 재발행)
  - 프론트: `MaedeupCard.tsx` (place_pending 영역 클릭 가능 처리 + 모달)
- **증상 (수정 전 — 해결점 I·J만 적용 시 갭)**:
  - time_only_ready 분기로 maedeup_card 부분 발행 (`place=null`)
  - 노드5에서 Kakao API 스킵 → 장소 추출 메커니즘 없음
  - 채팅에서 장소 합의돼도 자동 갱신 트리거가 없음 (stalemate/conclusion regex 매칭 안 되면 미발화)
  - **결과**: partial 카드가 영영 미완성 상태로 남을 수 있음
- **결정 수정안**: **옵션 4 — 사용자 명시 입력 (UI 인터랙션)**

  #### 1. 백엔드 PATCH 엔드포인트 신설
  ```python
  # backend/app/routers/meetings.py
  @router.patch("/{meeting_id}/place")
  async def patch_meeting_place(
      meeting_id: int,
      payload: PlacePatchRequest,  # {"place": str}
      session: AsyncSession,
      user: User,
  ):
      # 1. meeting_id 조회 + 권한 체크 (방 멤버만)
      # 2. place_hint UPDATE
      # 3. Kakao 좌표 조회
      # 4. (선택) GCal event 생성
      # 5. 갱신된 maedeup_card 페이로드 재발행 → Redis pub agent:room
      # 6. 같은 meeting_id로 발행 → 프론트 cardsByMeetingId Map upsert (해결점 J)
  ```

  #### 2. 프론트 MaedeupCard 인터랙션
  ```typescript
  // place_pending=true 영역 렌더
  <div
    className="place-pending"
    onClick={() => setShowPlaceModal(true)}
  >
    <SearchIcon />
    <span>장소를 정해주세요 (클릭)</span>
  </div>

  // 모달
  <PlaceInputModal
    onSubmit={async (place) => {
      await fetch(`/api/v1/meetings/${meetingId}/place`, {
        method: 'PATCH',
        body: JSON.stringify({ place })
      });
      // WebSocket으로 갱신된 카드 자동 수신 (해결점 J)
    }}
  />
  ```

  #### 3. 갱신 흐름
  ```
  사용자가 카드 placeholder 클릭
       ↓
  모달 입력 ("강남")
       ↓
  PATCH /meetings/142/place
       ↓
  백엔드: DB UPDATE + Kakao 좌표 + GCal event
       ↓
  Redis pub agent:room (maedeup_card 재발행, meeting_id=142)
       ↓
  프론트 cardsByMeetingId Map upsert (해결점 J) → 같은 카드 갱신
  ```

- **시연 효과**:
  - "장소 정해주세요" 인터랙션이 자연스러움
  - 클릭 한 번 + 짧은 입력으로 완성 카드 생성
  - 시연 ACT 4 (모임 확정) 시각적 임팩트
- **장점**:
  - 사용자 의도 명확 (자동 추출 false positive 위험 0)
  - 작업 비교적 단순
  - LLM 호출 0 (비용 미미)
- **단점**:
  - 사용자 액션 필요 (수동)
  - 채팅에서 "강남으로 가자" 합의해도 카드 자동 갱신 안 됨 → 별도 안내 필요
- **작업 분량**:
  - 백엔드: ~50줄 (엔드포인트 + 권한 + 카드 재발행)
  - 프론트: ~60줄 (모달 + 클릭 핸들러 + API 호출)
  - **총 ~110줄**
- **시급도**: 중-높 (해결점 I time_only_ready 동작 완성에 필수)
- **의존성**: 해결점 I (time_only_ready 분기), 해결점 J (meeting_id 카드 갱신)
- **다이어그램**: 별도 시퀀스 다이어그램 권장 (`06-card-update-flow.mmd` 신규)

---

### 확장 A. partial 카드 장소 자동 추출 (place_added_to_pending 트리거)

- **상태**: 🟡 확장 (보류, 운영 단계 누적 후 검토)
- **원본 위치**: 본 세션 (2026-05-06) 옵션 1로 제안되었으나 즉시 적용 보류
- **언제 검토할까**: 해결점 K(수동 입력) 운영 후 사용자 액션 빈도 낮으면 (불편하다는 피드백) 자동화 추가
- **위치**:
  - 백엔드: `backend/app/api/ws/social.py` (매 채팅 메시지에서 추가 게이트)
  - 백엔드: 신규 service `judge_place_agreement` (Gemini, ~0.5s)
  - 백엔드: Redis key `pending_partial_card:{room_id}`
  - 신규 trigger_reason: `place_added_to_pending`
- **설계 (judge_stalemate 패턴 복제)**:

  #### 2단계 게이트
  **1차 — 정규식 (false negative 방지, 무료)**:
  ```python
  # 한국 지명 패턴 매칭 — 후보 등장 빠르게 감지
  if _extract_korean_place_keyword(content):
      # 후속 LLM judge로
  ```

  **2차 — `judge_place_agreement` LLM (false positive 방지)**:
  ```python
  prompt = f"""
  다음은 그룹 채팅방의 최근 5개 대화입니다. 이미 시간은 확정됐고, 장소만 정해지면 됩니다.

  [대화]
  {recent_5_messages}

  판정: 위 대화에서 모두가 동의한 장소가 결정됐는지?

  JSON: {{"place_agreed": true/false, "place": "장소 또는 null", "confidence": 0~1, "reason": "..."}}

  [판정 기준]
  - 명시적 장소 제안 + 1명 이상 동의 → true
  - 단순 질문 ("강남 어때?") → false
  - 반대 의견 있음 → false
  - 모호하거나 토론 진행 중 → false
  """
  ```

  #### 트리거 발화 조건
  ```python
  if regex_match AND judge.place_agreed AND judge.confidence >= 0.7:
      publish ai_auto_trigger {
          trigger_reason: "place_added_to_pending",
          place_hint: judge.place,
          meeting_id: pending_meeting_id,
      }
  ```

  #### 비용 가드
  - 방에 `pending_partial_card:{room_id}` Redis 키 있을 때만 LLM 호출
  - 60초 쿨다운 (judge_stalemate와 동일)
  - 분당 최대 1회 → 운영 부하 미미

- **장점**:
  - 완전 자동화 — 사용자 액션 0
  - 채팅 흐름 자연스럽게 카드 완성
- **단점**:
  - LLM 비용 추가 (분당 최대 1회, 시연 영향 미미)
  - judge 오류 시 잘못된 갱신 가능 (confidence ≥ 0.7 게이트로 완화)
  - 신규 트리거 + state 관리 작업
- **작업 분량**: ~120~150줄
- **검토 시점**: 해결점 K 운영 1~2개월 후 사용자 피드백 누적
- **다이어그램**: `02-langgraph-flow.mmd`에 새 trigger_reason 추가 시 갱신

---

### 해결점 L. vote_card_creation EARLY-EMIT 메커니즘 정리

- **상태**: 🟡 확정 (시급도 낮-중, 본 세션 2026-05-06 신규)
- **위치**: `backend/app/services/langgraph_pipeline.py:3270~3305` (vote_card_creation 내부 직접 Redis pub)
- **증상 (수정 전)**:
  - vote_card_creation 노드 안에서 **직접 Redis pub 발행**
  - 정상 emit 경로(노드10 후 agent.py 발행)와 별개로 작동
  - `state["vote_card_emitted_early"]=True` 플래그를 agent.py가 보고 스킵
  - **이중 발행 위험**: 한쪽 실패 시 카드 0건 또는 2건 가능
  - 새 trigger_reason 추가 시 이 분기가 의도치 않게 깨질 수 있음
- **원인 (도입 배경)**:
  - 장소 추천(노드8)이 7~12초 걸리던 시기 vote_card 빨리 보여주려는 최적화
  - 단축 경로(해결점 E) 적용 후 전체 시간 3~5초로 단축되면 효용 감소
- **결정 수정안**: **EARLY-EMIT 제거**
  ```python
  # 제거 대상 (vote_card_creation 내부)
  await r.publish(channel, json.dumps(state["vote_card_payload"]))
  state["vote_card_emitted_early"] = True
  # narrator 메시지도 같이 제거
  ```
- **agent.py 변경**:
  - `vote_card_emitted_early` 플래그 체크 로직 제거
  - `emitted_early` 플래그 체크 로직 제거 (new_assistant_messages 중복 발행 방지용)
  - 정상 emit 경로 단일화
- **단축 경로(해결점 E) 적용 후 효과**:
  - 단축 schedule: ~4초 → vote_card 즉시 발행 → EARLY-EMIT 불필요
  - 자동 트리거 + EARLY-EMIT 제거: ~7~10초 (단, 해결점 B의 분석중 메시지로 UX 보완)
- **장점**:
  - 발행 경로 단일화 → 일관성 확보
  - 새 트리거 추가 시 이 분기 깨질 위험 0
  - 코드 ~40줄 감소
- **단점**:
  - vote_card 표시 시간 약간 늦어짐 (해결점 B 분석중 메시지로 보완 가능)
- **작업 분량**: ~50줄 (제거 + 플래그 정리 + 테스트)
- **시급도**: 낮-중 (시연에서 깨지면 직격이지만 빈도 낮음)
- **의존성**: 해결점 B(분석중 메시지) + 해결점 E(단축 경로) 적용 후 진행 권장
- **다이어그램**: `02-langgraph-flow.mmd` N7_OUT 박스에서 EARLY-EMIT 화살표 제거

---

### 해결점 M. created_by 하드코딩 제거 (privacy/audit cleanup)

- **상태**: 🟡 확정 (시급도 낮, 운영 전 cleanup, 본 세션 2026-05-06 신규)
- **위치**: `backend/app/services/langgraph_pipeline.py:3217` (vote_card_creation pending meeting 생성 시)
- **증상 (수정 전)**:
  ```python
  created_by = 1  # 디폴트 하드코딩
  if room_pk is not None:
      first_member = ...첫 멤버 조회...
      if first_member:
          created_by = first_member.user_id
  ```
  - 방 멤버 조회 실패 시 user_id=1을 작성자로 박음
  - 시연 환경에서 잠시 쓰던 흔적
  - **운영 환경 위험**: user_id=1이 실제 사용자라면 그 사람 이름으로 의도치 않은 모임 생성됨 → privacy/audit 이슈
- **결정 수정안**: **silent fallback 금지, 명시적 에러**
  ```python
  if room_pk is None:
      raise ValueError("room_pk is None when creating pending meeting")
  member_result = await db.execute(
      select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)
  )
  first_member = member_result.scalar_one_or_none()
  if first_member is None:
      raise ValueError(f"No members found in room {room_pk}")
  created_by = first_member.user_id
  ```
- **에러 처리 흐름**:
  - `_handle_node_exception`이 잡아서 logger.error + 사용자에게 안내 메시지
  - 카드 발행 0건 (silent corruption 대신 명시적 실패)
- **장점**:
  - privacy/audit 안전
  - 디버깅 용이 (원인 추적 가능)
  - silent corruption 차단
- **단점**: 없음 (정상 케이스에서 영향 0)
- **작업 분량**: ~5줄
- **시급도**: 낮 (시연 영향 거의 0, 운영 전 정리 차원)
- **다이어그램**: 변경 없음 (코드 cleanup만)

---

### 해결점 D. extract_meeting_summary 제거 (책임 중복 정리)

- **상태**: 🔴 확정 (단순 정리, 시급도 낮지만 코드 명확성 ↑)
- **원본 의심점**: A (`_analyze_conversation` 1+2회차 중복 호출)
- **위치**:
  - `backend/app/services/langgraph_pipeline.py:4080~4155` (제거 대상 함수 정의)
  - `backend/app/api/ws/agent.py:22` (import 제거)
  - `backend/app/api/ws/agent.py:140` (호출 제거)
- **검증 결과**:
  - 정상 케이스 (대부분): `_analyze_conversation` 1회 호출로 끝남 → 영향 0
  - 실패 케이스 (드뭄): `_analyze_conversation` 실패 시 `extract_meeting_summary`가 같은 함수 재호출 + 자체 legacy fallback (다른 프롬프트로 Gemini 또 호출)
  - 호출 위치 단 1곳 (`agent.py:140`) → 제거 영향 범위 좁음
- **원인**:
  - `extract_meeting_summary`는 LangGraph 도입 이전 legacy 함수
  - `_analyze_conversation`이 통합 버전으로 만들어진 후 legacy가 wrapper로 남음
  - `agent.py`가 두 함수 다 부르는 구조 → 책임 겹침
- **결정 수정안**:
  1. `agent.py:140`에서 `extract_meeting_summary` 호출 제거 → `summary = {}`로 빈 발행
  2. `langgraph_pipeline.py`의 `extract_meeting_summary` 함수 정의 삭제 (~80줄)
  3. `agent.py:22`에서 import 제거
- **영향**:
  - 정상 동작: 영향 0
  - 실패 케이스: AI 패널 "현재 대화 정리" 박스 빈 채로 표시 (legacy fallback 없어짐)
  - 코드: -80줄, 책임 단일화
- **시급도**: 낮음 (실패 케이스 드뭄, 시연 영향 미미)
- **다이어그램**: `02-langgraph-flow.mmd`의 A1/A2/A3 박스 → A1만 남기고 A2/A3 제거 표시

---

### 해결점 O. 정규식 단축 경로의 rejected_dates 누락 (확장)

- **상태**: 🔴 확정 (코드 검증 완료, 2026-05-06 세션)
- **위치**:
  - `backend/app/services/langgraph_pipeline.py:979-1047` (`_pattern_extract_entities`)
  - `backend/app/services/langgraph_pipeline.py:1054-1062` (`_extract_entities_from_context` shortcut)
  - `backend/app/services/langgraph_pipeline.py:283-295` (`_serialize_context` social_recent 포함)
- **증상**:
  - AI 패널 직접 요청 ("일정 잡아줘") 경로에서 채팅방 누적 거부 발언이 vote_card 후보 필터에 반영 안 됨
  - 자동 트리거 경로(`_analyze_conversation`)는 정상. AI 패널 직접 경로만 누락
- **원인 (코드 추적)**:
  - `_pattern_extract_entities`는 `rejected_dates` 키를 결과 dict에 만들지 않음 (line 981 result 초기화에 누락)
  - `_extract_entities_from_context`가 정규식 1차 단축 (date_hints≥2 OR date+place 존재) 시 Gemini 호출을 스킵 (line 1056, 1060)
  - `_serialize_context`는 social_recent 채팅방 전체 메시지를 LLM 입력 맥락에 포함 (line 291-292)
  - 채팅방에 "5월 8일 안돼", "5월 10일 어때?" 같은 다중 날짜 발언이 누적 → 정규식이 양쪽 다 포착 → date_hints 길이 ≥2 → 단축 경로 → Gemini 스킵 → rejected_dates 빈 채로 진행
- **2026-05-05 메모리 노트와의 관계**:
  - `project_pattern_skip_rejected_blindspot.md`에서 "단일 메시지 동시 발언" 케이스로 보류 등급 결정
  - 본 분석에서 social_recent까지 LLM 입력에 포함된다는 사실이 추가 → 채팅방 누적 거부 전체가 사각지대
  - 보류 → 시연 차단 등급 승격
- **트리거 조건 (재현)**:
  1. 채팅방에 `M월 D일` 또는 요일 표현 ≥2개 (한 개는 거부, 다른 한 개는 추천 후보)
  2. 또는 거부된 날짜 1개 + 명확한 지명 1개 (강남/홍대 등)
  3. 사용자가 AI 패널에서 "일정 추천해줘" 직접 요청
- **수정 후보**:
  - 옵션 A: `_pattern_extract_entities`에 거부 정규식 추가 (안 돼/못 가/힘들어/패스 등) — Completeness 7/10, ~15min
  - 옵션 B: shortcut 조건에 "context에 거부 키워드 없을 때만" AND 추가 — Completeness 9/10, ~10min, **추천**
  - 옵션 C: `social_recent`만 따로 LLM 콜로 rejected/conflict 별도 추출 — Completeness 8/10, ~30min, +1 LLM 호출
  - 옵션 D: `run_pipeline` 항상 `_analyze_conversation` 선행 — Completeness 10/10, ~20min, 매 요청 +1 LLM 호출 (비용 큼)
- **시급도**: 시연 직전. 단 사용자 시나리오 흐름이 auto-trigger 경유 위주라 시연에서 우연히 안 터질 가능성도 있음
- **사각지대 추가**: `_pattern_extract_entities`는 `conflict_detected/conflict_options/conflict_users`도 만들지 않음. 정규식 통과 시 충돌 감지도 같이 누락. 같은 fix로 해결 가능

---

### 해결점 P. 채팅 자연어 거부 → 캘린더 unavailability 동기화 갭

- **상태**: 🟡 기능 갭 (버그 아님, 미구현 feature)
- **위치**:
  - 채팅 자연어 추출: `backend/app/services/langgraph_pipeline.py:4309` (`_analyze_conversation` — 이미 존재)
  - 캘린더 데이터 소스: `backend/app/services/scheduling_round.py:704` (`record_unavailable_toggle` — 이미 존재)
  - 갭: 둘을 잇는 호출 없음
- **증상**:
  - 사용자가 채팅방에서 "5월 8일 안돼"라고 발언해도 캘린더 8일 셀의 "X/Y 가능" 카운트가 변경 안 됨
  - vote_card 추천에서는 8일이 후보에서 빠지지만 (auto-trigger 경로 한정), 캘린더 UI는 그대로 "전원 가능" 표시
- **원인**:
  - 캘린더 카운트는 멤버×날짜 명시 데이터(`record_availability` TimeBar 드래그 + `record_unavailable_toggle` 불가능 버튼)만 집계
  - 채팅 자연어 → unavailability 동기화 경로가 미구현
  - vote_card는 한 번 휙 보고 후보 필터하는 일회성 경로라 자연어 OK, 캘린더는 멤버별 영구 데이터라 정확한 매핑 필요
- **수정 방향 (사용자 제안)**:
  - 교착 감지 시 `_analyze_conversation`이 이미 `signals.rejected_dates = [{date, user, reason}]` 추출 중
  - 이걸 그대로 `record_unavailable_toggle(room_id, user_id, date, unavailable=True)`에 매핑하면 캘린더 카운트 갱신
  - 함정 1: `signals.rejected_dates[].user`는 발신자 NAME (string, LLM 추출), `record_unavailable_toggle`은 user_id (int) 요구 → 이름→ID 매핑 필요 (방 멤버 테이블 조회 + LLM 환각 방어)
  - 함정 2: 매핑 실패 또는 user 필드 null 시 정책 — skip / 전체 멤버 적용 / 호스트만 적용 — 결정 필요
  - 함정 3: 토글 인버스 ("아 8일 되네" 번복) — `signals.rejected_dates`에서 빠지면 자동 clear할지, 명시 unavailable=False 추출 받을지
  - WebSocket 브로드캐스트: 캘린더 즉시 리프레시 트리거 필요 (`scheduling_update` 등 기존 채널 활용)
- **시급도**: 시연 핵심 magical moment 후보. "AI가 채팅 읽고 캘린더까지 자동 갱신" 데모 가치 높음
- **코스트**:
  - 최소 구현 (auto-trigger 경로에 코드 30~50줄 추가): ~30~45min
  - 인버스/번복 케이스 + 매핑 강건화: 추가 ~30min
- **관련 메모리**: `project_pattern_skip_rejected_blindspot.md` (사각지대 노트 — 본 해결점 P가 그 파급의 한 갈래)
