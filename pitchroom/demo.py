"""데모 대화 몇 개를 출력한다.  실행: python -m pitchroom.demo"""
from .graph import chat, graph, new_thread


def main():
    print("=== 처음 온 고객: 메시 + 아디다스 ===")
    cfg = new_thread()
    chat("나는 메시 조아해 아디다스 축구화로 줘.", cfg)
    chat("인조잔디에서 주로 뛰어요", cfg)
    chat("발볼은 보통이고 25만원 정도요", cfg)

    print("\n=== 조건을 전부 맞추는 신발이 없을 때: 대안 제시 ===")
    cfg = new_thread()
    chat("천연잔디, 발볼 넓고 5만원 이하", cfg)

    print("\n=== 발 건강 언급: 사람에게 ===")
    cfg = new_thread()
    chat("발목 수술한 적 있는데 인조잔디용 추천해줘", cfg)

    print("\n=== 이미 주문한 고객 (지우): 주문 기록으로 교환 처리 ===")
    cfg = new_thread("jiwoo")
    chat("사이즈가 좀 작아요", cfg)
    chat("실내에서만 신어봤어요", cfg)
    print("   주문 상태 →", graph.get_state(cfg).values["account"]["orders"][0]["status"])

    print("\n=== 교환 이력 있는 고객 (현): 기간 지나 사장님 확인 ===")
    cfg = new_thread("hyun")
    chat("교환하고 싶어요", cfg)


if __name__ == "__main__":
    main()
