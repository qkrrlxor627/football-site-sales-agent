"""케이스별 연습 계정: 상황 하나에 계정 하나. 로그인해서 '해 볼 말'을 치면 그 케이스가 재현된다.

실행: python -m pitchroom.sample   (Docker: docker compose exec pitchroom python -m pitchroom.sample)
다시 실행하면 연습 계정만 처음 상태로 되돌린다 (가입한 고객과 그 주문은 건드리지 않는다).
"""
# 실제 가입·주문과 같은 길(Store)을 지나므로 재고도 같이 움직이고, 날짜만 과거로 돌려 상황을 만든다.
import os
import secrets

from .config import Settings
from .data import BY_CODE, day_iso, order_label
from .store import Store

# 주문 한 건: (상품, 사이즈, 상태, 주문 후 며칠, 출고 후 며칠, 수령 후 며칠, 교환 횟수, 고객 안내)
WAIT_NOTE = "평일 10:00–18:00에 사장님이 확인해요."
CASES = [  # (아이디, 이름, 연락처, 상황, 해 볼 말 → 기대 결과, [주문])
    ("c_new", "신규", None, "주문 없음 (막 가입한 고객)",
     "인조잔디에서 뛰어요 → 발볼 넓어요 → 20만원 ⇒ 추천 3켤레, 구매하기",
     []),
    ("c_paid", "결제", "010-0000-3002", "결제완료, 출고 대기",
     "언제 와요? ⇒ 출고 준비 중 / 교환하고 싶어요 ⇒ 배송 완료 후 신청 안내",
     [("S-05", 265, "결제완료", 0, None, None, 0, None)]),
    ("c_shipping", "배송", "010-0000-3003", "배송중 (어제 출고)",
     "어디쯤이에요? ⇒ 배송 중, 도착일은 약속하지 않음",
     [("S-10", 260, "배송중", 2, 1, None, 0, None)]),
    ("c_exchange", "교환", "010-0000-3004", "배송완료 2일째, 교환 이력 없음",
     "사이즈가 작아요 → 실내에서만 신어봤어요 ⇒ 교환 자동 접수",
     [("S-08", 270, "배송완료", 4, 3, 2, 0, None)]),
    ("c_return", "반품", "c_return@example.com", "배송완료 3일째",
     "반품하고 싶어요 → 안 신었어요 ⇒ 반품 자동 접수 (왕복 배송비 안내)",
     [("S-07", 275, "배송완료", 5, 4, 3, 0, None)]),
    ("c_worn", "착용", "010-0000-3006", "배송완료 3일째, 이미 신고 뛰었음",
     "교환하고 싶어요 → 경기 뛰었어요 ⇒ 자동 처리 안 됨, 사장님 확인으로 넘어감",
     [("S-02", 265, "배송완료", 5, 4, 3, 0, None)]),
    ("c_late", "기한", None, "배송완료 12일째 (교환 기한 7일 지남)",
     "교환하고 싶어요 ⇒ 기한이 지나 사장님 확인으로 넘어감 (연락처를 물어봄)",
     [("S-04", 270, "배송완료", 15, 14, 12, 0, None)]),
    ("c_again", "재교환", "010-0000-3008", "배송완료 4일째, 이미 한 번 교환함",
     "사이즈가 작아요 → 안 신었어요 ⇒ 무료 교환 1회를 넘겨 사장님 확인으로 넘어감",
     [("S-01", 275, "배송완료", 20, 19, 4, 1, "교환 상품이 도착했어요.")]),
    ("c_exchanging", "교환중", "010-0000-3009", "교환 접수됨 (회수 대기)",
     "교환하고 싶어요 ⇒ 중복 접수하지 않고 진행 상태 안내 / 관리자: 보낼 사이즈 골라 교환 완료 처리",
     [("S-09", 260, "교환 접수", 8, 7, 5, 1, "회수 기사님이 1~2일 안에 방문해요.")]),
    ("c_returning", "반품중", "010-0000-3010", "반품 접수됨 (회수 대기)",
     "반품 어떻게 됐어요? ⇒ 진행 상태 안내 / 관리자: 반품·환불 완료 처리 (재고 +1)",
     [("S-06", 265, "반품 접수", 7, 6, 4, 0, "회수 후 검수되면 환불돼요.")]),
    ("c_waiting", "결재", "010-0000-3011", "사장님 확인 중 (기한 지난 교환 요청)",
     "교환 어떻게 됐어요? ⇒ 확인 중 안내 / 관리자: 넘어온 건 확인 후 교환 승인·반품 승인·거절",
     [("S-03", 265, "사장님 확인 중", 16, 15, 12, 0, WAIT_NOTE)]),
    ("c_returned", "환불", None, "반품 완료 (환불 끝)",
     "로그인 ⇒ 반품 완료 안내 / 새 축구화 찾기로 다시 상담",
     [("S-05", 270, "반품 완료", 25, 24, 22, 0, "검수가 끝나 환불됐어요.")]),
    ("c_cancelled", "취소", None, "주문 취소됨 (출고 전 취소)",
     "언제 와요? ⇒ 진행 중인 배송 없음 / 로그인 첫 화면 ⇒ 주문 취소 안내",
     [("S-10", 255, "주문 취소", 3, None, None, 0, "주문이 취소됐어요. 결제 금액은 환불돼요.")]),
    ("c_many", "단골", "010-0000-3014", "주문 4건: 결제완료 + 배송중 + 교환 접수 + 오래된 배송완료",
     "언제 와요? ⇒ 진행 중인 주문 기준 / 교환하고 싶어요 ⇒ 진행 중인 교환 안내 (가장 급한 주문부터)",
     [("S-07", 270, "결제완료", 0, None, None, 0, None),
      ("S-05", 270, "배송중", 2, 1, None, 0, None),
      ("S-08", 280, "교환 접수", 9, 8, 6, 1, "회수 기사님이 1~2일 안에 방문해요."),
      ("S-10", 270, "배송완료", 40, 39, 37, 0, None)]),
]
GUESTS = [  # 비로그인 고객이 남긴 건: (종류, 고객 문장, 연락처)
    ("health", "평발인데 인조잔디에서 신을 만한 거 있을까요", "010-0000-2001"),
    ("health", "발목 인대 수술하고 복귀하려는데 추천해 주세요", None),
    ("empty", "실내에서 신을 건데 칼발이고 5만원 이하로요", "guest@example.com"),
]
OLD_IDS = ["dohyun", "seojun", "haeun", "minjae", "yuna", "jiho", "sua", "taeyang", "eunwoo", "chaewon", "junseo", "nayeon"]  # 예전 더미 고객
GONE = ("반품 완료", "주문 취소")   # 이미 재고로 돌아온 주문


