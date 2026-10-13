"""질문 답변: 상품·정책을 묻는 말에 표를 조회해 답한다. 그래프에서 유일하게 '도는' 구간이다.

    answer_agent ⇄ answer_tools  (최대 MAX_STEPS바퀴)  →  answer_check(규칙 검수)  →  respond
"""
# 추천과 교환·반품 판단은 여기서 하지 않는다. LLM은 읽기 전용 도구로 표를 조회해 '설명'만 쓰고,
# 그 답이 표와 맞는지는 answer_check가 규칙으로 다시 본다. 어긋나면 내보내지 않고 사장님께 넘긴다.
#
# 무한 루프 방지 (서로 기대지 않는 네 겹):
#   1) 바퀴 수는 State의 answer_steps가 세고, 계속 돌지 말지는 LLM이 아니라 answer_route가 이 숫자로 정한다
#   2) 마지막 바퀴는 도구가 없는 모델(WRITER)로 불러서 더 조회할 방법이 없다
#   3) 그래프 전체에 recursion_limit이 걸려 있다 (api.py)
#   4) LLM 호출마다 타임아웃, 구간 전체에 MAX_SECONDS
import json
import re
import time
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from . import telemetry
from .config import MODEL, USE_LLM
from .data import *  # noqa: F401,F403
from .extract import keyword_extract
from .tools import filter_products

MAX_STEPS = 3        # answer_agent가 도는 최대 횟수 (도구 조회는 많아야 2번, 마지막은 답만 쓴다)
MAX_SECONDS = 40     # 이 구간 전체가 쓸 수 있는 시간
MAX_REPLY = 400
FALLBACK = "정확히 확인이 필요한 질문이라 사장님께 전달했어요. 구장·발볼·예산을 알려 주시면 맞는 축구화는 바로 찾아 드릴게요."
STUD_TOKEN = re.compile(r"(?<![A-Za-z])(FG|SG|AG|MG|TF|HG|IC)(?![A-Za-z])")

SYSTEM = """너는 축구화 매장 PITCHROOM의 상담 직원이다. 고객의 질문에 '설명'으로만 답한다.
규칙:
- 반드시 도구로 조회한 내용만 말한다. 도구 결과에 없는 상품, 가격, 정책, 기능(방수, 무게 등)은 지어내지 말고 "확인이 필요해요"라고 한다.
- 가격은 도구가 준 숫자를 그대로 쓴다. 계산해서 새 숫자를 만들지 않는다.
- 구장에 맞는 스터드는 stud_guide 결과만 따른다. 거기 없는 스터드를 그 구장에 권하지 않는다.
- 발 건강·부상에 대한 조언은 하지 않는다.
- 한국어 존댓말, 세 문장 이내, 목록 기호 없이 쓴다.
- 교환·반품 접수나 주문은 네가 처리하지 않는다. 방법만 안내한다."""
LAST_ROUND = "더 조회할 수 없다. 지금까지 조회한 내용만으로 답을 써라. 모자라면 확인이 필요하다고 말해라."


# ---------- 도구: 전부 읽기 전용 ----------
def _brief(p: dict) -> dict:
    return {"code": p["code"], "name": p["name"], "color": p.get("color"), "line": p["line"], "stud": p["stud"], "width": p["width"],
            "price": p["price"], "list_price": p.get("list_price"), "feel": p["feel"]}


@tool
def find_products(line: Optional[str] = None, stud: Optional[str] = None, surface: Optional[str] = None,
                  width: Optional[str] = None, max_price: Optional[int] = None, on_sale: bool = False) -> list[dict]:
    """판매 중인 축구화를 조건으로 찾는다 (싼 순, 최대 8개). 쓰지 않는 조건은 비워 둔다.
    line: Mercurial, Phantom, Tiempo 중 하나. stud: FG, AG, MG, TF, IC 중 하나 (터프화는 TF).
    surface: 천연잔디, 인조잔디, 흙운동장, 풋살장, 실내 중 하나. 고객이 구장을 말했으면 stud 대신 surface를 쓴다 (그 구장에 허용된 스터드가 모두 나온다).
    width: 좁음, 보통, 넓음 중 하나. max_price: 원. on_sale: true면 할인 중인 것만 (list_price가 있는 상품이 할인 중이다)."""
    # 모델이 엉뚱한 값을 넣으면(예: "Mercurial|Phantom") 그 조건은 없는 것으로 본다. 잘못된 조건 때문에 "없어요"라고 답하게 두지 않는다
    line = next((l for l in LINES if l.lower() == str(line or "").strip().lower()), None)
    stud = str(stud or "").strip().upper() if str(stud or "").strip().upper() in STUD_INFO else None
    profile = {"surface": surface if surface in SURFACE_TO_STUD else None, "width": width if width in ("좁음", "보통", "넓음") else None,
               "budget": max_price if isinstance(max_price, int) and max_price > 0 else None}
    items = [p for p in filter_products(profile) if (not line or p["line"] == line) and (not stud or p["stud"] == stud)
             and (not on_sale or (p.get("list_price") or 0) > p["price"])]
    return [_brief(p) for p in sorted(items, key=lambda p: p["price"])[:8]]


