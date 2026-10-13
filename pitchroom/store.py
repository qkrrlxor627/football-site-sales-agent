"""계정·주문·넘어온 건 저장소 (SQLite). 주문 상태와 사람에게 넘긴 건을 재시작 뒤에도 유지한다.

데모 다시 깔기: python -m pitchroom.store --reset
"""
# 그래프 State의 account는 '이번 대화가 보는 사본'이고, 원본은 여기다.
# API가 매 턴 앞에서 원본을 State에 넣고, 턴이 끝나면 바뀐 주문만 다시 여기에 쓴다.
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from .config import DB_PATH
from .data import BY_CODE, DEMO_ACCOUNTS, day_iso, make_account, order_label

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    code TEXT NOT NULL,
    size INTEGER NOT NULL,
    status TEXT NOT NULL,
    exchanges INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    ordered_at TEXT NOT NULL,
    shipped_at TEXT,
    delivered_at TEXT
);
CREATE INDEX IF NOT EXISTS orders_account ON orders(account_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    thread_id TEXT,
    account_id TEXT,
    order_id TEXT,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT,
    resolution TEXT
);
CREATE INDEX IF NOT EXISTS handoffs_status ON handoffs(status);
CREATE TABLE IF NOT EXISTS threads (thread_id TEXT PRIMARY KEY, last_seen TEXT NOT NULL);
"""
# 나중에 추가된 열. 예전 DB 파일에도 그대로 붙는다.
ACCOUNT_COLUMNS = {"password_hash": "TEXT", "role": "TEXT NOT NULL DEFAULT 'customer'", "created_at": "TEXT"}
ORDER_COLS = ["id", "code", "size", "status", "exchanges", "note", "ordered_at", "shipped_at", "delivered_at"]

# 사장님이 주문을 다음 단계로 넘기는 규칙: 지금 상태 → [(다음 상태, 버튼 이름, 고객에게 보일 안내)]
TRANSITIONS = {
    "결제완료": [("배송중", "출고 처리", None)],
    "배송중": [("배송완료", "배송 완료 처리", None)],
    "교환 접수": [("배송완료", "교환 완료 처리", "교환 상품이 도착했어요.")],
    "반품 접수": [("반품 완료", "반품·환불 완료 처리", "검수가 끝나 환불됐어요.")],
    "사장님 확인 중": [
        ("교환 접수", "교환 승인", "교환이 승인됐어요. 회수 기사님이 1~2일 안에 방문해요."),
        ("반품 접수", "반품 승인", "반품이 승인됐어요. 회수 후 검수되면 환불돼요."),
        ("배송완료", "요청 거절", "확인 결과 교환·반품이 어려워요. 자세한 내용은 매장으로 문의해 주세요."),
    ],
}
HANDOFF_KIND = {"health": "발 건강 상담", "policy": "교환·반품 결재", "empty": "조건에 맞는 상품 없음", "review": "추천 검수 실패"}
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


class StoreError(Exception):
    """호출한 쪽이 사용자에게 그대로 보여줘도 되는 실패 (중복 아이디, 잘못된 상태 변경 등)."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def check_password(password: str, stored: Optional[str]) -> bool:
    try:
        _, salt, digest = (stored or "").split("$")
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), dklen=32, **SCRYPT)
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except ValueError:
        return False


