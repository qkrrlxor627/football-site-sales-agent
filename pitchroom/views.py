"""화면 응답: 그래프 State → 화면이 그대로 그릴 JSON. 판단은 graph가 하고, 여기서는 보여줄 모양만 정한다."""
# Gradio 화면(ui.py)이 HTML 문자열로 하던 일을 JSON으로 옮긴 것이다.
# 화면(Vue)은 이 JSON에 없는 것은 모른다. 내부 논의는 to_client에서 이미 빠져 있다.
import math
from datetime import date
from pathlib import Path
from typing import Optional

from .data import *  # noqa: F401,F403
from .graph import service_greeting, to_client
from .tools import filter_products, rank_products

IMAGE_DIR = Path(__file__).parent / "static" / "images"
STEP = ["결제완료", "배송중", "배송완료"]
DEFAULT_SIZE = 270
HOME_CODES = ["S-04", "S-08", "S-02"]
MAX_BLUR = 12
ACCOUNT_DESC = {
    "minsu": "결제 완료, 출고 준비 중",
    "jiwoo": "배송 완료 3일째",
    "hyun": "배송 완료 10일째, 교환 이력 1회",
    "seoyeon": "교환 진행 중 + 새 주문 배송 중",
}


def image_url(code: str) -> Optional[str]:
    return f"/images/{code}.webp" if (IMAGE_DIR / f"{code}.webp").exists() else None


# 구장별 무대 배경 사진. 사진이 없는 구장(흙운동장, 실내)은 기본 배경을 쓴다.
BACKGROUND = {"천연잔디": "natural", "인조잔디": "artificial", "풋살장": "futsal"}


def background_url(surface: Optional[str] = None) -> Optional[str]:
    name = BACKGROUND.get(surface or "", "default")
    return f"/images/bg/{name}.webp" if (IMAGE_DIR / "bg" / f"{name}.webp").exists() else None


def product_info(code: str) -> dict:
    p = BY_CODE[code]
    lp = p.get("list_price")
    return {"code": code, "name": p["name"], "line": p["line"], "stud": p["stud"], "stud_info": STUD_INFO[p["stud"]],
            "width": p["width"], "price": p["price"], "list_price": lp if lp and lp > p["price"] else None,   # 정가보다 싸게 팔 때만 할인으로 보여준다
            "color": p.get("color"), "feel": p["feel"], "image": image_url(code)}


def product_card(code, profile, label=None, quiet=False, trade=None, buyable=False) -> dict:
    p = BY_CODE[code]
    bits = []
    if profile.get("surface"):
        bits.append(f'{profile["surface"]} → {p["stud"]}')
    if profile.get("width"):
        bits.append(f'발볼 {p["width"]}')
    if profile.get("budget") not in (None, math.inf):
        bits.append(f'예산 안 {p["price"]:,}원')
    if profile.get("style") and p["line"] == profile["style"]["line"]:
        bits.append(f'{p["line"]} 선호')
    return {**product_info(code), "label": label, "quiet": quiet, "best": bool(label and not quiet),
            "trade": trade or None, "why": " · ".join(bits) or p["feel"], "buyable": buyable}


def order_card(o, primary=False) -> dict:
    p = BY_CODE[o["code"]]
    svc = o["status"] not in STEP
    idx = 1 if o["status"] == "주문 취소" else len(STEP) if svc else STEP.index(o["status"])   # 취소는 결제까지만 지나간 것
    steps = [{"text": s, "state": "done" if i < idx else "now" if i == idx and not svc else "todo"} for i, s in enumerate(STEP)]
    if svc:
        steps.append({"text": o["status"], "state": "svc"})
    when = f'배송 완료 {o["delivered_at"]}' if o["delivered_at"] else f'출고 {o["shipped_at"]}' if o["shipped_at"] else f'주문 {o["ordered_at"]}'
    return {"id": o["id"], "code": o["code"], "name": p["name"], "stud": p["stud"], "size": o["size"], "label": order_label(o),
            "image": image_url(o["code"]), "status": o["status"], "steps": steps, "when": when,
            "exchanges": o["exchanges"], "note": o.get("note"), "primary": primary}


