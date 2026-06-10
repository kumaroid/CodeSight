/**
 * Интегральная оценка качества проекта.
 *
 * Контракт и веса описаны в
 *   openspec/changes/rebalance-security-quality-score/specs/quality-scoring/spec.md
 * (после архивации change — в openspec/specs/quality-scoring/spec.md).
 *
 * Идея штрафов — "capped-linear":
 *   penalty(severity, count) = min(cap[severity], perItem[severity] * count)
 *
 * Linear по `critical`/`high` (каждая новая критичная находка должна
 * ощутимо бить), capped по `medium`/`low` — иначе шумные инструменты
 * (Bandit, regex-эвристики безопасности, ruff-замечания и т.п.)
 * зануляют направление одной только массой «жёлтых» сигналов.
 *
 * Веса (см. spec — версия 2, calibration tuned для шумных Bandit/regex):
 *   security:  critical 18 / high 4 / medium 1.2 cap 25 / low 0.2 cap 5
 *   code:                    high 4 / medium 1.2 cap 25 / low 0.2 cap 5
 *   arch:      critical 18 /         warning 3 cap 20
 *   dynamic:                 error 8 / warning 2 cap 18
 *   tests:     coverage_percent as-is (clamp 0..100)
 *
 * Итог `total = round(mean(all 5))`.
 */

export const SEVERITY_PILL = {
  critical: 'pill-error',
  high: 'pill-error',
  error: 'pill-error',
  medium: 'pill-warning',
  warning: 'pill-warning',
  low: 'pill-neutral',
  info: 'pill-primary',
};

export const severityRank = {
  critical: 4,
  high: 3,
  error: 3,
  warning: 2,
  medium: 2,
  low: 1,
  info: 0,
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const cappedPenalty = (count, perItem, cap = Infinity) =>
  Math.min(cap, (count || 0) * perItem);

const countBySeverity = (items, getSev) => {
  const acc = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  (items || []).forEach((item) => {
    const sev = (getSev(item) || '').toLowerCase();
    if (sev === 'error' || sev === 'high') acc.high += 1;
    else if (sev === 'critical') acc.critical += 1;
    else if (sev === 'medium' || sev === 'warning') acc.medium += 1;
    else if (sev === 'low') acc.low += 1;
    else acc.info += 1;
  });
  return acc;
};

/**
 * Балл архитектуры на основе списка рекомендаций.
 * Веса должны совпадать с arch_service/analyzer.py::summary_from_persisted_run
 * по духу, но с capped warning, чтобы 50 warning не валили балл в 0.
 */
export const architectureHealthFromRecommendations = (recommendations) => {
  if (!recommendations?.length) return null;
  const critical = recommendations.filter((r) => r.severity === 'critical').length;
  const warning = recommendations.filter((r) => r.severity === 'warning').length;
  const penalty =
    cappedPenalty(critical, 18) + cappedPenalty(warning, 3, 20);
  return clamp(100 - penalty, 0, 100);
};

/**
 * Балл DAST: error 10 (без cap) + warning 3 (cap 30).
 * Источники данных по приоритету:
 *   1) aggregate.findings_by_severity  (новый формат)
 *   2) findings_errors / findings_warnings (legacy)
 */
export const dastHealthFromRun = (dastRun) => {
  if (!dastRun) return null;
  const aggregate = dastRun.aggregate || {};
  const bySev = aggregate.findings_by_severity || {};
  const errors = bySev.error ?? dastRun.findings_errors ?? 0;
  const warnings = bySev.warning ?? dastRun.findings_warnings ?? 0;
  const penalty =
    cappedPenalty(errors, 8) + cappedPenalty(warnings, 2, 18);
  return clamp(100 - penalty, 0, 100);
};

export const computeQualityScore = ({
  codeIssues,
  securityFindings,
  archSummary,
  archRecommendations,
  testingRun,
  dastRun,
}) => {
  // --- Code (SAST) ---
  let codeScore = 100;
  if (codeIssues) {
    const c = countBySeverity(codeIssues, (i) => i.severity);
    const penalty =
      cappedPenalty(c.high, 4) +
      cappedPenalty(c.medium, 1.2, 25) +
      cappedPenalty(c.low, 0.2, 5);
    codeScore = clamp(100 - penalty, 0, 100);
  }

  // --- Security ---
  let secScore = 100;
  if (securityFindings) {
    const c = countBySeverity(securityFindings, (i) => i.severity);
    const penalty =
      cappedPenalty(c.critical, 18) +
      cappedPenalty(c.high, 4) +
      cappedPenalty(c.medium, 1.2, 25) +
      cappedPenalty(c.low, 0.2, 5);
    secScore = clamp(100 - penalty, 0, 100);
  }

  // --- Architecture ---
  // Если бекенд прислал готовый health-score — доверяем ему;
  // иначе считаем из рекомендаций.
  const archScore =
    typeof archSummary?.architecture_health_score === 'number'
      ? clamp(archSummary.architecture_health_score, 0, 100)
      : architectureHealthFromRecommendations(archRecommendations) ?? 100;

  // --- Tests --- coverage_percent в качестве балла (clamp 0..100).
  const coverage = testingRun?.coverage_percent;
  const testScore = typeof coverage === 'number' ? clamp(coverage, 0, 100) : 100;

  // --- Dynamic (DAST) ---
  const dastScore = dastHealthFromRun(dastRun) ?? 100;

  const parts = [codeScore, secScore, archScore, testScore, dastScore];
  const total = Math.round(parts.reduce((a, b) => a + b, 0) / parts.length);
  return {
    total,
    breakdown: {
      code: Math.round(codeScore),
      security: Math.round(secScore),
      architecture: Math.round(archScore),
      tests: Math.round(testScore),
      dynamic: Math.round(dastScore),
    },
  };
};

export const qualityFromSagaResults = (results) =>
  computeQualityScore({
    codeIssues: results?.analysis?.issues || [],
    securityFindings: results?.security?.findings || [],
    archSummary: results?.arch?.summary || null,
    archRecommendations: results?.arch?.recommendations || [],
    testingRun: results?.testing || null,
    dastRun: results?.dast || null,
  });
