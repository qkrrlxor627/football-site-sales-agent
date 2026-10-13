"""State, 노드, 그래프 조립, 대화 도우미."""
import math
from typing import Optional

from .data import *  # noqa: F401,F403
from .extract import extract, ground_check
from .tools import check_policy, filter_products, find_order, nearest_alternatives, player_line, rank_products

# 노드는 State 전체를 받고, 바꿀 키만 담은 dict를 반환한다. LangGraph가 그 dict를 State에 합친다.
# discussion은 reducer(operator.add)라서 '새 항목만' 반환하면 기존 기록 뒤에 붙는다.
import operator
from typing import Annotated, TypedDict


class State(TypedDict, total=False):
    user_text: str                                  # 이번 턴 고객 메시지 (매 턴 덮어씀)
    turn: int
    source: str                                     # 이번 턴 정보 추출 방식 (LLM / 키워드 규칙)
    extracted: dict
    profile: dict                                   # surface, width, budget, size, style, brand
    asked: dict                                     # 칸별 되묻기 횟수
    skipped: list
    intent: str
    cs: dict                                        # 교환·반품 대화 중 모은 정보
    account: Optional[dict]                         # 로그인한 고객과 주문
    route: str                                      # ask | recommend | alternative | cs | escalate
    reason: Optional[str]
    candidates: list
    tradeoffs: dict
    pool: int
    notice: Optional[str]
    cs_card: Optional[dict]
    alts: list
    reply: str
    discussion: Annotated[list, operator.add]       # {turn, agent, text, visibility} 누적


def say(state, agent, text, visibility="public"):
    return {"turn": state.get("turn", 0), "agent": agent, "text": text, "visibility": visibility}


EMPTY_PROFILE = {"surface": None, "width": None, "budget": None, "size": None, "style": None, "brand": None}
EMPTY_CS = {"topic": None, "days": None, "worn": None, "repeat": False, "waiting": False}


def intake_node(state: State) -> dict:
    """① 접수 에이전트: 문장에서 정보를 뽑아 profile에 합친다. 턴마다 바뀌는 값은 여기서 초기화."""
    turn = state.get("turn", 0) + 1
    st = {**state, "turn": turn}
    e, source = extract(state["user_text"], state)
    profile = {**EMPTY_PROFILE, **(state.get("profile") or {})}
    disc = []
    if source == "LLM":
        disc.append(say(st, "접수 에이전트", "LLM이 문장을 읽고 조건을 정리했어요. 판단은 규칙이 해요."))
        e, dropped = ground_check(e, state["user_text"])
        if dropped:
            disc.append(say(st, "검수 에이전트", f'고객이 말하지 않은 값을 LLM이 채워서 버렸어요: {", ".join(dropped)}'))
    filled = []
    if (state.get("cs") or {}).get("waiting"):
        e = e.model_copy(update={"surface": None, "width": None, "budget": None, "size": None})  # CS 질문에 답하는 중엔 "실내에서만 신었어요"를 구장으로 읽지 않는다
    if e.surface:
        profile["surface"] = e.surface; filled.append(f"구장: {e.surface}")
    if e.width:
        profile["width"] = e.width; filled.append(f"발볼: {e.width}")
    if e.budget is not None and (e.budget == -1 or 10000 <= e.budget <= 3000000):
        profile["budget"] = math.inf if e.budget == -1 else e.budget; filled.append(f'예산: {won(profile["budget"])}')
    if e.size and 220 <= e.size <= 310:
        profile["size"] = e.size; filled.append(f"사이즈: {e.size}mm")
    if filled:
        disc.append(say(st, "접수 에이전트", ", ".join(filled) + " 확인했어요."))
    if e.player or e.style_line:
        line, how = (player_line(e.player, e.style_line if source == "LLM" else None) if e.player else (e.style_line, "취향"))
        if line:
            src = f"선수: {e.player}" + (f" ({e.player_boot})" if e.player_boot else "") if e.player else "취향"
            profile["style"] = {"line": line, "why": e.style_why or "", "source": src}
            disc.append(say(st, "접수 에이전트", f"취향 신호: {src} → 우리 매장에선 {line} 라인이 가장 가까워요 ({how})."))
    notice = None
    if e.brand:
        profile["brand"] = e.brand
        if e.brand not in CARRIED_BRANDS:
            notice = f"{e.brand}는 취급하지 않아서, 나이키에서 가장 비슷한 쪽으로 골라 드릴게요."
            disc.append(say(st, "피팅 에이전트", f"{e.brand} 요청이에요. 거절로 끝내지 않고 나이키 대안으로 갈게요."))
            disc.append(say(st, "재고 에이전트", f"{e.brand} 입점 문의로 집계(내부).", "internal"))
    if e.other_requests:
        disc.append(say(st, "접수 에이전트", "규칙에 없는 요청은 참고로 기록해요: " + ", ".join(e.other_requests[:3])))
    missed = not filled and not profile.get("style") and not e.brand
    return {
        "turn": turn, "source": source, "extracted": e.model_dump(), "profile": profile, "discussion": disc,
        # 턴마다 새로 정해지는 값들 초기화
        "route": None, "reason": "missed" if missed else None, "candidates": [], "tradeoffs": {},
        "notice": notice, "cs_card": None, "alts": [], "reply": "",
        "asked": state.get("asked") or {k: 0 for k in SLOT_ORDER}, "skipped": state.get("skipped") or [],
        "cs": state.get("cs") or dict(EMPTY_CS), "account": state.get("account"),
    }


