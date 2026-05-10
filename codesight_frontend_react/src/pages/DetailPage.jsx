import { useNavigate, useParams } from 'react-router-dom';

export default function DetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Детали проекта</div>
          <h1>Проект backend-api #{id}</h1>
          <p className="description">Карточка проекта объединяет статус, последние результаты и быстрые переходы к специализированным отчётам анализа.</p>
        </div>
        <div className="hero-side">
          <div className="meta-box"><strong>Статус</strong><span><span className="pill pill-success">Готов к просмотру</span></span></div>
          <div className="meta-box"><strong>Источник</strong><span>GitHub repository</span></div>
        </div>
      </section>

      <section className="analysis-grid">
        <article className="analysis-card">
          <div className="analysis-icon">◫</div>
          <h3>Итоговый dashboard</h3>
          <p>Сводные метрики качества, coverage, security и архитектурные риски.</p>
          <button className="btn btn-primary" onClick={() => navigate(`/projects/${id}/report`)}>Открыть отчёт</button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">🔒</div>
          <h3>Security анализ</h3>
          <p>OWASP Top 10, CWE Top 25, уязвимости зависимостей и рекомендации.</p>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/security`)}>Открыть security</button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">◎</div>
          <h3>Архитектурный анализ</h3>
          <p>Граф связности, hotspot-модули и предложения по рефакторингу.</p>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/architecture`)}>Открыть архитектуру</button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">▶</div>
          <h3>Перезапуск анализа</h3>
          <p>Перейти к экрану статуса и запустить новый проход по проекту.</p>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/status`)}>Открыть статус</button>
        </article>
      </section>
    </div>
  );
}