class Store:
    def __init__(self, path: str = DB_PATH, demo: bool = True):
        self.path = path
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.executescript(SCHEMA)   # executescript는 스스로 커밋하므로 _tx 밖에서 돌린다
            have = {r[1] for r in db.execute("PRAGMA table_info(accounts)")}
            for col, decl in ACCOUNT_COLUMNS.items():
                if col not in have:
                    db.execute(f"ALTER TABLE accounts ADD COLUMN {col} {decl}")
            db.commit()
        finally:
            db.close()
        if demo and not self._has_demo():
            self.seed()

    @contextmanager
    def _tx(self):
        # 요청마다 새 연결: 스레드풀에서 불려도 안전하고, 이 규모에선 충분히 빠르다.
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    # ---------- 데모 ----------
    def _has_demo(self) -> bool:
        with self._tx() as db:
            return db.execute(f"SELECT 1 FROM accounts WHERE id IN ({', '.join('?' * len(DEMO_ACCOUNTS))}) LIMIT 1", tuple(DEMO_ACCOUNTS)).fetchone() is not None

    def seed(self):
        """데모 계정 4개를 오늘 날짜 기준으로 다시 만든다. 데모 계정과 그 주문만 지우고, 가입한 고객은 건드리지 않는다."""
        ids = tuple(DEMO_ACCOUNTS)
        marks = ", ".join("?" * len(ids))
        with self._tx() as db:
            db.execute(f"DELETE FROM handoffs WHERE account_id IN ({marks})", ids)
            db.execute(f"DELETE FROM orders WHERE account_id IN ({marks})", ids)
            db.execute(f"DELETE FROM accounts WHERE id IN ({marks})", ids)
            for user_id in ids:
                acc = make_account(user_id)
                db.execute("INSERT INTO accounts (id, name, role, created_at) VALUES (?, ?, 'customer', ?)", (acc["id"], acc["name"], now_iso()))
                for o in acc["orders"]:
                    db.execute(f"INSERT INTO orders (account_id, {', '.join(ORDER_COLS)}) VALUES (?, {', '.join('?' * len(ORDER_COLS))})",
                               (acc["id"], *[o[c] for c in ORDER_COLS]))

    # ---------- 계정 ----------
    def get_account(self, user_id: str) -> Optional[dict]:
        """그래프가 쓰는 account 모양: {id, name, role, orders: [...]} (최근 주문이 앞)."""
        with self._tx() as db:
            a = db.execute("SELECT id, name, role FROM accounts WHERE id = ?", (user_id,)).fetchone()
            if not a:
                return None
            rows = db.execute(f"SELECT {', '.join(ORDER_COLS)} FROM orders WHERE account_id = ? ORDER BY ordered_at DESC, id DESC", (user_id,)).fetchall()
        return {"id": a["id"], "name": a["name"], "role": a["role"], "orders": [dict(r) for r in rows]}

    def create_account(self, user_id: str, name: str, password: str, role: str = "customer") -> None:
        with self._tx() as db:
            if db.execute("SELECT 1 FROM accounts WHERE id = ?", (user_id,)).fetchone():
                raise StoreError("id_taken", "이미 쓰고 있는 아이디예요.")
            db.execute("INSERT INTO accounts (id, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                       (user_id, name, hash_password(password), role, now_iso()))

    def authenticate(self, user_id: str, password: Optional[str], allow_passwordless: bool) -> bool:
        """비밀번호가 맞으면 True. 비밀번호가 없는 계정(데모)은 데모 모드에서만 들어갈 수 있다."""
        with self._tx() as db:
            row = db.execute("SELECT password_hash FROM accounts WHERE id = ?", (user_id,)).fetchone()
        if not row:
            hash_password(password or "")   # 없는 아이디도 같은 시간이 걸리게 (아이디 존재 여부를 응답 시간으로 흘리지 않는다)
            return False
        if row["password_hash"] is None:
            return allow_passwordless and user_id in DEMO_ACCOUNTS
        return bool(password) and check_password(password, row["password_hash"])

    def ensure_admin(self, user_id: str, password: Optional[str]) -> Optional[str]:
        """관리자 계정을 보장한다. 비밀번호를 주면 그 값으로 맞추고, 없고 계정도 없으면 임시 비밀번호를 만들어 돌려준다."""
        with self._tx() as db:
            exists = db.execute("SELECT 1 FROM accounts WHERE id = ?", (user_id,)).fetchone()
            if exists and not password:
                db.execute("UPDATE accounts SET role = 'admin' WHERE id = ?", (user_id,))
                return None
            generated = None if password else secrets.token_urlsafe(9)
            hashed = hash_password(password or generated)
            if exists:
                db.execute("UPDATE accounts SET role = 'admin', password_hash = ? WHERE id = ?", (hashed, user_id))
            else:
                db.execute("INSERT INTO accounts (id, name, password_hash, role, created_at) VALUES (?, '사장', ?, 'admin', ?)", (user_id, hashed, now_iso()))
            return generated

    # ---------- 주문 ----------
    def save_orders(self, account: dict, before: Optional[dict] = None):
        """그래프(정책 에이전트)가 이번 턴에 바꾼 주문만 원본에 반영한다 (그 사이 사장님이 바꾼 다른 주문을 덮어쓰지 않게)."""
        old = {o["id"]: o for o in (before or {}).get("orders", [])}
        changed = [o for o in account["orders"] if o != old.get(o["id"])]
        if not changed:
            return
        with self._tx() as db:
            for o in changed:
                db.execute("UPDATE orders SET status = ?, exchanges = ?, note = ? WHERE id = ? AND account_id = ?",
                           (o["status"], o["exchanges"], o.get("note"), o["id"], account["id"]))

    def add_order(self, user_id: str, code: str, size: int) -> dict:
        """새 주문. 번호는 전체 주문에서 하나씩 올린다 (계정끼리 겹치지 않게)."""
        with self._tx() as db:
            last = db.execute("SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM orders").fetchone()[0] or 0
            o = {"id": f"PR-{last + 1:04d}", "code": code, "size": size, "status": "결제완료", "exchanges": 0, "note": None,
                 "ordered_at": day_iso(0), "shipped_at": None, "delivered_at": None}
            db.execute(f"INSERT INTO orders (account_id, {', '.join(ORDER_COLS)}) VALUES (?, {', '.join('?' * len(ORDER_COLS))})",
                       (user_id, *[o[c] for c in ORDER_COLS]))
        return o

    def list_orders(self, status: Optional[str] = None) -> list[dict]:
        """관리 화면용: 전체 주문 + 주문자. 손볼 일이 있는 주문이 앞에 온다."""
        q = (f"SELECT o.account_id, a.name AS account_name, {', '.join('o.' + c for c in ORDER_COLS)} "
             "FROM orders o JOIN accounts a ON a.id = o.account_id")
        with self._tx() as db:
            rows = db.execute(q + (" WHERE o.status = ?" if status else "") + " ORDER BY o.ordered_at DESC, o.id DESC", (status,) if status else ()).fetchall()
        out = [dict(r) for r in rows]
        out.sort(key=lambda o: 0 if o["status"] in TRANSITIONS else 1)
        return out

    def transition_order(self, order_id: str, to: str, note: Optional[str] = None) -> dict:
        """사장님이 주문을 다음 단계로 넘긴다. 규칙표에 없는 변경은 거절한다."""
        with self._tx() as db:
            row = db.execute(f"SELECT account_id, {', '.join(ORDER_COLS)} FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                raise StoreError("unknown_order", "없는 주문이에요.")
            o = dict(row)
            step = next((t for t in TRANSITIONS.get(o["status"], []) if t[0] == to), None)
            if not step:
                raise StoreError("bad_transition", f'"{o["status"]}" 상태에서는 "{to}"(으)로 바꿀 수 없어요.')
            was, today = o["status"], day_iso(0)
            o["status"], o["note"] = to, (note or "").strip() or step[2]
            if to == "배송중":
                o["shipped_at"] = today
            elif to == "배송완료" and was in ("배송중", "교환 접수"):
                o["delivered_at"] = today   # 교환 상품이 도착한 날부터 교환 기간을 다시 센다
            elif to == "교환 접수":
                o["exchanges"] += 1
            db.execute("UPDATE orders SET status = ?, note = ?, exchanges = ?, shipped_at = ?, delivered_at = ? WHERE id = ?",
                       (o["status"], o["note"], o["exchanges"], o["shipped_at"], o["delivered_at"], order_id))
            if was == "사장님 확인 중":   # 결재가 끝났으니 이 주문으로 넘어온 건도 닫는다
                db.execute("UPDATE handoffs SET status = 'done', resolved_at = ?, resolution = ? WHERE order_id = ? AND status = 'open'",
                           (now_iso(), f"{step[1]}: {o['note']}", order_id))
        return o

    # ---------- 사람에게 넘긴 건 ----------
    def add_handoff(self, kind: str, summary: str, detail: dict, thread_id: str, account_id: Optional[str] = None, order_id: Optional[str] = None) -> Optional[int]:
        """넘어온 건을 기록한다. 같은 대화에서 같은 종류가 아직 열려 있으면 다시 만들지 않는다 (같은 말을 반복해도 한 건)."""
        with self._tx() as db:
            if db.execute("SELECT 1 FROM handoffs WHERE status = 'open' AND kind = ? AND thread_id = ? AND order_id IS ?", (kind, thread_id, order_id)).fetchone():
                return None
            cur = db.execute("INSERT INTO handoffs (created_at, kind, thread_id, account_id, order_id, summary, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (now_iso(), kind, thread_id, account_id, order_id, summary, json.dumps(detail, ensure_ascii=False)))
            return cur.lastrowid

    def list_handoffs(self, status: str = "open") -> list[dict]:
        with self._tx() as db:
            rows = db.execute("SELECT h.*, a.name AS account_name FROM handoffs h LEFT JOIN accounts a ON a.id = h.account_id "
                              "WHERE h.status = ? ORDER BY h.id DESC LIMIT 200", (status,)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]

    def resolve_handoff(self, handoff_id: int, resolution: str) -> None:
        with self._tx() as db:
            cur = db.execute("UPDATE handoffs SET status = 'done', resolved_at = ?, resolution = ? WHERE id = ? AND status = 'open'",
                             (now_iso(), resolution, handoff_id))
            if cur.rowcount == 0:
                raise StoreError("unknown_handoff", "이미 처리했거나 없는 건이에요.")

    def summary(self) -> dict:
        with self._tx() as db:
            by_status = dict(db.execute("SELECT status, COUNT(*) FROM orders GROUP BY status").fetchall())
            return {
                "open_handoffs": db.execute("SELECT COUNT(*) FROM handoffs WHERE status = 'open'").fetchone()[0],
                "to_ship": by_status.get("결제완료", 0), "shipping": by_status.get("배송중", 0),
                "in_service": sum(by_status.get(s, 0) for s in ("교환 접수", "반품 접수", "사장님 확인 중")),
                "orders": sum(by_status.values()),
                "customers": db.execute("SELECT COUNT(*) FROM accounts WHERE role = 'customer'").fetchone()[0],
            }

    # ---------- 대화(thread) 청소 ----------
    def touch_thread(self, thread_id: str) -> None:
        with self._tx() as db:
            db.execute("INSERT INTO threads (thread_id, last_seen) VALUES (?, ?) ON CONFLICT(thread_id) DO UPDATE SET last_seen = excluded.last_seen", (thread_id, now_iso()))

    def forget_thread(self, thread_id: str) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))

    def stale_threads(self, days: int) -> list[str]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._tx() as db:
            return [r[0] for r in db.execute("SELECT thread_id FROM threads WHERE last_seen < ?", (cutoff,)).fetchall()]

    def secret(self) -> str:
        """세션 쿠키 서명 키. 한 번 만들어 DB에 두면 재시작해도 로그인이 풀리지 않는다."""
        with self._tx() as db:
            row = db.execute("SELECT value FROM meta WHERE key = 'secret'").fetchone()
            if row:
                return row["value"]
            value = secrets.token_urlsafe(32)
            db.execute("INSERT INTO meta (key, value) VALUES ('secret', ?)", (value,))
            return value


def order_actions(status: str) -> list[dict]:
    return [{"to": to, "label": label} for to, label, _ in TRANSITIONS.get(status, [])]


def order_title(o: dict) -> str:
    return order_label(o) if o["code"] in BY_CODE else o["code"]


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Store().seed()
        print(f"데모 계정·주문을 오늘 기준으로 다시 만들었어요: {DB_PATH}")
    else:
        print("사용법: python -m pitchroom.store --reset")