def guard_node(state: State) -> dict:
    """② 안전 가드: 발 건강 언급은 무조건 사람에게. 키워드 OR LLM 판단 중 하나라도 걸리면 멈춘다."""
    hit = next((w for w in RED_FLAGS if w in state["user_text"]), None)
    if not hit and state["extracted"].get("health_flag"):
        hit = "발 건강"
    if not hit:
        return {}
    return {
        "route": "escalate", "reason": "health",
        "discussion": [
            say(state, "접수 에이전트", f'"{hit}" 관련 언급이 있어요. 발 건강은 AI가 판단하지 않아요.'),
            say(state, "피팅 에이전트", "추천을 멈추고 피팅 전문가 상담으로 넘길게요."),
            say(state, "정책 에이전트", "건강 관련 건은 매니저 배정(내부 SLA).", "internal"),
        ],
    }


def classify_node(state: State) -> dict:
    """③ 분류: 교환·반품 정보를 기다리는 중이면 그 주제를 유지, 아니면 추출된 intent."""
    cs = state["cs"]
    return {"intent": cs["topic"] if cs.get("waiting") else state["extracted"]["intent"]}


def consult_node(state: State) -> dict:
    """④-a 피팅 에이전트: 규칙 필터 → 빈칸 되묻기 / 추천 / 대안."""
    p = state["profile"]
    asked, skipped = dict(state["asked"]), list(state["skipped"])
    items = filter_products(p)
    ranked = rank_products(items, p)
    d = []
    if p.get("surface"):
        n = len(filter_products({"surface": p["surface"]}))
        d.append(say(state, "피팅 에이전트", f'{p["surface"]}이면 {"·".join(SURFACE_TO_STUD[p["surface"]])}만 남길게요. {len(PRODUCTS)}종 → {n}종.'))
    if p.get("style"):
        has = any(x["line"] == p["style"]["line"] for x in items)
        d.append(say(state, "피팅 에이전트", f'{p["style"]["line"]} 라인을 앞에 둘게요.' if has else f'{p["style"]["line"]} 라인에는 지금 조건에 맞는 모델이 없어요. 조건을 어기지 않고 다른 라인으로 갈게요.'))

    if not items:
        near = nearest_alternatives(p)
        if near:
            top = near[:3]
            d.append(say(state, "피팅 에이전트", "조건을 전부 맞추는 신발이 없어요. 안전한 대체만 허용해서 가장 가까운 순서로 골랐어요."))
            d.append(say(state, "재고 에이전트", "같은 조건 문의가 쌓이면 입고를 검토하도록 사장님께 기록했어요."))
            d.append(say(state, "재고 에이전트", "해당 조건 매입 단가·발주 수량 검토(내부).", "internal"))
            return {"candidates": [x[0]["code"] for x in top], "tradeoffs": {x[0]["code"]: x[2] for x in top},
                    "pool": 0, "route": "alternative", "reason": "nearest", "discussion": d}
        d.append(say(state, "피팅 에이전트", "안전하게 대체할 신발도 없어요. 사람이 판단해야 해요."))
        return {"candidates": [], "pool": 0, "route": "escalate", "reason": "empty", "alts": ["입고 알림 신청", "매장 방문 시착 상담"], "discussion": d}

    nxt = next((k for k in SLOT_ORDER if p.get(k) is None and k not in skipped), None)
    if nxt and asked[nxt] >= MAX_ASK:
        skipped.append(nxt)
        d.append(say(state, "피팅 에이전트", f"{SLOT_LABEL[nxt]}는 두 번 물어도 몰라서 그 조건 없이 진행할게요."))
        nxt = next((k for k in SLOT_ORDER if p.get(k) is None and k not in skipped), None)
    if nxt:
        asked[nxt] += 1
        return {"candidates": [x["code"] for x in ranked[:3]], "pool": len(items), "asked": asked, "skipped": skipped,
                "route": "ask", "reason": nxt if state.get("reason") != "missed" else "missed:" + nxt, "discussion": d}

    top = ranked[:3]
    tradeoffs = {}
    if len(top) < 3:  # 딱 맞는 게 3켤레보다 적으면 남는 자리는 대안으로 채운다
        for prod, cost, trade in nearest_alternatives(p):
            if len(top) >= 3:
                break
            if trade and prod not in top:
                top.append(prod); tradeoffs[prod["code"]] = trade
        d.append(say(state, "피팅 에이전트", f"딱 맞는 건 {len(items)}켤레라 나머지 자리는 대안으로 채웠어요."))
    return {"candidates": [x["code"] for x in top], "tradeoffs": tradeoffs, "pool": len(items), "asked": asked,
            "skipped": skipped, "route": "recommend", "reason": None, "discussion": d}


