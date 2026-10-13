"""질문 답변 루프가 지켜야 하는 약속: 반드시 끝난다, 표와 다른 답은 나가지 않는다, 추천·교환 판단을 건드리지 않는다."""
import time

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import pitchroom.answer as an
import pitchroom.api as api_mod
import pitchroom.extract as ex
from pitchroom.api import create_app
from pitchroom.config import Settings
from pitchroom.extract import Extracted

ADMIN = {"user_id": "admin", "password": "test-admin-pw"}


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "t.db"), Settings(admin_password=ADMIN["password"]))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def say(c, text):
    r = c.post("/api/chat", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()["view"]


def board(app):
    with TestClient(app) as owner:
        owner.post("/api/login", json=ADMIN)
        return owner.get("/api/admin/board").json()


def call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}-{time.monotonic_ns()}"}])


class Scripted:
    """정해 둔 답을 차례로 내놓는 가짜 모델. 다 쓰면 마지막 것을 되풀이한다."""
    def __init__(self, *replies, delay=0.0):
        self.replies, self.calls, self.delay = list(replies), 0, delay

    def invoke(self, messages):
        self.calls += 1
        time.sleep(self.delay)
        r = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        if isinstance(r, Exception):
            raise r
        return r


def use(monkeypatch, agent, writer=None):
    monkeypatch.setattr(an, "AGENT", agent)
    monkeypatch.setattr(an, "WRITER", writer or agent)
    return agent


# ---------- 키 없이: 표에서 바로 나오는 답 ----------
@pytest.mark.parametrize("q, expect", [
    ("Phantom이랑 Tiempo 차이가 뭐예요?", "Phantom 라인은"),
    ("교환 며칠까지 돼요?", "7일 안에"),
    ("반품 배송비 얼마예요?", "6,000원"),
    ("인조잔디에 FG 신어도 돼요?", "FG(천연잔디용 긴 스터드)는 인조잔디에 권하지 않아요. 인조잔디에는 AG·TF·MG가 맞아요."),
    ("풋살장에서 TF 써도 되나요?", "네, TF(인조·풋살용 고무 돌기)는 풋살장에 맞는 스터드예요."),
    ("AG가 뭐예요?", "AG는 인조잔디용 짧고 많은 스터드예요."),
    ("몇 시까지 주문하면 당일 출고돼요?", "평일 14시"),
])
def test_table_answers_without_a_key(client, q, expect):
    view = say(client, q)
    assert (view["route"], view["reason"]) == ("answer", "faq")
    assert expect in view["headline"] and not view["collect"]


def test_cheapest_question_shows_that_shoe(client):
    view = say(client, "제일 싼 실내용이 뭐예요?")
    assert view["headline"] == "실내에 맞는 것 중 가장 저렴한 건 Mercurial Vapor 17 Club IC, 89,000원이에요."
    assert [c["code"] for c in view["shelf"]["cards"]] == ["S-10"] and view["shelf"]["cards"][0]["buyable"]


def test_unanswerable_question_goes_to_the_owner_as_demand(app, client):
    view = say(client, "이 신발 방수돼요?")
    assert (view["route"], view["reason"], view["headline"]) == ("answer", "unknown", an.FALLBACK)
    say(client, "이 신발 방수돼요?")   # 같은 대화에서 다시 물어도 한 번만 센다
    q = next(d for d in board(app)["demand"] if d["kind"] == "question")
    assert q["total"] == 1 and q["items"][0]["key"] == "이 신발 방수돼요?"


@pytest.mark.parametrize("text, route", [("인조잔디용 추천해 주세요", "ask"), ("인조잔디에서 뛰고 발볼 넓어요", "ask"), ("교환하고 싶어요", "ask"), ("배송 언제 와요?", "cs")])
def test_requests_are_not_mistaken_for_questions(client, text, route):
    assert say(client, text)["route"] == route


def test_question_in_the_middle_of_an_exchange_does_not_drop_the_exchange(client):
    client.post("/api/login", json={"user_id": "jiwoo"})
    assert say(client, "사이즈가 작아요")["reason"] == "cs-info"
    assert say(client, "교환 며칠까지 돼요?")["reason"] == "faq"
    done = say(client, "실내에서만 신어봤어요")
    assert done["news"]["verdict"] == "자동 접수"


def test_question_keeps_the_conditions_already_given(client):
    say(client, "인조잔디에서 뛰어요")
    view = say(client, "Mercurial이랑 Phantom 차이가 뭐예요?")
    assert view["route"] == "answer" and next(s for s in view["slots"] if s["key"] == "surface")["text"] == "인조잔디"
    assert say(client, "발볼 넓어요")["reason"] == "budget"   # 하던 상담이 그대로 이어진다


