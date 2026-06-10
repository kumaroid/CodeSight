export const PROJECT_STATUS = {
  pending: { label: 'Загружается', cls: 'pill-running' },
  ready: { label: 'Готов', cls: 'pill-success' },
  error: { label: 'Ошибка', cls: 'pill-error' },
};

export const SAGA_STATUS = {
  pending: { label: 'Ожидание', cls: 'pill-neutral' },
  running: { label: 'Выполняется', cls: 'pill-running' },
  completed: { label: 'Завершён', cls: 'pill-success' },
  failed: { label: 'Ошибка', cls: 'pill-error' },
  compensating: { label: 'Компенсация', cls: 'pill-warning' },
  compensated: { label: 'Откат завершён', cls: 'pill-warning' },
};

export const STEP_STATUS = {
  pending: { label: 'Ожидание', cls: 'pill-neutral', stageCls: 'stage-pending' },
  running: { label: 'Выполняется', cls: 'pill-running', stageCls: 'stage-running' },
  completed: { label: 'Готово', cls: 'pill-success', stageCls: 'stage-success' },
  failed: { label: 'Ошибка', cls: 'pill-error', stageCls: 'stage-error' },
  cancelled: { label: 'Остановлено', cls: 'pill-warning', stageCls: 'stage-pending' },
};

export const STEP_LABEL = {
  analysis: { label: 'Статический анализ', desc: 'Ruff, Bandit, mypy' },
  security: { label: 'Безопасность', desc: 'OWASP / CWE, pip-audit' },
  arch: { label: 'Архитектура', desc: 'Coupling и Cohesion' },
  testing: { label: 'Тесты', desc: 'pytest + coverage' },
  dast: { label: 'Динамика', desc: 'Байткод · импорты · pytest · RAM · deps · memcheck' },
};

export const STEPS_ORDER = ['analysis', 'security', 'arch', 'testing', 'dast'];

export const sagaStepStatus = (saga, step) =>
  (saga && saga.steps_status && saga.steps_status[step]) || 'pending';

export const sagaProgress = (saga) => {
  if (!saga || !saga.steps_status) return 0;
  const entries = Object.values(saga.steps_status);
  if (entries.length === 0) return 0;
  const done = entries.filter((s) =>
    s === 'completed' || s === 'failed' || s === 'cancelled',
  ).length;
  return Math.round((done / entries.length) * 100);
};

export const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
};
