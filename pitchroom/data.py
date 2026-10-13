"""매장 데이터와 규칙표 (데모). 규칙표가 추천의 안전선을 정한다."""
# 규칙표는 '전문가 판단을 코드로 옮긴 것'이다. LLM이 아니라 이 표가 추천의 안전선을 정한다.
import math
from datetime import date, timedelta

PRODUCTS = [
    {"code": "S-01", "line": "Mercurial", "name": "Mercurial Vapor 17 Elite",   "stud": "FG", "width": "좁음", "price": 359000, "feel": "가볍고 발에 딱 붙는 스피드형"},
    {"code": "S-02", "line": "Mercurial", "name": "Mercurial Vapor 17 Academy", "stud": "AG", "width": "좁음", "price": 149000, "feel": "인조잔디용 짧은 스터드, 입문 가격대"},
    {"code": "S-03", "line": "Mercurial", "name": "Mercurial Vapor 17 Pro",     "stud": "FG", "width": "좁음", "price": 259000, "feel": "가벼운 로우컷, 스피드형 중급 모델"},
    {"code": "S-04", "line": "Phantom",   "name": "Phantom 6 Low Elite",        "stud": "FG", "width": "보통", "price": 349000, "feel": "공을 감는 그립 텍스처, 플레이메이커용"},
    {"code": "S-05", "line": "Phantom",   "name": "Phantom 6 Academy",          "stud": "TF", "width": "보통", "price": 129000, "feel": "풋살·인조 구장용 고무 터프 아웃솔"},
    {"code": "S-06", "line": "Phantom",   "name": "Phantom 6 High Elite",       "stud": "FG", "width": "보통", "price": 369000, "feel": "끈 없이 발목까지 감싸는 하이탑"},
    {"code": "S-07", "line": "Tiempo",    "name": "Tiempo Maestro Academy",     "stud": "TF", "width": "넓음", "price": 119000, "feel": "여유 있는 발볼, 부드러운 합성 가죽"},
    {"code": "S-08", "line": "Tiempo",    "name": "Tiempo Maestro Pro",         "stud": "AG", "width": "넓음", "price": 219000, "feel": "넓은 발볼에 맞춘 가죽 어퍼, 인조잔디용"},
    {"code": "S-09", "line": "Tiempo",    "name": "Tiempo Maestro Elite",       "stud": "FG", "width": "넓음", "price": 339000, "feel": "천연 가죽 터치, 수비·빌드업용"},
    {"code": "S-10", "line": "Mercurial", "name": "Mercurial Vapor 17 Club",    "stud": "IC", "width": "보통", "price": 89000,  "feel": "체육관 바닥용 평평한 고무창"},
]
BY_CODE = {p["code"]: p for p in PRODUCTS}
BASE_PRODUCTS = [dict(p) for p in PRODUCTS]   # 코드에 적힌 원래 값 (가격·판매 여부는 DB가 덮어쓴다)

# 사이즈별 재고 시드 (데모 스냅샷). 0이면 품절. 실제 수량은 DB에 있고 관리 화면에서 바꾼다.
STOCK_SIZES = [250, 255, 260, 265, 270, 275, 280, 285, 290]
STOCK_SEED = {
    "S-01": [1, 2, 3, 2, 0, 1, 1, 0, 0],
    "S-02": [2, 3, 4, 5, 3, 0, 2, 1, 0],
    "S-03": [0, 1, 2, 2, 1, 1, 0, 0, 0],
    "S-04": [1, 1, 2, 3, 3, 2, 1, 1, 0],
    "S-05": [3, 4, 5, 4, 4, 3, 2, 2, 1],
    "S-06": [1, 2, 2, 0, 2, 2, 1, 0, 0],
    "S-07": [2, 3, 3, 4, 5, 4, 3, 2, 1],
    "S-08": [1, 1, 2, 2, 3, 0, 2, 1, 1],
    "S-09": [0, 1, 1, 2, 2, 1, 1, 0, 0],
    "S-10": [4, 5, 6, 6, 5, 4, 3, 2, 1],
}


def apply_catalog(overrides: dict):
    """DB의 가격·판매 여부를 규칙이 보는 상품 목록에 반영한다. {code: {"price": int, "active": bool}}

    PRODUCTS와 BY_CODE를 '제자리에서' 고친다: 다른 모듈이 이미 들고 있는 같은 목록이 함께 바뀐다.
    숨긴 상품은 PRODUCTS에서 빠져 추천되지 않지만, BY_CODE에는 남아 지난 주문의 이름을 계속 보여준다.
    """
    active = []
    for base in BASE_PRODUCTS:
        o = overrides.get(base["code"], {})
        BY_CODE[base["code"]].update({**base, "price": o.get("price", base["price"])})
        if o.get("active", True):
            active.append(BY_CODE[base["code"]])
    PRODUCTS[:] = active


def reset_catalog():
    apply_catalog({})
LINES = ["Mercurial", "Phantom", "Tiempo"]
CARRIED_BRANDS = ["나이키"]
# 가정: 모든 상품이 전 사이즈 재고 있음 → 사이즈는 묻지도 거르지도 않고, 말하면 기록만 한다.