def lines(*rows):
    return [{"agent": agent, "text": text, "internal": internal} for agent, text, internal in rows]


def clear(store: Store) -> None:
    """연습 계정과 그 주문·넘어온 건을 지운다. 아직 재고에서 빠져 있던 켤레는 되돌린다."""
    ids = [c[0] for c in CASES] + OLD_IDS
    marks = ", ".join("?" * len(ids))
    with store._tx() as db:
        for o in db.execute(f"SELECT code, size, status FROM orders WHERE account_id IN ({marks})", ids).fetchall():
            if o["status"] not in GONE:
                store._put_back(db, o["code"], o["size"])
        db.execute(f"DELETE FROM handoffs WHERE account_id IN ({marks}) OR thread_id LIKE 'sample-%'", ids)
        db.execute(f"DELETE FROM orders WHERE account_id IN ({marks})", ids)
        db.execute(f"DELETE FROM accounts WHERE id IN ({marks})", ids)


def main(path=None, quiet=False):
    demo = Settings().demo   # 데모 계정을 끈 서버(운영 설정)에는 데모 계정을 만들지 않는다
    store = Store(path, demo=demo) if path else Store(demo=demo)
    clear(store)
    password = os.getenv("PITCHROOM_SAMPLE_PASSWORD") or secrets.token_urlsafe(9)

    for user_id, name, contact, _, _, orders in CASES:
        store.create_account(user_id, name, password)
        if contact:
            store.set_contact(user_id, contact)
        for code, size, status, ordered, shipped, delivered, exchanges, note in reversed(orders):   # 뒤에서부터 넣어 앞의 주문이 최신 번호
            with store._tx() as db:   # 연습용 한 켤레가 항상 있도록
                db.execute("UPDATE stock SET qty = 1 WHERE code = ? AND size = ? AND qty = 0", (code, size))
            o = store.add_order(user_id, code, size)
            with store._tx() as db:   # 날짜와 상태만 과거로 돌린다
                db.execute("UPDATE orders SET status = ?, exchanges = ?, note = ?, ordered_at = ?, shipped_at = ?, delivered_at = ? WHERE id = ?",
                           (status, exchanges, note, day_iso(ordered), day_iso(shipped) if shipped is not None else None,
                            day_iso(delivered) if delivered is not None else None, o["id"]))
                if status in GONE:
                    store._put_back(db, code, size)
            if status == "사장님 확인 중":   # 결재를 기다리는 주문에는 넘어온 건이 함께 있어야 한다
                thread = f"sample-{user_id}"
                store.add_handoff(
                    "policy", f"{name}님 · {o['id']} · 교환 요청",
                    {"text": "받은 지 좀 됐는데 사이즈가 작아서 교환하고 싶어요", "source": "연습 데이터", "conditions": [],
                     "reply": "사장님이 확인 중이에요. 원하시는 처리 방법을 말씀해 주시면 그 기준으로 검토해요.",
                     "rules": [f"수령 후 7일 이내 ✗ {delivered}일째", "실외 미착용 (확인 안 됨)", "사이즈 교환 1회 무료 ✓"],
                     "options": ["피팅 상담 후 다른 모델로 교환", "같은 모델 다른 사이즈 (예외 승인 요청)"],
                     "order": order_label({"code": code, "size": size}),
                     "discussion": lines(("정책 에이전트", f"{o['id']} 주문 기록에서 수령 {delivered}일째, 교환 이력 {exchanges}회를 확인했어요.", False),
                                         ("정책 에이전트", "규칙 밖이라 제가 약속할 수 없어요. 사장님 결재로 넘길게요.", False),
                                         ("정책 에이전트", "착용품 재판매 불가 시 손실액 기준 결재 라인(내부).", True))},
                    thread_id=thread, account_id=user_id, order_id=o["id"])
                if contact:
                    store.set_handoff_contact(thread, contact)

    for n, (kind, text, contact) in enumerate(GUESTS):
        health, thread = kind == "health", f"sample-guest-{n}"
        store.add_handoff(
            kind, f"발 건강 언급: “{text[:60]}”" if health else "조건에 맞는 상품이 없어요",
            {"text": text, "source": "연습 데이터", "rules": [], "options": [], "order": None,
             "reply": "발 건강과 관련된 부분은 제가 판단하지 않고 피팅 전문가에게 연결해 드릴게요." if health else "안전하게 권할 수 있는 신발이 없어서 사장님께 넘겼어요.",
             "conditions": [] if health else ["구장 실내", "발볼 좁음", "예산 5만원 이하"],
             "discussion": lines(("접수 에이전트", "발 건강 관련 언급이 있어요. 발 건강은 AI가 판단하지 않아요.", False),
                                 ("피팅 에이전트", "추천을 멈추고 피팅 전문가 상담으로 넘길게요.", False),
                                 ("정책 에이전트", "건강 관련 건은 매니저 배정(내부 SLA).", True)) if health else
                           lines(("피팅 에이전트", f"실내이면 IC만 남길게요. 조건에 맞는 건 {BY_CODE['S-10']['name']}뿐인데 발볼·예산이 안 맞아요.", False),
                                 ("피팅 에이전트", "안전하게 대체할 신발도 없어요. 사람이 판단해야 해요.", False))},
            thread_id=thread)
        if contact:
            store.set_handoff_contact(thread, contact)

    if not quiet:
        print(f"연습 계정 {len(CASES)}개를 처음 상태로 만들었어요. 공통 비밀번호: {password}\n")
        for user_id, _, _, situation, try_it, _ in CASES:
            print(f"  {user_id:<13} {situation}\n  {'':<13} 해 볼 말: {try_it}\n")
        print(f"비로그인 고객이 남긴 건 {len(GUESTS)}개도 관리 화면 '넘어온 건'에 넣었어요.")
    return password


if __name__ == "__main__":
    main()
