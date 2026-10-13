"""상품 사진을 data URI로 읽어 둔다 (Gradio HTML에 바로 넣기 위해). 파일: static/images/<상품코드>.webp"""
import base64
from pathlib import Path

_DIR = Path(__file__).parent / "static" / "images"

PHOTOS = {
    p.stem: "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()
    for p in sorted(_DIR.glob("*.webp"))
}
