"""Gradio 화면: HTML 데모와 같은 구성. 판단은 graph가 하고, 여기서는 그리기만 한다."""
# 화면은 그래프 결과(to_client JSON + State)를 HTML로 그리기만 한다. 판단은 전부 위의 LangGraph가 한다.
import html as _html
import math
import uuid
from datetime import date

import gradio as gr

from .data import *  # noqa: F401,F403
from .graph import graph, service_greeting, to_client
from .photos import PHOTOS

CSS = """
#pr-wrap { max-width: 1040px; margin: 0 auto; }
.pr-brand { display: flex; align-items: center; gap: 10px; padding: 6px 2px; }
.pr-brand b { font-weight: 800; letter-spacing: .14em; font-size: 15px; color: #1d1d1f; }
.pr-brand span { font-size: 12px; color: #6b6d75; border: 1px solid #e2e4ea; border-radius: 999px; padding: 2px 9px; }
.pr-who { text-align: right; font-size: 13px; color: #1d1d1f; padding: 8px 2px; }
.pr-stage { position: relative; border-radius: 28px; overflow: hidden; background: #fbfbfd; border: 1px solid #eceef2; font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif; color: #1d1d1f; }
.pr-pitch { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.pr-pitch * { stroke: #d7dbe3; fill: none; stroke-width: 1.5; }
.pr-shelfwrap { position: relative; padding: 26px 20px 22px; }
.pr-count { font-weight: 700; font-size: 13px; color: #6b6d75; margin-bottom: 12px; }
.pr-count b { color: #1d1d1f; font-size: 15px; }
.pr-shelf { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; transition: filter .6s, opacity .6s; }
.pr-shelf.paused { filter: grayscale(1) blur(2px) !important; opacity: .45 !important; }
.pr-card { position: relative; background: #f1f2f5; border-radius: 22px; padding: 16px 16px 18px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.pr-card.best { box-shadow: 0 0 0 2px #1a73e8, 0 8px 28px rgba(20,24,40,.08); }
.pr-label { position: absolute; top: 12px; left: 14px; font-size: 11.5px; font-weight: 700; color: #1a73e8; }
.pr-label.quiet { color: #6b6d75; }
.pr-shoe { aspect-ratio: 24 / 13; width: 100%; margin: 8px 0 4px; }
.pr-shoe img { width: 100%; height: 100%; object-fit: contain; mix-blend-mode: multiply; }
.pr-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 11.5px; color: #6b6d75; }
.pr-stud { font-weight: 800; letter-spacing: .06em; padding: 2px 8px; border-radius: 6px; background: #fff; color: #1d1d1f; }
.pr-name { font-weight: 700; font-size: 16px; line-height: 1.3; }
.pr-price { font-weight: 700; font-size: 15px; }
.pr-why { font-size: 12.5px; color: #6b6d75; line-height: 1.45; }
.pr-trade { display: flex; flex-direction: column; gap: 4px; }
.pr-trade span { font-size: 12.5px; padding: 4px 8px; border-radius: 8px; background: #fbefd2; color: #1d1d1f; }
.pr-empty { border: 1.5px dashed #e2e4ea; border-radius: 22px; display: flex; align-items: center; justify-content: center; min-height: 220px; color: #6b6d75; font-size: 13px; text-align: center; }
.pr-ask { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; padding: 22px 16px 26px; position: relative; }
.pr-stage.collect .pr-ask { position: absolute; inset: 0; justify-content: center; background: radial-gradient(ellipse at center, rgba(251,251,253,.86) 35%, rgba(251,251,253,0) 80%); }
.pr-echo { font-size: 13px; color: #6b6d75; margin: 0; }
.pr-q { margin: 0; font-weight: 700; letter-spacing: -.02em; line-height: 1.3; max-width: 760px; font-size: 30px; color: #1d1d1f; }
.pr-q.long { font-size: 21px; font-weight: 600; }
.pr-slots { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 16px; font-size: 13px; color: #6b6d75; }
.pr-slots span { display: inline-flex; align-items: center; gap: 6px; }
.pr-slots i { width: 7px; height: 7px; border-radius: 50%; background: #e2e4ea; display: inline-block; }
.pr-slots b { color: #1d1d1f; font-weight: 600; }
.pr-slots .s-surface i { background: #1a73e8; } .pr-slots .s-width i { background: #d93025; }
.pr-slots .s-budget i { background: #188038; } .pr-slots .s-size i { background: #e8a100; } .pr-slots .s-style i { background: #1d1d1f; }
.pr-disc { width: min(600px, 100%); text-align: left; font-size: 13px; }
.pr-disc summary { cursor: pointer; color: #6b6d75; text-align: center; list-style: none; }
.pr-disc ul { list-style: none; margin: 10px 0 0; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; background: #fff; border: 1px solid #e2e4ea; border-radius: 14px; }
.pr-disc li { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: baseline; color: #1d1d1f; }
.pr-agent { font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 6px; white-space: nowrap; background: #f1f2f5; color: #6b6d75; }
.a-접수 { color: #1a73e8; background: #e8f0fd; } .a-피팅 { color: #188038; background: #e6f4ea; }
.a-정책 { color: #d93025; background: #fce8e6; } .a-재고, .a-검색 { color: #b06000; background: #fdf3d6; }
.pr-lock { color: #6b6d75; }
.pr-news { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 6px; }
.pr-slide { flex: 1 0 210px; min-height: 260px; border-radius: 22px; padding: 18px; display: flex; flex-direction: column; gap: 10px; background: #fff; border: 1px solid #e2e4ea; min-width: 0; text-align: left; }
.pr-slide .st { display: flex; justify-content: space-between; font-weight: 800; font-size: 12px; letter-spacing: .08em; }
.pr-slide .st em { font-style: normal; color: #6b6d75; }
.pr-slide h3 { margin: 0; font-size: 18px; line-height: 1.35; color: #1d1d1f; }
.pr-slide ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 13.5px; color: #1d1d1f; }
.pr-slide p { margin: 0; font-size: 13.5px; color: #1d1d1f; }
.pr-slide .ag { display: block; font-size: 11.5px; font-weight: 700; color: #6b6d75; }
.pr-slide.s1 { background: #eef4fe; } .pr-slide.s1 .st { color: #1a73e8; } .pr-slide.s2 .st { color: #188038; }
.pr-slide.s3 .st { color: #d93025; } .pr-slide.s4 .st { color: #b06000; }
.pr-verdict { align-self: flex-start; font-size: 12.5px; font-weight: 700; padding: 4px 10px; border-radius: 999px; color: #188038; background: #e6f4ea; }
.pr-verdict.hold { color: #b06000; background: #fdf3d6; }
.pr-hand { width: min(600px, 100%); text-align: left; border: 1px solid #e2e4ea; background: #fff; border-radius: 18px; padding: 14px 18px; font-size: 13.5px; color: #1d1d1f; }
.pr-hand b { font-size: 15px; }
.pr-steps { display: flex; gap: 4px; flex-wrap: wrap; }
.pr-steps span { font-size: 11.5px; padding: 2px 8px; border-radius: 999px; color: #6b6d75; background: #fff; }
.pr-steps span.done { color: #1d1d1f; } .pr-steps span.now { color: #fff; background: #1d1d1f; font-weight: 700; }
.pr-steps span.svc { color: #d93025; background: #fce8e6; font-weight: 700; }
@media (max-width: 760px) {
  .pr-shelf { grid-template-columns: none; grid-auto-flow: column; grid-auto-columns: 78%; overflow-x: auto; }
  .pr-stage.collect .pr-ask { position: relative; background: none; }
  .pr-q { font-size: 22px; }
}
"""

