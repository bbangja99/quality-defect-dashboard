import { describe, expect, it } from "vitest";
import { aggregateProduction, weeklySummary } from "./quality.js";

describe("25주차 품질 집계", () => {
  it("관리본 평균·가중 불량률과 일치한다", () => {
    const meta = { year: 2026, week: "26-W25", weekNum: 202625 };
    const production = [
      { ...meta, process: "Kopac", inputQty: 235836, defectQty: 852, lossQty: 1284 },
      { ...meta, process: "주사침", inputQty: 429057, defectQty: 2501, lossQty: 559 },
      { ...meta, process: "사출 통합", inputQty: 2837421, defectQty: 5251, lossQty: 0 },
      { ...meta, process: "연마", inputQty: 339230, defectQty: 580, lossQty: 20850 },
    ];
    const result = weeklySummary(aggregateProduction(production))[0];
    expect(result.complete).toBe(true);
    expect(result.totalInput).toBe(3841544);
    expect(result.totalDefect).toBe(9184);
    expect(result.totalLoss).toBe(22693);
    expect(result.avgDefectRate).toBeCloseTo(0.003250530248025093, 12);
    expect(result.weightedDefectRate).toBeCloseTo(0.002390705403868861, 12);
  });
});
