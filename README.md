# 공정별 불량률 취합·분석 대시보드

풍림파마텍 품질팀 · 주차별 생산·불량 현황을 **자동 취합·분석**하는 Streamlit 웹앱.
공정마다 양식이 다른 주차별 엑셀(사출/연마/Kopac/주사침)을 공통 스키마로 정규화하여
주차×공정 집계, 평균/가중 불량률, 손실률, 불량유형 파레토를 산출하고 마스터 취합본(xlsx)을 재생성합니다.

> ⚠️ **보안**: 불량 데이터는 사내 자료입니다. GitHub 레포는 **반드시 Private**으로,
> 외부 공유 시 **비밀번호 게이트**(아래)를 켜세요. 데이터 파일은 `.gitignore`로 커밋이 차단됩니다.

---

## 1. 로컬 실행 (사내 PC)

```bash
cd webapp
pip install -r requirements.txt
streamlit run app.py
```

- 브라우저가 자동으로 열립니다(기본 http://localhost:8501).
- **로컬 폴더 모드**: 사이드바에서 `생산 현황 및 불량/` 폴더 경로를 지정하면 공정별 최신 파일을 자동 인식·취합합니다.
- **파일 업로드 모드**: 공정별로 엑셀을 끌어다 놓으면 취합합니다.

## 2. 화면 구성
- **전체 현황**: 최신 주차 KPI(가중/평균 불량률·손실률) + 주차별 추이 라인
- **공정별**: 공정·주차 선택 → 불량유형 파레토 + 도넛 + 손실률 추이
- **불량유형/모델**: 불량유형 파레토(전체), 모델별 불량수량
- **다운로드**: 정규화 CSV 3종 + **마스터 취합본(xlsx)** 재생성
- **검증/로그**: 주차×공정 집계표, 주차별 요약, 경고 로그

## 3. 비밀번호 게이트 (선택)
`.streamlit/secrets.toml.example` 를 참고해 비밀번호를 설정하면 접속 시 게이트가 활성화됩니다.
- 로컬: `webapp/.streamlit/secrets.toml` 생성 후 `password = "..."`
- 미설정 시 게이트 비활성(누구나 접속).

## 4. GitHub Private 레포 배포 → Streamlit Community Cloud (무료)

1. **Private 레포 푸시** (이미 코드가 올라가 있다면 생략)
   ```bash
   cd webapp
   git init && git add . && git commit -m "init: 불량률 대시보드"
   gh repo create <레포명> --private --source=. --push
   ```
2. **Streamlit Cloud 연결**: https://share.streamlit.io → *Create app* → GitHub 레포 선택
   - **Main file path**: `app.py`
   - **Branch**: `main`
3. **비밀번호 설정**: 앱 *Settings → Secrets* 에 아래 붙여넣기
   ```toml
   password = "사내-공유용-비밀번호"
   ```
4. 배포 완료 후 발급되는 URL을 품질팀에 공유. (클라우드에서는 데이터가 없으므로 **파일 업로드 모드**로 사용)

> 외부 노출이 곤란하면 4번을 생략하고 **사내 PC 로컬 실행**(`streamlit run app.py`)만 사용하세요.

## 5. 폴더 구조
```
webapp/
├─ app.py                 # Streamlit 진입점
├─ requirements.txt
├─ PROGRESS.md            # 개발 현황·핵심 규칙(유지보수용)
├─ src/
│  ├─ config.py           # 공정·손실규칙·불량유형사전·주사침 제외모델
│  ├─ normalize.py        # 공통 스키마·주차 정규화·표준화
│  ├─ aggregate.py        # 주차×공정 집계·평균/가중 불량률·파레토
│  ├─ pipeline.py         # 폴더/업로드 로더
│  ├─ charts.py           # Plotly 차트
│  ├─ master_excel.py     # 마스터 취합본 재생성
│  └─ parsers/            # 공정별 파서 4종(사출/연마/Kopac/주사침)
└─ tests/                 # 회귀 테스트 6종 (전부 PASS)
```

## 6. 테스트
```bash
cd webapp
PYTHONUTF8=1 python tests/test_aggregate.py   # 마스터 회귀(평균/가중 불량률)
# 그 외 test_injection / test_grinding / test_kopac / test_needle / test_master_excel
```

## 7. 핵심 규칙 (유지보수)
- **손실률**: 공정검사·세팅류는 불량률에서 제외, 손실률로 별도 관리(`config.LOSS_TYPES`).
- **주사침**: 주사침/범용/안과용만 관리, 의료기기 set 모델 제외(`config.NEEDLE_EXCLUDE_MODELS`).
- **사출**: `주차별_트렌드` 시트가 진실 소스(Raw_Data 아님).
- 상세는 `PROGRESS.md` 참고.
