"""HTTP API가 지켜야 하는 약속: 그래프와 같은 판단, 내부 정보 차단, 재시작 뒤 유지, 입력 검증."""
import json

import pytest
from fastapi.testclient import TestClient

from pitchroom.api import create_app
from pitchroom.config import Settings
from pitchroom.data import FORBIDDEN_WORDS
from pitchroom.evaluation import SCENARIOS, unsafe


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def client(db):
    with TestClient(create_app(db)) as c:
        yield c


def say(client, text):
    r = client.post("/api/chat", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("sc", SCENARIOS, ids=[sc[0] for sc in SCENARIOS])
def test_scenario_route_over_http(client, sc):
    _, user, turns, route, _, surface = sc
    if user:
        assert client.post("/api/login", json={"user_id": user}).status_code == 200
    for t in turns:
        body = say(client, t)
    view = body["view"]
    assert view["route"] == route
    codes = [c["code"] for c in view["shelf"]["cards"]] if view["shelf"]["kind"] == "products" else []
    assert not unsafe(codes, surface), "구장에 위험한 스터드를 추천하면 안 된다"
    raw = json.dumps(body, ensure_ascii=False)
    assert not any(w in view["headline"] for w in FORBIDDEN_WORDS)
    assert "(내부)" not in raw, "내부 논의가 화면 응답에 실리면 안 된다"
    assert "Infinity" not in raw and "NaN" not in raw


def test_home_and_catalog(client):
    cat = client.get("/api/catalog").json()
    assert len(cat["products"]) == 10 and all(p["image"] for p in cat["products"])
    assert [a["id"] for a in cat["demo_accounts"]] == ["minsu", "jiwoo", "hyun", "seoyeon"]
    body = client.get("/api/session").json()
    assert body["account"] is None and body["view"]["screen"] == "shop" and body["view"]["collect"]
    assert client.get("/images/S-01.webp").headers["content-type"] == "image/webp"
    assert client.get("/api/health").json() == {"ok": True, "llm": False, "model": None, "search": False}


def test_budget_any_is_json_safe(client):
    say(client, "실내 체육관에서 차요")
    say(client, "보통")
    body = say(client, "예산 상관없어요")
    budget = next(s for s in body["view"]["slots"] if s["key"] == "budget")
    assert budget == {"key": "budget", "label": "예산", "text": "상관없음", "on": True}
    assert body["view"]["route"] == "recommend" and body["view"]["shelf"]["blur"] == 0


def test_recommend_marks_first_card_and_allows_buying(client):
    for t in ["인조잔디에서 뛰어요", "발볼 넓어요"]:
        assert say(client, t)["view"]["collect"]
    view = say(client, "20만원")["view"]
    cards = view["shelf"]["cards"]
    assert cards[0]["label"] == "먼저 신어볼 1켤레" and cards[0]["best"]
    assert all(c["buyable"] for c in cards)
    assert view["echo"] == "20만원"


def test_health_escalation_pauses_shelf(client):
    view = say(client, "발목 수술한 적 있어요 인조잔디용 추천")["view"]
    assert view["route"] == "escalate" and view["shelf"]["paused"]
    assert view["handoff"]["title"] == "피팅 전문가에게 넘겼어요"


def test_login_shows_service_home_and_exchange_updates_order(client):
    body = client.post("/api/login", json={"user_id": "JiWoo "}).json()
    assert body["account"]["name"] == "지우" and body["view"]["screen"] == "service"
    assert body["view"]["shelf"]["kind"] == "orders" and body["view"]["shelf"]["cards"][0]["primary"]
    asked = say(client, "사이즈가 작아요")["view"]
    assert asked["route"] == "ask" and asked["shelf"]["kind"] == "orders"
    done = say(client, "실내에서만 신어봤어요")
    assert done["view"]["news"]["verdict"] == "자동 접수" and not done["view"]["news"]["hold"]
    assert done["view"]["news"]["discussion"] and done["view"]["discussion"] == []   # 논의는 카드뉴스 안에만
    assert done["account"]["orders"][0]["status"] == "교환 접수"
    assert done["account"]["orders"][0]["steps"][-1] == {"text": "교환 접수", "state": "svc"}


def test_order_and_conversation_survive_restart(db):
    with TestClient(create_app(db)) as c:
        c.post("/api/login", json={"user_id": "minsu"})
        say(c, "풋살장")
        r = c.post("/api/orders", json={"code": "S-07", "size": 265})
        assert r.status_code == 200 and r.json()["order_id"] == "PR-0006"
        assert r.json()["view"]["headline"].startswith("주문했어요. PR-0006")
        cookies = dict(c.cookies)
    with TestClient(create_app(db), cookies=cookies) as c:   # 서버를 다시 띄워도
        body = c.get("/api/session").json()
        assert [o["id"] for o in body["account"]["orders"]] == ["PR-0006", "PR-0001"]   # 주문이 남아 있고
        assert body["view"]["echo"] == "풋살장"                                          # 대화도 이어진다
        slot = next(s for s in body["view"]["slots"] if s["key"] == "surface")
        assert slot["text"] == "풋살장"


def test_order_ids_do_not_collide_across_accounts(db):
    ids = []
    for user in ["minsu", "jiwoo"]:
        with TestClient(create_app(db)) as c:
            c.post("/api/login", json={"user_id": user})
            ids.append(c.post("/api/orders", json={"code": "S-05", "size": 270}).json()["order_id"])
    assert ids == ["PR-0006", "PR-0007"]


def test_login_keep_preserves_recommendation_for_pending_purchase(client):
    for t in ["인조잔디에서 뛰어요", "발볼 넓어요", "20만원"]:
        say(client, t)
    body = client.post("/api/login", json={"user_id": "minsu", "keep": True}).json()
    assert body["account"]["id"] == "minsu" and body["view"]["route"] == "recommend"


def test_reset_keeps_login_and_logout_clears_it(client):
    client.post("/api/login", json={"user_id": "seoyeon"})
    say(client, "인조잔디")
    body = client.post("/api/reset").json()
    assert body["account"]["id"] == "seoyeon" and body["view"]["screen"] == "service" and body["view"]["echo"] is None
    assert "교환 접수" in body["view"]["headline"]   # 가장 급한 주문부터 말을 건다
    body = client.post("/api/logout").json()
    assert body["account"] is None and body["view"]["screen"] == "shop"


@pytest.mark.parametrize("path, payload, status, code", [
    ("/api/chat", {"text": "   "}, 422, "invalid_input"),
    ("/api/chat", {"text": "가" * 501}, 422, "invalid_input"),
    ("/api/chat", {}, 422, "invalid_input"),
    ("/api/login", {"user_id": "nobody"}, 401, "bad_credentials"),
    ("/api/admin/board", {}, 404, "not_found"),
    ("/api/orders", {"code": "S-01", "size": 270}, 401, "login_required"),
    ("/api/nope", {}, 404, "not_found"),
])
def test_errors_share_one_shape(client, path, payload, status, code):
    r = client.post(path, json=payload)
    assert r.status_code == status
    assert r.json()["error"]["code"] == code and r.json()["error"]["message"]


@pytest.mark.parametrize("payload", [{"code": "S-99", "size": 270}, {"code": "S-01", "size": 271}, {"code": "S-01", "size": 400}])
def test_order_validation(client, payload):
    client.post("/api/login", json={"user_id": "minsu"})
    r = client.post("/api/orders", json=payload)
    assert r.status_code in (409, 422) and r.json()["error"]["code"] in ("invalid_input", "out_of_stock")
    assert len(client.get("/api/session").json()["account"]["orders"]) == 1


def test_keyword_budget_accepts_won_with_commas():
    from pitchroom.extract import keyword_extract
    assert keyword_extract("150,000원 이하요").budget == 150000
    assert keyword_extract("20만원").budget == 200000


# ---------- 회원가입 · 비밀번호 ----------
ADMIN = {"user_id": "admin", "password": "test-admin-pw"}


def app_with(db, **over):
    return create_app(db, Settings(admin_password=ADMIN["password"], **over))


def test_signup_then_password_login(client):
    r = client.post("/api/signup", json={"user_id": "Taeho_9", "name": "태호", "password": "correct-horse"})
    assert r.status_code == 200 and r.json()["account"] == {"id": "taeho_9", "name": "태호", "role": "customer", "orders": []}
    assert client.post("/api/orders", json={"code": "S-05", "size": 270}).status_code == 200   # 가입하면 바로 로그인 상태
    client.post("/api/logout")
    assert client.post("/api/login", json={"user_id": "taeho_9", "password": "wrong-password"}).json()["error"]["code"] == "bad_credentials"
    assert client.post("/api/login", json={"user_id": "taeho_9"}).status_code == 401            # 비밀번호 없이도 안 된다
    body = client.post("/api/login", json={"user_id": "taeho_9", "password": "correct-horse"}).json()
    assert [o["status"] for o in body["account"]["orders"]] == ["결제완료"]


@pytest.mark.parametrize("payload, code", [
    ({"user_id": "ab", "name": "태호", "password": "correct-horse"}, "invalid_input"),
    ({"user_id": "한글아이디", "name": "태호", "password": "correct-horse"}, "invalid_input"),
    ({"user_id": "taeho", "name": " ", "password": "correct-horse"}, "invalid_input"),
    ({"user_id": "taeho", "name": "태호", "password": "short"}, "invalid_input"),
    ({"user_id": "jiwoo", "name": "지우", "password": "correct-horse"}, "id_taken"),
    ({"user_id": "admin", "name": "가짜", "password": "correct-horse"}, "id_taken"),
])
def test_signup_validation(client, payload, code):
    r = client.post("/api/signup", json=payload)
    assert r.status_code in (409, 422) and r.json()["error"]["code"] == code


def test_password_is_stored_hashed(db):
    import sqlite3
    with TestClient(create_app(db)) as c:
        c.post("/api/signup", json={"user_id": "taeho", "name": "태호", "password": "correct-horse"})
    stored = sqlite3.connect(db).execute("SELECT password_hash FROM accounts WHERE id = 'taeho'").fetchone()[0]
    assert stored.startswith("scrypt$") and "correct-horse" not in stored


def test_demo_accounts_are_off_outside_demo_mode(db):
    with TestClient(app_with(db, demo=False)) as c:
        assert c.get("/api/catalog").json()["demo_accounts"] == []
        assert c.post("/api/login", json={"user_id": "jiwoo"}).status_code == 401
    with TestClient(app_with(db, demo=True)) as c:    # 데모로 한 번 띄워 계정이 DB에 생긴 뒤에도
        assert c.post("/api/login", json={"user_id": "jiwoo"}).status_code == 200
    with TestClient(app_with(db, demo=False)) as c:   # 데모를 끄면 비밀번호 없는 계정으로는 못 들어간다
        assert c.post("/api/login", json={"user_id": "jiwoo"}).status_code == 401


# ---------- 요청 제한 · 공개용 설정 ----------
def test_login_attempts_are_rate_limited(db):
    with TestClient(app_with(db, auth_per_minute=3)) as c:
        codes = [c.post("/api/login", json={"user_id": "admin", "password": "nope-nope"}).status_code for _ in range(5)]
        assert codes == [401, 401, 401, 429, 429]
        assert c.post("/api/login", json=ADMIN).json()["error"]["code"] == "rate_limited"   # 맞는 비밀번호도 잠시 막힌다


def test_chat_is_rate_limited_per_conversation(db):
    with TestClient(app_with(db, chat_per_minute=2)) as c:
        assert [c.post("/api/chat", json={"text": "인조잔디"}).status_code for _ in range(3)] == [200, 200, 429]
    with TestClient(app_with(db, chat_per_minute=2)) as other:
        assert other.post("/api/chat", json={"text": "인조잔디"}).status_code == 200


def test_security_headers_and_production_switches(db):
    with TestClient(app_with(db)) as c:
        h = c.get("/api/health").headers
        assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in h["content-security-policy"]
        assert c.get("/api/openapi.json").status_code == 200
    with TestClient(app_with(db, docs=False, cookie_secure=True)) as c:
        assert c.get("/api/openapi.json").status_code == 404
        assert "secure" in c.get("/api/session").headers["set-cookie"].lower()


# ---------- 관리 화면: 주문을 끝까지 흘려보내기 ----------
def login_admin(c):
    r = c.post("/api/login", json=ADMIN)
    assert r.status_code == 200 and r.json()["account"]["role"] == "admin"


def test_admin_routes_need_admin(db):
    with TestClient(app_with(db)) as c:
        assert c.get("/api/admin/board").json()["error"]["code"] == "login_required"
        c.post("/api/login", json={"user_id": "jiwoo"})
        assert c.get("/api/admin/board").status_code == 403
        assert c.post("/api/admin/orders/PR-0001/status", json={"to": "배송중"}).status_code == 403
        assert c.post("/api/login", json={"user_id": "admin", "password": "wrong-password"}).status_code == 401


def test_new_order_flows_to_delivery_and_then_exchange(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner:
        shopper.post("/api/signup", json={"user_id": "taeho", "name": "태호", "password": "correct-horse"})
        oid = shopper.post("/api/orders", json={"code": "S-08", "size": 270}).json()["order_id"]
        assert say(shopper, "교환하고 싶어요")["view"]["reason"] == "no-order"   # 아직 못 받은 신발은 교환할 수 없다

        login_admin(owner)
        board = owner.get("/api/admin/board").json()
        mine = next(o for o in board["orders"] if o["id"] == oid)
        assert mine["account_name"] == "태호" and mine["actions"] == [{"to": "배송중", "label": "출고 처리", "needs_size": False}]
        assert owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송완료"}).json()["error"]["code"] == "bad_transition"   # 단계를 건너뛸 수 없다
        owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송중"})
        assert "배송 중" in say(shopper, "언제 와요?")["view"]["headline"]         # 고객 답변이 바뀐 상태를 바로 따른다
        board = owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송완료"}).json()
        assert next(o for o in board["orders"] if o["id"] == oid)["delivered_at"]

        shopper.post("/api/reset")
        say(shopper, "사이즈가 작아요")
        done = say(shopper, "실내에서만 신어봤어요")
        assert done["view"]["news"]["verdict"] == "자동 접수"
        assert owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송완료"}).json()["error"]["code"] == "size_required"
        board = owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송완료", "new_size": 275}).json()   # 275mm로 바꿔 보냄
        assert board["error"]["code"] == "out_of_stock"                                                          # S-08 275mm는 품절
        board = owner.post(f"/api/admin/orders/{oid}/status", json={"to": "배송완료", "new_size": 280}).json()
        o = next(o for o in board["orders"] if o["id"] == oid)
        assert (o["status"], o["exchanges"], o["note"], o["size"]) == ("배송완료", 1, "교환 상품이 도착했어요.", 280)
        stock = {x["size"]: x["qty"] for x in next(p for p in board["products"] if p["code"] == "S-08")["stock"]}
        assert (stock[270], stock[280]) == (3, 1)   # 270은 주문 때 -1, 돌아와서 +1 / 280은 -1
        assert owner.post("/api/admin/orders/PR-9999/status", json={"to": "배송중"}).status_code == 404


def test_escalations_reach_the_owner_and_approval_closes_them(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner, TestClient(app) as guest:
        shopper.post("/api/login", json={"user_id": "hyun"})
        for _ in range(2):   # 같은 말을 반복해도 한 건
            assert say(shopper, "교환하고 싶어요")["view"]["route"] in ("escalate", "cs")
        say(guest, "발목 수술한 적 있어요 인조잔디용 추천")
        say(guest, "발목 수술한 적 있어요")

        login_admin(owner)
        board = owner.get("/api/admin/board").json()
        assert board["summary"]["open_handoffs"] == 2
        health, policy = board["handoffs"]
        assert (health["kind"], health["account_id"], health["detail"]["text"]) == ("health", None, "발목 수술한 적 있어요 인조잔디용 추천")
        assert (policy["kind"], policy["account_name"], policy["order_id"]) == ("policy", "현", "PR-0003")
        assert any(d["internal"] for d in policy["detail"]["discussion"])      # 사장님은 내부 논의까지 본다
        assert any("✗" in r for r in policy["detail"]["rules"])

        board = owner.post("/api/admin/orders/PR-0003/status", json={"to": "교환 접수", "note": "이번만 예외로 교환해 드려요."}).json()
        assert [h["kind"] for h in board["handoffs"]] == ["health"]              # 결재하면 그 건은 닫힌다
        assert board["done"][0]["resolution"].startswith("교환 승인")
        body = shopper.get("/api/session").json()
        assert body["account"]["orders"][0]["status"] == "교환 접수" and body["account"]["orders"][0]["note"] == "이번만 예외로 교환해 드려요."

        board = owner.post(f'/api/admin/handoffs/{health["id"]}/resolve', json={"note": "전화 상담 완료"}).json()
        assert board["handoffs"] == [] and board["summary"]["open_handoffs"] == 0
        assert owner.post(f'/api/admin/handoffs/{health["id"]}/resolve', json={}).status_code == 404


def test_customer_turn_does_not_overwrite_owner_change_to_another_order(db):
    from pitchroom.store import Store
    s = Store(db)
    acc = s.get_account("seoyeon")                       # 고객 대화가 들고 있던 사본
    s.transition_order("PR-0005", "배송완료")             # 그 사이 사장님이 다른 주문을 넘김
    changed = {**acc, "orders": [{**o, "note": "메모"} if o["id"] == "PR-0004" else o for o in acc["orders"]]}
    s.save_orders(changed, acc)                          # 고객 턴은 PR-0004만 바꿨다
    now = {o["id"]: o for o in s.get_account("seoyeon")["orders"]}
    assert now["PR-0005"]["status"] == "배송완료" and now["PR-0004"]["note"] == "메모"


def test_reseeding_demo_keeps_real_customers(db):
    from pitchroom.store import Store
    with TestClient(create_app(db)) as c:
        c.post("/api/signup", json={"user_id": "taeho", "name": "태호", "password": "correct-horse"})
        c.post("/api/orders", json={"code": "S-05", "size": 270})
    Store(db).seed()
    acc = Store(db).get_account("taeho")
    assert acc and len(acc["orders"]) == 1 and Store(db).get_account("jiwoo")["orders"][0]["status"] == "배송완료"


# ---------- 재고 · 가격 ----------
def stock_of(board, code):
    return {x["size"]: x["qty"] for x in next(p for p in board["products"] if p["code"] == code)["stock"]}


def test_last_pair_cannot_be_sold_twice(db):
    app = app_with(db)
    with TestClient(app) as a, TestClient(app) as b, TestClient(app) as owner:
        a.post("/api/login", json={"user_id": "minsu"}); b.post("/api/login", json={"user_id": "jiwoo"})
        assert a.post("/api/orders", json={"code": "S-01", "size": 250}).status_code == 200   # S-01 250mm는 1켤레
        r = b.post("/api/orders", json={"code": "S-01", "size": 250})
        assert r.status_code == 409 and r.json()["error"] == {"code": "out_of_stock", "message": "250mm는 품절이에요. 다른 사이즈를 골라 주세요."}
        assert len(b.get("/api/session").json()["account"]["orders"]) == 1
        login_admin(owner)
        assert stock_of(owner.get("/api/admin/board").json(), "S-01")[250] == 0


def test_cards_and_catalog_show_only_sizes_in_stock(client):
    cat = {p["code"]: p["sizes"] for p in client.get("/api/catalog").json()["products"]}
    assert cat["S-01"] == [250, 255, 260, 265, 275, 280]          # 270, 285, 290 품절
    for t in ["천연잔디", "좁아요", "상관없어요"]:
        say(client, t)
    view = say(client, "270 신어요")["view"]
    first = view["shelf"]["cards"][0]
    assert first["code"] == "S-03" and first["sizes"] == [255, 260, 265, 270, 275] and first["size_note"] is None
    elite = next(c for c in view["shelf"]["cards"] if c["code"] == "S-01")
    assert elite["size_note"] == "270mm 품절"


def test_owner_changes_price_stock_and_visibility(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner:
        login_admin(owner)
        board = owner.post("/api/admin/products/S-07", json={"price": 99000, "stock": {"250": 0, "270": 7}}).json()
        item = next(p for p in board["products"] if p["code"] == "S-07")
        assert item["price"] == 99000 and stock_of(board, "S-07")[250] == 0 and stock_of(board, "S-07")[270] == 7
        for t in ["풋살장", "발볼 넓어요"]:
            say(shopper, t)
        view = say(shopper, "15만원")["view"]
        card = view["shelf"]["cards"][0]
        assert (card["code"], card["price"]) == ("S-07", 99000) and 250 not in card["sizes"]   # 바꾼 값이 바로 추천에 쓰인다

        owner.post("/api/admin/products/S-07", json={"active": False})
        shopper.post("/api/reset")
        for t in ["풋살장", "발볼 넓어요"]:
            say(shopper, t)
        codes = [c["code"] for c in say(shopper, "15만원")["view"]["shelf"]["cards"]]
        assert "S-07" not in codes                                                          # 숨긴 상품은 추천되지 않고
        shopper.post("/api/login", json={"user_id": "minsu", "keep": True})
        assert shopper.post("/api/orders", json={"code": "S-07", "size": 270}).json()["error"]["code"] == "not_for_sale"   # 살 수도 없다
        assert "S-07" not in [p["code"] for p in shopper.get("/api/catalog").json()["products"]]

    with TestClient(app_with(db)) as again:   # 다시 띄워도 유지
        login_admin(again)
        item = next(p for p in again.get("/api/admin/board").json()["products"] if p["code"] == "S-07")
        assert (item["price"], item["active"]) == (99000, False)


@pytest.mark.parametrize("payload, status", [
    ({"price": 500}, 422), ({"price": 9_000_000}, 422), ({"stock": {"270": -1}}, 422), ({"stock": {"270": 1000}}, 422),
    ({"stock": {"333": 1}}, 422),
])
def test_product_update_validation(db, payload, status):
    with TestClient(app_with(db)) as owner:
        login_admin(owner)
        assert owner.post("/api/admin/products/S-07", json=payload).status_code == status
        assert owner.post("/api/admin/products/S-99", json={"price": 10000}).status_code == 404


def test_return_puts_the_pair_back_in_stock(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner:
        shopper.post("/api/login", json={"user_id": "jiwoo"})          # S-08 270mm, 받은 지 3일
        say(shopper, "반품하고 싶어요"); say(shopper, "안 신었어요")
        login_admin(owner)
        before = stock_of(owner.get("/api/admin/board").json(), "S-08")[270]
        board = owner.post("/api/admin/orders/PR-0002/status", json={"to": "반품 완료"}).json()
        assert stock_of(board, "S-08")[270] == before + 1
        body = shopper.post("/api/reset").json()
        assert body["account"]["orders"][0]["status"] == "반품 완료" and "반품이 완료됐어요" in body["view"]["headline"]


# ---------- 연락처 · 알림 ----------
def test_guest_leaves_contact_on_a_handoff(db):
    app = app_with(db)
    with TestClient(app) as guest, TestClient(app) as owner:
        assert guest.post("/api/contact", json={"contact": "010-1234-5678"}).json()["error"]["code"] == "nothing_to_attach"
        view = say(guest, "발목 수술한 적 있어요")["view"]
        assert view["contact"] == {"saved": None}
        assert guest.post("/api/contact", json={"contact": "연락주세요"}).status_code == 422
        view = guest.post("/api/contact", json={"contact": " 010-1234-5678 "}).json()["view"]
        assert view["contact"] == {"saved": "010-1234-5678"} and view["route"] == "escalate"
        login_admin(owner)
        assert owner.get("/api/admin/board").json()["handoffs"][0]["contact"] == "010-1234-5678"


def test_account_contact_is_remembered_for_later_handoffs(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner:
        shopper.post("/api/login", json={"user_id": "hyun"})
        say(shopper, "교환하고 싶어요")
        shopper.post("/api/contact", json={"contact": "hyun@example.com"})
        shopper.post("/api/reset")
        view = say(shopper, "무릎 인대를 다쳤어요")["view"]
        assert view["contact"] == {"saved": "hyun@example.com"}            # 다시 묻지 않는다
        login_admin(owner)
        board = owner.get("/api/admin/board").json()
        assert {h["contact"] for h in board["handoffs"]} == {"hyun@example.com"}
        assert next(c for c in board["customers"] if c["id"] == "hyun")["contact"] == "hyun@example.com"
        assert say(shopper, "인조잔디")["view"]["contact"] is None           # 넘긴 건이 아니면 묻지 않는다


def test_webhook_gets_handoffs_and_orders_without_customer_text(db):
    import json as _json, threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    got, seen = [], threading.Event()

    class Hook(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(_json.loads(self.rfile.read(int(self.headers["content-length"]))))
            self.send_response(204); self.end_headers()
            if len(got) == 2:
                seen.set()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Hook)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with TestClient(app_with(db, notify_webhook=f"http://127.0.0.1:{server.server_port}/hook")) as c:
            say(c, "족저근막염이 있는데 괜찮을까요")
            c.post("/api/login", json={"user_id": "minsu"})
            c.post("/api/orders", json={"code": "S-05", "size": 270})
            assert seen.wait(5)
    finally:
        server.shutdown()
    texts = sorted(m["text"] for m in got)
    assert texts[0].startswith("[PITCHROOM] 넘어온 건: 발 건강 상담 · 비로그인 고객") and "족저근막" not in texts[0]   # 건강 내용은 밖으로 안 나간다
    assert texts[1].startswith("[PITCHROOM] 새 주문 PR-0006") and got[0]["content"] == got[0]["text"]


def test_dead_webhook_does_not_break_the_request(db):
    with TestClient(app_with(db, notify_webhook="http://127.0.0.1:9/nope")) as c:
        assert say(c, "발목 수술한 적 있어요")["view"]["route"] == "escalate"


# ---------- 비밀번호 변경 · 재발급 ----------
def test_customer_changes_password(client):
    client.post("/api/signup", json={"user_id": "taeho", "name": "태호", "password": "correct-horse"})
    assert client.post("/api/password", json={"current": "wrong-one", "new": "battery-staple"}).json()["error"]["code"] == "bad_credentials"
    assert client.post("/api/password", json={"current": "correct-horse", "new": "short"}).status_code == 422
    assert client.post("/api/password", json={"current": "correct-horse", "new": "battery-staple"}).json() == {"ok": True}
    client.post("/api/logout")
    assert client.post("/api/login", json={"user_id": "taeho", "password": "correct-horse"}).status_code == 401
    assert client.post("/api/login", json={"user_id": "taeho", "password": "battery-staple"}).status_code == 200
    client.post("/api/logout")
    assert client.post("/api/password", json={"current": "x", "new": "battery-staple"}).status_code == 401
    client.post("/api/login", json={"user_id": "jiwoo"})
    assert client.post("/api/password", json={"current": "", "new": "battery-staple"}).json()["error"]["code"] == "no_password"


def test_owner_issues_a_temporary_password(db):
    app = app_with(db)
    with TestClient(app) as shopper, TestClient(app) as owner:
        shopper.post("/api/signup", json={"user_id": "taeho", "name": "태호", "password": "correct-horse"})
        shopper.post("/api/logout")
        assert shopper.post("/api/admin/customers/taeho/reset-password").status_code == 401
        login_admin(owner)
        assert next(c for c in owner.get("/api/admin/board").json()["customers"] if c["id"] == "taeho")["has_password"]
        temp = owner.post("/api/admin/customers/taeho/reset-password").json()["temp_password"]
        assert len(temp) >= 10
        assert shopper.post("/api/login", json={"user_id": "taeho", "password": "correct-horse"}).status_code == 401
        assert shopper.post("/api/login", json={"user_id": "taeho", "password": temp}).status_code == 200
        for other in ["admin", "jiwoo", "nobody"]:   # 관리자·데모 계정·없는 계정은 안 된다
            assert owner.post(f"/api/admin/customers/{other}/reset-password").status_code == 404
