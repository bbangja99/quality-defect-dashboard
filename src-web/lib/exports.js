import { PROCESS_COLORS, PROCESS_ORDER, aggregateProduction, pareto, weeklySummary } from "./quality.js";

const pct = (value) => `${(value * 100).toFixed(3)}%`;
const numberFormat = (value) => Math.round(value).toLocaleString("ko-KR");

const saveBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
};

const addSheet = (workbook, name, rows) => {
  const sheet = workbook.addWorksheet(name);
  if (!rows.length) return sheet;
  sheet.columns = Object.keys(rows[0]).map((header) => ({
    header, key: header, width: Math.max(12, Math.min(28, header.length * 2 + 4)),
  }));
  sheet.addRows(rows);
  sheet.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
  sheet.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF15324B" } };
  sheet.views = [{ state: "frozen", ySplit: 1 }];
  sheet.autoFilter = { from: "A1", to: sheet.getRow(1).getCell(sheet.columnCount).address };
  return sheet;
};

export async function downloadMaster(production, details) {
  const { default: ExcelJS } = await import("exceljs");
  const processWeeks = aggregateProduction(production);
  const summary = weeklySummary(processWeeks);
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "품질팀";
  workbook.created = new Date();

  const summaryRows = summary.map((row) => ({
    주차: row.week,
    공정수: row.processCount,
    완전취합: row.complete ? "Y" : "N",
    미제출공정: row.missing.join(", "),
    총투입수량: row.totalInput,
    총불량수량: row.totalDefect,
    총손실수량: row.totalLoss,
    평균불량률: row.avgDefectRate,
    가중불량률: row.weightedDefectRate,
    가중손실률: row.weightedLossRate,
  }));
  addSheet(workbook, "주차별 요약", summaryRows);

  PROCESS_ORDER.forEach((process) => {
    const rows = processWeeks.filter((row) => row.process === process).map((row) => ({
      주차: row.week, 투입수량: row.inputQty, 불량수량: row.defectQty,
      불량률: row.defectRate, 손실수량: row.lossQty, 손실률: row.lossRate, PPM: row.ppm,
    }));
    if (rows.length) addSheet(workbook, process, rows);
  });

  const prodRows = production.map((row) => ({
    연도: row.year, 주차: row.week, 공정: row.process, 모델: row.model,
    투입수량: row.inputQty, 불량수량: row.defectQty, 손실수량: row.lossQty,
    불량률: row.defectRate, 손실률: row.lossRate, 원본파일: row.source,
  }));
  const detailRows = details.map((row) => ({
    연도: row.year, 주차: row.week, 공정: row.process, 모델: row.model,
    불량유형: row.defectType, 수량: row.defectQty,
    구분: row.isLoss ? "손실" : "불량", 원본파일: row.source,
  }));
  addSheet(workbook, "Raw_production", prodRows);
  addSheet(workbook, "Raw_defect_detail", detailRows);
  const buffer = await workbook.xlsx.writeBuffer();
  saveBlob(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
    `품질_불량률_취합_${summary.at(-1)?.week ?? "결과"}.xlsx`);
}

const addTitle = (slide, title, subtitle = "") => {
  slide.addText(title, { x: 0.55, y: 0.28, w: 12.2, h: 0.38, fontFace: "Malgun Gothic", fontSize: 22, bold: true, color: "15324B" });
  if (subtitle) slide.addText(subtitle, { x: 0.57, y: 0.72, w: 11.8, h: 0.24, fontFace: "Malgun Gothic", fontSize: 9.5, color: "61758A" });
  slide.addShape("line", { x: 0.55, y: 1.03, w: 12.2, h: 0, line: { color: "D9E2EC", width: 1 } });
};

