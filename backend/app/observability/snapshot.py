"""NDJSON snapshot dumper — P0 instrumentation.

MAEDEUP_SNAPSHOT=1 환경변수가 켜진 경우에만 /tmp/maedeup_snapshot_YYYYMMDD.ndjson에 append.
운영 환경에서는 env 미설정 → dump() 즉시 return → 영향 없음.

형식 (1줄 = JSON):
{"ts": "<iso8601>Z", "event_type": "node_in", "run_id": "abc12345", "payload": {...}}
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def dump(event_type: str, run_id: str | None, payload: dict[str, Any]) -> None:
    """MAEDEUP_SNAPSHOT=1 일 때만 /tmp/maedeup_snapshot_YYYYMMDD.ndjson append.

    직렬화 실패 대비: default=str 로 datetime 등 처리.
    예외는 swallow 하지 않고 그대로 raise (테스트에서 발견되도록).
    """
    if os.environ.get("MAEDEUP_SNAPSHOT") != "1":
        return
    line = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "run_id": run_id,
        "payload": payload,
    }
    date = datetime.utcnow().strftime("%Y%m%d")
    path = Path(f"/tmp/maedeup_snapshot_{date}.ndjson")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
