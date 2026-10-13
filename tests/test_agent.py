"""규칙이 지켜야 하는 약속을 테스트로 고정한다."""
import pytest

from pitchroom.evaluation import SCENARIOS, run_graph, unsafe
from pitchroom.extract import CsInfo, Extracted, ground_check
from pitchroom.graph import chat, graph, new_thread
import pitchroom.extract as ex


@pytest.mark.parametrize("sc", SCENARIOS, ids=[sc[0] for sc in SCENARIOS])
def test_scenario_route(sc):
    r = run_graph(sc)
    assert r["route"] == sc[3]
    assert not unsafe(r["codes"], sc[5]), "구장에 위험한 스터드를 추천하면 안 된다"
    assert not r["leak"], "내부 정보가 고객 답변에 나오면 안 된다"


def test_ground_check_drops_values_customer_did_not_say():
    e = Extracted(intent="교환", size=270, cs=CsInfo(worn=False))
    _, dropped = ground_check(e, "사이즈가 좀 작아요")
    assert set(dropped) == {"사이즈", "착용 여부"}


def test_lying_llm_cannot_auto_approve_exchange(monkeypatch):
    """실제 실행에서 났던 버그: LLM이 worn=False를 지어내 교환이 바로 승인됐다."""
    class LyingLLM:
        def invoke(self, prompt):
            return Extracted(intent="교환", size=270, cs=CsInfo(worn=False))

    monkeypatch.setattr(ex, "EXTRACTOR", LyingLLM())
    cfg = new_thread("jiwoo")
    c = chat("사이즈가 좀 작아요", cfg, quiet=True)
    assert c["route"] == "ask"  # 착용 여부를 다시 물어야 한다
    assert graph.get_state(cfg).values["account"]["orders"][0]["status"] == "배송완료"


def test_internal_discussion_never_reaches_client():
    cfg = new_thread()
    c = chat("천연잔디, 발볼 넓고 5만원 이하", cfg, quiet=True)
    assert c["hidden"] >= 1
    assert all("내부" not in m["text"] for m in c["discussion"])


def test_known_player_uses_fixed_table_even_when_search_is_on(monkeypatch):
    """검색이 켜져 있어도 고정표에 있는 선수는 검색하지 않는다 (검색이 음바페를 Phantom으로 답한 적이 있다)."""
    import pitchroom.tools as tl
    monkeypatch.setattr(tl, "USE_TAVILY", True)
    monkeypatch.setitem(__import__("sys").modules, "tavily", None)   # 검색을 부르면 ImportError로 바로 드러난다
    assert tl.player_line("음바페", "Phantom") == ("Mercurial", "고정표")
    assert tl.player_line("킬리안 음바페", None) == ("Mercurial", "고정표")
    assert tl.player_line("모르는선수", "Tiempo") == ("Tiempo", "LLM 추정")
