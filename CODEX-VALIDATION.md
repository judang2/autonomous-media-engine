# Codex 연결 검증 — 2026-09-09

- GPT-5.5 / low / ChatGPT 구독 인증을 사용하는 planner 추가.
- 사용자 로컬 `.env`를 `PLANNER=codex`, `ENABLE_LIVE=false`로 변경. Instagram 계정 설정·세션 유지.
- `codex login status`로 ChatGPT 구독 로그인 확인.
- 로컬 자동 테스트 **30개 통과**. 기존 테스트와 API 키 배제, API 로그인 거부, 잘못된/미완료 응답 거부, 예상치 못한 도구 결과 거부, GPT-5.5 low 인자 및 토큰 로그 검증 포함.
- **실제 모델 호출 미완료:** 앱 실행 환경에서 Codex 내부 app-server 초기화가 Access denied로 실패. 폴더/네트워크 권한 허용 후에도 실패.
- 따라서 실제 답장 10개의 품질·토큰 수·구독 사용량 변화는 아직 측정하지 못함. 사용자 PowerShell에서 `python -m igagent.benchmark`로 측정 가능.
- 이번 작업에서 Instagram 조회·전송은 수행하지 않음.
