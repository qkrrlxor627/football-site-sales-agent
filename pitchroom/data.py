"""매장 데이터와 규칙표 (데모). 규칙표가 추천의 안전선을 정한다."""
# 규칙표는 '전문가 판단을 코드로 옮긴 것'이다. LLM이 아니라 이 표가 추천의 안전선을 정한다.
import math
from datetime import date, timedelta

PRODUCTS = [
    {"code": "S-01", "color": "레드", "line": "Mercurial", "name": "Mercurial Vapor 17 Elite",   "stud": "FG", "width": "좁음", "price": 359000, "feel": "가볍고 발에 딱 붙는 스피드형"},
    {"code": "S-02", "color": "블랙/그린", "line": "Mercurial", "name": "Mercurial Vapor 17 Academy", "stud": "AG", "width": "좁음", "price": 149000, "feel": "인조잔디용 짧은 스터드, 입문 가격대"},
    {"code": "S-03", "color": "핑크/화이트", "line": "Mercurial", "name": "Mercurial Vapor 17 Pro",     "stud": "FG", "width": "좁음", "price": 259000, "feel": "가벼운 로우컷, 스피드형 중급 모델"},
    {"code": "S-04", "color": "블랙/블루", "line": "Phantom",   "name": "Phantom 6 Low Elite",        "stud": "FG", "width": "보통", "price": 349000, "feel": "공을 감는 그립 텍스처, 플레이메이커용"},
    {"code": "S-05", "color": "핑크/화이트", "line": "Phantom",   "name": "Phantom 6 Academy",          "stud": "TF", "width": "보통", "price": 129000, "feel": "풋살·인조 구장용 고무 터프 아웃솔"},
    {"code": "S-06", "color": "레드/블랙", "line": "Phantom",   "name": "Phantom 6 High Elite",       "stud": "FG", "width": "보통", "price": 369000, "feel": "끈 없이 발목까지 감싸는 하이탑"},
    {"code": "S-07", "color": "블랙/그린", "line": "Tiempo",    "name": "Tiempo Maestro Academy",     "stud": "TF", "width": "넓음", "price": 119000, "feel": "여유 있는 발볼, 부드러운 합성 가죽"},
    {"code": "S-08", "color": "핑크", "line": "Tiempo",    "name": "Tiempo Maestro Pro",         "stud": "AG", "width": "넓음", "price": 219000, "feel": "넓은 발볼에 맞춘 가죽 어퍼, 인조잔디용"},
    {"code": "S-09", "color": "핑크", "line": "Tiempo",    "name": "Tiempo Maestro Elite",       "stud": "FG", "width": "넓음", "price": 339000, "feel": "천연 가죽 터치, 수비·빌드업용"},
    {"code": "S-10", "color": "핑크/화이트", "line": "Mercurial", "name": "Mercurial Vapor 17 Club",    "stud": "IC", "width": "보통", "price": 89000,  "feel": "체육관 바닥용 평평한 고무창"},
    # S-11~S-30: 나이키 미국 공식몰에서 2026-10-13에 확인한 상품. 가격은 1달러 = 1,400원으로 바꿔 천 원 단위로 맞췄다.
    # list_price가 있으면 할인 중(정가 → price). 발볼은 라인 기준(Mercurial 좁음, Phantom 보통, Tiempo 넓음)으로 넣은 값이다.
    # S-15(Tiempo Maestro Academy TF 블랙/그린)는 S-07과 같은 신발이라 넣지 않았다.
    {"code": "S-11", "line": "Mercurial", "name": "Mercurial Vapor 17 Academy", "stud": "TF", "width": "좁음", "price": 133000, "color": "블랙/그린", "sku": "IO5002-001", "feel": "짧은 고무 돌기, 가볍고 낮은 스피드형"},
    {"code": "S-12", "line": "Mercurial", "name": "Mercurial Superfly 11 Academy", "stud": "TF", "width": "좁음", "price": 140000, "color": "블랙/그린", "sku": "IO1494-001", "feel": "발목을 감싸는 하이탑, 터프 구장용 스피드형"},
    {"code": "S-13", "line": "Phantom", "name": "Phantom 6 Low Academy", "stud": "TF", "width": "보통", "price": 133000, "color": "화이트/틸", "sku": "HQ2325-100", "feel": "터프 구장용, 볼 컨트롤에 맞춘 입문 모델"},
    {"code": "S-14", "line": "Phantom", "name": "Phantom 6 Low Pro", "stud": "TF", "width": "보통", "price": 146000, "color": "블루/핑크", "sku": "HJ4123-446", "feel": "그립 텍스처 어퍼, 터프 구장용 중급 모델", "list_price": 224000},
    {"code": "S-16", "line": "Tiempo", "name": "Tiempo Ligera Pro", "stud": "TF", "width": "넓음", "price": 196000, "color": "화이트/블루", "sku": "IB4477-100", "feel": "부드러운 가죽 느낌의 클래식 터프화"},
    {"code": "S-17", "line": "Mercurial", "name": "Mercurial Vapor 17 Academy", "stud": "TF", "width": "좁음", "price": 94000, "color": "레드", "sku": "IO5002-600", "feel": "짧은 고무 돌기, 가벼운 스피드형 입문 모델", "list_price": 133000},
    {"code": "S-18", "line": "Mercurial", "name": "Mercurial Superfly 11 Academy", "stud": "TF", "width": "좁음", "price": 99000, "color": "화이트/골드", "sku": "IO1494-100", "feel": "발목을 감싸는 하이탑, 터프 구장용", "list_price": 140000},
    {"code": "S-19", "line": "Phantom", "name": "Phantom 6 Low Club", "stud": "MG", "width": "보통", "price": 63000, "color": "블랙/블루", "sku": "HM8933-003", "feel": "천연·인조 겸용 스터드, 가장 부담 없는 가격", "list_price": 98000},
    {"code": "S-20", "line": "Tiempo", "name": "Tiempo Maestro Club", "stud": "TF", "width": "넓음", "price": 91000, "color": "블랙/그린", "sku": "IB4482-001", "feel": "여유 있는 발볼의 입문 터프화"},
    {"code": "S-21", "line": "Mercurial", "name": "Mercurial Superfly 11 Elite", "stud": "AG", "width": "좁음", "price": 413000, "color": "블랙/그린", "sku": "IM2513-001", "feel": "인조잔디 전용 최상급, 가장 가벼운 스피드형"},
    {"code": "S-22", "line": "Phantom", "name": "Phantom 6 Low Academy", "stud": "AG", "width": "보통", "price": 94000, "color": "레드/블랙", "sku": "HQ2322-600", "feel": "인조잔디용 짧은 스터드, 컨트롤형 입문 모델", "list_price": 133000},
    {"code": "S-23", "line": "Phantom", "name": "Phantom 6 Low Elite", "stud": "AG", "width": "보통", "price": 364000, "color": "레드/네이비", "sku": "HQ2335-600", "feel": "인조잔디 전용 최상급, 그립 텍스처 어퍼"},
    {"code": "S-24", "line": "Tiempo", "name": "Tiempo Maestro Academy", "stud": "AG", "width": "넓음", "price": 90000, "color": "화이트/레드", "sku": "IB4479-100", "feel": "넓은 발볼, 인조잔디용 입문 모델", "list_price": 126000},
    {"code": "S-25", "line": "Mercurial", "name": "Mercurial Superfly 11 Elite", "stud": "FG", "width": "좁음", "price": 413000, "color": "화이트/틸", "sku": "IF8507-100", "feel": "천연잔디 최상급, 발에 딱 붙는 하이탑 스피드형"},
    {"code": "S-26", "line": "Phantom", "name": "Phantom 6 Low Club", "stud": "MG", "width": "보통", "price": 98000, "color": "블랙/그린", "sku": "HM8933-001", "feel": "천연·인조 겸용 스터드, 컨트롤형 입문 모델"},
    {"code": "S-27", "line": "Tiempo", "name": "Tiempo Maestro Club", "stud": "MG", "width": "넓음", "price": 64000, "color": "화이트/레드", "sku": "IB1602-100", "feel": "천연·인조 겸용 스터드, 넓은 발볼 입문 모델", "list_price": 91000},
    {"code": "S-28", "line": "Phantom", "name": "Phantom 6 Low Academy", "stud": "IC", "width": "보통", "price": 94000, "color": "레드/블랙", "sku": "HQ2319-600", "feel": "실내 체육관용 평평한 창, 컨트롤형", "list_price": 133000},
    {"code": "S-29", "line": "Tiempo", "name": "Tiempo Reactgato", "stud": "IC", "width": "넓음", "price": 129000, "color": "화이트/블루", "sku": "HQ3159-100", "feel": "실내 풋살용, 쿠션 좋은 가죽 느낌 어퍼", "list_price": 182000},
    {"code": "S-30", "line": "Mercurial", "name": "Mercurial Vapor 17 Academy", "stud": "IC", "width": "좁음", "price": 133000, "color": "블랙/그린", "sku": "IM5845-001", "feel": "실내 체육관용 평평한 창, 스피드형"},
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
    "S-11": [4, 2, 4, 0, 4, 5, 1, 2, 0],
    "S-12": [3, 3, 5, 1, 0, 3, 0, 4, 1],
    "S-13": [0, 0, 1, 4, 4, 3, 5, 2, 4],
    "S-14": [0, 3, 0, 1, 4, 5, 2, 3, 4],
    "S-16": [0, 1, 2, 0, 2, 1, 1, 0, 1],
    "S-17": [2, 2, 4, 0, 1, 1, 5, 2, 0],
    "S-18": [0, 3, 5, 4, 2, 1, 4, 5, 1],
    "S-19": [3, 5, 2, 4, 3, 5, 2, 4, 2],
    "S-20": [0, 0, 5, 0, 3, 3, 2, 3, 2],
    "S-21": [2, 1, 0, 0, 0, 2, 1, 1, 0],
    "S-22": [1, 3, 2, 3, 5, 4, 2, 4, 3],
    "S-23": [1, 1, 1, 1, 1, 2, 0, 0, 1],
    "S-24": [4, 2, 0, 5, 1, 0, 2, 4, 0],
    "S-25": [2, 2, 1, 1, 2, 0, 1, 0, 0],
    "S-26": [4, 3, 4, 2, 2, 3, 4, 1, 1],
    "S-27": [3, 4, 0, 5, 2, 0, 1, 3, 4],
    "S-28": [3, 0, 1, 3, 0, 3, 1, 2, 2],
    "S-29": [4, 0, 2, 2, 0, 3, 3, 5, 0],
    "S-30": [2, 3, 3, 4, 5, 1, 0, 1, 2],
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
# MG(멀티그라운드)는 제조사가 천연·인조잔디 겸용으로 만든 스터드라 두 구장 모두에 허용한다.
SURFACE_TO_STUD = {
    "천연잔디": ["FG", "SG", "MG"],
    "인조잔디": ["AG", "TF", "MG"],
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


