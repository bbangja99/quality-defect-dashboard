import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle, BarChart3, CheckCircle2, Download, FileArchive,
  FileSpreadsheet, FileUp, LockKeyhole, Presentation, RefreshCw, ShieldCheck,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { parseFiles } from "./lib/parsers.js";
import {
  PROCESS_COLORS, PROCESS_ORDER, aggregateProduction, pareto, weeklySummary,
} from "./lib/quality.js";
import { downloadMaster, downloadTftPpt } from "./lib/exports.js";

const pct = (value, digits = 3) => `${(value * 100).toFixed(digits)}%`;
const fmt = (value) => Math.round(value || 0).toLocaleString("ko-KR");

function App() {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({ production: [], details: [], files: [], errors: [] });
  const [selectedWeek, setSelectedWeek] = useState("");
  const [selectedProcess, setSelectedProcess] = useState("전체");
  const [tab, setTab] = useState("dashboard");

  const processWeeks = useMemo(() => aggregateProduction(data.production), [data.production]);
  const summary = useMemo(() => weeklySummary(processWeeks), [processWeeks]);
  const completeSummary = summary.filter((row) => row.complete);
  const latest = completeSummary.at(-1) || summary.at(-1);
  const activeWeek = selectedWeek || latest?.week || "";
  const activeRows = processWeeks.filter((row) => row.week === activeWeek);
  const paretoRows = useMemo(
    () => pareto(data.details, selectedProcess === "전체" ? null : selectedProcess, activeWeek),
    [data.details, selectedProcess, activeWeek],
  );
  const trendData = completeSummary.map((row) => ({
    week: row.week,
    가중불량률: Number((row.weightedDefectRate * 100).toFixed(4)),
    평균불량률: Number((row.avgDefectRate * 100).toFixed(4)),
    손실률: Number((row.weightedLossRate * 100).toFixed(4)),
  }));

  const load = async (fileList) => {
    const files = [...fileList].filter((file) => /\.(xlsx|xlsm)$/i.test(file.name));
    if (!files.length) return;
    setLoading(true);
    try {
      const result = await parseFiles(files);
      setData(result);
      const latestResult = weeklySummary(aggregateProduction(result.production)).filter((row) => row.complete).at(-1);
      setSelectedWeek(latestResult?.week || "");
    } finally {
      setLoading(false);
      setDragging(false);
    }
  };

  if (!data.production.length) {
    return (
      <main className="landing">
        <section className="landing-copy">
          <div className="brand"><BarChart3 size={22} /> QUALITY FLOW</div>
          <span className="eyebrow">MEDICAL DEVICE QUALITY ANALYTICS</span>
          <h1>매주 반복되는<br />불량률 취합을<br /><em>한 번에.</em></h1>
          <p>각 공정에서 받은 엑셀을 올리면 불량률과 손실률을 분리해 분석하고, 관리본 Excel과 품질 TFT 발표자료까지 생성합니다.</p>
          <div className="privacy-note"><ShieldCheck size={20} /><span><b>데이터는 외부로 전송되지 않습니다.</b><br />모든 계산은 현재 브라우저 안에서만 처리됩니다.</span></div>
        </section>
        <section
          className={`drop-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); load(event.dataTransfer.files); }}
        >
          <input ref={inputRef} type="file" multiple accept=".xlsx,.xlsm" hidden onChange={(event) => load(event.target.files)} />
          <div className="drop-icon">{loading ? <RefreshCw className="spin" /> : <FileUp />}</div>
          <h2>{loading ? "엑셀을 분석하고 있습니다" : "공정별 엑셀 파일을 올려주세요"}</h2>
          <p>사출 · 연마 · 주사침 · Kopac 파일을 여러 개 동시에 선택할 수 있습니다.</p>
          <button onClick={() => inputRef.current?.click()} disabled={loading}>
            <FileSpreadsheet size={18} /> 파일 선택
          </button>
          <div className="formats"><span>지원 형식</span> XLSX · XLSM</div>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside>
        <div className="logo"><BarChart3 size={21} /><span>QUALITY<br /><b>FLOW</b></span></div>
        <nav>
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}><BarChart3 /> 대시보드</button>
          <button className={tab === "data" ? "active" : ""} onClick={() => setTab("data")}><FileArchive /> 데이터 검증</button>
        </nav>
        <div className="source-list">
          <span>불러온 파일</span>
          {data.files.map((file) => (
            <div className="source-file" key={file.file}><CheckCircle2 /><p><b>{file.kind}</b><small>{file.file}</small></p></div>
          ))}
          {data.errors.map((error) => (
            <div className="source-file error" key={error.file}><AlertTriangle /><p><b>인식 실패</b><small>{error.file}</small></p></div>
          ))}
        </div>
        <button className="reset" onClick={() => setData({ production: [], details: [], files: [], errors: [] })}><RefreshCw /> 다른 파일 분석</button>
        <div className="local-badge"><LockKeyhole /> 브라우저 로컬 처리</div>
      </aside>

      <main className="workspace">
        <header>
          <div><span className="eyebrow">WEEKLY QUALITY REVIEW</span><h1>공정별 불량률 현황</h1></div>
          <div className="header-actions">
            <select value={activeWeek} onChange={(event) => setSelectedWeek(event.target.value)}>
              {summary.slice().reverse().map((row) => <option key={row.week} value={row.week}>{row.week} {row.complete ? "" : "· 미완전"}</option>)}
            </select>
            <button className="secondary" onClick={() => downloadMaster(data.production, data.details)}><Download /> Excel</button>
            <button className="primary" onClick={() => downloadTftPpt(data.production, data.details, activeWeek)}><Presentation /> TFT PPT</button>
          </div>
        </header>

        {tab === "dashboard" ? (
          <>
            {!summary.find((row) => row.week === activeWeek)?.complete && (
              <div className="warning-banner"><AlertTriangle /> 이 주차는 일부 공정 파일이 없어 전체 지표 비교에 주의가 필요합니다.</div>
            )}
            <section className="kpi-grid">
              <Kpi label="총 투입수량" value={`${fmt(summary.find((row) => row.week === activeWeek)?.totalInput)} EA`} meta={`${activeRows.length}/4개 공정`} />
              <Kpi label="총 불량수량" value={`${fmt(summary.find((row) => row.week === activeWeek)?.totalDefect)} EA`} meta="손실 제외" />
              <Kpi label="가중 불량률" value={pct(summary.find((row) => row.week === activeWeek)?.weightedDefectRate || 0)} accent meta="불량 ÷ 투입" />
              <Kpi label="가중 손실률" value={pct(summary.find((row) => row.week === activeWeek)?.weightedLossRate || 0)} meta="공정검사·세팅" />
            </section>

            <section className="chart-grid">
              <article className="panel wide">
                <PanelTitle title="완전 취합 주차 불량률 추이" caption="모든 주요 공정이 제출된 주차만 비교" />
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6edf3" />
                    <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                    <YAxis unit="%" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value) => [`${value}%`]} />
                    <Legend />
                    <Line type="monotone" dataKey="가중불량률" stroke="#2672ff" strokeWidth={3} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="평균불량률" stroke="#8b9db0" strokeWidth={2} strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              </article>
              <article className="panel">
                <PanelTitle title="공정별 불량률" caption={activeWeek} />
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={activeRows} layout="vertical" margin={{ left: 15 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e6edf3" />
                    <XAxis type="number" unit="%" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="process" width={68} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value) => [`${(value * 100).toFixed(3)}%`, "불량률"]} />
                    <Bar dataKey="defectRate" radius={[0, 5, 5, 0]}>
                      {activeRows.map((row) => <Cell key={row.process} fill={PROCESS_COLORS[row.process]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </article>
            </section>

            <section className="panel">
              <div className="panel-head split">
                <PanelTitle title="불량유형 파레토" caption={`${activeWeek} · 손실 항목 제외`} />
                <div className="segmented">
                  {["전체", ...PROCESS_ORDER].map((process) => (
                    <button key={process} className={selectedProcess === process ? "active" : ""} onClick={() => setSelectedProcess(process)}>{process}</button>
                  ))}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={340}>
                <ComposedChart data={paretoRows.slice(0, 12)}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6edf3" />
                  <XAxis dataKey="defectType" interval={0} angle={-18} textAnchor="end" height={70} tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="qty" tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="share" orientation="right" domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                  <Tooltip formatter={(value, name) => name === "cumulative" ? [`${(value * 100).toFixed(1)}%`, "누적 점유율"] : [fmt(value), "불량수량"]} />
                  <Bar yAxisId="qty" dataKey="defectQty" fill="#2672ff" radius={[5, 5, 0, 0]} />
                  <Line yAxisId="share" type="monotone" dataKey="cumulative" stroke="#e5484d" strokeWidth={2.5} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </section>
          </>
        ) : (
          <DataView summary={summary} processWeeks={processWeeks} files={data.files} errors={data.errors} />
        )}
      </main>
    </div>
  );
}

function Kpi({ label, value, meta, accent }) {
  return <article className={`kpi ${accent ? "accent" : ""}`}><span>{label}</span><strong>{value}</strong><small>{meta}</small></article>;
}

function PanelTitle({ title, caption }) {
  return <div className="panel-title"><h3>{title}</h3><p>{caption}</p></div>;
}

function DataView({ summary, processWeeks, files, errors }) {
  return (
    <>
      <section className="panel">
        <PanelTitle title="주차별 제출 완전성" caption="전체 지표는 4개 주요 공정 완전 취합 주차를 기준으로 비교합니다." />
        <div className="table-wrap"><table><thead><tr><th>주차</th><th>제출 공정</th><th>상태</th><th>미제출 공정</th><th>가중 불량률</th><th>가중 손실률</th></tr></thead>
          <tbody>{summary.slice().reverse().map((row) => <tr key={row.week}><td><b>{row.week}</b></td><td>{row.processCount}/4</td><td><span className={`status ${row.complete ? "ok" : "warn"}`}>{row.complete ? "완전 취합" : "미완전"}</span></td><td>{row.missing.join(", ") || "-"}</td><td>{pct(row.weightedDefectRate)}</td><td>{pct(row.weightedLossRate)}</td></tr>)}</tbody>
        </table></div>
      </section>
      <section className="panel">
        <PanelTitle title="공정별 정규화 데이터" caption={`${processWeeks.length}개 주차×공정 레코드`} />
        <div className="table-wrap"><table><thead><tr><th>주차</th><th>공정</th><th>투입</th><th>불량</th><th>불량률</th><th>손실</th><th>손실률</th><th>PPM</th></tr></thead>
          <tbody>{processWeeks.slice().reverse().map((row) => <tr key={`${row.week}-${row.process}`}><td>{row.week}</td><td><b>{row.process}</b></td><td>{fmt(row.inputQty)}</td><td>{fmt(row.defectQty)}</td><td>{pct(row.defectRate)}</td><td>{fmt(row.lossQty)}</td><td>{pct(row.lossRate)}</td><td>{fmt(row.ppm)}</td></tr>)}</tbody>
        </table></div>
      </section>
      {(errors.length > 0 || files.some((file) => file.warnings?.length)) && <section className="panel"><PanelTitle title="파싱 경고" caption="원본 파일 확인이 필요한 항목" />
        {[...errors.map((error) => `${error.file}: ${error.message}`), ...files.flatMap((file) => (file.warnings || []).map((warning) => `${file.file}: ${warning}`))].map((message) => <div className="log-line" key={message}><AlertTriangle />{message}</div>)}
      </section>}
    </>
  );
}

export default App;