def slots(profile, skipped) -> list[dict]:
    cells = []
    for k in SLOT_ORDER:
        v = profile.get(k)
        if v is None:
            text = "건너뜀" if k in (skipped or []) else "—"
        elif k == "budget":
            text = won(v) if v == math.inf else f"{v // 10000}만원 이하"
        else:
            text = v
        cells.append({"key": k, "label": SLOT_LABEL[k], "text": text, "on": v is not None})
    if profile.get("size"):
        cells.append({"key": "size", "label": "사이즈", "text": f'{profile["size"]}mm', "on": True})
    if profile.get("style"):
        cells.append({"key": "style", "label": "취향", "text": profile["style"]["line"], "on": True})
    return cells


def _view(**kw) -> dict:
    """화면 한 장. 화면은 여기 있는 키만 보고 그린다."""
    base = {
        "screen": "shop",            # shop | service | result
        "headline": "", "echo": None, "collect": False,
        "count": {"prefix": "", "strong": "", "suffix": ""},
        "shelf": {"kind": "products", "blur": 0, "paused": False, "cards": [], "empty_text": None},
        "news": None, "slots": [], "handoff": None, "hint": None,
        "discussion": [], "hidden": 0,
        "route": None, "reason": None, "source": None,
        "placeholder": "여기에 답해 주세요", "default_size": DEFAULT_SIZE,
        "background": background_url(),
    }
    return {**base, **kw}


def _sorted_orders(acc) -> list[dict]:
    pri = lambda o: 0 if o["status"] in IN_SERVICE else 1 if o["status"] == "배송중" else 2 if o["status"] == "결제완료" else 4 if o["status"] in ("반품 완료", "주문 취소") else 3
    return sorted(acc["orders"], key=lambda o: (pri(o), -date.fromisoformat(o["ordered_at"]).toordinal()))  # 급한 상태 → 최근 주문 순


def shop_home() -> dict:
    return _view(
        screen="shop", headline="어떤 구장에서 뛰세요?", collect=True,
        count={"prefix": f"전체 {len(PRODUCTS)}종", "strong": "", "suffix": ""},
        shelf={"kind": "products", "blur": MAX_BLUR, "paused": False, "cards": [product_card(c, {}) for c in HOME_CODES], "empty_text": None},
        slots=slots({}, []), hint="답할수록 뒤에 있는 축구화 3켤레가 선명해져요.",
        placeholder="예: 흙운동장에서 뛰고, 호날두를 좋아해요",
    )


def service_home(acc, headline=None) -> dict:
    """이미 주문한 고객의 첫 화면: 가장 급한 주문부터 보여준다."""
    orders = _sorted_orders(acc)
    return _view(
        screen="service",
        headline=headline or service_greeting({**acc, "orders": orders}).replace("🧾 ", ""),
        count={"prefix": f'{acc["name"]}님 주문 ', "strong": f'{len(orders)}건', "suffix": ""},
        shelf={"kind": "orders", "blur": 0, "paused": False, "cards": [order_card(o, i == 0) for i, o in enumerate(orders[:3])], "empty_text": None},
        hint="교환, 반품, 배송… 무엇이든 아래에 말씀해 주세요.",
        placeholder="교환, 반품, 배송… 무엇이든 말씀해 주세요",
    )


