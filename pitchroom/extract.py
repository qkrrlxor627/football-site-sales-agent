"""정보 추출: 자연어 이해는 LLM, 실패하면 키워드 규칙. LLM이 지어낸 값은 ground_check가 버린다."""
# LLM 출력은 Pydantic 스키마로 받는다. 선택지는 Literal로 묶어서 '없는 구장' 같은 값이 들어오지 못하게 한다.
import re
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import telemetry
from .config import MODEL, USE_LLM
from .data import PLAYER_TABLE, RED_FLAGS, order_label


class CsInfo(BaseModel):
    days: Optional[int] = Field(None, description="고객이 이번 메시지에서 직접 말한 수령 후 일수. 말하지 않았으면 null")
    worn: Optional[bool] = Field(None, description="고객이 직접 말했을 때만: 실외에서 신었으면 true, 실내 시착만이면 false. 말하지 않았으면 null")
    repeat: bool = Field(False, description="이미 교환한 적이 있으면 true")


class Extracted(BaseModel):
    intent: Literal["상담", "배송", "교환", "반품", "질문"] = Field("상담", description=(
        "신발이 작다·크다·불편하다는 교환, 내 주문이 어디쯤이냐는 배송. "
        "질문: 상품·스터드·라인의 차이나 특징, 매장 정책(교환 기한, 배송비 등)을 '설명해 달라'는 물음. "
        "조건을 말하거나 추천·구매를 원하면 질문이 아니라 상담"))
    surface: Optional[Literal["천연잔디", "인조잔디", "흙운동장", "풋살장", "실내"]] = Field(None, description="맨땅·학교 흙바닥은 흙운동장")
    width: Optional[Literal["좁음", "보통", "넓음"]] = Field(None, description="칼발은 좁음")
    budget: Optional[int] = Field(None, description="원 단위 예산. 상관없다고 하면 -1")
    size: Optional[int] = Field(None, description="고객이 이번 메시지에서 직접 말한 mm 사이즈. 주문 기록의 사이즈를 옮겨 적지 말 것")
    brand: Optional[str] = Field(None, description="고객이 원하는 브랜드의 한국어 이름 (예: 아디다스)")
    player: Optional[str] = Field(None, description="언급한 선수 이름")
    player_boot: Optional[str] = Field(None, description="그 선수가 주로 신는 축구화 (아는 범위)")
    style_line: Optional[Literal["Mercurial", "Phantom", "Tiempo"]] = Field(None, description="취향·선수 스타일에 가장 가까운 나이키 라인")
    style_why: Optional[str] = Field(None, description="15자 이내 이유")
    health_flag: bool = Field(False, description="발·발목 통증, 부상, 수술, 질환 언급이면 true")
    wants_new_order: bool = Field(False, description="새로 사거나 추가로 주문·재구매하고 싶다고 하면 true (교환·반품·배송 문의는 false)")
    cs: CsInfo = Field(default_factory=CsInfo)
    other_requests: list[str] = Field(default_factory=list, description="매장 규칙으로 다루지 않는 요청 (예: 골키퍼용, 방수)")


EXTRACT_PROMPT = """너는 축구화 매장 상담 시스템의 정보 추출기다. 추천이나 판단은 하지 말고 고객 메시지에서 정보만 뽑아라.
매장: PITCHROOM. 나이키 축구화만 판매. 라인: Mercurial(가볍고 빠른 스피드형), Phantom(볼 터치·컨트롤형), Tiempo(가죽, 편안함, 넓은 발볼).
최근 대화: {history}
직전에 매장이 한 말: {last_reply}
지금까지 파악한 조건: {profile}
고객 상태: {account}
고객 메시지: {text}"""

EXTRACTOR = None
if USE_LLM:
    from langchain_openai import ChatOpenAI
    # function_calling 방식: Optional·기본값이 많은 스키마에서 strict json_schema보다 덜 까다롭다.
    # timeout: 응답이 늦으면 기다리지 않고 키워드 규칙으로 넘어간다 (웹 요청이 멈춰 있지 않게).
    EXTRACTOR = ChatOpenAI(model=MODEL, temperature=0, timeout=20, max_retries=1).with_structured_output(Extracted, method="function_calling")


