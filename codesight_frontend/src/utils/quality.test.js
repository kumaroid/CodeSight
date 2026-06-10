/**
 * Standalone smoke-тесты формулы качества.
 * Запуск: `node src/utils/quality.test.js` (или `npm test`).
 * Тест-раннер не используется — оставляем фронтенд без лишних dev-deps.
 */

import assert from 'node:assert/strict';
import {
  computeQualityScore,
  architectureHealthFromRecommendations,
  dastHealthFromRun,
} from './quality.js';

const cases = [];
function test(name, fn) {
  cases.push({ name, fn });
}

const mkFindings = ({ critical = 0, high = 0, medium = 0, low = 0 } = {}) => [
  ...Array.from({ length: critical }, () => ({ severity: 'critical' })),
  ...Array.from({ length: high }, () => ({ severity: 'high' })),
  ...Array.from({ length: medium }, () => ({ severity: 'medium' })),
  ...Array.from({ length: low }, () => ({ severity: 'low' })),
];

// --- 1. Базовая структура ---------------------------------------------------

test('пустой ввод → все breakdown и total = 100', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: { coverage_percent: 100 },
    dastRun: { findings_total: 0, findings_errors: 0, findings_warnings: 0 },
  });
  assert.equal(q.total, 100);
  assert.deepEqual(q.breakdown, {
    code: 100,
    security: 100,
    architecture: 100,
    tests: 100,
    dynamic: 100,
  });
});

test('форма ответа: total число и breakdown с пятью полями', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  assert.equal(typeof q.total, 'number');
  assert.deepEqual(Object.keys(q.breakdown).sort(), [
    'architecture',
    'code',
    'dynamic',
    'security',
    'tests',
  ]);
});

// --- 2. Security ------------------------------------------------------------

test('шумный security medium не зануляет балл (3 high · 16 medium · 1 low)', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: mkFindings({ high: 3, medium: 16, low: 1 }),
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  // ожидаем: 100 - 0 - 12 - min(25, 19.2) - min(5, 0.2) = 68.6 → 69
  assert.equal(q.breakdown.security, 69);
  assert.ok(
    q.breakdown.security >= 65 && q.breakdown.security <= 75,
    `security вышел из ожидаемого диапазона: ${q.breakdown.security}`,
  );
});

test('один critical security сильно бьёт, но не до нуля', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: mkFindings({ critical: 1, medium: 5 }),
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  // ожидаем: 100 - 18 - 0 - min(25, 6) - 0 = 76 → 76
  assert.equal(q.breakdown.security, 76);
});

test('много critical security всё ещё ощутимо валит балл', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: mkFindings({ critical: 5 }),
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  // 100 - 90 = 10
  assert.equal(q.breakdown.security, 10);
});

test('очень много critical security → 0', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: mkFindings({ critical: 20 }),
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  assert.equal(q.breakdown.security, 0);
});

// --- 3. Code (SAST) ---------------------------------------------------------

test('40 medium ruff-findings → код = 75 (cap 25)', () => {
  const q = computeQualityScore({
    codeIssues: mkFindings({ medium: 40 }),
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  // 100 - min(25, 40*1.2) - 0 = 75
  assert.equal(q.breakdown.code, 75);
});

// --- 4. Architecture --------------------------------------------------------

test('20 warning архитектурных рекомендаций → 80 (cap 20)', () => {
  const score = architectureHealthFromRecommendations(
    Array.from({ length: 20 }, () => ({ severity: 'warning' })),
  );
  // 100 - min(20, 20*3) = 80
  assert.equal(score, 80);
});

test('бекенд прислал готовый arch health score — рекомендации игнорируются', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: { architecture_health_score: 73 },
    archRecommendations: Array.from({ length: 10 }, () => ({ severity: 'critical' })),
    testingRun: null,
    dastRun: null,
  });
  assert.equal(q.breakdown.architecture, 73);
});

// --- 5. DAST ----------------------------------------------------------------

test('DAST: 20 warnings без errors → 82 (cap 18)', () => {
  const score = dastHealthFromRun({
    findings_errors: 0,
    findings_warnings: 20,
  });
  // 100 - min(18, 20*2) = 82
  assert.equal(score, 82);
});

test('DAST: null прогон → balance.dynamic = 100', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  assert.equal(q.breakdown.dynamic, 100);
});

// --- 6. Tests ---------------------------------------------------------------

test('coverage прокидывается напрямую (73.4 → 73)', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: { coverage_percent: 73.4 },
    dastRun: null,
  });
  assert.equal(q.breakdown.tests, 73);
});

test('нет тестового прогона → breakdown.tests = 100 (нейтрально)', () => {
  const q = computeQualityScore({
    codeIssues: [],
    securityFindings: [],
    archSummary: null,
    archRecommendations: [],
    testingRun: null,
    dastRun: null,
  });
  assert.equal(q.breakdown.tests, 100);
});

// --- 7. Round + clamp -------------------------------------------------------

test('огромное число findings всё равно даёт неотрицательный результат', () => {
  const q = computeQualityScore({
    codeIssues: mkFindings({ high: 100, medium: 200, low: 500 }),
    securityFindings: mkFindings({ critical: 50, high: 50 }),
    archSummary: null,
    archRecommendations: [],
    testingRun: { coverage_percent: 0 },
    dastRun: { findings_errors: 50, findings_warnings: 50 },
  });
  for (const v of Object.values(q.breakdown)) {
    assert.ok(v >= 0 && v <= 100, `breakdown out of range: ${v}`);
  }
  assert.ok(q.total >= 0 && q.total <= 100);
});

// --- Runner -----------------------------------------------------------------

let failed = 0;
for (const { name, fn } of cases) {
  try {
    fn();
    console.log(`  ok  · ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`FAIL  · ${name}`);
    console.error(err?.stack || err);
  }
}

console.log(`\n${cases.length - failed}/${cases.length} passed`);
if (failed > 0) process.exit(1);
