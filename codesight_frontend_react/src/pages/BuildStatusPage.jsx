import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle, Loader, XCircle } from 'lucide-react';
import { getProject } from '../api/projects';

const STAGES = [
  { id: 'upload', label: 'Загрузка', desc: 'Файлы проекта' },
  { id: 'static', label: 'Статика', desc: 'Ruff, Radon, mypy' },
  { id: 'security', label: 'Безопасность', desc: 'Bandit, Semgrep' },
  { id: 'arch', label: 'Архитектура', desc: 'Граф зависимостей' },
  { id: 'ai', label: 'AI-анализ', desc: 'GigaChat агент' },
];

const SAMPLE_LOGS = [
  { type: 'info', text: '[10:32:01] INFO Starting analysis pipeline...' },
  { type: 'success', text: '[10:32:03] OK Project files extracted successfully' },
  { type: 'info', text: '[10:32:05] INFO Running Ruff linter...' },
  { type: 'success', text: '[10:32:08] OK Ruff completed: 3 issues found' },
  { type: 'warning', text: '[10:32:13] WARN High complexity in auth/service.py (CC=18)' },
  { type: 'info', text: '[10:32:14] INFO Running Bandit security scan...' },
  { type: 'error', text: '[10:32:19] ERR Bandit: 1 HIGH severity issue detected' },
  { type: 'success', text: '[10:32:45] OK AI analysis complete' },
];

const LOG_CLASS = {
  success: 'log-line-success',
  warning: 'log-line-warning',
  error: 'log-line-error',
  info: 'log-line-info',
};

export default function BuildStatusPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [logLines, setLogLines] = useState([]);
  const logRef = useRef(null);

  useEffect(() => {
    getProject(id).then((response) => setProject(response.data)).catch(() => {});
    const interval = setInterval(() => {
      getProject(id).then((response) => setProject(response.data)).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    let index = 0;
    const timer = setInterval(() => {
      if (index < SAMPLE_LOGS.length) {
        setLogLines((current) => [...current, SAMPLE_LOGS[index]]);
        index += 1;
      } else {
        clearInterval(timer);
      }
    }, 800);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logLines]);

  const status = project?.status || 'running';
  const isRunning = status === 'running' || status === 'pending';
  const progress = status === 'completed' ? 100 : status === 'failed' ? 60 : 68;

  const stageClass = (index) => {
    if (status === 'completed') return 'stage-success';
    if (status === 'failed') return index < 3 ? 'stage-success' : index === 3 ? 'stage-error' : 'stage-pending';
    return index < 2 ? 'stage-success' : index === 2 ? 'stage-running' : 'stage-pending';
  };

  return (
    <div className="container">
      <section className="hero">
        <div>
          <p className="eyebrow">Статус анализа</p>
          <h1>{project?.name || `Проект #${id || '—'}`}</h1>
          <p className="description">Следите за ходом выполнения анализа в реальном времени. После завершения вы увидите полный отчёт с результатами и рекомендациями.</p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Статус</strong>
            <span><span className={`pill ${status === 'completed' ? 'pill-success' : status === 'failed' ? 'pill-error' : 'pill-running'}`}>{status === 'completed' ? 'Завершён' : status === 'failed' ? 'Ошибка' : 'Выполняется'}</span></span>
          </div>
          <div className="meta-box">
            <strong>Прогресс</strong>
            <span style={{ fontSize: 22, fontWeight: 700 }}>{progress}%</span>
          </div>
        </div>
      </section>

      <div className="card">
        <div className="section-header">
          <div>
            <h2>Прогресс выполнения</h2>
            <p>Все шаги анализа проекта</p>
          </div>
          {isRunning && <span className="pill pill-running"><Loader size={12} style={{ marginRight: 4 }} />Выполняется</span>}
          {status === 'completed' && <span className="pill pill-success"><CheckCircle size={12} style={{ marginRight: 4 }} />Готово</span>}
          {status === 'failed' && <span className="pill pill-error"><XCircle size={12} style={{ marginRight: 4 }} />Ошибка</span>}
        </div>
        <div className="bar-wrap">
          <div className="bar-top"><span>Общий прогресс</span><span>{progress}%</span></div>
          <div className="bar"><span className="bar-fill" style={{ width: `${progress}%` }} /></div>
        </div>
        <div className="stages">
          {STAGES.map((stage, index) => (
            <div key={stage.id} className={`stage ${stageClass(index)}`}>
              <strong>{stage.label}</strong>
              <span>{stage.desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="log-card">
        <div className="log-top">
          <h3 style={{ margin: 0 }}>Логи выполнения</h3>
          <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 13 }}>Поток событий анализа</p>
        </div>
        <div className="log-body" ref={logRef}>
          {logLines.map((line, index) => <div key={index} className={LOG_CLASS[line.type]}>{line.text}</div>)}
          {isRunning && <div style={{ color: 'var(--primary)' }}>█</div>}
        </div>
      </div>

      {status === 'completed' && (
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button className="btn btn-primary" onClick={() => navigate(`/projects/${id}/report`)}>Смотреть результаты →</button>
        </div>
      )}
    </div>
  );
}