def cs_node(state: State) -> dict:
    """④-b 정책 에이전트: 로그인했으면 주문 기록으로, 아니면 고객에게 물어서 정책 규칙으로 판단."""
    e = state["extracted"]
    cs = {**state["cs"], "topic": state["intent"]}
    for k in ("days", "worn"):
        if e["cs"].get(k) is not None:
            cs[k] = e["cs"][k]
    cs["repeat"] = cs.get("repeat") or e["cs"].get("repeat", False)
    acc = state.get("account")
    d = []

    if cs["topic"] == "배송":
        kind, o = find_order(acc, "배송")
        rules = [f'{POLICY["ship_cutoff"]} 이전 결제 → 당일 출고', "출고 후 1~2일 내 도착", "주말·공휴일은 출고 없음"]
        d.append(say(state, "정책 에이전트", "택배사 지연 시 보상 쿠폰 기준(내부).", "internal"))
        if kind == "none":
            nxt = f'{POLICY["ship_cutoff"]} 전 결제는 당일 출고되고 보통 1~2일 뒤 도착해요. 로그인하면 주문별로 알려 드려요.'
        elif kind == "open":
            nxt = (f'{order_label(o)} 주문({o["id"]})은 결제 완료, 출고 준비 중이에요.' if o["status"] == "결제완료"
                   else f'{order_label(o)} 주문({o["id"]})은 {"오늘" if days_since(o["shipped_at"]) == 0 else str(days_since(o["shipped_at"])) + "일 전"} 출고돼 배송 중이에요. 보통 1~2일 안에 도착해요.')
            d.append(say(state, "검수 에이전트", "도착 날짜를 확정해서 약속하지 않도록 했어요."))
        else:
            nxt = f'진행 중인 배송은 없어요.' + (f' 최근 주문 {order_label(o)}은 {days_since(o["delivered_at"])}일 전에 배송 완료됐어요.' if o else "")
        return {"cs": {**cs, "waiting": False}, "route": "cs", "reason": "ship", "discussion": d,
                "cs_card": {"summary": f'{acc["name"]}님 · {o["id"]}' if (acc and o) else "배송 문의", "rules": rules, "verdict": "자동 답변", "next": nxt}}

    kind, order = find_order(acc, cs["topic"])
    if kind == "busy" and not state["cs"].get("waiting"):
        d.append(say(state, "정책 에이전트", f'{order["id"]}는 이미 사후 서비스 중이라 중복 접수하지 않아요.'))
        return {"cs": {**cs, "waiting": False}, "route": "cs", "reason": "status", "discussion": d,
                "cs_card": {"summary": f'{acc["name"]}님 · {order["id"]}', "rules": ["진행 중인 교환·반품은 중복 접수하지 않음"], "verdict": order["status"],
                            "next": f'{order_label(order)}은 지금 "{order["status"]}" 상태예요. {order.get("note") or ""}'.strip()}}
    if kind == "no_delivered":
        return {"cs": {**cs, "waiting": False}, "route": "cs", "reason": "no-order", "discussion": d,
                "cs_card": {"summary": f'{acc["name"]}님 · {cs["topic"]} 문의', "rules": ["교환·반품은 배송 완료 후 신청"], "verdict": "안내",
                            "next": "배송 완료된 주문이 아직 없어요. 상품을 받은 뒤 다시 말씀해 주세요."}}
    if order:
        cs["days"], cs["repeat"] = days_since(order["delivered_at"]), order["exchanges"] > 0
        d.append(say(state, "정책 에이전트", f'{order["id"]} 주문 기록에서 수령 {cs["days"]}일째, 교환 이력 {order["exchanges"]}회를 확인했어요.'))

    missing = []
    if cs.get("days") is None:
        missing.append("받으신 지 며칠 되셨나요?")
    if cs.get("worn") is None and not (cs.get("days") is not None and cs["days"] > POLICY["return_days"]):
        missing.append("실외 구장에서 신으셨나요, 실내에서 신어보기만 하셨나요?")  # 기간이 지났으면 답이 같아 묻지 않음
    if missing and not state["cs"].get("waiting"):
        d.append(say(state, "정책 에이전트", "착용 여부는 기록에 없어서 고객에게 물어볼게요." if order else "수령일과 착용 여부를 알아야 판단할 수 있어요."))
        return {"cs": {**cs, "waiting": True}, "route": "ask", "reason": "cs-info", "discussion": d,
                "reply": " ".join(missing) + ("" if acc else " 로그인하면 주문 기록으로 바로 확인해요.")}

    pol = check_policy(cs["topic"], cs.get("days"), cs.get("worn"), cs.get("repeat", False))
    auto = pol["auto"]
    d.append(say(state, "정책 에이전트", "조건을 모두 충족해서 자동 접수할게요." if auto else "규칙 밖이라 제가 약속할 수 없어요. 사장님 결재로 넘길게요."))
    if not auto:
        d.append(say(state, "정책 에이전트", "착용품 재판매 불가 시 손실액 기준 결재 라인(내부).", "internal"))
    if cs["topic"] == "교환":
        d.append(say(state, "피팅 에이전트", "같은 모델 교환이 반복되면 발 모양 문제일 수 있어요. 피팅 상담을 같이 제안할게요." if cs.get("repeat") else "교환 사이즈는 평소 운동화보다 5mm 크게 고르는 경우가 많아요."))
    update = {}
    if order:
        status = ("교환 접수" if cs["topic"] == "교환" else "반품 접수") if auto else "사장님 확인 중"
        note = ("회수 기사님이 1~2일 안에 방문해요." if cs["topic"] == "교환" else "회수 후 검수되면 환불돼요.") if auto else "평일 10:00–18:00에 사장님이 확인해요."
        orders = [{**o, "status": status, "note": note, "exchanges": o["exchanges"] + (1 if auto and cs["topic"] == "교환" else 0)} if o["id"] == order["id"] else o for o in acc["orders"]]
        update["account"] = {**acc, "orders": orders}
        d.append(say(state, "접수 에이전트", f'{order["id"]} 주문을 "{status}" 상태로 바꿨어요.'))
    nxt = (("교환 접수 완료. 회수 기사님이 1~2일 안에 방문해요." if cs["topic"] == "교환" else f'반품 접수 완료. 검수 후 왕복 배송비 {won(POLICY["return_fee"])}을 뺀 금액이 환불돼요.')
           if auto else "사장님이 확인 중이에요. 원하시는 처리 방법을 말씀해 주시면 그 기준으로 검토해요.")
    return {**update, "cs": {**cs, "waiting": False}, "route": "cs" if auto else "escalate", "reason": "auto" if auto else "policy", "discussion": d,
            "cs_card": {"summary": (f'{acc["name"]}님 · {order["id"]} · ' if order else "") + f'{cs["topic"]} 요청', "rules": pol["rules"],
                        "verdict": "자동 접수" if auto else "사장님 확인", "next": nxt,
                        "options": None if auto else (["피팅 상담 후 다른 모델로 교환", "같은 모델 다른 사이즈 (예외 승인 요청)"] if cs["topic"] == "교환" else ["예외 반품 요청", "같은 가격대 다른 모델로 교환"])}}