PITCH_SVG = ('<svg class="pr-pitch" viewBox="0 0 1000 420" preserveAspectRatio="none" aria-hidden="true">'
             '<rect x="6" y="6" width="988" height="408" rx="26"/><line x1="500" y1="6" x2="500" y2="414"/>'
             '<circle cx="500" cy="210" r="78"/><rect x="6" y="110" width="120" height="200"/><rect x="874" y="110" width="120" height="200"/></svg>')
STEP = ["결제완료", "배송중", "배송완료"]


def esc(x):
    return _html.escape(str(x))


def photo(code):
    src = PHOTOS.get(code)
    return f'<img src="{src}" alt="{esc(BY_CODE[code]["name"])}">' if src else ""


def product_card(code, profile, label=None, trade=None, quiet_label=False):
    p = BY_CODE[code]
    if trade:
        body = '<div class="pr-trade">' + "".join(f"<span>{esc(t)}</span>" for t in trade) + "</div>"
    else:
        bits = []
        if profile.get("surface"):
            bits.append(f'{profile["surface"]} → {p["stud"]}')
        if profile.get("width"):
            bits.append(f'발볼 {p["width"]}')
        if profile.get("budget") not in (None, math.inf):
            bits.append(f'예산 안 {p["price"]:,}원')
        if profile.get("style") and p["line"] == profile["style"]["line"]:
            bits.append(f'{p["line"]} 선호')
        body = f'<div class="pr-why">{esc(" · ".join(bits) or p["feel"])}</div>'
    lab = f'<span class="pr-label{" quiet" if quiet_label else ""}">{esc(label)}</span>' if label else ""
    return (f'<article class="pr-card{" best" if label and not quiet_label else ""}">{lab}<div class="pr-shoe">{photo(code)}</div>'
            f'<div class="pr-meta"><span class="pr-stud">{p["stud"]}</span><span>{code}</span></div>'
            f'<div class="pr-name">{esc(p["name"])}</div><div class="pr-price">{p["price"]:,}원</div>{body}</article>')


