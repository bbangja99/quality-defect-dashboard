import {
  LOSS_TYPES, NEEDLE_EXCLUDES, cleanText, normalizeWeek, number, rate, weekFromDate, weekFromFilename,
} from "./quality.js";

const sheetNames = (workbook) => workbook.worksheets.map((sheet) => sheet.name);
const getSheet = (workbook, name) => workbook.worksheets.find((sheet) => sheet.name === name);
const rowValues = (sheet) => {
  const rows = [];
  sheet.eachRow({ includeEmpty: true }, (row, rowNumber) => {
    rows[rowNumber - 1] = row.values.slice(1).map((value) => {
      if (value && typeof value === "object" && "result" in value) return value.result;
      if (value && typeof value === "object" && "text" in value) return value.text;
      return value ?? null;
    });
  });
  return rows;
};

const productionRow = (meta, process, model, inputQty, defectQty, lossQty = 0) => ({
  ...meta, process, model: model || null,
  inputQty, defectQty, lossQty,
  defectRate: rate(defectQty, inputQty),
  lossRate: rate(lossQty, inputQty),
});

const detailRow = (meta, process, model, defectType, defectQty, isLoss = false) => ({
  ...meta, process, model: model || null, defectType, defectQty, isLoss,
});

function parseInjection(workbook) {
  const name = sheetNames(workbook).find((sheet) => sheet.trim() === "주차별_트렌드");
  if (!name) throw new Error("사출 '주차별_트렌드' 시트를 찾지 못했습니다.");
  const rows = rowValues(getSheet(workbook, name));
  const headers = rows[0].map((value) => String(value ?? "").trim());
  const production = [];
  const details = [];
  for (const row of rows.slice(1)) {
    if (!/^W\d{1,2}$/i.test(String(row[0] ?? "").trim())) continue;
    const meta = normalizeWeek(row[0], 2026);
    const defectQty = number(row[2]);
    const inputQty = number(row[3]);
    production.push(productionRow(meta, "사출 통합", null, inputQty, defectQty, 0));
    headers.slice(4).forEach((header, index) => {
      const qty = number(row[index + 4]);
      if (header && qty) details.push(detailRow(meta, "사출 통합", null, header, qty, false));
    });
  }
  return { production, details, warnings: [] };
}

function parseGrinding(workbook, filename) {
  const name = sheetNames(workbook).find((sheet) => sheet.trim() === "불량유형");
  if (!name) throw new Error("연마 '불량유형' 시트를 찾지 못했습니다.");
  const rows = rowValues(getSheet(workbook, name));
  let meta = weekFromFilename(filename);
  for (const row of rows.slice(0, 8)) {
    const found = row.find((value) => /W\s*\d{1,2}/i.test(String(value ?? "")));
    if (found) {
      meta = normalizeWeek(found);
      break;
    }
  }
  if (!meta) throw new Error("연마 파일에서 주차를 찾지 못했습니다.");

  const production = [];
  const details = [];
  let model = null;
  let inputQty = 0;
  let defects = [];
  let collecting = false;
  const summaryLabels = new Set(["불량명", "제조번호", "투입수량", "생산수량", "불량합계", "불량율", "세팅+검사", "총손실수량", "총손실률"]);
  const flush = () => {
    if (!collecting || !defects.length) return;
    const defectQty = defects.filter(([type]) => !LOSS_TYPES.연마.has(cleanText(type))).reduce((sum, [, qty]) => sum + qty, 0);
    const lossQty = defects.filter(([type]) => LOSS_TYPES.연마.has(cleanText(type))).reduce((sum, [, qty]) => sum + qty, 0);
    production.push(productionRow(meta, "연마", model, inputQty, defectQty, lossQty));
    defects.filter(([, qty]) => qty).forEach(([type, qty]) => {
      const normalized = String(type).trim();
      details.push(detailRow(meta, "연마", model, normalized, qty, LOSS_TYPES.연마.has(cleanText(normalized))));
    });
  };

  for (const row of rows) {
    const labelIndex = row.findIndex((value) => typeof value === "string" && cleanText(value));
    if (labelIndex < 0) continue;
    const rawLabel = row[labelIndex];
    const label = cleanText(rawLabel);
    const value = row.slice(labelIndex + 1).find((item) => typeof item === "number");
    if (label.includes("불량유형분석")) {
      flush();
      model = String(rawLabel).replace(/불량\s*유형\s*분석/, "").trim();
      inputQty = 0;
      defects = [];
      collecting = false;
    } else if (label === "불량명") {
      collecting = true;
      defects = [];
    } else if (label === "투입수량") {
      inputQty = number(value);
    } else if (!summaryLabels.has(label) && collecting && rawLabel != null && value != null) {
      defects.push([String(rawLabel).trim(), number(value)]);
    }
  }
  flush();
  return { production, details, warnings: [] };
}