# 구장 → 그대로 허용되는 스터드
SURFACE_TO_STUD = {
    "천연잔디": ["FG", "SG"],
    "인조잔디": ["AG", "TF"],
    "흙운동장": ["HG", "TF"],
    "풋살장":   ["TF", "IC"],
    "실내":     ["IC"],
}
# 구장 → '안전하게' 대체 가능한 스터드와 양보 점수. 여기 없는 조합(예: 인조잔디에 FG)은 후보에서 아예 제외.
SUBSTITUTE = {
    "천연잔디": {"HG": 0.5, "AG": 0.6, "TF": 0.9},
    "인조잔디": {"HG": 0.7},
    "흙운동장": {"AG": 0.6},
    "풋살장":   {"AG": 0.8},
    "실내":     {"TF": 0.8},
}
SUB_NOTE = {
    "천연잔디": {"HG": "맨땅용 HG, 단단한 잔디에서도 사용 가능", "AG": "인조잔디용 AG, 마른 천연잔디에서 사용 가능", "TF": "터프화 TF, 잔디에선 접지가 약함"},
    "인조잔디": {"HG": "맨땅용 HG, 인조잔디에서도 사용 가능"},
    "흙운동장": {"AG": "인조잔디용 AG, 흙에선 스터드가 빨리 닳음"},
    "풋살장":   {"AG": "인조잔디용 AG, 풋살장에선 스터드가 길게 느껴질 수 있음"},
    "실내":     {"TF": "터프화 TF, 실내 바닥에선 접지 확인 필요"},
}
RED_FLAGS = ["통증", "아프", "아파", "부상", "수술", "평발", "무지외반", "족저근막", "인대", "골절"]
SLOT_ORDER = ["surface", "width", "budget"]
SLOT_LABEL = {"surface": "구장", "width": "발볼", "budget": "예산"}
ASK_TEXT = {
    "surface": "어떤 구장에서 주로 뛰세요? 천연잔디, 인조잔디, 흙운동장, 풋살장, 실내 중에 알려 주세요.",
    "width": "발볼은 어떤 편이에요? 좁은 편, 보통, 넓은 편 중에 알려 주세요.",
    "budget": "예산은 어느 정도 생각하세요? 상관없으면 상관없다고 해 주세요.",
}
MAX_ASK = 2  # 같은 칸을 두 번 물어도 비면 그 조건 없이 진행 (무한 되묻기 방지)
POLICY = {"return_days": 7, "free_exchange": 1, "ship_cutoff": "평일 14시", "return_fee": 6000}
IN_SERVICE = ["교환 접수", "반품 접수", "사장님 확인 중"]
FORBIDDEN_WORDS = ["매입", "마진", "원가", "결재 기준"]  # 고객 답변에 나오면 안 되는 내부 정보

# 선수 → 라인 고정표. 여기 있는 선수는 이 표가 우선이고, 없는 선수만 검색(Tavily)으로 찾는다. 선수 장비는 바뀌므로 주기적으로 갱신한다.
PLAYER_TABLE = {
    "호날두": ("Nike Mercurial", "Mercurial"),
    "메시": ("adidas F50", "Mercurial"),
    "음바페": ("Nike Mercurial", "Mercurial"),
    "홀란드": ("Nike Phantom", "Phantom"),
}


def won(n):
    return "상관없음" if n == math.inf else f"{n:,}원"


def day_iso(offset):
    return (date.today() - timedelta(days=offset)).isoformat()


def days_since(iso):
    return max(0, (date.today() - date.fromisoformat(iso)).days)


# 데모 계정 (더미 데이터). 날짜는 실행일 기준 상대값이라 언제 돌려도 같은 상황이 재현된다.
DEMO_ACCOUNTS = {
    "minsu":   {"name": "민수", "orders": [{"id": "PR-0001", "code": "S-05", "size": 265, "status": "결제완료", "ordered": 0, "exchanges": 0}]},
    "jiwoo":   {"name": "지우", "orders": [{"id": "PR-0002", "code": "S-08", "size": 270, "status": "배송완료", "ordered": 5, "shipped": 4, "delivered": 3, "exchanges": 0}]},
    "hyun":    {"name": "현",   "orders": [{"id": "PR-0003", "code": "S-01", "size": 275, "status": "배송완료", "ordered": 14, "shipped": 13, "delivered": 10, "exchanges": 1}]},
    "seoyeon": {"name": "서연", "orders": [
        {"id": "PR-0005", "code": "S-10", "size": 250, "status": "배송중", "ordered": 1, "shipped": 0, "exchanges": 0},
        {"id": "PR-0004", "code": "S-09", "size": 250, "status": "교환 접수", "ordered": 8, "shipped": 7, "delivered": 6, "exchanges": 1, "note": "255mm로 교환, 회수 기사님 방문 예정이에요."},
    ]},
}


def make_account(user_id):
    a = DEMO_ACCOUNTS.get(user_id)
    if not a:
        return None
    orders = []
    for o in a["orders"]:
        orders.append({
            "id": o["id"], "code": o["code"], "size": o["size"], "status": o["status"],
            "exchanges": o["exchanges"], "note": o.get("note"),
            "ordered_at": day_iso(o["ordered"]),
            "shipped_at": day_iso(o["shipped"]) if "shipped" in o else None,
            "delivered_at": day_iso(o["delivered"]) if "delivered" in o else None,
        })
    return {"id": user_id, "name": a["name"], "orders": orders}


def order_label(o):
    p = BY_CODE[o["code"]]
    return f'{p["name"]} {p["stud"]} {o["size"]}mm'