# ---------- LLM이 도구로 조회해서 답한다 ----------
def test_llm_looks_up_the_table_then_answers(monkeypatch, client):
    llm = use(monkeypatch, Scripted(call("find_products", surface="실내"), AIMessage(content="실내용으로는 Mercurial Vapor 17 Club IC가 89,000원으로 가장 부담이 적어요.")))
    view = say(client, "실내에서 신을 만한 것 중에 뭐가 달라요?")
    assert (view["route"], view["reason"]) == ("answer", "llm") and llm.calls == 2
    assert view["headline"].startswith("실내용으로는") and [c["code"] for c in view["shelf"]["cards"]] == ["S-10"]
    assert "1번 조회" in view["discussion"][-2]["text"]


def test_tools_only_return_what_is_safe_for_the_surface():
    from pitchroom.data import SURFACE_TO_STUD
    for surface, ok in SURFACE_TO_STUD.items():
        found = an.find_products.invoke({"surface": surface})
        assert found and all(p["stud"] in ok for p in found)
    assert an.find_products.invoke({"surface": "달"})[0]["price"] == 63000        # 모르는 구장은 조건 없이 (싼 순)
    assert an.product_detail.invoke({"name_or_code": "s-10"})[0]["name"] == "Mercurial Vapor 17 Club"
    assert an.store_policy.invoke({})["단순 변심 반품 왕복 배송비(원)"] == 6000


# ---------- 무한 루프 방지 ----------
def test_model_that_only_ever_calls_tools_stops_at_the_cap(monkeypatch, app, client):
    llm = use(monkeypatch, Scripted(call("store_policy")))        # 끝없이 도구만 부른다
    started = time.time()
    view = say(client, "이 신발 방수돼요?")
    assert llm.calls == an.MAX_STEPS == 3                          # 정확히 상한만큼만 불렸다
    assert (view["route"], view["reason"], view["headline"]) == ("answer", "unknown", an.FALLBACK)
    assert time.time() - started < 5
    assert next(d for d in board(app)["demand"] if d["kind"] == "question")["total"] == 1


def test_last_round_uses_the_model_that_has_no_tools(monkeypatch, client):
    agent = Scripted(call("store_policy"))
    writer = Scripted(AIMessage(content="교환·반품은 받으신 날부터 7일 안에 신청할 수 있어요."))
    use(monkeypatch, agent, writer)
    view = say(client, "이 신발 방수돼요?")
    assert (agent.calls, writer.calls) == (2, 1)                  # 두 바퀴 조회, 세 번째는 답만
    assert view["reason"] == "llm" and "7일" in view["headline"]


def test_a_tool_storm_in_one_message_is_capped(monkeypatch, client):
    many = AIMessage(content="", tool_calls=[{"name": "store_policy", "args": {}, "id": f"c{i}"} for i in range(30)])
    use(monkeypatch, Scripted(many, AIMessage(content="교환은 7일 안에 가능해요.")))
    view = say(client, "이 신발 방수돼요?")
    assert "4번 조회" in view["discussion"][-2]["text"]            # 한 번에 30개를 불러도 4개만 실행한다


def test_time_budget_ends_the_loop(monkeypatch, client):
    monkeypatch.setattr(an, "MAX_SECONDS", -1)                    # 시간이 이미 다 됐다
    agent, writer = Scripted(call("store_policy")), Scripted(AIMessage(content="교환은 7일 안에 가능해요."))
    use(monkeypatch, agent, writer)
    say(client, "이 신발 방수돼요?")
    assert (agent.calls, writer.calls) == (0, 1)                  # 조회 없이 바로 마무리


def test_graph_step_limit_returns_a_fallback_and_leaves_the_conversation_intact(monkeypatch, app, client):
    say(client, "인조잔디에서 뛰어요")
    monkeypatch.setattr(api_mod, "RECURSION_LIMIT", 8)            # 상담(6단계)은 지나가고 질문 루프(10단계)는 못 지나가는 값
    use(monkeypatch, Scripted(call("store_policy")))
    r = client.post("/api/chat", json={"text": "이 신발 방수돼요?"})
    assert r.status_code == 200                                    # 500이 아니다
    view = r.json()["view"]
    assert view["headline"] == an.FALLBACK and view["echo"] == "이 신발 방수돼요?"
    restored = client.get("/api/session").json()["view"]
    assert restored["echo"] == "인조잔디에서 뛰어요" and next(s for s in restored["slots"] if s["key"] == "surface")["text"] == "인조잔디"
    assert say(client, "발볼 넓어요")["reason"] == "budget"        # 다음 턴은 멀쩡하다
    assert board(app)["llm"]["fallbacks"] >= 1


