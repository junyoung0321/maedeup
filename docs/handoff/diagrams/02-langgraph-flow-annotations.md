# 02-langgraph-flow.mmd 보조 주석 (FigJam 보드 보존본)

본 문서는 FigJam 다이어그램(`02-langgraph-flow.mmd` 렌더본)에 사용자가 직접 추가한 주석을 보존합니다.
다이어그램 재렌더 시 노드 ID가 바뀌면 connector가 끊기므로 주석 텍스트를 여기에 동기화해두면 안전합니다.

원본 FigJam: https://www.figma.com/board/oHlaUCdw8Z70Cb0TZECVEZ
보존일: 2026-05-06

---

## 노드별 보조 설명

### A. "agent.py · trigger_reason별 분석중 메시지 즉시 발행 (해결점 B)"

> 채팅방 자동 트리거(stalemate/conclusion/all_members)가 발화하면 AI 패널에 즉시 한 줄 메시지를 띄움

**연결 노드**: AUTO_PATH (자동 트리거 진입 직후)

---

### B. "_analyze_conversation 1회 (해결점 D 적용 후 1회만)"

> 채팅방 최근 메시지 ~20개를 한 번에 Gemini에 보내서 두 가지를 동시에 추출:
> - card: 모임 요약 (date/place/headcount/type) — AI 패널 "현재 대화 정리" 박스용
> - signals: 파이프라인이 쓸 신호 묶음 (date_hints, conflict, rejected_dates 등)

**연결 노드**: A1 (AUTO_PATH 다음)

---

### C. "pre_extracted_signals · 파이프라인이 Gemini 추가 호출 없이 쓸 신호 묶음"

> 위 B에서 뽑은 signals 딕셔너리. 파이프라인이 LangGraph 내부에서 Gemini 추가 호출 없이 바로 쓸 데이터.

**연결 노드**: A4 (A1 다음)

---

### D. "run_pipeline 진입 · GraphState 초기화 trigger_reason 주입"

> 무엇: LangGraph 파이프라인을 실제로 실행. GraphState라는 dict가 노드 간 데이터를 운반함.
>
> 진입 시 채워지는 것들:
> - room_id, db (세션)
> - message_records (최근 채팅)
> - extracted_entities = pre_extracted_signals (C에서 받은 거)
> - trigger_reason ← 해결점 C 핵심 추가

**연결 노드**: AUTO_RUN (A4 다음)

---

### E. "노드1 intent_detection · classify_intent 신뢰도 0.7"

> 채팅에서 가장 마지막 user 메시지가 어떤 의도인지 분류 → meeting_schedule / place_suggestion / general 중 하나로 라벨링.

**연결 노드**: N1

---

## 사용 규칙

- 다이어그램 재렌더 후 새 보드에서 위 주석을 그대로 복사 + 해당 노드에 다시 부착
- 본문(.mmd)에 직접 인라인하지 않는 이유: 박스 라벨이 너무 길어지면 가독성 ↓
- 새 주석 추가 시 본 파일에도 추가 (단방향 동기화: FigJam → 본 파일)