function parseNeedle(workbook, filename) {
  const rows = rowValues(workbook.worksheets[0]);
  let meta = weekFromFilename(filename);
  for (const row of rows.slice(0, 12)) {
    const found = row.find((value) => /W\s*\d{1,2}/i.test(String(value ?? "")));
    if (found) {
      meta = normalizeWeek(found);
      break;
    }
  }
  if (!meta) throw new Error("주사침 파일에서 주차를 찾지 못했습니다.");

  const findCell = (label, start = 0, end = rows.length, maxCol = 14) => {
    const target = cleanText(label);
    for (let r = start; r < Math.min(end, rows.length); r += 1) {
      for (let c = 0; c < Math.min(maxCol, rows[r].length); c += 1) {
        if (cleanText(rows[r][c]) === target) return { row: r, col: c };
      }
    }
    return null;
  };
  const plan = findCell("계획수량", 0, 50);
  const fit = findCell("적합수량", plan?.row ?? 0, 60);
  const totalHeader = findCell("합계", 10, 55);
  const defectHeader = findCell("불량합계", 30, 70);
  if (!plan || !fit || !totalHeader || !defectHeader) throw new Error("주사침 핵심 합계 영역을 찾지 못했습니다.");

  let managedFit = 0;
  for (let r = plan.row + 1; r < fit.row; r += 1) {
    const model = rows[r].slice(0, 4).find((value) => typeof value === "string" && cleanText(value));
    if (!model || NEEDLE_EXCLUDES.has(cleanText(model))) continue;
    managedFit += number(rows[r][totalHeader.col]);
  }

  const details = [];
  let defectQty = 0;
  let lossQty = 0;
  let excluded = 0;
  let block = "";
  for (let r = defectHeader.row + 1; r < rows.length; r += 1) {
    const blockValue = rows[r].slice(0, 2).find((value) =>
      typeof value === "string" && cleanText(value).includes("불량"));
    if (blockValue) block = cleanText(blockValue);
    const typeValue = rows[r].slice(0, 4).find((value, index) =>
      index > 0 && typeof value === "string" && cleanText(value));
    if (!typeValue) continue;
    const type = String(typeValue).trim();
    const key = cleanText(type);
    if (["총불량수량", "총로스수량"].includes(key)) continue;
    const qty = number(rows[r][defectHeader.col]);
    if (!qty) continue;
    if (LOSS_TYPES.주사침.has(key)) {
      lossQty += qty;
      details.push(detailRow(meta, "주사침", "주사침", type, qty, true));
    } else if (block.includes("의료기기") || NEEDLE_EXCLUDES.has(key) || key.includes("set불량")) {
      excluded += qty;
    } else {
      defectQty += qty;
      const model = block.includes("안과") || block.includes("범용") ? "안과·범용" : "주사침";
      details.push(detailRow(meta, "주사침", model, type, qty, false));
    }
  }
  return {
    production: [productionRow(meta, "주사침", null, managedFit + defectQty, defectQty, lossQty)],
    details,
    warnings: excluded ? [`의료기기 set 불량 ${excluded.toLocaleString()}건 제외`] : [],
  };
}