def review_node(state: State) -> dict:
    """⑤ 검수 에이전트: 추천 후보가 구장 규칙을 어기면 내보내지 않는다 (LLM이 끼어들어도 마지막 안전선)."""
    surf = state["profile"].get("surface")
    if not surf or state.get("route") not in ("recommend", "alternative"):
        return {}
    allowed = set(SURFACE_TO_STUD[surf]) | set(SUBSTITUTE.get(surf, {}))
    bad = [c for c in state["candidates"] if BY_CODE[c]["stud"] not in allowed]
    if bad:
        return {"route": "escalate", "reason": "review", "candidates": [c for c in state["candidates"] if c not in bad],
                "discussion": [say(state, "검수 에이전트", f"{bad}는 {surf}에 위험한 스터드라 뺐어요.")]}
    return {"discussion": [say(state, "검수 에이전트", "추천 후보가 구장 규칙을 지키는지 확인했어요.")]}


def respond_node(state: State) -> dict:
    """⑥ 답변 작성 + 내부 정보 차단. 템플릿 문장이라 같은 입력에 항상 같은 답."""
    r, reason, p = state.get("route"), state.get("reason"), state["profile"]
    reply = state.get("reply") or ""
    if not reply:
        if r == "ask":
            slot = (reason or "").replace("missed:", "")
            pre = "조건을 찾지 못했어요. " if (reason or "").startswith("missed") else ""
            filled = sum(p.get(k) is not None for k in SLOT_ORDER)
            reply = pre + (f'지금 조건으로 {state["pool"]}종이 남았어요. ' if filled else "") + ASK_TEXT[slot]
        elif r == "recommend":
            top = [BY_CODE[c] for c in state["candidates"]]
            lead = f'조건에 맞는 {state["pool"]}종 중 3켤레를 골랐어요.' if state["pool"] >= 3 else f'딱 맞는 건 {state["pool"]}켤레라, 나머지는 가장 가까운 대안으로 채웠어요.'
            reply = f'{lead} 가장 먼저 신어볼 만한 건 {top[0]["name"]} {top[0]["stud"]}예요. {top[0]["feel"]}.'
            st = (p.get("style") or {}).get("line")
            if st and top[0]["line"] != st:
                liked = next((x for x in top if x["line"] == st), None)
                reply += f' 좋아하시는 {st}는 대안으로 {liked["name"]} {liked["stud"]}를 넣었어요.' if liked else f" 좋아하시는 {st} 라인에는 이 조건에 맞는 모델이 없어요."
        elif r == "alternative":
            top = BY_CODE[state["candidates"][0]]
            reply = f'조건을 전부 맞추는 신발은 없어서, 가장 가까운 {len(state["candidates"])}켤레를 골랐어요. 1순위는 {top["name"]} {top["stud"]}예요. (양보: {" · ".join(state["tradeoffs"][top["code"]])})'
        elif r == "cs":
            reply = state["cs_card"]["next"]
        elif r == "escalate":
            reply = {"health": "발 건강과 관련된 부분은 제가 판단하지 않고 피팅 전문가에게 연결해 드릴게요. 상담 전까지 추천은 잠시 멈춰 둘게요.",
                     "empty": "안전하게 권할 수 있는 신발이 없어서 사장님께 넘겼어요. 입고 알림이나 매장 시착 상담을 도와드릴게요.",
                     "review": "추천을 확인하다가 문제가 있어 담당자에게 넘겼어요."}.get(reason) or (state.get("cs_card") or {}).get("next", "담당자에게 넘겼어요.")
    if state.get("notice") and r not in ("cs",):
        reply = f'{state["notice"]} {reply}'
    leaked = [w for w in FORBIDDEN_WORDS if w in reply]
    if leaked:  # 템플릿이라 거의 없지만, 나중에 LLM이 답변을 쓰게 되면 이 줄이 마지막 방어선
        reply = "내부 정보가 섞여 답변을 다시 만들고 있어요. 담당자가 확인할게요."
    return {"reply": reply}