@tool
def product_detail(name_or_code: str) -> list[dict]:
    """상품 이름(일부)이나 코드(S-01)로 상품을 찾는다. 같은 이름에 스터드·색상이 여러 개면 모두 나온다."""
    q = name_or_code.strip().lower()
    return [_brief(p) for p in PRODUCTS if q == p["code"].lower() or q in p["name"].lower()][:6]


@tool
def stud_guide(surface: Optional[str] = None) -> dict:
    """스터드 종류 설명과, 구장별로 신어도 되는 스터드. surface를 주면 그 구장만."""
    surfaces = [surface] if surface in SURFACE_TO_STUD else list(SURFACE_TO_STUD)
    return {"studs": STUD_INFO, "allowed": {s: SURFACE_TO_STUD[s] for s in surfaces}, "lines": LINE_INFO}


@tool
def store_policy() -> dict:
    """매장 정책: 교환·반품 기한, 무료 교환 횟수, 반품 배송비, 당일 출고 마감."""
    return {"교환·반품 기한(수령 후 일)": POLICY["return_days"], "조건": "실외에서 신지 않은 상품", "무료 사이즈 교환 횟수": POLICY["free_exchange"],
            "단순 변심 반품 왕복 배송비(원)": POLICY["return_fee"], "당일 출고 마감": POLICY["ship_cutoff"], "배송": "출고 후 1~2일"}


TOOLS = {t.name: t for t in (find_products, product_detail, stud_guide, store_policy)}

AGENT = WRITER = None   # 도구를 쓸 수 있는 모델 / 답만 쓰는 모델. 테스트는 이 둘을 가짜로 바꿔 낀다
if USE_LLM:
    from langchain_openai import ChatOpenAI
    WRITER = ChatOpenAI(model=MODEL, temperature=0, timeout=20, max_retries=1)
    AGENT = WRITER.bind_tools(list(TOOLS.values()))