def order_card(o, primary):
    p = BY_CODE[o["code"]]
    svc = o["status"] not in STEP
    idx = 3 if svc else STEP.index(o["status"])
    steps = "".join(f'<span class="{"done" if i < idx else "now" if i == idx else ""}">{s}</span>' for i, s in enumerate(STEP))
    if svc:
        steps += f'<span class="svc">{esc(o["status"])}</span>'
    when = f'배송 완료 {o["delivered_at"]}' if o["delivered_at"] else f'출고 {o["shipped_at"]}' if o["shipped_at"] else f'주문 {o["ordered_at"]}'
    lab = '<span class="pr-label">지금 볼 주문</span>' if primary else ""
    note = f'<br>{esc(o["note"])}' if o.get("note") else ""
    exch = f' · 교환 {o["exchanges"]}회' if o["exchanges"] else ""
    return (f'<article class="pr-card{" best" if primary else ""}">{lab}<div class="pr-shoe">{photo(o["code"])}</div>'
            f'<div class="pr-meta"><span class="pr-stud">{p["stud"]}</span><span>{o["id"]} · {o["size"]}mm</span></div>'
            f'<div class="pr-name">{esc(p["name"])}</div><div class="pr-steps">{steps}</div>'
            f'<div class="pr-why">{when}{exch}{note}</div></article>')


def slots_html(profile, skipped):
    cells = []
    for k in SLOT_ORDER:
        v = profile.get(k)
        text = ("건너뜀" if k in (skipped or []) else "—") if v is None else (won(v) if k == "budget" and v == math.inf else f"{v // 10000}만원 이하" if k == "budget" else v)
        cells.append(f'<span class="{"s-" + k if v is not None else ""}"><i></i>{SLOT_LABEL[k]} <b>{esc(text)}</b></span>')
    if profile.get("size"):
        cells.append(f'<span class="s-size"><i></i>사이즈 <b>{profile["size"]}mm</b></span>')
    if profile.get("style"):
        cells.append(f'<span class="s-style"><i></i>취향 <b>{esc(profile["style"]["line"])}</b></span>')
    return '<div class="pr-slots">' + "".join(cells) + "</div>"


def disc_html(c):
    if not c["discussion"] and not c["hidden"]:
        return ""
    items = "".join(f'<li><span class="pr-agent a-{esc(m["agent"].split()[0])}">{esc(m["agent"].replace(" 에이전트", ""))}</span><span>{esc(m["text"])}</span></li>' for m in c["discussion"])
    if c["hidden"]:
        items += f'<li class="pr-lock">🔒 <span>내부 논의 {c["hidden"]}건은 공개하지 않아요 (매입가·결재 기준 등)</span></li>'
    hidden = f' · 비공개 {c["hidden"]}건' if c["hidden"] else ""
    return f'<details class="pr-disc"><summary>에이전트 논의 보기 · 공개 {len(c["discussion"])}건{hidden}</summary><ul>{items}</ul></details>'