from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


def route_after_guard(state: State) -> str:
    return "health" if state.get("reason") == "health" else "ok"


def route_by_intent(state: State) -> str:
    return "consult" if state["intent"] == "상담" else "cs"


builder = StateGraph(State)
builder.add_node("intake", intake_node)
builder.add_node("guard", guard_node)
builder.add_node("classify", classify_node)
builder.add_node("consult", consult_node)
builder.add_node("cs", cs_node)
builder.add_node("review", review_node)
builder.add_node("respond", respond_node)
builder.add_edge(START, "intake")
builder.add_edge("intake", "guard")
builder.add_conditional_edges("guard", route_after_guard, {"health": "respond", "ok": "classify"})
builder.add_conditional_edges("classify", route_by_intent, {"consult": "consult", "cs": "cs"})
builder.add_edge("consult", "review")
builder.add_edge("review", "respond")
builder.add_edge("cs", "respond")
builder.add_edge("respond", END)


def build_graph(checkpointer=None):
    """같은 그래프를 다른 저장소로 컴파일한다. API는 SQLite 체크포인터를 넘겨 재시작해도 대화가 이어지게 한다."""
    return builder.compile(checkpointer=checkpointer or MemorySaver())


graph = build_graph()  # CLI·데모·평가·테스트용 (메모리)



