/*
  FibEdge Premium website logic
  -----------------------------
  This file is intentionally isolated from the Classic/Clean scanner code.
  It is for the future static/Netlify dashboard layer only.

  IMPORTANT:
  - It does not calculate Fibonacci levels.
  - It does not alter scanner outputs.
  - Premium Clean is only "exact" when Recovery Efficiency is present.
  - Premium+ consumes already-confirmed scanner candidates from JSON.
*/

export const PREMIUM_CLEAN_RULES = Object.freeze({
  recoveryEfficiencyMin: 0.94
});

export const PREMIUM_PLUS_V1_RULES = Object.freeze({
  baseMinDeclinePct: 8.0,
  premiumMinDeclinePct: 15.0,
  minSwingDays: 15,
  maxLowerWickPct: 10.0,
  maxCompression3v10: 0.90,
  minCloseAbove786Pct: 2.0,
  signalTiming: "after completed daily candle",
  entryTiming: "next session"
});

const liveStatuses = new Set(["OPEN", "ENTRY AREA", "NEAR 0.786"]);

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function selectPremiumClean(rows = []) {
  const hasRecoveryField = rows.some(row =>
    Object.prototype.hasOwnProperty.call(row, "Recovery Efficiency")
  );

  if (!hasRecoveryField) {
    return {
      exact: false,
      reason: "Recovery Efficiency is not present in this live feed.",
      candidates: []
    };
  }

  const candidates = rows
    .filter(row => liveStatuses.has(String(row.Status || "").trim()))
    .filter(row => {
      const recovery = num(row["Recovery Efficiency"]);
      return recovery !== null &&
             recovery >= PREMIUM_CLEAN_RULES.recoveryEfficiencyMin;
    });

  return {
    exact: true,
    reason: null,
    candidates
  };
}

export function selectPremiumPlus(payload = {}) {
  const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  return {
    exact: true,
    candidates
  };
}
