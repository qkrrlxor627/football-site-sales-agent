"""웹 서버 실행: python app.py  (코드 바뀔 때마다 다시 띄우려면 --reload)

API와 빌드된 화면(frontend/dist)을 한 프로세스로 서빙한다. 주소와 포트는 .env의 PITCHROOM_HOST / PITCHROOM_PORT.
"""
import sys

import uvicorn

from pitchroom.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("pitchroom.api:create_app", factory=True, host=HOST, port=PORT, reload="--reload" in sys.argv)