def test_step_limit_on_the_very_first_turn(monkeypatch, client):
    monkeypatch.setattr(api_mod, "RECURSION_LIMIT", 8)
    use(monkeypatch, Scripted(call("store_policy")))
    r = client.post("/api/chat", json={"text": "이 신발 방수돼요?"})
    assert r.status_code == 200 and r.json()["view"]["headline"] == an.FALLBACK
    assert client.get("/api/session").json()["view"]["screen"] == "shop"
    assert say(client, "인조잔디")["reason"] == "width"


def test_unknown_tool_and_bad_arguments_do_not_crash(monkeypatch, client):
    use(monkeypatch, Scripted(call("drop_tables"), call("find_products", max_price="비싸게"), AIMessage(content="교환은 7일 안에 가능해요.")))
    assert say(client, "이 신발 방수돼요?")["reason"] == "llm"


# ---------- 검수: 표와 다른 답은 나가지 않는다 ----------
@pytest.mark.parametrize("draft, why", [
    ("Phantom 6 Low Club MG는 12,345원이에요.", "지어낸 가격"),
    ("교환은 받으신 날부터 30일 안에 가능해요.", "지어낸 기간"),
    ("S-99가 가장 잘 맞아요.", "없는 상품 코드"),
    ("Tiempo Maestro Academy FG가 좋아요.", "없는 상품(이름+스터드)"),
    ("매입 원가는 말씀드릴 수 없지만 싸요.", "내부 정보 단어"),
    ("발목이 아프시면 이 신발이 좋아요.", "건강 조언"),
    ("가" * 401, "너무 긴 답"),
    ("", "빈 답"),
])
def test_answers_that_disagree_with_the_tables_are_not_sent(monkeypatch, app, client, draft, why):
    use(monkeypatch, Scripted(AIMessage(content=draft)))
    view = say(client, "이 신발 방수돼요?")
    assert (view["reason"], view["headline"]) == ("unknown", an.FALLBACK), why


def test_unsafe_stud_for_the_customers_surface_is_rejected(monkeypatch, client):
    say(client, "인조잔디에서 뛰어요")
    use(monkeypatch, Scripted(AIMessage(content="Mercurial Vapor 17 Elite FG가 가볍고 좋아요.")))
    view = say(client, "가벼운 건 어떤 차이가 있어요?")
    assert view["headline"] != "Mercurial Vapor 17 Elite FG가 가볍고 좋아요."
    assert all(c["stud"] in ("AG", "TF", "MG") for c in view["shelf"]["cards"])


def test_why_an_answer_was_rejected_stays_internal(monkeypatch, client):
    use(monkeypatch, Scripted(AIMessage(content="Vapor는 12,345원부터 시작해요.")))
    view = say(client, "이 신발 방수돼요?")
    assert view["headline"] == an.FALLBACK
    assert any("내보내지 않았어요" in d["text"] for d in view["discussion"])
    assert all("12,345" not in d["text"] and "내부" not in d["text"] for d in view["discussion"]) and view["hidden"] == 1   # 걸린 이유는 내부 논의로만


def test_llm_error_falls_back(monkeypatch, app, client):
    use(monkeypatch, Scripted(TimeoutError("slow")))
    assert say(client, "이 신발 방수돼요?")["headline"] == an.FALLBACK
    assert say(client, "Superfly는 소재가 뭐예요?")["headline"] == an.FALLBACK
    assert say(client, "Phantom이랑 Tiempo 차이가 뭐예요?")["reason"] == "faq"   # 표로 답하는 질문은 LLM이 죽어도 그대로 답한다
    stats = board(app)["llm"]
    assert stats["calls"] == 2 and stats["fallbacks"] == 2


def test_stud_and_surface_questions_never_go_to_the_llm(monkeypatch, client):
    llm = use(monkeypatch, Scripted(AIMessage(content="FG도 괜찮아요.")))
    view = say(client, "인조잔디에 FG 신어도 돼요?")
    assert llm.calls == 0 and "권하지 않아요" in view["headline"]


