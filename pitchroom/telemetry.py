"""LLM 호출 기록: 몇 번 불렀고, 몇 번이 실패해 규칙으로 대체됐는지. 저장할 곳은 API가 시작할 때 꽂는다."""
# 그래프 노드와 추출기는 DB를 모른다. 여기에 기록만 던지고, 꽂힌 곳이 없으면(CLI·테스트) 아무 일도 일어나지 않는다.
import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)
_sink: Optional[Callable[..., None]] = None


def set_sink(fn: Optional[Callable[..., None]]) -> None:
    global _sink
    _sink = fn


def record(kind: str, fallback: bool = False, ms: float = 0, tokens: int = 0) -> None:
    """kind: extract(문장 이해) | answer(질문 답변). fallback: LLM이 실패해 규칙·대체 답으로 넘어갔는가."""
    if _sink is None:
        return
    try:
        _sink(kind, fallback, int(ms), int(tokens or 0))
    except Exception as err:   # 기록 실패가 고객 요청을 깨뜨리면 안 된다
        log.warning("LLM 호출 기록 실패: %s", type(err).__name__)
