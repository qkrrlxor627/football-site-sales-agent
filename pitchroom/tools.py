"""도구: 하나의 책임만 가진 함수들. State를 직접 바꾸지 않고 값만 돌려준다."""
import logging
import math
from typing import Optional

from .config import USE_TAVILY
from .data import *  # noqa: F401,F403  (규칙표 상수)

log = logging.getLogger(__name__)

# 모든 도구는 State를 직접 바꾸지 않고 값만 돌려준다. State 변경은 노드의 반환 dict로만 일어난다.


def filter_products(profile: dict) -> list[dict]:
    """[규칙] 구장·발볼·예산을 모두 만족하는 상품."""
    out = []
    for p in PRODUCTS:
        if profile.get("surface") and p["stud"] not in SURFACE_TO_STUD[profile["surface"]]:
            continue
        if profile.get("width") and p["width"] != profile["width"]:
            continue
        if profile.get("budget") is not None and p["price"] > profile["budget"]:
            continue
        out.append(p)
    return out


def rank_products(items: list[dict], profile: dict) -> list[dict]:
    """[규칙] 취향 라인 우선, 그다음 예산 대비 저렴한 순."""
    style = (profile.get("style") or {}).get("line")
    return sorted(items, key=lambda p: (0 if p["line"] == style else 1, p["price"]))


def nearest_alternatives(profile: dict) -> list[tuple[dict, float, list[str]]]:
    """[규칙] 조건을 전부 맞추는 상품이 없을 때, 양보 점수가 낮은 순의 대안과 양보 항목."""
    out = []
    for p in PRODUCTS:
        cost, trade = 0.0, []
        surf = profile.get("surface")
        if surf and p["stud"] not in SURFACE_TO_STUD[surf]:
            c = SUBSTITUTE.get(surf, {}).get(p["stud"])
            if c is None:
                continue  # 위험한 대체(예: 인조잔디에 FG)는 대안으로도 내놓지 않는다
            cost += c
            trade.append(SUB_NOTE[surf].get(p["stud"], f'{p["stud"]} 대체'))
        b = profile.get("budget")
        if b is not None and b != math.inf and p["price"] > b:
            cost += (p["price"] - b) / 100000
            trade.append(f'예산보다 {won(p["price"] - b)} 높음')
        if profile.get("width") and p["width"] != profile["width"]:
            cost += 1
            trade.append(f'발볼 {p["width"]} (매장 시착 권장)')
        out.append((p, cost, trade))
    return sorted(out, key=lambda x: (x[1], x[0]["price"]))


def check_policy(topic: str, days: Optional[int], worn: Optional[bool], repeat: bool) -> dict:
    """[규칙] 교환·반품 자동 처리 가능 여부와 근거."""
    in_period = days is not None and days <= POLICY["return_days"]
    unworn = worn is False
    rules = [
        f'수령 후 {POLICY["return_days"]}일 이내 ' + ("(확인 안 됨)" if days is None else (f"✓ {days}일째" if in_period else f"✗ {days}일째")),
        "실외 미착용 " + ("(확인 안 됨)" if worn is None else ("✓" if unworn else "✗ 스터드 사용 흔적")),
    ]
    if topic == "교환":
        rules.append(f'사이즈 교환 {POLICY["free_exchange"]}회 무료 ' + ("✗ 이미 교환 이력" if repeat else "✓"))
    else:
        rules.append(f'단순 변심 반품 왕복 배송비 {won(POLICY["return_fee"])} 고객 부담')
    auto = in_period and unworn and not (topic == "교환" and repeat)
    return {"auto": auto, "rules": rules}


def find_order(account: Optional[dict], topic: str) -> tuple[str, Optional[dict]]:
    """[조회] 문의에 해당하는 주문. ('none'|'busy'|'open'|'delivered'|'no_delivered', 주문)"""
    if not account:
        return "none", None
    orders = account["orders"]
    if topic == "배송":
        open_ = [o for o in orders if o["status"] in ("결제완료", "배송중")]
        return ("open", open_[0]) if open_ else ("no_open", next((o for o in orders if o["delivered_at"]), None))
    busy = next((o for o in orders if o["status"] in IN_SERVICE), None)
    if busy:
        return "busy", busy
    done = sorted([o for o in orders if o["status"] == "배송완료"], key=lambda o: o["delivered_at"], reverse=True)
    return ("delivered", done[0]) if done else ("no_delivered", None)


def player_line(player: str, llm_line: Optional[str]) -> tuple[Optional[str], str]:
    """[검색] 선수가 신는 축구화 → 우리 매장 라인. 고정표 → Tavily → LLM 추정 순으로 시도."""
    # 고정표가 먼저다: 검색은 결과 글에 라인 이름이 몇 번 나오는지만 세서, 아는 선수도 틀리게 답한 적이 있다 (음바페 → Phantom).
    known = next((line for name, (_, line) in PLAYER_TABLE.items() if name in player), None)
    if known:
        return known, "고정표"
    if USE_TAVILY:
        try:
            from tavily import TavilyClient
            res = TavilyClient().search(f"{player} football boots", max_results=5)
            text = " ".join(r.get("content", "") for r in res.get("results", [])).lower()
            hits = [line for line in LINES if line.lower() in text]
            if hits:
                return max(set(hits), key=hits.count), "Tavily 검색"
        except Exception as err:
            log.warning("Tavily 실패, 대체 경로 사용: %s", type(err).__name__)
    if llm_line:
        return llm_line, "LLM 추정"
    return None, "모름"