def test_amounts_the_customer_said_and_real_prices_pass(monkeypatch, client):
    use(monkeypatch, Scripted(AIMessage(content="10만원 이하로는 Phantom 6 Low Club MG가 63,000원이에요. 정가는 98,000원이에요.")))
    view = say(client, "10만원 이하로는 소재가 어떤 게 있어요?")
    assert view["reason"] == "llm" and [c["code"] for c in view["shelf"]["cards"]][0] == "S-19"


# ---------- 수요 기록 ----------
def test_unmet_conditions_and_brands_are_really_recorded(app, client):
    say(client, "천연잔디, 발볼 넓고 5만원 이하")          # 맞는 상품 없음 → 대안
    say(client, "아디다스로 보여주세요")
    with TestClient(app) as other:
        say(other, "천연잔디, 발볼 넓고 5만원 이하")
        say(other, "실내에서 신을 건데 칼발이고 5만원 이하로요")   # 안전한 대안도 없음 → 사장님
    demand = {d["kind"]: d for d in board(app)["demand"]}
    assert demand["no_match"]["items"][0] == {"key": "구장 천연잔디 · 발볼 넓음 · 예산 5만원 이하", "count": 2, "last_at": demand["no_match"]["items"][0]["last_at"]}
    assert demand["no_match"]["total"] == 3
    assert [i["key"] for i in demand["brand"]["items"]] == ["아디다스"]


def test_llm_free_text_is_trimmed_before_it_is_shown_or_recorded(monkeypatch, app, client):
    class Chatty:
        def invoke(self, prompt):
            return Extracted(brand="아디다스" + "!" * 300 + "\n<script>", other_requests=["방수" * 100, "골키퍼용", "a", "b", "c"], style_why="이유" * 50)
    monkeypatch.setattr(ex, "EXTRACTOR", Chatty())
    view = say(client, "아디다스로 방수되는 거 있어요?")
    assert len(view["headline"]) < 200 and "\n" not in view["headline"]
    demand = {d["kind"]: d for d in board(app)["demand"]}
    assert len(demand["brand"]["items"][0]["key"]) == 20
    assert len(demand["other"]["items"]) == 3 and all(len(i["key"]) <= 30 for i in demand["other"]["items"])
    assert board(app)["llm"]["calls"] == 1


# ---------- 대화 기록과 상태 크기 ----------
def test_handoff_carries_the_conversation_that_led_to_it(app, client):
    for t in ["인조잔디에서 뛰어요", "발볼 넓어요", "발목 수술한 적 있는데 괜찮을까요"]:
        say(client, t)
    h = board(app)["handoffs"][0]
    texts = [(m["role"], m["text"]) for m in h["detail"]["transcript"]]
    assert texts[0] == ("user", "인조잔디에서 뛰어요") and texts[-2] == ("user", "발목 수술한 적 있는데 괜찮을까요")
    assert texts[1][0] == "assistant" and len(texts) == 6


def test_long_conversations_do_not_grow_the_state_without_bound():
    from pitchroom.graph import graph, new_thread
    cfg = new_thread()
    for i in range(45):
        graph.invoke({"user_text": ["인조잔디", "발볼 넓어요", "20만원", "교환 며칠까지 돼요?"][i % 4]}, cfg)
    s = graph.get_state(cfg).values
    assert s["turn"] == 45 and len(s["history"]) == 40 and len(s["discussion"]) == 60
    assert s["history"][-1]["role"] == "assistant" and s["answer_msgs"] == [] or s["answer_steps"] <= an.MAX_STEPS


def test_graph_has_exactly_one_cycle_and_it_is_the_answer_loop():
    from pitchroom.graph import graph
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("answer_tools", "answer_agent") in edges and ("answer_agent", "answer_tools") in edges
    back = {(a, b) for a, b in edges if (b, a) in edges}
    assert back == {("answer_tools", "answer_agent"), ("answer_agent", "answer_tools")}
    assert ("answer_check", "respond") in edges and not any(a == "respond" and b != "__end__" for a, b in edges)


# ---------- LLM이 질문을 다른 의도로 읽어도, 정책·안전 질문은 표로 답한다 ----------
@pytest.mark.parametrize("q, llm_intent, expect", [
    ("교환 며칠까지 돼요?", "교환", "7일 안에"),
    ("반품하면 배송비는 누가 내요?", "반품", "6,000원"),
    ("이 신발 방수돼요?", "상담", an.FALLBACK),
])
def test_keyword_rule_catches_questions_the_llm_read_as_requests(monkeypatch, client, q, llm_intent, expect):
    class Misreads:
        def invoke(self, prompt):
            return Extracted(intent=llm_intent)
    monkeypatch.setattr(ex, "EXTRACTOR", Misreads())
    view = say(client, q)
    assert view["route"] == "answer" and expect in view["headline"]