# ---------- 키 없이도 답할 수 있는 것: 표에서 바로 나오는 답 ----------
def table_answer(text: str) -> tuple[Optional[str], Optional[str]]:
    """표만 보고 할 수 있는 답 → (종류, 답). 종류가 FIXED에 들면 LLM이 있어도 이 답을 쓴다 (정책·안전은 문장이 흔들리면 안 된다)."""
    t = re.sub(r"\s+", " ", text)
    surface = keyword_extract(t).surface
    studs = [s.upper() for s in STUD_TOKEN.findall(t.upper())]
    if surface and studs:   # "인조잔디에 FG 신어도 돼요?"
        s, ok = studs[0], SURFACE_TO_STUD[surface]
        if s in ok:
            return "stud", f"네, {s}({STUD_INFO[s]})는 {surface}에 맞는 스터드예요."
        sub = SUB_NOTE.get(surface, {}).get(s)
        if sub:
            return "stud", f"{s}는 {surface}용은 아니지만 대신 쓸 수는 있어요 ({sub}). {surface}에는 {'·'.join(ok)}가 맞아요."
        return "stud", f"{s}({STUD_INFO[s]})는 {surface}에 권하지 않아요. {surface}에는 {'·'.join(ok)}가 맞아요."
    if studs and re.search(r"뭐|무엇|무슨|차이|종류", t):
        return "stud", " ".join(f"{s}는 {STUD_INFO[s]}예요." for s in dict.fromkeys(studs) if s in STUD_INFO)
    if re.search(r"배송비|(반품|교환).{0,8}(비용|돈|얼마)", t):
        return "policy", f'단순 변심 반품은 왕복 배송비 {won(POLICY["return_fee"])}을 고객님이 부담해요. 사이즈 교환은 {POLICY["free_exchange"]}회 무료예요.'
    if re.search(r"몇\s*번|몇\s*회|무료\s*교환", t):
        return "policy", f'사이즈 교환은 {POLICY["free_exchange"]}회까지 무료예요. 그 뒤로는 사장님이 확인해요.'
    if re.search(r"(교환|반품).{0,10}(며칠|기간|언제까지|조건|되나요|가능한가)", t):
        return "policy", f'교환·반품은 받으신 날부터 {POLICY["return_days"]}일 안에, 실외에서 신지 않은 상품만 신청할 수 있어요. 조건에서 벗어나면 사장님이 따로 확인해요.'
    if re.search(r"몇\s*시까지|당일\s*출고", t):
        return "policy", f'{POLICY["ship_cutoff"]} 전에 결제하면 당일 출고되고, 보통 1~2일 뒤에 도착해요. 주말·공휴일은 출고가 없어요.'
    if re.search(r"(제일|가장)\s*(싼|저렴)", t):
        items = sorted(filter_products({"surface": surface}), key=lambda p: p["price"])
        if items:
            p = items[0]
            return "cheapest", f'{surface + "에 맞는 것 중 " if surface else ""}가장 저렴한 건 {p["name"]} {p["stud"]}, {won(p["price"])}이에요.'
    if re.search(r"차이|다른\s*점|달라|비교", t):   # 라인 비교: 라인 이름을 말했거나 "라인"을 물었을 때만 (모델끼리 비교는 표 조회가 필요하다)
        named = [l for l in LINES if l.lower() in t.lower()] or (LINES if "라인" in t else [])
        if named:
            return "line", " ".join(f"{l} 라인은 {LINE_INFO[l]}이에요." for l in named)
    return None, None


FIXED = ("stud", "policy", "cheapest", "line")   # 이 종류는 LLM이 있어도 표로 답한다 (LLM은 표에 없는 설명을 덧붙이곤 한다)


def faq_answer(text: str) -> Optional[str]:
    return table_answer(text)[1]


# ---------- 노드 ----------
def _context(state: dict) -> str:
    prof = {SLOT_LABEL[k]: (won(v) if k == "budget" else v) for k in SLOT_ORDER if (v := (state.get("profile") or {}).get(k)) is not None}
    recent = " / ".join(f'{"고객" if h["role"] == "user" else "매장"}: {h["text"][:80]}' for h in (state.get("history") or [])[-5:-1])
    return f'지금까지 파악한 조건: {prof or "없음"}\n최근 대화: {recent or "없음"}\n고객 질문: {state["user_text"]}'


def answer_agent_node(state: dict) -> dict:
    """④-c 상담 에이전트: 표를 조회할지, 답을 쓸지 정한다. 돌 때마다 answer_steps가 1 오른다."""
    steps = (state.get("answer_steps") or 0) + 1
    started = state.get("answer_started") or time.time()
    out = {"answer_steps": steps, "answer_started": started}
    kind, faq = table_answer(state["user_text"])
    if AGENT is None or kind in FIXED:
        return {**out, "answer_draft": faq, "answer_msgs": []}   # 키가 없거나, 정책·스터드처럼 표로 답해야 하는 질문
    msgs = list(state.get("answer_msgs") or []) or [SystemMessage(SYSTEM), HumanMessage(_context(state))]
    last_round = steps >= MAX_STEPS or time.time() - started > MAX_SECONDS
    model = WRITER if last_round else AGENT
    t0 = time.perf_counter()
    try:
        ai = model.invoke(msgs + ([SystemMessage(LAST_ROUND)] if last_round else []))
        telemetry.record("answer", ms=(time.perf_counter() - t0) * 1000, tokens=((getattr(ai, "usage_metadata", None) or {}).get("total_tokens", 0)))
    except Exception:
        telemetry.record("answer", fallback=True, ms=(time.perf_counter() - t0) * 1000)
        return {**out, "answer_error": True, "answer_msgs": msgs}
    return {**out, "answer_msgs": msgs + [ai]}