def news_html(c):
    k = c["cs_card"]
    disc = "".join(f'<li><span class="ag">{esc(m["agent"])}</span>{esc(m["text"])}</li>' for m in c["discussion"])
    lock = f'<li class="pr-lock">🔒 내부 논의 {c["hidden"]}건 비공개</li>' if c["hidden"] else ""
    opts = ('<ul>' + "".join(f"<li>· {esc(o)}</li>" for o in k["options"]) + "</ul>") if k.get("options") else ""
    hold = " hold" if k["verdict"] in ("사장님 확인",) else ""
    return ('<div class="pr-news">'
            f'<section class="pr-slide s1"><div class="st">문의 <em>1/4</em></div><h3>{esc(k["summary"])}</h3></section>'
            f'<section class="pr-slide s2"><div class="st">에이전트 논의 <em>2/4</em></div><ul>{disc}{lock}</ul></section>'
            f'<section class="pr-slide s3"><div class="st">적용 규칙 <em>3/4</em></div><ul>{"".join(f"<li>{esc(r)}</li>" for r in k["rules"])}</ul></section>'
            f'<section class="pr-slide s4"><div class="st">결론 <em>4/4</em></div><span class="pr-verdict{hold}">{esc(k["verdict"])}</span><p>{esc(k["next"])}</p>{opts}</section>'
            "</div>")


def stage(shelf_inner, count, q, collect=False, blur=0.0, paused=False, echo="", slots="", extra="", disc=""):
    dim, sat = 0.42 + (1 - blur / 12) * 0.58, 0.7 + (1 - blur / 12) * 0.3
    style = f'filter: blur({blur:.1f}px) saturate({sat:.2f}); opacity: {dim:.2f};'
    is_news = shelf_inner.startswith('<div class="pr-news">')
    shelf = shelf_inner if is_news else f'<div class="pr-shelf{" paused" if paused else ""}" style="{style}">{shelf_inner}</div>'
    echo_html = f'<p class="pr-echo">“{esc(echo)}”</p>' if echo else ""
    return (f'<div class="pr-stage{" collect" if collect else ""}">{PITCH_SVG}'
            f'<div class="pr-shelfwrap"><div class="pr-count">{count}</div>{shelf}</div>'
            f'<div class="pr-ask">{echo_html}'
            f'<h2 class="pr-q{" long" if len(q) > 40 else ""}">{esc(q)}</h2>{slots}{extra}{disc}</div></div>')


def shop_home():
    cards = "".join(product_card(c, {}) for c in ["S-04", "S-08", "S-02"])
    return stage(cards, f"전체 {len(PRODUCTS)}종", "어떤 구장에서 뛰세요?", collect=True, blur=12,
                 slots=slots_html({}, []), extra='<p class="pr-echo">답할수록 뒤에 있는 축구화 3켤레가 선명해져요.</p>')


def service_home(acc, headline=None):
    pri = lambda o: 0 if o["status"] in IN_SERVICE else 1 if o["status"] == "배송중" else 2 if o["status"] == "결제완료" else 3
    os_ = sorted(acc["orders"], key=lambda o: (pri(o), -date.fromisoformat(o["ordered_at"]).toordinal()))  # 급한 상태 → 최근 주문 순
    cards = "".join(order_card(o, i == 0) for i, o in enumerate(os_[:3]))
    q = headline or service_greeting(acc).replace("🧾 ", "")
    return stage(cards, f'{esc(acc["name"])}님 주문 <b>{len(acc["orders"])}건</b>', q,
                 extra='<p class="pr-echo">교환, 반품, 배송… 무엇이든 아래에 말씀해 주세요. 새 축구화를 찾으면 그렇게 말해도 돼요.</p>')


