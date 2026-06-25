# QUALITY FLOW — 공정별 불량률 취합·분석 웹앱

의료기기 제조 품질팀의 주간 생산·불량 Excel을 브라우저에서 자동 취합합니다.

**웹앱:** https://bbangja99.github.io/quality-defect-dashboard/

## 주요 기능

- 사출·연마·주사침·Kopac 원본 형식 자동 인식
- 공정검사·세팅·QC 샘플을 불량에서 제외하고 손실률로 분리
- 완전 취합 주차 기준 전체/공정별 불량률 추이
- 불량유형 파레토와 공정별 KPI
- 품질팀 관리용 Excel 자동 생성
- 품질 TFT PowerPoint 자동 생성
- 업로드 파일을 서버로 전송하지 않는 브라우저 로컬 처리

## 로컬 실행

`대시보드_실행.bat`을 더블클릭하거나 다음 명령을 실행합니다.

```bash
npm install
npm run dev
```

## 검증 및 빌드

```bash
npm test
npm run build
```

## 자동 배포

`main` 브랜치에 푸시하면 `.github/workflows/deploy.yml`이 아래 작업을 자동 수행합니다.

1. 의존성 설치
2. 집계 회귀 테스트
3. 프로덕션 빌드
4. GitHub Pages 배포

## 보안

원본 생산·불량 파일과 관리본은 `.gitignore`로 차단합니다. 앱은 정적 웹앱이며 업로드한 파일은 사용자의 브라우저 메모리에서만 처리됩니다.

## Legacy Python

이전 Python/Streamlit 구현은 계산 회귀 검증과 파서 참고를 위해 `app.py`, `src/`, `tests/`에 보존되어 있습니다.