function parseKopac(workbook, filename) {
  const sheetName = sheetNames(workbook).find((sheet) => sheet.trim() === "Defect Repair Summary By Type");
  if (!sheetName) throw new Error("Kopac 불량유형 시트를 찾지 못했습니다.");
  const rows = rowValues(getSheet(workbook, sheetName));
  let meta = weekFromFilename(filename);
  if (!meta) {
    const dates = rows.flat().map((value) => {
      if (value instanceof Date) return value;
      const match = String(value ?? "").match(/(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})/);
      return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
    }).filter(Boolean);
    if (dates.length) {
      const latest = dates.sort((a, b) => b - a)[0];
      meta = weekFromDate(latest);
    }
  }
  if (!meta) throw new Error("Kopac 파일에서 주차를 찾지 못했습니다.");

  const details = [];
  for (const [start, model] of [[0, "1ml"], [6, "3ml"]]) {
    for (let r = 2; r < rows.length; r += 1) {
      const code = rows[r][start];
      const name = rows[r][start + 1];
      if ((!code && !name) || !name) break;
      const qty = number(rows[r][start + 2]);
      if (!qty) continue;
      const cleanName = String(name).replace(/\s*\([^)]*\)\s*$/, "").trim();
      details.push(detailRow(meta, "Kopac", model, cleanName, qty, String(name).includes("공정검사")));
    }
  }

  const summary = new Map();
  for (let r = 2; r < Math.min(19, rows.length); r += 1) {
    if (typeof rows[r][11] === "string" && rows[r][11].trim()) {
      summary.set(String(rows[r][11]).trim(), number(rows[r][12]));
    }
  }
  const defectTotal = [...summary.values()].reduce((sum, value) => sum + value, 0);
  const lossQty = [...summary.entries()]
    .filter(([label]) => label.includes("공정검사"))
    .reduce((sum, [, value]) => sum + value, 0);
  const defectQty = defectTotal - lossQty;

  const periodHeader = rows.findIndex((row) => row.some((value) => cleanText(value) === "기간합계"));
  const candidates = rows.slice(periodHeader + 1, periodHeader + 12)
    .flatMap((row) => row.map(number))
    .filter((value) => value > 0);
  const inputQty = candidates.length ? Math.max(...candidates) : 0;
  if (!inputQty) throw new Error("Kopac 기간합계 투입수량을 찾지 못했습니다.");

  return {
    production: [productionRow(meta, "Kopac", null, inputQty, defectQty, lossQty)],
    details,
    warnings: [],
  };
}

export function classifyWorkbook(workbook, filename) {
  const sheets = sheetNames(workbook).map((name) => name.trim());
  if (sheets.includes("주차별_트렌드") || filename.includes("사출")) return "사출";
  if (sheets.includes("불량유형") || filename.includes("연마")) return "연마";
  if (sheets.includes("Defect Repair Summary By Type") || /코팩|Kopac/i.test(filename)) return "Kopac";
  if (/주사침/.test(filename)) return "주사침";
  throw new Error("공정을 자동 판별하지 못했습니다.");
}

export async function parseFile(file) {
  const { default: ExcelJS } = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await file.arrayBuffer());
  const kind = classifyWorkbook(workbook, file.name);
  const parser = { 사출: parseInjection, 연마: parseGrinding, Kopac: parseKopac, 주사침: parseNeedle }[kind];
  return { file: file.name, kind, ...parser(workbook, file.name) };
}

export async function parseFiles(files) {
  const parsed = [];
  const errors = [];
  for (const file of files) {
    try {
      parsed.push(await parseFile(file));
    } catch (error) {
      errors.push({ file: file.name, message: error.message });
    }
  }
  const productionMap = new Map();
  const detailMap = new Map();
  parsed.forEach((result, fileIndex) => {
    result.production.forEach((row) => {
      const key = `${row.week}|${row.process}|${row.model ?? ""}`;
      productionMap.set(key, { ...row, source: result.file, fileIndex });
    });
    result.details.forEach((row) => {
      const key = `${row.week}|${row.process}|${row.model ?? ""}|${row.defectType}|${row.isLoss}`;
      detailMap.set(key, { ...row, source: result.file, fileIndex });
    });
  });
  return {
    production: [...productionMap.values()],
    details: [...detailMap.values()],
    files: parsed.map(({ file, kind, warnings }) => ({ file, kind, warnings })),
    errors,
  };
}
