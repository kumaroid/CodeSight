import { useParams, useNavigate } from 'react-router-dom';

const trendData = [108, 124, 132, 146, 152, 160];
const issues = [
  { title: 'Высокая сложность модуля auth/service.py', severity: 'High', cls: 'pill-error', text: 'Cyclomatic complexity = 18, требуется рефакторинг сервисного слоя.' },
  { title: 'Уязвимая зависимость urllib3', severity: 'Critical', cls: 'pill-error', text: 'Зафиксирована версия зависимости с известными advisories.' },
  { title: 'Низкое покрытие tests/api/test_users.py', severity: 'Medium', cls: 'pill-warning', text: 'Покрытие критичного сценария регистрации ниже целевого уровня.' },
];

export default function ReportPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Результаты анализа</div>
          <h1>Итоговый dashboard проекта backend-api</h1>
          <p className="description">Сводный экран показывает ключевые метрики качества проекта, тренд по последним запускам, критические замечания и основные архитектурные и security-риски.</p>
        </div>
        <div className="hero-side">
          <div className="meta-box"><strong>Последний запуск</strong><span>#{id || 1843} · Completed</span></div>
          <div className="meta-box"><strong>Время анализа</strong><span>19m 42s · main branch</span></div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Ключевые показатели качества</h2>
            <p>Основные метрики, которые позволяют быстро оценить состояние проекта.</p>
          </div>
          <span className="pill pill-primary">Quality overview</span>
        </div>
        <div className="kpi-grid">
          <div className="kpi"><strong>Quality score</strong><span className="value">76</span><span className="meta">Умеренно стабильное состояние, требуется доработка security и сложности модулей.</span></div>
          <div className="kpi"><strong>Coverage</strong><span className="value">76.4%</span><span className="meta">Покрытие улучшилось на 4.1% относительно предыдущего запуска.</span></div>
          <div className="kpi"><strong>Issues</strong><span className="value">12</span><span className="meta">Из них 3 критичных и 4 средних замечания.</span></div>
          <div className="kpi"><strong>Security</strong><span className="value">5</span><span className="meta">Найдены уязвимые зависимости и одно критичное предупреждение.</span></div>
          <div className="kpi"><strong>Coupling</strong><span className="value">0.68</span><span className="meta">Связность модулей выше желаемого порога для API-слоя.</span></div>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="stack">
          <article className="card">
            <h3>Динамика показателей</h3>
            <p>Изменение интегрального качества по последним запускам анализа.</p>
            <div className="trend-panel">
              {trendData.map((value, index) => (
                <div className="trend-col" key={index}>
                  <div className="trend-bar" style={{ height: `${value}px` }} />
                  <span>{`Run ${1798 + index * 9}`}</span>
                </div>
              ))}
            </div>
          </article>

          <div className="detail-grid">
            <article className="card">
              <h3>Критические замечания</h3>
              <p>Список проблем, на которые нужно обратить внимание в первую очередь.</p>
              <div className="issue-list">
                {issues.map((issue) => (
                  <div className="issue" key={issue.title}>
                    <div className="issue-top"><strong>{issue.title}</strong><span className={`pill ${issue.cls}`}>{issue.severity}</span></div>
                    <small>{issue.text}</small>
                  </div>
                ))}
              </div>
            </article>

            <article className="card">
              <h3>Архитектурная сводка</h3>
              <p>Свод по основным модулям и рискам связности.</p>
              <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                <div className="vuln-row"><strong>api/auth</strong><small>Coupling 0.74 · Cohesion 0.41</small><span className="pill pill-error">Risk</span></div>
                <div className="vuln-row"><strong>services/users</strong><small>Coupling 0.63 · Cohesion 0.52</small><span className="pill pill-warning">Review</span></div>
                <div className="vuln-row"><strong>repositories/base</strong><small>Coupling 0.38 · Cohesion 0.71</small><span className="pill pill-success">Stable</span></div>
              </div>
            </article>
          </div>
        </div>

        <aside className="stack">
          <article className="card" style={{ textAlign: 'center' }}>
            <h3>Интегральная оценка</h3>
            <p>Итоговый score с разложением по ключевым направлениям.</p>
            <div className="score-ring">
              <div className="score-content"><span className="big">76</span><span className="sub">из 100</span></div>
            </div>
            <div className="legend">
              <div className="legend-row"><div className="legend-left"><span className="dot dot-primary" /><span>Code quality</span></div><strong>81</strong></div>
              <div className="legend-row"><div className="legend-left"><span className="dot dot-success" /><span>Test health</span></div><strong>78</strong></div>
              <div className="legend-row"><div className="legend-left"><span className="dot dot-warning" /><span>Security</span></div><strong>65</strong></div>
              <div className="legend-row"><div className="legend-left"><span className="dot dot-error" /><span>Architecture</span></div><strong>69</strong></div>
            </div>
          </article>

          <article className="card">
            <h3>Навигация по отчётам</h3>
            <p>Перейдите к специализированным экранам анализа.</p>
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/security`)}>Открыть Security анализ</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/architecture`)}>Открыть Архитектуру</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}`)}>Открыть детали проекта</button>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