def result_stage(s, c, text):
    p, route = s["profile"], c["route"]
    if c["cs_card"]:
        return stage(news_html(c), "고객 문의 처리 과정", c["reply"], echo=text)
    filled = sum(p.get(k) is not None or k in (s.get("skipped") or []) for k in SLOT_ORDER)
    done = route in ("recommend", "alternative")
    blur = 0 if done else 12 * (1 - filled / len(SLOT_ORDER))
    cards = ""
    for i, x in enumerate(c["candidates"]):
        if route == "alternative":
            label, quiet = ("가장 가까운 1켤레" if i == 0 else None), False
        elif route == "recommend":
            label, quiet = (("먼저 신어볼 1켤레", False) if i == 0 else (("대안", True) if x["trade"] else (None, False)))
        else:
            label, quiet = None, False
        cards += product_card(x["code"], p, label, x["trade"], quiet)
    for _ in range(3 - len(c["candidates"])):
        cards += '<div class="pr-empty">조건을 통과한 신발은 여기까지예요</div>'
    count = ("조건을 전부 맞추는 신발 0종 → <b>가장 가까운 3켤레</b>" if route == "alternative"
             else f'전체 {len(PRODUCTS)}종 → <b>{s.get("pool", len(PRODUCTS))}종</b> 남음')
    extra = ""
    if route == "escalate":
        health = c["reason"] == "health"
        alts = ["피팅 전문가 상담 예약", "매장 방문 시착"] if health else (s.get("alts") or ["조건을 바꿔서 다시 찾기"])
        extra = (f'<div class="pr-hand"><b>{"피팅 전문가에게 넘겼어요" if health else "사장님께 대안과 함께 넘겼어요"}</b><br>'
                 + "<br>".join(f"· {esc(a)}" for a in alts) + "</div>")
    return stage(cards, count, c["reply"], collect=not (done or route == "escalate"), blur=blur,
                 paused=(route == "escalate" and c["reason"] == "health"), echo=text,
                 slots=slots_html(p, s.get("skipped")), extra=extra, disc=disc_html(c))


# ---------- 세션 (Gradio 사용자 1명 = LangGraph thread 1개) ----------
def _cfg(sess):
    return {"configurable": {"thread_id": sess["thread"]}}


def _new_session(user_id=None):
    sess = {"thread": str(uuid.uuid4())}
    if user_id:
        graph.update_state(_cfg(sess), {"account": make_account(user_id)}, as_node="respond")
    return sess


def _account(sess):
    snap = graph.get_state(_cfg(sess))
    return (snap.values or {}).get("account")


def _who(acc):
    return f'<div class="pr-who">{esc(acc["name"])}님 · 주문 {len(acc["orders"])}건</div>' if acc else '<div class="pr-who">로그인 전</div>'


def _orders_html(acc):
    if not acc:
        return ""
    return '<div class="pr-stage" style="padding:16px"><div class="pr-shelf">' + "".join(order_card(o, False) for o in acc["orders"]) + "</div></div>"


def _buy_update(s, c):
    if c and c["route"] in ("recommend", "alternative") and c["candidates"]:
        choices = [(f'{x["name"]} · {x["price"]:,}원', x["code"]) for x in c["candidates"]]
        size = str((s.get("profile") or {}).get("size") or 270)
        return gr.update(visible=True), gr.update(choices=choices, value=choices[0][1]), gr.update(value=size)
    return gr.update(visible=False), gr.update(), gr.update()


def ui_start():
    sess = _new_session()
    return sess, shop_home(), _who(None), "", gr.update(visible=False), *_buy_update({}, None)


def ui_send(text, sess):
    sess = sess or _new_session()
    text = (text or "").strip()
    if not text:
        return sess, gr.update(), gr.update(), gr.update(), gr.update(), "", *_buy_update({}, None)
    s = graph.invoke({"user_text": text}, _cfg(sess))
    c = to_client(s)
    acc = s.get("account")
    return (sess, result_stage(s, c, text), _who(acc), _orders_html(acc), gr.update(visible=bool(acc)), "", *_buy_update(s, c))


def ui_login(user_id, sess):
    uid = (user_id or "").strip().lower()
    if uid not in DEMO_ACCOUNTS:
        gr.Warning("없는 데모 아이디예요. minsu, jiwoo, hyun, seoyeon 중 하나를 입력해 주세요.")
        return sess, gr.update(), gr.update(), gr.update(), gr.update(), *_buy_update({}, None)
    sess = _new_session(uid)
    acc = _account(sess)
    return sess, service_home(acc), _who(acc), _orders_html(acc), gr.update(visible=True), *_buy_update({}, None)


