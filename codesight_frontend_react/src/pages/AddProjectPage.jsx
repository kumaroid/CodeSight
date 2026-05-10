import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, GitBranch, Upload } from 'lucide-react';
import { uploadRepo, uploadZip } from '../api/projects';

function CheckboxItem({ label, desc, defaultChecked = true }) {
  const [checked, setChecked] = useState(defaultChecked);
  return (
    <div className={`checkbox-item ${checked ? 'checked' : ''}`} onClick={() => setChecked((value) => !value)}>
      <div className="checkbox-box">
        {checked && <Check size={12} color="white" />}
      </div>
      <div className="checkbox-label">
        <strong>{label}</strong>
        <span>{desc}</span>
      </div>
    </div>
  );
}

export default function AddProjectPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [tab, setTab] = useState('url');
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const handleDrop = (event) => {
    event.preventDefault();
    setDrag(false);
    const droppedFile = event.dataTransfer.files[0];
    if (droppedFile?.name.endsWith('.zip')) setFile(droppedFile);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (tab === 'url') {
        const response = await uploadRepo({ repo_url: repoUrl, branch });
        navigate(`/projects/${response.data.id}/status`);
        return;
      }

      if (!file) {
        setError('Выберите ZIP-файл');
        setLoading(false);
        return;
      }

      const formData = new FormData();
      formData.append('file', file);
      const response = await uploadZip(formData, (eventData) => {
        if (!eventData.total) return;
        setProgress(Math.round((eventData.loaded / eventData.total) * 100));
      });
      navigate(`/projects/${response.data.id}/status`);
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка загрузки');
      setLoading(false);
    }
  };

  return (
    <>
      <div className="topbar">
        <div className="page-title">
          <h1>Добавить проект</h1>
          <p>Загрузите проект для комплексного анализа качества кода</p>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate('/projects')}>Отмена</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20, alignItems: 'start' }}>
        <form onSubmit={handleSubmit}>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-header">
              <div>
                <h2>Источник проекта</h2>
                <p>Выберите способ загрузки кода</p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
              {[
                { id: 'url', label: 'Git URL', icon: GitBranch },
                { id: 'zip', label: 'ZIP-архив', icon: Upload },
              ].map(({ id, label, icon: Icon }) => (
                <button key={id} type="button" className={`btn ${tab === id ? 'btn-primary' : 'btn-secondary'}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={() => setTab(id)}>
                  <Icon size={15} /> {label}
                </button>
              ))}
            </div>

            {tab === 'url' ? (
              <>
                <div className="field">
                  <label>URL репозитория</label>
                  <input className="input" type="url" placeholder="https://github.com/user/repo" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} required />
                </div>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label>Ветка</label>
                  <input className="input" value={branch} onChange={(e) => setBranch(e.target.value)} />
                </div>
              </>
            ) : (
              <div className={`upload-zone ${drag ? 'drag' : ''}`} onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={handleDrop} onClick={() => fileRef.current?.click()}>
                <input ref={fileRef} type="file" accept=".zip" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files[0])} />
                <div className="upload-zone-icon"><Upload size={48} /></div>
                {file ? <p><strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(1)} МБ)</p> : <p><strong>Перетащите ZIP-файл</strong> или нажмите для выбора</p>}
                <p style={{ fontSize: 12, marginTop: 4 }}>Максимум 50 МБ</p>
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-header">
              <div>
                <h2>Параметры анализа</h2>
                <p>Настройте модули, которые будут применены</p>
              </div>
            </div>
            <div className="checkbox-group">
              <CheckboxItem label="Статический анализ" desc="Ruff, Radon, mypy — качество и стиль кода" />
              <CheckboxItem label="Анализ безопасности" desc="Bandit, Semgrep — OWASP Top 10, CWE Top 25" />
              <CheckboxItem label="Архитектурная связность" desc="Граф зависимостей, hotspot-модули" />
              <CheckboxItem label="AI-рекомендации" desc="LangGraph + GigaChat — приоритизация проблем" />
            </div>
          </div>

          {error && <div style={{ marginBottom: 16, padding: '12px 14px', borderRadius: 12, background: 'var(--error-bg)', color: 'var(--error-text)', fontSize: 14 }}>{error}</div>}

          {loading && progress > 0 && (
            <div className="bar-wrap" style={{ marginBottom: 16 }}>
              <div className="bar-top"><span>Загрузка...</span><span>{progress}%</span></div>
              <div className="bar"><span className="bar-fill" style={{ width: `${progress}%` }} /></div>
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? 'Загружаем...' : '▶ Запустить анализ'}
          </button>
        </form>

        <div style={{ display: 'grid', gap: 16 }}>
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Что будет проверено</h3>
            {[
              { title: 'Качество кода', desc: 'Сложность, стиль, типы' },
              { title: 'Безопасность', desc: 'OWASP, CWE, ASVS' },
              { title: 'Архитектура', desc: 'Связность модулей' },
              { title: 'AI-отчёт', desc: 'Рекомендации и приоритеты' },
            ].map(({ title, desc }) => (
              <div key={title} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 12 }}>
                <span style={{ fontSize: 18, color: 'var(--primary)', flexShrink: 0 }}>⬡</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="card">
            <h3 style={{ marginBottom: 8 }}>Поддерживаемые форматы</h3>
            <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
              GitHub, GitLab, Bitbucket и любые Git-репозитории.
              <br />
              ZIP-архивы до 50 МБ.
              <br />
              Язык: Python 3.10+
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