export async function downloadTftPpt(production, details, selectedWeek) {
  const { default: PptxGenJS } = await import("pptxgenjs");
  const processWeeks = aggregateProduction(production);
  const summary = weeklySummary(processWeeks);
  const target = summary.find((row) => row.week === selectedWeek) || summary.at(-1);
  if (!target) return;
  const weekRows = processWeeks.filter((row) => row.week === target.week);
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "품질팀";
  pptx.subject = "주간 품질 TFT";
  pptx.title = `품질 TFT ${target.week}`;
  pptx.company = "풍림파마텍";
  pptx.lang = "ko-KR";
  pptx.theme = {
    headFontFace: "Malgun Gothic",
    bodyFontFace: "Malgun Gothic",
    lang: "ko-KR",
  };

  let slide = pptx.addSlide();
  slide.background = { color: "F4F7FA" };
  slide.addShape("rect", { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: "102A43" }, line: { color: "102A43" } });
  slide.addText("QUALITY TFT", { x: 0.72, y: 0.65, w: 4.2, h: 0.4, fontSize: 14, bold: true, color: "63B3ED", charSpacing: 2.5 });
  slide.addText(`${target.week.replace("26-W", "")}주차\n품질 현황`, { x: 0.72, y: 1.55, w: 5.7, h: 1.65, fontSize: 38, bold: true, color: "FFFFFF", breakLine: false, margin: 0 });
  slide.addText(`가중 불량률 ${pct(target.weightedDefectRate)}  ·  손실률 ${pct(target.weightedLossRate)}`, { x: 0.75, y: 3.52, w: 5.8, h: 0.35, fontSize: 14, color: "D9EAF7", margin: 0 });
  slide.addText("공정검사·세팅은 불량에서 제외하고 손실로 별도 집계", { x: 0.75, y: 5.9, w: 6.2, h: 0.3, fontSize: 11, color: "9FB3C8", margin: 0 });
  slide.addText(new Date().toLocaleDateString("ko-KR"), { x: 0.75, y: 6.55, w: 2.5, h: 0.25, fontSize: 10, color: "829AB1", margin: 0 });

  slide = pptx.addSlide();
  addTitle(slide, `${target.week} 전체 품질 현황`, target.complete ? "4개 주요 공정 완전 취합" : `미제출: ${target.missing.join(", ")}`);
  const cards = [
    ["총 투입", numberFormat(target.totalInput), "EA"],
    ["총 불량", numberFormat(target.totalDefect), "EA"],
    ["가중 불량률", pct(target.weightedDefectRate), ""],
    ["가중 손실률", pct(target.weightedLossRate), ""],
  ];
  cards.forEach(([label, value, unit], index) => {
    const x = 0.62 + index * 3.12;
    slide.addShape("roundRect", { x, y: 1.3, w: 2.82, h: 1.15, rectRadius: 0.08, fill: { color: index === 2 ? "E8F1FF" : "F4F7FA" }, line: { color: index === 2 ? "8AB4F8" : "D9E2EC" } });
    slide.addText(label, { x: x + 0.18, y: 1.52, w: 2.35, h: 0.22, fontSize: 10, color: "61758A", margin: 0 });
    slide.addText(`${value}${unit ? ` ${unit}` : ""}`, { x: x + 0.18, y: 1.83, w: 2.35, h: 0.35, fontSize: 21, bold: true, color: "15324B", margin: 0 });
  });
  slide.addChart(pptx.ChartType.bar, [{
    name: "불량률",
    labels: weekRows.map((row) => row.process),
    values: weekRows.map((row) => Number((row.defectRate * 100).toFixed(4))),
  }], {
    x: 0.68, y: 2.85, w: 6.05, h: 3.65,
    catAxisLabelFontFace: "Malgun Gothic", catAxisLabelFontSize: 10,
    valAxisLabelFontSize: 9, valAxisTitle: "불량률 (%)",
    showLegend: false, showTitle: true, title: "공정별 불량률",
    chartColors: ["2672FF"], showValue: true, dataLabelPosition: "outEnd",
  });
  slide.addChart(pptx.ChartType.bar, [{
    name: "손실률",
    labels: weekRows.map((row) => row.process),
    values: weekRows.map((row) => Number((row.lossRate * 100).toFixed(4))),
  }], {
    x: 6.93, y: 2.85, w: 5.75, h: 3.65,
    catAxisLabelFontFace: "Malgun Gothic", catAxisLabelFontSize: 10,
    valAxisLabelFontSize: 9, valAxisTitle: "손실률 (%)",
    showLegend: false, showTitle: true, title: "공정별 손실률",
    chartColors: ["F59E0B"], showValue: true, dataLabelPosition: "outEnd",
  });

  for (const process of PROCESS_ORDER) {
    const row = weekRows.find((item) => item.process === process);
    if (!row) continue;
    const top = pareto(details, process, target.week).slice(0, 7);
    slide = pptx.addSlide();
    addTitle(slide, `${process} 불량 현황`, `${target.week} · 불량률 ${pct(row.defectRate)} · 손실률 ${pct(row.lossRate)}`);
    slide.addChart(pptx.ChartType.bar, [{
      name: "불량수량",
      labels: top.map((item) => item.defectType),
      values: top.map((item) => item.defectQty),
    }], {
      x: 0.65, y: 1.35, w: 7.4, h: 5.45,
      catAxisLabelFontFace: "Malgun Gothic", catAxisLabelFontSize: 9,
      valAxisLabelFontSize: 9, showLegend: false, showTitle: true,
      title: "불량유형 TOP 7", chartColors: [PROCESS_COLORS[process]],
      showValue: true, dataLabelPosition: "outEnd",
    });
    slide.addText([
      { text: "핵심 수치\n", options: { bold: true, color: "15324B", fontSize: 16 } },
      { text: `투입수량  ${numberFormat(row.inputQty)} EA\n`, options: { fontSize: 13 } },
      { text: `불량수량  ${numberFormat(row.defectQty)} EA\n`, options: { fontSize: 13 } },
      { text: `손실수량  ${numberFormat(row.lossQty)} EA\n\n`, options: { fontSize: 13 } },
      { text: "우선 개선 대상\n", options: { bold: true, color: "15324B", fontSize: 16 } },
      ...top.slice(0, 3).flatMap((item, index) => [
        { text: `${index + 1}. ${item.defectType}`, options: { bold: true, fontSize: 13, breakLine: true } },
        { text: `   ${numberFormat(item.defectQty)}건 · ${(item.share * 100).toFixed(1)}%`, options: { color: "61758A", fontSize: 11, breakLine: true } },
      ]),
    ], { x: 8.42, y: 1.55, w: 4.15, h: 4.8, margin: 0.18, breakLine: false, valign: "top", fill: { color: "F4F7FA" }, line: { color: "D9E2EC" } });
  }

  await pptx.writeFile({ fileName: `품질_TFT_${target.week}.pptx` });
}