def answer_route(state: dict) -> str:
    """더 돌지 말지는 여기서, 숫자와 시계로 정한다. LLM이 도구를 더 부르고 싶어 해도 상한에서 끝낸다."""
    msgs = state.get("answer_msgs") or []
    if state.get("answer_error") or not msgs:
        return "check"
    if (state.get("answer_steps") or 0) >= MAX_STEPS:
        return "check"
    if time.time() - (state.get("answer_started") or 0) > MAX_SECONDS:
        return "check"
    return "tools" if getattr(msgs[-1], "tool_calls", None) else "check"


def answer_tools_node(state: dict) -> dict:
    """도구 실행. 모르는 도구나 잘못된 인자는 오류 문장으로 돌려주고 멈추지 않는다."""
    msgs = list(state["answer_msgs"])
    used = list(state.get("answer_used") or [])
    for call in (getattr(msgs[-1], "tool_calls", None) or [])[:4]:   # 한 번에 부를 수 있는 도구 수도 묶는다
        fn = TOOLS.get(call["name"])
        try:
            result = fn.invoke(call.get("args") or {}) if fn else f'없는 도구: {call["name"]}'
        except Exception as err:
            result = f"조회 실패: {type(err).__name__}"
        used.append(call["name"])
        msgs.append(ToolMessage(json.dumps(result, ensure_ascii=False), tool_call_id=call.get("id") or call["name"]))
    return {"answer_msgs": msgs, "answer_used": used}


def _amounts(text: str) -> set[int]:
    out = {int(m.replace(",", "")) for m in re.findall(r"(\d[\d,]{3,})\s*원", text)}
    out |= {int(float(m) * 10000) for m in re.findall(r"(\d+(?:\.\d+)?)\s*만\s*원?", text)}
    return out


def mentioned_products(text: str, surface: Optional[str] = None) -> tuple[list[str], list[str]]:
    """답에 나온 상품 → (화면에 보여줄 코드, 문제). 이름 뒤에 스터드가 붙어 있으면 그 상품, 없으면 그 이름의 상품들."""
    allowed = set(SURFACE_TO_STUD[surface]) | set(SUBSTITUTE.get(surface, {})) if surface else None
    found, problems = [], []   # found: (답에서 나온 위치, 코드) — 화면에는 답에 나온 순서대로 보여준다
    for m in re.finditer(r"S-\d{2}", text):
        if m.group() in BY_CODE:
            found.append((m.start(), m.group()))
        else:
            problems.append(f"없는 상품 코드 {m.group()}")
    for name in sorted({p["name"] for p in PRODUCTS}, key=len, reverse=True):
        for hit in re.finditer(re.escape(name), text):
            near = text[hit.end():hit.end() + 45]
            stud = STUD_TOKEN.search(text[hit.end():hit.end() + 6].upper())
            same = [p for p in PRODUCTS if p["name"] == name]
            if stud:
                same = [p for p in same if p["stud"] == stud.group(1)]
                if not same:
                    problems.append(f"{name} {stud.group(1)}는 없는 상품")
                    continue
                if allowed is not None and stud.group(1) not in allowed:
                    problems.append(f"{name} {stud.group(1)}는 {surface}에 위험한 스터드")
                    continue
            # 같은 이름(과 스터드)에 색상·가격이 다른 상품이 있다: 바로 뒤에 나온 색상이나 가격으로 어느 것인지 좁힌다
            same = [p for p in same if p.get("color") and p["color"] in near] or [p for p in same if p["price"] in _amounts(near)] or same
            if allowed is not None:
                same = [p for p in same if p["stud"] in allowed]   # 그 구장에 안전한 것만 보여준다
            found += [(hit.start(), p["code"]) for p in sorted(same, key=lambda p: p["price"])]
        text = text.replace(name, " " * len(name))   # 긴 이름을 먼저 지워 짧은 이름이 겹쳐 잡히지 않게 (위치는 그대로 둔다)
    return list(dict.fromkeys(code for _, code in sorted(found, key=lambda f: f[0])))[:3], problems


