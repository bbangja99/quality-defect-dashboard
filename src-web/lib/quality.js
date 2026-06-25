export const PROCESS_ORDER = ["Kopac", "주사침", "사출 통합", "연마"];
export const PROCESS_COLORS = {
  Kopac: "#2672ff",
  주사침: "#f59e0b",
  "사출 통합": "#16a34a",
  연마: "#e5484d",
};

export const LOSS_TYPES = {
  연마: new Set(["세팅", "QC샘플", "공정검사"]),
  주사침: new Set(["세팅소모", "QC검사", "공정검사"]),
};

export const NEEDLE_EXCLUDES = new Set([
  "3E-10", "3E-20", "VPL-2", "BSK-10", "Intracell-F",
  "지방분리용기구", "유트로핀S펜", "유트로핀바이알", "10ml외통", "10ml밀대",
  "3E-10set불량", "3E-20set불량", "VPL-2set불량", "BSK-10set불량",
  "ATACset불량", "S펜set불량", "바이알set불량",
]);

export const cleanText = (value) =>
  value == null ? "" : String(value).replace(/\s+/g, "").trim();

export const number = (value) => {
  if (value == null || value === "" || String(value).startsWith("#")) return 0;
  const parsed = Number(String(value).replaceAll(",", ""));
  return Number.isFinite(parsed) ? parsed : 0;
};

export const rate = (numerator, denominator) => denominator ? numerator / denominator : 0;

export function normalizeWeek(value, fallbackYear = 2026) {
  const text = String(value ?? "");
  const four = text.match(/(20\d{2})\s*[-_]?\s*W\s*(\d{1,2})/i);
  const two = text.match(/(\d{2})\s*[-_]\s*W\s*(\d{1,2})/i);
  const bare = text.match(/W\s*(\d{1,2})/i);
  let year;
  let week;
  if (four) [year, week] = [Number(four[1]), Number(four[2])];
  else if (two) [year, week] = [2000 + Number(two[1]), Number(two[2])];
  else if (bare) {
    week = Number(bare[1]);
    year = fallbackYear || (week >= 40 ? 2025 : 2026);
  } else {
    throw new Error(`주차를 해석할 수 없습니다: ${text}`);
  }
  return { year, week: `${String(year).slice(-2)}-W${String(week).padStart(2, "0")}`, weekNum: year * 100 + week };
}

export function weekFromFilename(name, fallback = null) {
  try {
    return normalizeWeek(name);
  } catch {
    const match = String(name).match(/(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)/);
    if (!match) return fallback;
    const date = new Date(2000 + Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    const first = new Date(Date.UTC(date.getFullYear(), 0, 4));
    const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const day = target.getUTCDay() || 7;
    target.setUTCDate(target.getUTCDate() + 4 - day);
    const week = Math.ceil((((target - first) / 86400000) + (first.getUTCDay() || 7)) / 7);
    return normalizeWeek(`${date.getFullYear()}-W${week}`);
  }
}

export function weekFromDate(date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((target - yearStart) / 86400000) + 1) / 7);
  return normalizeWeek(`${target.getUTCFullYear()}-W${week}`);
}

export function aggregateProduction(rows) {
  const map = new Map();
  for (const row of rows) {
    const key = `${row.week}|${row.process}`;
    const current = map.get(key) || {
      year: row.year, week: row.week, weekNum: row.weekNum, process: row.process,
      inputQty: 0, defectQty: 0, lossQty: 0,
    };
    current.inputQty += number(row.inputQty);
    current.defectQty += number(row.defectQty);
    current.lossQty += number(row.lossQty);
    map.set(key, current);
  }
  return [...map.values()].map((row) => ({
    ...row,
    defectRate: rate(row.defectQty, row.inputQty),
    lossRate: rate(row.lossQty, row.inputQty),
    ppm: rate(row.defectQty, row.inputQty) * 1_000_000,
  })).sort((a, b) => a.weekNum - b.weekNum || PROCESS_ORDER.indexOf(a.process) - PROCESS_ORDER.indexOf(b.process));
}

export function weeklySummary(processWeeks) {
  const map = new Map();
  for (const row of processWeeks) {
    const current = map.get(row.week) || {
      year: row.year, week: row.week, weekNum: row.weekNum, rows: [],
    };
    current.rows.push(row);
    map.set(row.week, current);
  }
  return [...map.values()].map((group) => {
    const valid = group.rows.filter((row) => row.inputQty > 0);
    const totalInput = valid.reduce((sum, row) => sum + row.inputQty, 0);
    const totalDefect = valid.reduce((sum, row) => sum + row.defectQty, 0);
    const totalLoss = valid.reduce((sum, row) => sum + row.lossQty, 0);
    const processes = new Set(valid.map((row) => row.process));
    const missing = PROCESS_ORDER.filter((process) => !processes.has(process));
    return {
      year: group.year, week: group.week, weekNum: group.weekNum,
      processCount: processes.size, complete: missing.length === 0, missing,
      totalInput, totalDefect, totalLoss,
      avgDefectRate: valid.length ? valid.reduce((sum, row) => sum + row.defectRate, 0) / valid.length : 0,
      weightedDefectRate: rate(totalDefect, totalInput),
      avgLossRate: valid.length ? valid.reduce((sum, row) => sum + row.lossRate, 0) / valid.length : 0,
      weightedLossRate: rate(totalLoss, totalInput),
    };
  }).sort((a, b) => a.weekNum - b.weekNum);
}

export function pareto(details, process, week) {
  const map = new Map();
  details
    .filter((row) => !row.isLoss && (!process || row.process === process) && (!week || row.week === week))
    .forEach((row) => map.set(row.defectType, (map.get(row.defectType) || 0) + number(row.defectQty)));
  const rows = [...map.entries()]
    .map(([defectType, defectQty]) => ({ defectType, defectQty }))
    .sort((a, b) => b.defectQty - a.defectQty);
  const total = rows.reduce((sum, row) => sum + row.defectQty, 0);
  let cumulative = 0;
  return rows.map((row) => {
    cumulative += row.defectQty;
    return { ...row, share: rate(row.defectQty, total), cumulative: rate(cumulative, total) };
  });
}
