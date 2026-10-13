"""테스트는 항상 키워드 규칙 모드로 돈다 (API 키·네트워크 없이 같은 결과가 나오게)."""
import pytest

import pitchroom.extract as ex
import pitchroom.tools as tl


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    monkeypatch.setattr(ex, "EXTRACTOR", None)
    monkeypatch.setattr(tl, "USE_TAVILY", False)