QUESTION = re.compile(
    r"차이|다른\s*점|뭐가\s*달라|어떻게\s*달라|비교해|방수|무게|소재|재질|제일\s*(싼|비싼|저렴)|가장\s*(싼|비싼|저렴)"
    r"|(FG|SG|AG|MG|TF|HG|IC)\s*(가|는|이|란|이란|도|를)?\s*(뭐|무엇|무슨|신어도|써도|괜찮|되나|돼|안\s*되)"
    r"|스터드.{0,6}(뭐|무엇|종류|차이)|(교환|반품).{0,10}(며칠|기간|언제까지|몇\s*번|몇\s*회|조건|되나요|가능한가)"
    r"|배송비|몇\s*시까지|당일\s*출고", re.I)


def is_question(text: str) -> bool:
    """설명을 바라는 물음인가. LLM이 교환·상담으로 읽어도 이 규칙에 걸리면 질문으로 본다 ("교환 며칠까지 돼요?"는 교환 접수가 아니다)."""
    return bool(QUESTION.search(text)) and not re.search(r"추천|골라|찾아\s*(줘|주)", text)


def keyword_extract(text: str) -> Extracted:
    """LLM이 없거나 실패했을 때의 대체 경로. 일부러 단순하게 둔다."""
    t = re.sub(r"\s+", " ", text)
    e = Extracted()
    if re.search(r"흙|맨땅|마사토|모래", t) or (re.search(r"운동장", t) and not re.search(r"잔디|인조|천연", t)):
        e.surface = "흙운동장"
    elif "천연" in t:
        e.surface = "천연잔디"
    elif "인조" in t:
        e.surface = "인조잔디"
    elif "풋살" in t:
        e.surface = "풋살장"
    elif re.search(r"실내|체육관|강당", t):
        e.surface = "실내"
    if re.search(r"칼발|좁", t):
        e.width = "좁음"
    elif re.search(r"넓|발볼이 커|볼이 커", t):
        e.width = "넓음"
    elif re.search(r"보통|평범|중간", t) and (re.search(r"발|볼|편", t) or len(t.strip()) <= 6):
        e.width = "보통"  # "보통이요"처럼 짧은 답도 발볼 답으로 본다
    m = re.search(r"(2[2-9]\d)\s*(mm|미리|사이즈|신어|신고|이요|요|$|\s)", t)
    if m:
        e.size = round(int(m.group(1)) / 5) * 5
    m = re.search(r"(\d{1,3})\s*만\s*원?", t)
    won_ = re.search(r"(\d{1,3}(?:,\d{3})+|\d{5,7})\s*원", t)  # "150,000원", "150000원"
    if m:
        e.budget = int(m.group(1)) * 10000
    elif won_:
        e.budget = int(won_.group(1).replace(",", ""))
    elif re.search(r"상관\s*없|무관|제한\s*없", t):
        e.budget = -1
    for name, (boot, line) in PLAYER_TABLE.items():
        if name in t:
            e.player, e.player_boot, e.style_line = name, boot, line
    if not e.style_line:
        if re.search(r"빠른|스피드|가벼운|윙어|공격수", t):
            e.style_line, e.style_why = "Mercurial", "가볍고 빠른 스피드형"
        elif re.search(r"터치|패스|드리블|감아|미드필더", t):
            e.style_line, e.style_why = "Phantom", "볼 터치·컨트롤형"
        elif re.search(r"가죽|편한|편안|수비|센터백", t):
            e.style_line, e.style_why = "Tiempo", "편안한 가죽 터치"
    for pat, brand in [(r"아디다스|adidas", "아디다스"), (r"퓨마|puma", "퓨마"), (r"미즈노|mizuno", "미즈노"), (r"나이키|nike", "나이키")]:
        if re.search(pat, t, re.I):
            e.brand = brand
    e.health_flag = any(w in t for w in RED_FLAGS)
    # "주문 추가로 하고 싶어", "하나 더 살게요", "같은 걸로 또 주문" 같은 말: 배송·교환 문의가 아니라 새 주문이다
    e.wants_new_order = bool(re.search(r"추가.{0,8}(주문|구매|사고|살)|(주문|구매).{0,8}추가|(하나|한\s*켤레|한\s*개|또|더|다시|새로).{0,6}(주문|구매|사고|살게|살래|사려)|재주문|재구매", t))
    if re.search(r"배송|언제\s*와|도착|출고|택배|어디쯤", t):
        e.intent = "배송"
    elif re.search(r"반품|환불", t):
        e.intent = "반품"
    elif re.search(r"교환|바꾸|바꿔|작아|커요|커서|헐렁|꽉 껴|끼어|안 맞", t):
        e.intent = "교환"
    # 설명을 바라는 물음: 차이·특징·정책. 조건을 말했거나("인조잔디용 추천") 내 주문 이야기면 질문이 아니다
    if is_question(t):
        e.intent = "질문"
    m = re.search(r"(\d{1,2})\s*일", t)
    if m:
        e.cs.days = int(m.group(1))
    elif "오늘" in t:
        e.cs.days = 0
    elif "어제" in t:
        e.cs.days = 1
    if re.search(r"안\s*신|미착용|실내에서만|집에서만|신어만|신어보기만", t):
        e.cs.worn = False
    elif re.search(r"신고|신었|착용|경기|뛰었|밖에서|훈련", t):
        e.cs.worn = True
    if re.search(r"두\s*번|2번|또 교환|다시 교환", t):
        e.cs.repeat = True
    return e


