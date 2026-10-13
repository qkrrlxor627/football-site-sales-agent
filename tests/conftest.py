"""테스트는 항상 키워드 규칙 모드로 돈다 (API 키·네트워크 없이 같은 결과가 나오게)."""
import pytest

import pitchroom.extract as ex
import pitchroom.tools as tl


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    monkeypatch.setattr(ex, "EXTRACTOR", None)
    monkeypatch.setattr(tl, "USE_TAVILY", False)


@pytest.fixture(autouse=True)
def base_catalog():
    """가격·판매 여부는 프로세스 전체가 같이 보는 목록이라, 한 테스트가 바꾼 값이 다음 테스트로 넘어가지 않게 되돌린다."""
    from pitchroom.data import reset_catalog
    reset_catalog()
    yield
    reset_catalog()