def ui_reset(sess):
    acc = _account(sess) if sess else None
    if acc:
        new = {"thread": str(uuid.uuid4())}
        graph.update_state(_cfg(new), {"account": acc}, as_node="respond")
        return new, service_home(acc), _who(acc), _orders_html(acc), gr.update(visible=True), *_buy_update({}, None)
    return ui_start()


def ui_buy(code, size, sess):
    acc = _account(sess) if sess else None
    if not acc:
        gr.Warning("구매하려면 위에서 데모 아이디로 로그인해 주세요.")
        return sess, gr.update(), gr.update(), gr.update(), gr.update(), *_buy_update({}, None)
    o = {"id": f'PR-{len(acc["orders"]) + 100:04d}', "code": code, "size": int(size), "status": "결제완료", "exchanges": 0, "note": None,
         "ordered_at": day_iso(0), "shipped_at": None, "delivered_at": None}
    acc = {**acc, "orders": [o] + acc["orders"]}
    graph.update_state(_cfg(sess), {"account": acc}, as_node="respond")   # 주문도 '바꿀 키만' State에 반영
    head = f'주문했어요. {o["id"]} · {order_label(o)}, 지금은 결제 완료 상태예요.'
    return sess, service_home(acc, head), _who(acc), _orders_html(acc), gr.update(visible=True), *_buy_update({}, None)


with gr.Blocks(css=CSS, title="PITCHROOM 축구화 상담", theme=gr.themes.Soft()) as demo:
    sess = gr.State(None)
    with gr.Column(elem_id="pr-wrap"):
        with gr.Row(equal_height=True):
            gr.HTML('<div class="pr-brand"><b>PITCHROOM</b><span>AI 축구화 상담 · 데모</span></div>')
            who = gr.HTML(_who(None))
        with gr.Row(equal_height=True):
            login_id = gr.Textbox(placeholder="데모 아이디: minsu · jiwoo · hyun · seoyeon (비밀번호 없음)", show_label=False, scale=5)
            login_btn = gr.Button("로그인", scale=1)
            logout_btn = gr.Button("로그아웃", scale=1)
            reset_btn = gr.Button("처음부터", scale=1)
        stage_html = gr.HTML(shop_home())
        with gr.Row(equal_height=True):
            msg = gr.Textbox(placeholder="예: 흙운동장에서 뛰고, 호날두를 좋아해요", show_label=False, scale=8, autofocus=True)
            send_btn = gr.Button("보내기", variant="primary", scale=1)
        with gr.Row(visible=False, equal_height=True) as buy_row:
            buy_pick = gr.Dropdown(label="구매할 축구화", choices=[], scale=4)
            buy_size = gr.Dropdown(label="사이즈(mm)", choices=[str(z) for z in range(250, 295, 5)], value="270", scale=1)
            buy_btn = gr.Button("주문하기 (데모 결제)", scale=2)
        with gr.Accordion("내 주문", open=False, visible=False) as orders_acc:
            orders_html = gr.HTML()
        gr.Markdown("데모입니다. 상품·가격·주문·정책은 시연용 예시예요. 문장 이해는 LLM, 판단은 규칙 그래프가 하고, 화면에는 공개 논의만 전달돼요.")

    OUT_SEND = [sess, stage_html, who, orders_html, orders_acc, msg, buy_row, buy_pick, buy_size]
    OUT_ACC = [sess, stage_html, who, orders_html, orders_acc, buy_row, buy_pick, buy_size]
    demo.load(ui_start, None, OUT_ACC)
    send_btn.click(ui_send, [msg, sess], OUT_SEND)
    msg.submit(ui_send, [msg, sess], OUT_SEND)
    login_btn.click(ui_login, [login_id, sess], OUT_ACC)
    login_id.submit(ui_login, [login_id, sess], OUT_ACC)
    logout_btn.click(lambda s: ui_start(), [sess], OUT_ACC)
    reset_btn.click(ui_reset, [sess], OUT_ACC)
    buy_btn.click(ui_buy, [buy_pick, buy_size, sess], OUT_ACC)

def main(share: bool = False):
    demo.launch(share=share)


if __name__ == "__main__":   # python -m pitchroom.ui  (다른 기기에서 열려면 --share)
    import sys
    main(share="--share" in sys.argv)
