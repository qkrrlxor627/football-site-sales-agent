"""사장님 알림: 넘어온 건·새 주문을 웹훅(Slack, Discord 등)으로 보낸다. 주소가 없으면 아무것도 하지 않는다."""
# 알림은 부가 기능이다: 고객 요청을 기다리게 하지 않도록 따로 보내고, 실패해도 로그만 남긴다.
# 고객이 쓴 문장(건강 정보일 수 있다)은 밖으로 보내지 않는다. 종류와 주문 번호만 보내고 내용은 관리 화면에서 본다.
import json
import logging
import threading
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)
TIMEOUT = 5


def _post(url: str, text: str) -> None:
    body = json.dumps({"text": text, "content": text}, ensure_ascii=False).encode()   # text: Slack, content: Discord
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT):
            pass
    except Exception as err:
        log.warning("알림을 보내지 못했어요: %s", type(err).__name__)


def send(url: Optional[str], text: str) -> Optional[threading.Thread]:
    if not url:
        return None
    t = threading.Thread(target=_post, args=(url, text), daemon=True, name="pitchroom-notify")
    t.start()
    return t
