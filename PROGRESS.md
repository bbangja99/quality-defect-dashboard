# 공정별 불량률 취합·분석 웹앱 — 작업 현황 (핸드오프)

> 풍림파마텍 품질팀 / 주차별 생산·불량 자동 취합·대시보드
> 최종 갱신: 2026-06-22 기준. 다음 세션은 이 문서부터 읽고 이어서 진행.

## 0. 한 줄 요약
공정마다 양식이 다른 주차별 엑셀(사출/연마/Kopac/주사침)을 공통 long-format으로 정규화하는
**4개 공정 파서를 구현·검증 완료**. 모두 품질팀 마스터의 **26-W25 값과 소수점까지 일치**.

## 1. 진행 상태
| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 실제 엑셀 ↔ 명세서 대조 | ✅ 완료 |
| 1 | 스캐폴딩(`config.py`,`normalize.py`,`base.py`) | ✅ 완료 |
| 2~3 | 공정별 파서 4종 구현 + 회귀 테스트 | ✅ 완료 |
| 4 | `aggregate.py` (주차×공정 집계, 평균/가중 불량률, 손실률, 파레토/PPM) | ✅ 완료 |
| 5 | `pipeline.py` + `charts.py` + `app.py` (Streamlit 대시보드) | ✅ 완료 |
| 6 | `master_excel.py` (마스터 취합본 재생성) + 다운로드 연결 | ✅ 완료 |

**→ 핵심 자동화 파이프라인(파서→집계→대시보드→마스터 재생성) 전 단계 완료.**

## 2. 검증 결과 — 마스터 26-W25 정확 일치
| 공정 | 투입 / 불량 / 불량률 |
|---|---|
| 사출 통합 | 2,837,421 / 5,251 / 0.00185 |
| 주사침 | 429,057 / 2,501 / 0.00583 |
| 연마 | 339,230 / 580 / 0.00171 |
| Kopac | 235,836 / 852 / 0.00361 |

테스트 실행: `cd webapp && PYTHONUTF8=1 python tests/test_<공정>.py` (injection/grinding/kopac/needle)

## 3. 파일 구조
```
webapp/
├─ requirements.txt          # streamlit, pandas, openpyxl, plotly, XlsxWriter, pytest
├─ PROGRESS.md               # (이 문서)
├─ src/
│  ├─ config.py              # 공정·색상·손실규칙·불량유형사전·주사침 제외모델·주차연도임계값
│  ├─ normalize.py           # 공통스키마(production/defect_detail), 주차정규화, 파일명날짜, 표준화, 클린징
│  ├─ aggregate.py           # 주차×공정 집계, 평균/가중 불량률·손실률, 파레토(점유율/누적/PPM)
│  ├─ pipeline.py            # 폴더 자동로드/업로드 → 공정별 파서 실행·결합(LoadResult)
│  ├─ charts.py              # Plotly: 전체추이/공정추이/손실추이/파레토막대/도넛
│  ├─ master_excel.py        # 마스터 취합본 xlsx 재생성(주차별생산현황+공정별+모델별+Raw)
│  └─ parsers/
│     ├─ base.py             # BaseParser(load_sheet/build_frames) + ParseResult
│     ├─ injection.py        # 사출 — 주차별_트렌드 1차, Raw_Data 폴백
│     ├─ grinding.py         # 연마 — 불량유형 시트, 세팅/QC샘플/공정검사 손실분리
│     ├─ kopac.py            # Kopac — 신규파일(파레토+요약+생산테이블) & 구 전수검사 양식 자동판별
│     └─ needle.py           # 주사침 — 주사침/범용/안과용만, 의료기기 제외, 세팅소모/QC/공정검사 손실
├─ app.py                    # Streamlit 진입점 (탭/필터/KPI/차트/다운로드)
└─ tests/                    # 회귀 테스트 6종 (공정 4 + aggregate + master_excel, 전부 PASS)
```

**실행**: `cd webapp && python -m streamlit run app.py` (의존성: `pip install -r requirements.txt`).
프리뷰 설정: `D:/Project/불량률/.claude/launch.json` (name: `defect-dashboard`, port 8501).