def extract(text: str, state: dict) -> tuple[Extracted, str]:
    """LLM 추출 → 실패하면 키워드 규칙. 어느 쪽이 쓰였는지도 함께 돌려준다."""
    if EXTRACTOR is None:
        return keyword_extract(text), "키워드 규칙"
    acc = state.get("account")
    prompt = EXTRACT_PROMPT.format(
        history=" / ".join(f'{"고객" if h["role"] == "user" else "매장"}: {h["text"][:80]}' for h in (state.get("history") or [])[-4:]) or "(없음)",
        last_reply=state.get("reply") or "(없음)",
        profile={k: v for k, v in (state.get("profile") or {}).items() if v is not None},
        account=("로그인, 주문: " + " / ".join(f'{o["id"]} {order_label(o)} {o["status"]}' for o in acc["orders"])) if acc else "로그인 전",
        text=text,
    )
    started = time.perf_counter()
    try:
        out = EXTRACTOR.invoke(prompt)
        telemetry.record("extract", ms=(time.perf_counter() - started) * 1000)
        return out, "LLM"
    except Exception as err:  # 네트워크·스키마 오류 등: 대화를 멈추지 않고 규칙으로 계속
        telemetry.record("extract", fallback=True, ms=(time.perf_counter() - started) * 1000)
        return keyword_extract(text), f"키워드 규칙 (LLM 실패: {type(err).__name__})"


# LLM은 그럴듯한 값을 '채워 넣는' 실수를 한다. 판단에 직접 쓰이는 값은 문장에 근거가 있을 때만 받는다.
# (실제 실행에서 "사이즈가 좀 작아요"에 LLM이 worn=False, size=270을 채워 교환이 바로 승인된 사례가 있었다.)
GROUNDS = {
    "size": r"\d{3}|mm|미리",
    "budget": r"\d|만|상관|무관|얼마든",
    "days": r"\d|오늘|어제|그제|그저께|일주일|주일|한 ?달|며칠",
    "worn": r"신[었어고은]|신어|착용|경기|뛰[었어]|실내|밖|훈련|시착|택",
}


def ground_check(e: Extracted, text: str) -> tuple[Extracted, list[str]]:
    dropped, upd, cs = [], {}, e.cs.model_copy()
    if e.size is not None and not re.search(GROUNDS["size"], text):
        upd["size"] = None; dropped.append("사이즈")
    if e.budget is not None and not re.search(GROUNDS["budget"], text):
        upd["budget"] = None; dropped.append("예산")
    if cs.days is not None and not re.search(GROUNDS["days"], text):
        cs.days = None; dropped.append("수령일")
    if cs.worn is not None and not re.search(GROUNDS["worn"], text):
        cs.worn = None; dropped.append("착용 여부")
    return e.model_copy(update={**upd, "cs": cs}), dropped