def result_view(s: dict) -> dict:
    """대화 한 턴의 결과 화면."""
    c = to_client(s)
    p, route, reason = s.get("profile") or {}, c["route"], c["reason"]
    acc = s.get("account")
    common = {"screen": "result", "headline": c["reply"], "echo": s.get("user_text"), "route": route, "reason": reason,
              "source": c["source"], "default_size": p.get("size") or DEFAULT_SIZE, "background": background_url(p.get("surface"))}

    if c["cs_card"]:   # 축구화 자리에 CS 카드뉴스가 뜬다. 논의는 카드 안에 있으므로 아래에 또 그리지 않는다
        k = c["cs_card"]
        return _view(**common, count={"prefix": "고객 문의 처리 과정", "strong": "", "suffix": ""},
                     shelf={"kind": "news", "blur": 0, "paused": False, "cards": [], "empty_text": None},
                     news={"summary": k["summary"], "rules": k["rules"], "verdict": k["verdict"], "hold": k["verdict"] == "사장님 확인",
                           "next": k["next"], "options": k.get("options") or [], "discussion": c["discussion"], "hidden": c["hidden"],
                           "date": day_iso(0)})   # 내려받는 접수 메모에 찍히는 날짜

    if route == "ask" and reason == "cs-info":   # 교환·반품 정보를 묻는 중: 주문이 있으면 그 주문을, 없으면 흐린 진열대를 뒤에 둔다
        if acc and acc["orders"]:
            orders = _sorted_orders(acc)
            return _view(**common, count={"prefix": f'{acc["name"]}님 주문 ', "strong": f'{len(orders)}건', "suffix": ""},
                         shelf={"kind": "orders", "blur": 0, "paused": False, "cards": [order_card(o, i == 0) for i, o in enumerate(orders[:3])], "empty_text": None},
                         discussion=c["discussion"], hidden=c["hidden"])
        return _view(**common, collect=True, count={"prefix": "교환·반품 문의", "strong": "", "suffix": ""},
                     shelf={"kind": "products", "blur": MAX_BLUR, "paused": False, "cards": [product_card(x, {}) for x in HOME_CODES], "empty_text": None},
                     discussion=c["discussion"], hidden=c["hidden"])

    if route == "ask" and (reason or "").startswith("more:") and acc:   # 추가 주문: 지난번에 산 축구화를 다시 살 수 있게 먼저 보여준다
        on_sale = {x["code"] for x in PRODUCTS}
        again = list(dict.fromkeys(o["code"] for o in acc["orders"] if o["code"] in on_sale))[:3]
        if again:
            last_size = next(o["size"] for o in acc["orders"] if o["code"] == again[0])
            return _view(**{**common, "default_size": p.get("size") or last_size},
                         count={"prefix": "지난번에 주문한 축구화 ", "strong": f"{len(again)}종", "suffix": ""},
                         shelf={"kind": "products", "blur": 0, "paused": False, "empty_text": "새 축구화는 아래에 조건을 말씀해 주세요",
                                "cards": [product_card(code, {}, "지난번 주문", quiet=i > 0, buyable=True) for i, code in enumerate(again)]},
                         slots=slots(p, s.get("skipped")), discussion=c["discussion"], hidden=c["hidden"])

    if route == "answer":   # 질문에 답한 화면: 답에 나온 상품이 있으면 그것을, 없으면 지금 조건에 맞는 것을 뒤에 둔다
        codes = [x["code"] for x in c["candidates"]]
        shown = codes or [x["code"] for x in rank_products(filter_products(p), p)[:3]]
        return _view(**common,
                     count={"prefix": "질문에 나온 축구화" if codes else f"전체 {len(PRODUCTS)}종", "strong": "", "suffix": ""},
                     shelf={"kind": "products", "blur": 0, "paused": False, "empty_text": None,
                            "cards": [product_card(code, p, buyable=True) for code in shown]},
                     slots=slots(p, s.get("skipped")), discussion=c["discussion"], hidden=c["hidden"],
                     hint="조건(구장·발볼·예산)을 말씀해 주시면 맞는 축구화를 골라 드려요.")

    done = route in ("recommend", "alternative")
    filled = sum(p.get(k) is not None or k in (s.get("skipped") or []) for k in SLOT_ORDER)
    cards = []
    for i, x in enumerate(c["candidates"]):
        if route == "alternative":
            label, quiet = ("가장 가까운 1켤레" if i == 0 else None), False
        elif route == "recommend":
            label, quiet = ("먼저 신어볼 1켤레", False) if i == 0 else (("대안", True) if x["trade"] else (None, False))
        else:
            label, quiet = None, False
        cards.append(product_card(x["code"], p, label, quiet, x["trade"], buyable=done))
    health = route == "escalate" and reason == "health"
    if health and not cards:   # 추천을 멈춘 화면: 빈 칸 대신 멈춰 선 진열대를 보여준다
        cards = [product_card(code, {}) for code in HOME_CODES if code in {x["code"] for x in PRODUCTS}]
    count = ({"prefix": "조건을 전부 맞추는 신발 0종 → ", "strong": f'가장 가까운 {len(cards)}켤레', "suffix": ""} if route == "alternative"
             else {"prefix": "추천을 잠시 멈췄어요", "strong": "", "suffix": ""} if health
             else {"prefix": f"전체 {len(PRODUCTS)}종 → ", "strong": f'{s.get("pool", len(PRODUCTS))}종', "suffix": " 남음"})
    handoff = None
    if route == "escalate":
        health = reason == "health"
        handoff = {
            "title": "피팅 전문가에게 넘겼어요" if health else "사장님께 대안과 함께 넘겼어요",
            "body": "발 건강은 AI가 판단하지 않아요. 평일 10:00–18:00에 순서대로 연락드려요." if health else "조건을 모두 맞추는 신발이 없어서, 아래 대안을 붙여 전달했어요.",
            "items": ["피팅 전문가 상담 예약", "매장 방문 시착"] if health else (s.get("alts") or ["조건을 바꿔서 다시 찾기"]),
        }
    return _view(
        **common, collect=not (done or route == "escalate"), count=count,
        shelf={"kind": "products", "blur": 0 if done else round(MAX_BLUR * (1 - filled / len(SLOT_ORDER)), 1),
               "paused": route == "escalate" and reason == "health", "cards": cards,
               "empty_text": "조건에 맞는 재고가 없어요" if (route == "escalate" and reason == "empty") else "조건을 통과한 신발은 여기까지예요"},
        slots=slots(p, s.get("skipped")), handoff=handoff, discussion=c["discussion"], hidden=c["hidden"],
    )


