"""로그에 노출되는 인증 토큰(JWT) 마스킹.

WebSocket 인증은 토큰을 쿼리스트링(`?token=...`)으로 받는다 — 브라우저 WebSocket
API가 커스텀 헤더(Authorization)를 못 붙이기 때문. 그런데 uvicorn이 접속 로그에
요청 URL 전체를 찍어서, 로그인 자격증명인 JWT가 평문 그대로 컨테이너 로그에 남는다
(예: `WebSocket /ws/agent/351?token=eyJ... [accepted]`).

이 필터는 모든 로그 레코드의 메시지에서 `token=<값>`을 `token=***`로 치환한다.
인증 메커니즘은 건드리지 않고 출력만 가린다.
"""
import logging
import re

# token= 뒤의 값(JWT 등)을 잡되, 구분자(공백·&·따옴표·괄호)에서 멈춘다.
_TOKEN_RE = re.compile(r"(token=)[^\s&\"'\])]+", re.IGNORECASE)


class TokenMaskingFilter(logging.Filter):
    """레코드 메시지의 `token=...`를 `token=***`로 가린 뒤 통과시킨다."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # 포맷 실패 시 원본 흐름 방해하지 않음
            return True
        if "token=" in msg:
            # 포맷 완료된 문자열로 치환 + args 제거 → 핸들러가 그대로 출력.
            record.msg = _TOKEN_RE.sub(r"\1***", msg)
            record.args = ()
        return True


def install_token_masking(
    logger_names: tuple[str, ...] = (
        "",  # root (app 로그 — basicConfig 핸들러)
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",  # WebSocket accept 줄을 찍는 로거
        "maedeup",
    ),
) -> None:
    """지정 로거와 그 핸들러에 토큰 마스킹 필터를 부착한다(중복 부착 방지).

    핸들러에 붙이면 자식 로거에서 전파(propagate)된 레코드까지 가려진다.
    uvicorn은 앱 import 전에 로깅을 구성하므로 import 시점에 핸들러가 이미 존재한다.
    """
    flt = TokenMaskingFilter()
    for name in logger_names:
        lg = logging.getLogger(name)
        if not any(isinstance(f, TokenMaskingFilter) for f in lg.filters):
            lg.addFilter(flt)
        for handler in lg.handlers:
            if not any(isinstance(f, TokenMaskingFilter) for f in handler.filters):
                handler.addFilter(flt)