def validate(draft: str, question: str, surface: Optional[str]) -> tuple[list[str], list[str]]:
    """LLM이 쓴 답이 표와 맞는지. (보여줄 상품 코드, 문제 목록). 문제가 하나라도 있으면 내보내지 않는다."""
    problems = []
    if not draft.strip():
        problems.append("빈 답")
    if len(draft) > MAX_REPLY:
        problems.append("너무 긴 답")
    problems += [f"내부 정보 단어 '{w}'" for w in FORBIDDEN_WORDS if w in draft]
    problems += [f"건강 조언 '{w}'" for w in RED_FLAGS if w in draft]
    prices = {p["price"] for p in BASE_PRODUCTS} | {p["price"] for p in PRODUCTS} | {p["list_price"] for p in PRODUCTS if p.get("list_price")}
    ok_amounts = prices | {POLICY["return_fee"]} | _amounts(question)
    problems += [f"표에 없는 금액 {won(a)}" for a in sorted(_amounts(draft) - ok_amounts)]
    problems += [f"표에 없는 기간 {d}일" for d in sorted({int(d) for d in re.findall(r"(\d+)\s*일", draft)} - {POLICY["return_days"], 1, 2})]
    codes, more = mentioned_products(draft, surface)
    if "할인" in draft or "세일" in draft:   # 할인 중이라고 말했으면 말한 상품이 정말 할인 중이어야 한다
        problems += [f'{BY_CODE[c]["name"]} {BY_CODE[c]["stud"]}는 할인 중이 아님' for c in codes if not BY_CODE[c].get("list_price") or BY_CODE[c]["list_price"] <= BY_CODE[c]["price"]]
    return codes, problems + more


def flatten(text: str) -> str:
    """LLM이 목록·줄바꿈으로 쓴 답을 한 문단으로. 문장이 끝난 줄은 띄어 잇고, 목록 항목은 쉼표로 잇는다."""
    lines = [re.sub(r"^(?:[-•*]|\d+[.)])\s*", "", l.strip()) for l in text.splitlines() if l.strip()]
    out = ""
    for line in lines:
        out += ("" if not out else " " if out[-1] in ".!?:요다" else ", ") + line
    return out.strip()


def answer_check_node(state: dict) -> dict:
    """④-d 검수 에이전트: 답의 금액·기간·상품·스터드를 표와 맞춰 본다. 어긋나면 내보내지 않고 사장님께 넘긴다."""
    def say(agent, text, visibility="public"):
        return {"turn": state.get("turn", 0), "agent": agent, "text": text, "visibility": visibility}

    question = state["user_text"]
    surface = (state.get("profile") or {}).get("surface") or keyword_extract(question).surface
    msgs = state.get("answer_msgs") or []
    last = msgs[-1] if msgs else None
    used = state.get("answer_used") or []
    by_llm = isinstance(last, AIMessage) and not state.get("answer_error") and not getattr(last, "tool_calls", None)
    draft = (last.content if by_llm and isinstance(last.content, str) else "") or state.get("answer_draft") or ""
    draft = flatten(draft)
    if not by_llm and not draft:   # LLM이 답을 내지 못했다(오류, 상한까지 도구만 불렀다): 표에서 바로 나오는 답이 있으면 쓴다
        draft = faq_answer(question) or ""
    codes, problems = validate(draft, question, surface)
    if by_llm and "확인이 필요" in draft and len(draft) < 60:   # LLM이 "모르겠다"고 한 것: 답한 게 아니라 사장님께 넘길 일이다
        problems.append("표에 없는 내용")
    disc = []
    if by_llm:
        disc.append(say("상담 에이전트", f"상품표·정책표를 {len(used)}번 조회해서 답을 썼어요." if used else "조회 없이 답을 썼어요."))
    if problems and by_llm:   # LLM 답이 표와 어긋났다: 표에서 바로 나오는 답이 있으면 그것으로 바꾼다
        disc.append(say("검수 에이전트", "답변이 표와 맞지 않는 부분이 있어 내보내지 않았어요."))
        disc.append(say("검수 에이전트", "걸린 이유: " + ", ".join(problems[:3]) + "(내부).", "internal"))
        draft, by_llm = faq_answer(question) or "", False
        codes, problems = validate(draft, question, surface)
    if problems:
        disc.append(say("상담 에이전트", "표로 답할 수 없는 질문이라 사장님께 전달할게요."))
        return {"route": "answer", "reason": "unknown", "reply": FALLBACK, "candidates": [], "discussion": disc}
    disc.append(say("검수 에이전트", "답변의 금액·기간·상품·스터드가 표와 맞는지 확인했어요." if by_llm else "정책표·규칙표에 있는 내용으로 답했어요."))
    return {"route": "answer", "reason": "llm" if by_llm else "faq", "reply": draft.strip(), "candidates": codes, "discussion": disc}