def test_policy_questions_use_the_table_even_when_the_llm_is_available(monkeypatch, client):
    llm = use(monkeypatch, Scripted(AIMessage(content="교환은 언제든 가능해요.")))
    view = say(client, "교환 며칠까지 돼요?")
    assert llm.calls == 0 and view["reason"] == "faq" and "7일 안에" in view["headline"]


def test_claiming_a_sale_on_a_full_price_shoe_is_rejected(monkeypatch, client):
    use(monkeypatch, Scripted(AIMessage(content="할인 중인 터프화로는 Tiempo Maestro Club TF가 91,000원이에요.")))
    assert say(client, "할인하는 터프화는 소재가 뭐예요?")["headline"] == an.FALLBACK
    use(monkeypatch, Scripted(AIMessage(content="할인 중인 터프화로는 Phantom 6 Low Pro TF가 146,000원이에요.")))
    view = say(client, "할인하는 터프화는 소재가 뭐예요?")
    assert view["reason"] == "llm" and view["shelf"]["cards"][0]["code"] == "S-14"


def test_list_formatting_from_the_llm_is_flattened(monkeypatch, client):
    use(monkeypatch, Scripted(AIMessage(content="차이는 이래요.\n\n1. Phantom 6 Low Pro TF - 146,000원\n- Phantom 6 Low Club MG - 63,000원")))
    view = say(client, "둘이 뭐가 달라요?")
    assert view["headline"] == "차이는 이래요. Phantom 6 Low Pro TF - 146,000원, Phantom 6 Low Club MG - 63,000원" and view["reason"] == "llm"
    assert [c["code"] for c in view["shelf"]["cards"]] == ["S-14", "S-19"]   # 답에 나온 순서대로
    assert on_sale_only() == ["S-19", "S-27", "S-24", "S-17", "S-22", "S-28", "S-18", "S-29"]


def on_sale_only():
    return [p["code"] for p in an.find_products.invoke({"on_sale": True})]


def test_tool_ignores_nonsense_filters_instead_of_finding_nothing():
    sale_tf = [p["code"] for p in an.find_products.invoke({"line": "Mercurial|Phantom|Tiempo", "stud": "tf", "on_sale": True})]
    assert sale_tf == ["S-17", "S-18", "S-14"]                       # 실제로 모델이 이렇게 불러 "할인 터프화 없음"이라고 답한 적이 있다
    assert len(an.find_products.invoke({"stud": "터프", "max_price": -5, "width": "wide"})) == 8
    assert [p["line"] for p in an.find_products.invoke({"line": "tiempo", "surface": "실내"})] == ["Tiempo"]


def test_llm_saying_it_does_not_know_becomes_a_handoff_to_the_owner(monkeypatch, app, client):
    use(monkeypatch, Scripted(AIMessage(content="확인이 필요해요.")))
    view = say(client, "이 신발 방수돼요?")
    assert (view["reason"], view["headline"]) == ("unknown", an.FALLBACK)
    assert next(d for d in board(app)["demand"] if d["kind"] == "question")["total"] == 1


def test_line_comparison_uses_the_table_but_model_comparison_goes_to_the_llm(monkeypatch, client):
    llm = use(monkeypatch, Scripted(call("product_detail", name_or_code="Superfly"), AIMessage(content="Mercurial Superfly 11 Academy는 발목을 감싸는 하이탑이에요.")))
    assert say(client, "Phantom이랑 Tiempo 차이가 뭐예요?")["reason"] == "faq" and llm.calls == 0
    view = say(client, "Superfly랑 Vapor는 뭐가 달라요?")
    assert view["reason"] == "llm" and llm.calls == 2 and view["shelf"]["cards"][0]["name"] == "Mercurial Superfly 11 Academy"


def test_a_name_without_a_stud_is_matched_by_the_colour_or_price_next_to_it():
    text = "할인 중인 터프화는 Phantom 6 Low Pro (블루/핑크) 146,000원, Mercurial Vapor 17 Academy 레드 94,000원, Mercurial Superfly 11 Academy는 99,000원이에요."
    codes, problems = an.validate(text, "할인하는 터프화 있어요?", None)
    assert (codes, problems) == (["S-14", "S-17", "S-18"], [])
    codes, problems = an.validate("할인 중인 Mercurial Vapor 17 Academy는 133,000원이에요.", "얼마예요?", None)
    assert problems and "할인 중이 아님" in problems[0]            # 133,000원짜리는 정가 상품이다
