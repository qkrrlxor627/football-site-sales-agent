# PITCHROOM 실행 명령 모음.  처음: make install → make dev
PY := .venv/bin/python

.PHONY: install dev build start test reset-demo sample docker docker-logs docker-down docker-sample

install:        ## 가상환경 + 파이썬/프론트 의존성 설치
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements-dev.txt
	cd frontend && npm install
	@test -f .env || cp .env.example .env

dev:            ## 개발 서버: API(8000, 자동 재시작) + 화면(5173, HMR). http://127.0.0.1:5173
	@trap 'kill 0' EXIT INT TERM; \
	$(PY) app.py --reload & \
	(cd frontend && npm run dev) & \
	wait

build:          ## 화면을 frontend/dist로 빌드
	cd frontend && npm run build

start: build    ## 한 프로세스로 실행 (API + 빌드된 화면). http://127.0.0.1:8000
	$(PY) app.py

test:           ## 백엔드(pytest) + 프론트(타입 검사, vitest)
	$(PY) -m pytest -q
	cd frontend && npm run type-check && npm test

reset-demo:     ## 데모 계정·주문을 오늘 날짜 기준으로 다시 만들기
	$(PY) -m pitchroom.store --reset

sample:         ## 케이스별 연습 계정 만들기 (다시 실행하면 처음 상태로 되돌림)
	$(PY) -m pitchroom.sample

docker:         ## Docker로 실행 (운영 설정). http://127.0.0.1:8000
	docker compose up -d --build

docker-logs:    ## Docker 서버 로그 (처음 만든 관리자 임시 비밀번호가 여기 나온다)
	docker compose logs -f pitchroom

docker-down:    ## Docker 중지 (데이터 볼륨은 남는다)
	docker compose down

docker-sample:  ## Docker 서버에 케이스별 연습 계정 만들기·되돌리기
	docker compose exec pitchroom python -m pitchroom.sample