## 4. 반드시 기억할 핵심 규칙·함정 (재발견 방지)
1. **손실률(요청 5번)**: 공정검사·세팅류는 불량률 제외 → `loss_qty`/`loss_rate` 별도. 공정별 손실유형은 `config.LOSS_TYPES`.
2. **주사침**: 주사침/범용/안과용만 관리. 의료기기 set 모델 10종 제외(`config.NEEDLE_EXCLUDE_MODELS`).
3. **사출 진실 소스 = `주차별_트렌드` 시트** (Raw_Data·개별 주차시트 아님 — 설비동 일부/구버전이라 합계 어긋남).
   `사출 통합` 정의가 **26-W18부터** 트렌드 기준으로 변경 → W18 이전은 새만금+오식도 분리라 마스터와 다름(버그 아님).
4. **Kopac 신규 포맷**: 파일 하나에 좌측 1ml/3ml 파레토 + 우측 요약블록 + 생산 테이블.
   투입 = Σ(기간합계 양품) + 불량합계 / 불량 = 불량합계 − 공정검사(손실).
   생산 테이블에 합계행이 있어 좌측 키열(총계획수량)로 제품행만 합산(안 그러면 2배). 주차는 파일명 실패 시 시트 내 최신 날짜로 추론.
5. 콘솔 한글 깨짐 방지: 스크립트 실행 시 `PYTHONUTF8=1`.

## 5. 입력 파일 위치 (현재 폴더)
`생산 현황 및 불량/` 아래 — 사출: `사출 불량유형(2026)_W25.xlsx`, 연마: `2026-W25-주간업무보고-연마.xlsx`,
주사침: `2026-W25-불량유형_주사침 0619, 20.xlsx`, Kopac: `불량유형_코팩_2606022.xlsx`(=W25).
마스터(회귀 기준): `품질팀 관리본/각 공정별 불량 현황_주요 공정_공정검사 미포함.xlsx`.

## 6. 집계(단계 4) 결과 + 다음 단계(단계 5) 착수 메모
- `aggregate.py` 완료. **W25 평균 불량률 0.0032505 / 가중 0.0023907 → 마스터 '사출통합' 시트와 4자리 일치**(`test_aggregate.py`).
  - `aggregate_by_process_week(production)` → 주차×공정 투입/불량/손실 + 불량률/손실률/PPM
  - `weekly_summary(proc_week)` → 주차별 평균(투입>0 공정 단순평균)/가중(Σ불량/Σ투입) 불량률·손실률
  - `pareto(defect_detail, process, week)` → 점유율·누적점유율(손실 기본 제외)
- ⚠ 현재 연마/주사침/Kopac은 W25 파일만 있어 다(多)주차 집계는 사출만 전 주차. 전 주차 회귀하려면 각 공정 과거 주차 파일 필요.
- 단계 5 완료: `pipeline.py`(로컬폴더/업로드 로더) + `charts.py` + `app.py`. 브라우저 렌더링 검증 완료
  (전체현황/공정별/불량유형/다운로드/검증 5개 탭, W25 KPI: 가중 0.239%·평균 0.325%·손실 0.591%).
  - ⚠ 로더 파일선택: 파일명에 주차 없으면(`2606022` 등) 내용 최신 날짜로 보완(`_content_weeknum`).
  - ⚠ 전체추이 차트의 W02~W17은 사출만 존재(타 공정 W25 파일만 있어서) → 다주차 채우려면 과거 주차 파일 필요.
- 단계 6 완료: `master_excel.py` — '주차별 생산현황'(메인 집계, 마스터 레이아웃) + 공정별(주차표+불량유형 피벗)
  + 모델별 불량률 현황 + Raw_production/Raw_defect_detail. `app.py` 다운로드 탭에 연결.
  검증: 생성본 W25 좌측 블록 4공정 + 우측 평균/가중 불량률 모두 마스터 일치(`test_master_excel.py`).

## 7. 향후 확장(선택) — 핵심 기능은 완료
- 과거 주차 파일 확보 시 다(多)주차 회귀(마스터 전 주차 평균/가중 4자리 일치) 확대.
- PPTX 자동생성(품질 TFT 발표자료), 간트(개선일정) 시트 연계.
- GitHub Private + Streamlit Cloud 배포(`.streamlit/secrets.toml` 비밀번호) — README에 절차 추가.
- 의존성 설치 완료: streamlit 1.58, plotly 6.7, XlsxWriter, pandas, openpyxl.
