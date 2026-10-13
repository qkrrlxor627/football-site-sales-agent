"""터미널에서 직접 대화.  실행: python -m pitchroom.cli [--user jiwoo]"""
import argparse

from .data import DEMO_ACCOUNTS
from .graph import chat, new_thread


def main():
    ap = argparse.ArgumentParser(description="PITCHROOM 축구화 상담 (q 입력 시 종료)")
    ap.add_argument("--user", choices=list(DEMO_ACCOUNTS), help="데모 계정으로 로그인한 상태로 시작")
    args = ap.parse_args()
    cfg = new_thread(args.user)
    while True:
        try:
            msg = input("👤 ")
        except (EOFError, KeyboardInterrupt):
            break
        if msg.strip().lower() in ("q", "quit", "종료"):
            break
        if msg.strip():
            chat(msg, cfg)


if __name__ == "__main__":
    main()