def mermaid() -> str:
    """그래프 구조를 Mermaid 텍스트로. README나 발표 자료에 붙여 쓰면 된다."""
    return graph.get_graph().draw_mermaid()


import uuid

SHOW_DISCUSSION = True


def to_client(s: dict) -> dict:
    """서버 → 화면 응답. internal 논의는 여기서 빠진다 (화면이 아니라 서버에서 거르는 게 핵심)."""
    turn_disc = [m for m in s.get("discussion", []) if m["turn"] == s["turn"]]
    return {
        "route": s.get("route"), "reason": s.get("reason"), "reply": s.get("reply"), "source": s.get("source"),
        "candidates": [{"code": c, "name": f'{BY_CODE[c]["name"]} {BY_CODE[c]["stud"]}', "price": BY_CODE[c]["price"], "trade": s.get("tradeoffs", {}).get(c)} for c in s.get("candidates", [])],
        "cs_card": s.get("cs_card"),
        "discussion": [{"agent": m["agent"], "text": m["text"]} for m in turn_disc if m["visibility"] == "public"],
        "hidden": sum(m["visibility"] == "internal" for m in turn_disc),
    }


def new_thread(user_id: Optional[str] = None) -> dict:
    """대화 하나 = thread 하나. user_id를 주면 데모 계정으로 로그인한 상태로 시작한다."""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    if user_id:
        acc = make_account(user_id)
        assert acc, f"없는 데모 계정: {user_id}"
        graph.update_state(config, {"account": acc}, as_node="respond")
        print(service_greeting(acc))
    return config


def service_greeting(acc: dict) -> str:
    """이미 주문한 고객의 첫 화면: 가장 급한 주문부터 먼저 말을 건다."""
    pri = lambda o: 0 if o["status"] in IN_SERVICE else 1 if o["status"] == "배송중" else 2 if o["status"] == "결제완료" else 4 if o["status"] == "반품 완료" else 3
    os_ = sorted(acc["orders"], key=pri)
    o = os_[0]
    if o["status"] in IN_SERVICE:
        line = f'{order_label(o)} 건은 "{o["status"]}" 상태예요. {o.get("note") or ""}'
    elif o["status"] == "배송중":
        line = f'{order_label(o)}은 배송 중이에요. 보통 1~2일 안에 도착해요.'
    elif o["status"] == "결제완료":
        line = f'{order_label(o)}은 결제 완료, 출고 준비 중이에요.'
    elif o["status"] == "반품 완료":
        line = f'{order_label(o)} 반품이 완료됐어요.'
    else:
        d = days_since(o["delivered_at"])
        line = f'{order_label(o)} 받으신 지 {d}일째예요.' + (f' 교환은 {POLICY["return_days"] - d}일 안에 신청할 수 있어요.' if d <= POLICY["return_days"] else "")
    return f'🧾 {acc["name"]}님, {line.strip()} 무엇을 도와드릴까요?'


def chat(text: str, config: dict, quiet: bool = False) -> dict:
    s = graph.invoke({"user_text": text}, config)
    c = to_client(s)
    if not quiet:
        print(f"\n👤 {text}")
        print(f'🤖 {c["reply"]}   [{c["route"]}/{c["reason"]} · {c["source"]}]')
        for x in c["candidates"]:
            print(f'   · {x["name"]} {x["price"]:,}원' + (f'  (양보: {" · ".join(x["trade"])})' if x["trade"] else ""))
        if c["cs_card"]:
            print("   📰", c["cs_card"]["summary"], "|", " / ".join(c["cs_card"]["rules"]), "|", c["cs_card"]["verdict"])
        if SHOW_DISCUSSION:
            for m in c["discussion"]:
                print(f'   💬 {m["agent"]}: {m["text"]}')
            if c["hidden"]:
                print(f'   🔒 내부 논의 {c["hidden"]}건 비공개')
    return c
