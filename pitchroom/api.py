"""HTTP API (FastAPI): 화면(Vue)이 부르는 유일한 창구. 판단은 graph, 화면 모양은 views가 정한다.

실행: python app.py  (또는 uvicorn pitchroom.api:create_app --factory)
"""
# 브라우저 한 개 = 서명된 세션 쿠키 한 개 = LangGraph thread 한 개.
# 쿠키에는 thread 번호와 로그인 아이디만 들어 있고, 대화·주문은 전부 서버 DB에 있다.
import logging
import re
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config, extract, notify
from . import tools as tools_mod
from .data import BY_CODE, order_label
from .graph import build_graph
from .store import HANDOFF_KIND, Store, StoreError, order_actions, order_title
from .views import IMAGE_DIR, account_view, catalog, service_home, slots, view_for

log = logging.getLogger("pitchroom.api")
DIST_DIR = config.ROOT / "frontend" / "dist"
MAX_TEXT = 500
USER_ID = re.compile(r"^[a-z0-9_]{3,20}$")
PHONE = re.compile(r"^[0-9+\-() ]{9,20}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
FIELD_MESSAGE = {
    "text": f"메시지는 1~{MAX_TEXT}자로 입력해 주세요.",
    "user_id": "아이디는 영문 소문자·숫자·밑줄 3~20자로 입력해 주세요.",
    "name": "이름은 1~20자로 입력해 주세요.",
    "password": "비밀번호는 8~72자로 입력해 주세요.",
    "code": "상품을 다시 골라 주세요.",
    "size": "사이즈를 다시 골라 주세요.",
    "to": "바꿀 상태를 다시 골라 주세요.",
    "note": "메모는 200자 이내로 입력해 주세요.",
    "contact": "전화번호나 이메일을 입력해 주세요. (예: 010-1234-5678)",
    "price": "가격은 1,000원~5,000,000원 사이로 입력해 주세요.",
    "stock": "재고는 0~999 사이 숫자로 입력해 주세요.",
    "new_size": "교환해 보낼 사이즈를 골라 주세요.",
    "current": "지금 비밀번호를 입력해 주세요.",
    "new": "새 비밀번호는 8~72자로 입력해 주세요.",
}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                               "font-src 'self' https://fonts.gstatic.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class RateLimiter:
    """최근 60초 동안의 요청 수를 키별로 센다 (프로세스 메모리. 워커 1개 기준)."""
    def __init__(self, window: float = 60.0):
        self.window, self.hits, self.lock = window, defaultdict(deque), threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        with self.lock:
            if len(self.hits) > 20000:   # 오래된 키 청소
                for k in [k for k, q in self.hits.items() if not q or q[-1] < now - self.window]:
                    del self.hits[k]
            q = self.hits[key]
            while q and q[0] < now - self.window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


class ChatIn(BaseModel):
    text: str = Field(max_length=MAX_TEXT)


class LoginIn(BaseModel):
    user_id: str = Field(max_length=40)
    password: Optional[str] = Field(None, max_length=72)
    keep: bool = False   # True면 지금 대화를 유지한 채 로그인만 붙인다 (추천을 보고 구매하려다 로그인하는 경우)


class SignupIn(BaseModel):
    user_id: str = Field(max_length=40)
    name: str = Field(max_length=40)
    password: str = Field(max_length=200)
    keep: bool = False


class OrderIn(BaseModel):
    code: str = Field(max_length=10)
    size: int


class TransitionIn(BaseModel):
    to: str = Field(max_length=20)
    note: Optional[str] = Field(None, max_length=200)
    new_size: Optional[int] = None   # 교환 완료 처리할 때 보내는 사이즈


class ContactIn(BaseModel):
    contact: str = Field(max_length=60)


class PasswordIn(BaseModel):
    current: str = Field(max_length=72)
    new: str = Field(max_length=200)


class ProductIn(BaseModel):
    price: Optional[int] = Field(None, ge=1000, le=5_000_000)
    active: Optional[bool] = None
    stock: Optional[dict[int, int]] = None


class ResolveIn(BaseModel):
    note: str = Field("", max_length=200)


def create_app(db_path: Optional[str] = None, settings: Optional[config.Settings] = None) -> FastAPI:
    logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = settings or config.Settings()
    db_path = db_path or config.DB_PATH
    store = Store(db_path, demo=settings.demo)
    saver = SqliteSaver(sqlite3.connect(db_path, check_same_thread=False, timeout=10))
    graph = build_graph(saver)
    limiter = RateLimiter()
    locks: dict[str, threading.Lock] = defaultdict(threading.Lock)   # 같은 대화에 요청이 겹치면 순서대로 처리
    locks_guard = threading.Lock()

    generated = store.ensure_admin(settings.admin_id, settings.admin_password)
    if generated:   # 처음 한 번만 나온다. 바꾸려면 PITCHROOM_ADMIN_PASSWORD를 정하고 다시 띄운다
        log.warning("관리자 계정을 만들었어요. 아이디: %s / 임시 비밀번호: %s  (.env의 PITCHROOM_ADMIN_PASSWORD로 바꿀 수 있어요)", settings.admin_id, generated)
    for old in store.stale_threads(settings.thread_days):   # 오래 쉬는 대화 청소 (DB가 끝없이 커지지 않게)
        saver.delete_thread(old)
        store.forget_thread(old)

    app = FastAPI(title="PITCHROOM", docs_url="/api/docs" if settings.docs else None,
                  openapi_url="/api/openapi.json" if settings.docs else None, redoc_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/docs"):   # 문서 화면은 외부 CDN을 쓰므로 개발 중에만, CSP 없이 연다
            for k, v in SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(SessionMiddleware, secret_key=config.SECRET or store.secret(), session_cookie="pitchroom",
                       max_age=60 * 60 * 24 * 30, same_site="lax", https_only=settings.cookie_secure)

    # ---------- 오류: 항상 {error: {code, message}} 한 모양 ----------
    @app.exception_handler(ApiError)
    def _api_error(request: Request, err: ApiError):
        return _error(err.status, err.code, err.message)

    @app.exception_handler(RequestValidationError)
    def _invalid(request: Request, err: RequestValidationError):
        field = next((str(loc) for e in err.errors() for loc in e.get("loc", ()) if str(loc) in FIELD_MESSAGE), None)
        return _error(422, "invalid_input", FIELD_MESSAGE.get(field, "입력 값을 확인해 주세요."))

    @app.exception_handler(StarletteHTTPException)
    def _http(request: Request, err: StarletteHTTPException):
        return _error(err.status_code, "not_found" if err.status_code == 404 else "http_error", "요청한 주소를 찾지 못했어요." if err.status_code == 404 else str(err.detail))

    @app.exception_handler(Exception)
    def _crash(request: Request, err: Exception):
        log.exception("처리하지 못한 오류: %s %s", request.method, request.url.path)
        return _error(500, "server_error", "서버에서 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요.")

    # ---------- 세션 ----------
    def cfg(thread: str) -> dict:
        return {"configurable": {"thread_id": thread}}

    def lock_for(thread: str) -> threading.Lock:
        with locks_guard:
            return locks[thread]

    def new_thread(request: Request) -> str:
        """새 대화로 갈아탄다. 버린 대화의 체크포인트는 지운다."""
        old = request.session.get("thread")
        if old:
            try:
                saver.delete_thread(old)
                store.forget_thread(old)
            except Exception:   # 지우기는 청소일 뿐이라 실패해도 요청은 계속한다
                log.warning("이전 대화 체크포인트를 지우지 못했어요: %s", old[:8])
            with locks_guard:
                locks.pop(old, None)
        request.session["thread"] = str(uuid.uuid4())
        return request.session["thread"]

    def current(request: Request) -> tuple[str, Optional[str]]:
        return request.session.get("thread") or new_thread(request), request.session.get("user")

    def sync_account(request: Request, thread: str, user: Optional[str]) -> dict:
        """DB의 계정·주문(원본)을 이 대화의 State에 맞춰 넣고, 최신 State를 돌려준다."""
        acc = store.get_account(user) if user else None
        if user and not acc:
            request.session.pop("user", None)
        state = graph.get_state(cfg(thread)).values or {}
        if state.get("account") != acc:
            graph.update_state(cfg(thread), {"account": acc}, as_node="respond")
            state = {**state, "account": acc}
        return state

    def in_stock(code: str, stock: dict) -> list[int]:
        return [size for size, qty in sorted(stock.get(code, {}).items()) if qty > 0]

    def envelope(request: Request, state: dict, view: Optional[dict] = None, **extra) -> dict:
        """화면 응답. 그래프가 모르는 것(재고, 남긴 연락처)은 여기서 붙인다."""
        view = view or view_for(state)
        acc = state.get("account")
        if view["shelf"]["kind"] == "products":
            stock, want = store.stock_map(), (state.get("profile") or {}).get("size")
            for card in view["shelf"]["cards"]:
                card["sizes"] = in_stock(card["code"], stock)
                card["size_note"] = (None if card["sizes"] else "전 사이즈 품절") if not want or want in card["sizes"] else f"{want}mm 품절"
        if view["route"] == "escalate":   # 사람이 이어받는 건: 연락받을 곳을 묻는다
            thread = request.session.get("thread")
            view["contact"] = {"saved": (thread and store.thread_contact(thread)) or (acc and store.get_contact(acc["id"])) or None}
        else:
            view["contact"] = None
        return {"account": account_view(acc), "view": view, **extra}

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def throttle(request: Request, bucket: str, limit: int, key: Optional[str] = None):
        if not limiter.allow(f"{bucket}:{key or client_ip(request)}", limit):
            log.warning("요청 제한: %s %s", bucket, key or client_ip(request))
            raise ApiError(429, "rate_limited", "요청이 너무 많아요. 잠시 뒤 다시 시도해 주세요.")

    def sign_in(request: Request, user: str, keep: bool) -> dict:
        thread = current(request)[0] if keep else new_thread(request)
        request.session["user"] = user
        with lock_for(thread):
            return envelope(request, sync_account(request, thread, user))

    def require_admin(request: Request) -> dict:
        user = request.session.get("user")
        acc = store.get_account(user) if user else None
        if not acc:
            raise ApiError(401, "login_required", "로그인해 주세요.")
        if acc["role"] != "admin":
            raise ApiError(403, "forbidden", "관리자만 볼 수 있어요.")
        return acc

    def record_handoff(thread: str, state: dict, before: Optional[dict]):
        """사람에게 넘긴 턴을 사장님이 볼 목록에 남긴다. 내부 논의까지 담는다 (고객 화면에는 가지 않는다)."""
        kind, acc, card = state.get("reason") or "review", state.get("account"), state.get("cs_card") or {}
        old = {o["id"]: o["status"] for o in (before or {}).get("orders", [])}
        order = next((o for o in (acc or {}).get("orders", []) if o["status"] == "사장님 확인 중" and old.get(o["id"]) != o["status"]), None)
        profile = state.get("profile") or {}
        summary = {"health": f'발 건강 언급: “{state["user_text"][:60]}”',
                   "policy": card.get("summary") or "교환·반품 결재 요청",
                   "empty": "조건에 맞는 상품이 없어요"}.get(kind, "추천 검수에서 걸렸어요")
        detail = {
            "text": state["user_text"], "reply": state.get("reply"), "source": state.get("source"),
            "conditions": [f'{s["label"]} {s["text"]}' for s in slots(profile, state.get("skipped")) if s["on"]],
            "rules": card.get("rules") or [], "options": card.get("options") or [],
            "order": order_label(order) if order else None,
            "discussion": [{"agent": m["agent"], "text": m["text"], "internal": m["visibility"] == "internal"}
                           for m in state.get("discussion", []) if m["turn"] == state["turn"]],
        }
        kind = kind if kind in HANDOFF_KIND else "review"
        made = store.add_handoff(kind, summary, detail, thread, account_id=acc["id"] if acc else None, order_id=order["id"] if order else None)
        if made and acc and store.get_contact(acc["id"]):
            store.set_handoff_contact(thread, store.get_contact(acc["id"]))
        if made:
            who = f'{acc["name"]}({acc["id"]})' if acc else "비로그인 고객"
            notify.send(settings.notify_webhook, f'[PITCHROOM] 넘어온 건: {HANDOFF_KIND[kind]} · {who}' + (f' · {order["id"]}' if order else "") + " — 관리 화면에서 확인해 주세요.")
            log.info("handoff id=%s kind=%s user=%s order=%s", made, kind, acc["id"] if acc else "-", order["id"] if order else "-")

    # ---------- 고객 라우트 ----------
    @app.get("/api/health")
    def health():
        return {"ok": True, "llm": extract.EXTRACTOR is not None, "model": config.MODEL if extract.EXTRACTOR is not None else None,
                "search": tools_mod.USE_TAVILY}

    @app.get("/api/catalog")
    def get_catalog():
        return catalog(settings.demo, store.stock_map())

    @app.get("/api/session")
    def get_session(request: Request):
        thread, user = current(request)
        with lock_for(thread):
            return envelope(request, sync_account(request, thread, user))

    @app.post("/api/chat")
    def chat(body: ChatIn, request: Request):
        text = body.text.strip()
        if not text:
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["text"])
        thread, user = current(request)
        throttle(request, "chat-ip", settings.ip_per_minute)
        throttle(request, "chat", settings.chat_per_minute, key=thread)
        started = time.perf_counter()
        with lock_for(thread):
            before = sync_account(request, thread, user).get("account")
            state = graph.invoke({"user_text": text}, cfg(thread))
            if state.get("account"):
                store.save_orders(state["account"], before)   # 정책 에이전트가 바꾼 주문 상태를 원본에 반영
            if state.get("route") == "escalate":
                record_handoff(thread, state, before)
            store.touch_thread(thread)
        log.info("chat thread=%s user=%s route=%s/%s source=%s chars=%d %.0fms", thread[:8], user or "-", state.get("route"),
                 state.get("reason"), state.get("source"), len(text), (time.perf_counter() - started) * 1000)
        return envelope(request, state)

    @app.post("/api/login")
    def login(body: LoginIn, request: Request):
        user = body.user_id.strip().lower()
        if not user:
            raise ApiError(422, "invalid_input", "아이디를 입력해 주세요.")
        throttle(request, "auth", settings.auth_per_minute)
        if not store.authenticate(user, body.password, allow_passwordless=settings.demo):
            # 아이디가 없는지 비밀번호가 틀렸는지는 구분해 알려주지 않는다
            raise ApiError(401, "bad_credentials", "아이디 또는 비밀번호가 맞지 않아요.")
        log.info("login user=%s", user)
        return sign_in(request, user, body.keep)

    @app.post("/api/signup")
    def signup(body: SignupIn, request: Request):
        user, name = body.user_id.strip().lower(), body.name.strip()
        if not USER_ID.match(user):
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["user_id"])
        if not 1 <= len(name) <= 20:
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["name"])
        if not 8 <= len(body.password) <= 72:
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["password"])
        throttle(request, "auth", settings.auth_per_minute)
        try:
            store.create_account(user, name, body.password)
        except StoreError as err:
            raise ApiError(409, err.code, err.message)
        log.info("signup user=%s", user)
        return sign_in(request, user, body.keep)

    @app.post("/api/logout")
    def logout(request: Request):
        request.session.pop("user", None)
        thread = new_thread(request)
        return envelope(request, sync_account(request, thread, None))

    @app.post("/api/reset")
    def reset(request: Request):
        """대화만 처음으로. 로그인은 유지한다."""
        user = request.session.get("user")
        thread = new_thread(request)
        return envelope(request, sync_account(request, thread, user))

    @app.post("/api/orders")
    def order(body: OrderIn, request: Request):
        thread, user = current(request)
        if not user or not store.get_account(user):
            raise ApiError(401, "login_required", "구매하려면 로그인해 주세요.")
        if body.code not in BY_CODE:
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["code"])
        throttle(request, "chat-ip", settings.ip_per_minute)
        throttle(request, "order", 10, key=user)
        with lock_for(thread):
            try:
                o = store.add_order(user, body.code, body.size)   # 재고 확인과 차감을 한 번에
            except StoreError as err:
                raise ApiError(409, err.code, err.message)
            state = sync_account(request, thread, user)
        notify.send(settings.notify_webhook, f'[PITCHROOM] 새 주문 {o["id"]}: {order_label(o)} — 출고 대기')
        log.info("order thread=%s user=%s id=%s code=%s size=%d", thread[:8], user, o["id"], o["code"], o["size"])
        headline = f'주문했어요. {o["id"]} · {order_label(o)}, 지금은 결제 완료 상태예요.'
        return envelope(request, state, service_home(state["account"], headline), order_id=o["id"])

    @app.post("/api/contact")
    def contact(body: ContactIn, request: Request):
        """사람이 이어받는 건에 연락받을 곳을 남긴다. 로그인했으면 계정에도 저장해 다음부터 묻지 않는다."""
        value = body.contact.strip()
        if not (PHONE.match(value) or EMAIL.match(value)):
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["contact"])
        thread, user = current(request)
        throttle(request, "chat-ip", settings.ip_per_minute)
        with lock_for(thread):
            state = sync_account(request, thread, user)
            attached = store.set_handoff_contact(thread, value)
            if state.get("account"):
                store.set_contact(state["account"]["id"], value)
            elif not attached:
                raise ApiError(409, "nothing_to_attach", "연락처를 남길 문의가 없어요.")
            return envelope(request, state)

    @app.post("/api/password")
    def change_password(body: PasswordIn, request: Request):
        user = request.session.get("user")
        if not user:
            raise ApiError(401, "login_required", "로그인해 주세요.")
        if not 8 <= len(body.new) <= 72:
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["new"])
        throttle(request, "auth", settings.auth_per_minute)
        try:
            store.change_password(user, body.current, body.new)
        except StoreError as err:
            raise ApiError(401 if err.code == "bad_credentials" else 409, err.code, err.message)
        log.info("password changed user=%s", user)
        return {"ok": True}

    # ---------- 관리(사장님) 라우트 ----------
    def admin_order(o: dict) -> dict:
        return {"id": o["id"], "account_id": o["account_id"], "account_name": o.get("account_name"), "title": order_title(o),
                "status": o["status"], "note": o["note"], "exchanges": o["exchanges"], "ordered_at": o["ordered_at"],
                "size": o["size"], "code": o["code"],
                "shipped_at": o["shipped_at"], "delivered_at": o["delivered_at"], "actions": order_actions(o["status"])}

    def admin_board() -> dict:
        return {
            "summary": store.summary(),
            "handoffs": [{**h, "kind_label": HANDOFF_KIND.get(h["kind"], h["kind"])} for h in store.list_handoffs("open")],
            "done": [{**h, "kind_label": HANDOFF_KIND.get(h["kind"], h["kind"])} for h in store.list_handoffs("done")[:20]],
            "orders": [admin_order(o) for o in store.list_orders()],
            "products": store.list_products(),
            "customers": store.list_customers(),
        }

    @app.get("/api/admin/board")
    def board(request: Request):
        require_admin(request)
        return admin_board()

    @app.post("/api/admin/orders/{order_id}/status")
    def set_status(order_id: str, body: TransitionIn, request: Request):
        admin = require_admin(request)
        try:
            o = store.transition_order(order_id, body.to, body.note, body.new_size)
        except StoreError as err:
            raise ApiError({"unknown_order": 404, "size_required": 422}.get(err.code, 409), err.code, err.message)
        log.info("admin=%s order=%s → %s", admin["id"], order_id, o["status"])
        return admin_board()

    @app.post("/api/admin/handoffs/{handoff_id}/resolve")
    def resolve(handoff_id: int, body: ResolveIn, request: Request):
        admin = require_admin(request)
        try:
            store.resolve_handoff(handoff_id, body.note.strip() or "처리 완료")
        except StoreError as err:
            raise ApiError(404, err.code, err.message)
        log.info("admin=%s handoff=%s 처리", admin["id"], handoff_id)
        return admin_board()

    @app.post("/api/admin/products/{code}")
    def update_product(code: str, body: ProductIn, request: Request):
        """가격, 판매 여부, 사이즈별 재고를 바꾼다. 바꾼 값은 다음 추천부터 바로 쓰인다."""
        admin = require_admin(request)
        if body.stock and any(not 0 <= q <= 999 for q in body.stock.values()):
            raise ApiError(422, "invalid_input", FIELD_MESSAGE["stock"])
        try:
            store.update_product(code, body.price, body.active, body.stock)
        except StoreError as err:
            raise ApiError(404 if err.code == "unknown_product" else 422, err.code, err.message)
        log.info("admin=%s product=%s price=%s active=%s stock=%s", admin["id"], code, body.price, body.active, body.stock)
        return admin_board()

    @app.post("/api/admin/customers/{user_id}/reset-password")
    def reset_password(user_id: str, request: Request):
        """고객이 비밀번호를 잊었을 때: 임시 비밀번호를 만들어 사장님 화면에 한 번 보여준다 (사장님이 고객에게 전한다)."""
        admin = require_admin(request)
        try:
            temp = store.reset_password(user_id)
        except StoreError as err:
            raise ApiError(404, err.code, err.message)
        log.info("admin=%s reset password for user=%s", admin["id"], user_id)
        return {"temp_password": temp, "user_id": user_id}

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def unknown_api(rest: str):
        """없는 API 주소가 아래의 화면 서빙으로 넘어가지 않게 여기서 끊는다."""
        raise ApiError(404, "not_found", "요청한 주소를 찾지 못했어요.")

    # ---------- 정적 파일: 상품 사진 + 빌드된 화면 ----------
    app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")
    if (DIST_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        def no_build():
            return HTMLResponse("<meta charset='utf-8'><title>PITCHROOM</title><p style='font-family:system-ui;padding:24px'>"
                                "화면이 아직 빌드되지 않았어요. <code>make build</code> 뒤 다시 열거나, 개발 중이면 <code>make dev</code>로 "
                                "띄우고 <a href='http://127.0.0.1:5173'>http://127.0.0.1:5173</a>을 여세요.</p>")

    log.info("PITCHROOM API 준비: env=%s db=%s 데모=%s 문장 이해=%s", config.ENV, db_path, "켬" if settings.demo else "끔",
             f"LLM({config.MODEL})" if extract.EXTRACTOR is not None else "키워드 규칙")
    return app
