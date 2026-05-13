import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, GitBranch, Upload } from 'lucide-react';
import { uploadRepo, uploadZip } from '../api/projects';
import { ALL_STEPS, createSaga } from '../api/orchestrator';
import { STEP_LABEL } from '../utils/status';

const STEP_DEFINITIONS = ALL_STEPS.map((id) => ({
  id,
  label: STEP_LABEL[id]?.label || id,
  desc: STEP_LABEL[id]?.desc || '',
}));

export default function AddProjectPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [tab, setTab] = useState('url');
  const [repoUrl, setRepoUrl] = useState('');
  const [projectName, setProjectName] = useState('');
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [selectedSteps, setSelectedSteps] = useState(
    () => new Set(['analysis', 'security', 'arch', 'testing']),
  );

  const toggleStep = (step) => {
    setSelectedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(step)) {
        next.delete(step);
      } else {
        next.add(step);
      }
      return next;
    });
  };

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
    setProgress(0);

    try {
      let project;
      if (tab === 'url') {
        if (!repoUrl) {
          throw new Error('Укажите URL репозитория');
        }
        project = await uploadRepo({
          repo_url: repoUrl,
          ...(projectName ? { name: projectName } : {}),
        });
      } else {
        if (!file) {
          throw new Error('Выберите ZIP-файл');
        }
        const formData = new FormData();
        formData.append('file', file);
        project = await uploadZip(formData, (eventData) => {
          if (!eventData.total) return;
          setProgress(Math.round((eventData.loaded / eventData.total) * 100));
        });
      }

      if (project?.status === 'error') {
        throw new Error(project?.error_message || 'Не удалось загрузить проект');
      }

      const steps = Array.from(selectedSteps);
      if (steps.length > 0 && project?.id) {
        try {
          const saga = await createSaga(project.id, steps);
          navigate(`/projects/${project.id}/status?saga=${saga.saga_id}`);
          return;
        } catch (sagaError) {
          const detail = sagaError.response?.data?.detail || sagaError.message;
          setError(`Проект загружен, но не удалось запустить анализ: ${detail}`);
        }
      }

      navigate(`/projects/${project.id}/status`);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="topbar">
        <div className="page-title">
          <h1>Добавить проект</h1>
          <p>Загрузите проект и выберите модули анализа</p>
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
                <button
                  key={id}
                  type="button"
                  className={`btn ${tab === id ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                  onClick={() => setTab(id)}
                >
                  <Icon size={15} /> {label}
                </button>
              ))}
            </div>

            {tab === 'url' ? (
              <>
                <div className="field">
                  <label>URL репозитория</label>
                  <input
                    className="input"
                    type="url"
                    placeholder="https://github.com/user/repo"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    required
                  />
                </div>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label>Имя проекта (необязательно)</label>
                  <input
                    className="input"
                    placeholder="будет получено из URL"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                  />
                </div>
              </>
            ) : (
              <div
                className={`upload-zone ${drag ? 'drag' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".zip"
                  style={{ display: 'none' }}
                  onChange={(e) => setFile(e.target.files[0])}
                />
                <div className="upload-zone-icon"><Upload size={48} /></div>
                {file ? (
                  <p><strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(1)} МБ)</p>
                ) : (
                  <p><strong>Перетащите ZIP-файл</strong> или нажмите для выбора</p>
                )}
                <p style={{ fontSize: 12, marginTop: 4 }}>Максимум 50 МБ</p>
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-header">
              <div>
                <h2>Параметры анализа</h2>
                <p>Будут запущены после загрузки проекта</p>
              </div>
            </div>
            <div className="checkbox-group">
              {STEP_DEFINITIONS.map(({ id, label, desc }) => {
                const checked = selectedSteps.has(id);
                return (
                  <div
                    key={id}
                    className={`checkbox-item ${checked ? 'checked' : ''}`}
                    onClick={() => toggleStep(id)}
                  >
                    <div className="checkbox-box">
                      {checked && <Check size={12} color="white" />}
                    </div>
                    <div className="checkbox-label">
                      <strong>{label}</strong>
                      <span>{desc}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {error && (
            <div style={{
              marginBottom: 16, padding: '12px 14px', borderRadius: 12,
              background: 'var(--error-bg)', color: 'var(--error-text)', fontSize: 14,
            }}>
              {error}
            </div>
          )}

          {loading && progress > 0 && (
            <div className="bar-wrap" style={{ marginBottom: 16 }}>
              <div className="bar-top"><span>Загрузка...</span><span>{progress}%</span></div>
              <div className="bar"><span className="bar-fill" style={{ width: `${progress}%` }} /></div>
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? 'Загружаем...' : '▶ Загрузить и запустить анализ'}
          </button>
        </form>

        <div style={{ display: 'grid', gap: 16 }}>
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Что будет проверено</h3>
            {STEP_DEFINITIONS.map(({ id, label, desc }) => (
              <div key={id} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 12 }}>
                <span style={{ fontSize: 18, color: 'var(--primary)', flexShrink: 0 }}>⬡</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{label}</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="card">
            <h3 style={{ marginBottom: 8 }}>Поддерживаемые источники</h3>
            <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
              GitHub, GitLab, Bitbucket и любые публичные Git-репозитории.<br />
              ZIP-архивы до 50 МБ.<br />
              Язык: Python 3.10+
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
