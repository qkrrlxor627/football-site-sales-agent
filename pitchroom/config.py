"""환경 설정. 키는 프로젝트 루트의 .env에서 읽는다 (.env.example 참고)."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

MODEL = os.getenv("PITCHROOM_MODEL", "gpt-4o-mini")
USE_LLM = bool(os.getenv("OPENAI_API_KEY"))
USE_TAVILY = bool(os.getenv("TAVILY_API_KEY"))

# 웹 서버 (FastAPI)
HOST = os.getenv("PITCHROOM_HOST", "127.0.0.1")
PORT = int(os.getenv("PITCHROOM_PORT", "8000"))
DB_PATH = os.getenv("PITCHROOM_DB", str(ROOT / "pitchroom.db"))   # 대화 체크포인트 + 계정·주문
SECRET = os.getenv("PITCHROOM_SECRET")                            # 세션 쿠키 서명 키. 없으면 DB에 하나 만들어 둔다
LOG_LEVEL = os.getenv("PITCHROOM_LOG_LEVEL", "INFO")


# 운영 설정. PITCHROOM_ENV=production이면 데모 계정·API 문서를 끄고 쿠키를 HTTPS 전용으로 바꾼다 (각각 따로 덮어쓸 수 있다).
ENV = os.getenv("PITCHROOM_ENV", "development")
PRODUCTION = ENV == "production"


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return default if raw == "" else raw in ("1", "true", "yes", "on")


@dataclass
class Settings:
    demo: bool = field(default_factory=lambda: _flag("PITCHROOM_DEMO", not PRODUCTION))            # 비밀번호 없는 데모 계정 4개
    docs: bool = field(default_factory=lambda: _flag("PITCHROOM_DOCS", not PRODUCTION))            # /api/docs
    cookie_secure: bool = field(default_factory=lambda: _flag("PITCHROOM_COOKIE_SECURE", PRODUCTION))
    admin_id: str = field(default_factory=lambda: os.getenv("PITCHROOM_ADMIN_ID", "admin"))
    admin_password: Optional[str] = field(default_factory=lambda: os.getenv("PITCHROOM_ADMIN_PASSWORD") or None)
    chat_per_minute: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_CHAT_PER_MINUTE", "20")))   # 대화 하나당
    ip_per_minute: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_IP_PER_MINUTE", "120")))      # 주소 하나당 (대화·주문)
    auth_per_minute: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_AUTH_PER_MINUTE", "10")))   # 주소 하나당 로그인·가입 시도
    thread_days: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_THREAD_DAYS", "30")))           # 이만큼 쉬는 대화는 지운다
    session_days: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_SESSION_DAYS", "30")))        # 로그인 유지 최대 기간
    session_idle_days: int = field(default_factory=lambda: int(os.getenv("PITCHROOM_SESSION_IDLE_DAYS", "14")))  # 이만큼 안 쓰면 다시 로그인
    notify_webhook: Optional[str] = field(default_factory=lambda: os.getenv("PITCHROOM_NOTIFY_WEBHOOK") or None)  # 넘어온 건·새 주문 알림 (Slack·Discord 웹훅)