def account_view(acc) -> Optional[dict]:
    if not acc:
        return None
    return {"id": acc["id"], "name": acc["name"], "role": acc.get("role", "customer"), "orders": [order_card(o) for o in acc["orders"]]}


def view_for(s: dict) -> dict:
    """지금 이 대화가 보여줄 화면 (새로고침해도 같은 화면이 나오게 State만으로 정한다)."""
    acc = s.get("account")
    if s.get("turn"):
        return result_view(s)
    if acc and acc["orders"]:
        return service_home(acc)
    return shop_home()


def catalog_card(p: dict, stock: dict) -> dict:
    """둘러보기 화면의 상품 한 장: 추천 카드와 같은 모양에 '어느 구장에 맞는지'를 더한다."""
    sizes = [z for z, q in sorted(stock.get(p["code"], {}).items()) if q > 0]
    return {**product_card(p["code"], {}, buyable=True), "sizes": sizes, "size_note": None if sizes else "전 사이즈 품절",
            "surfaces": [surf for surf, studs in SURFACE_TO_STUD.items() if p["stud"] in studs]}


def catalog(demo: bool = True, stock: Optional[dict] = None) -> dict:
    """화면이 처음 받아 두는 데이터. 데모 모드가 아니면 데모 계정 목록은 비운다. sizes는 재고가 있는 사이즈만."""
    stock = stock or {}
    return {
        "products": [catalog_card(p, stock) for p in PRODUCTS],
        "surfaces": list(SURFACE_TO_STUD), "lines": LINES,
        "demo_accounts": [{"id": k, "name": v["name"], "desc": ACCOUNT_DESC.get(k, "")} for k, v in DEMO_ACCOUNTS.items()] if demo else [],
        "policy": POLICY,
        "shop_home": shop_home(),
    }
