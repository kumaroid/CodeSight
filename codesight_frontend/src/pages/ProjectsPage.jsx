import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Code2, Eye, FolderOpen, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { deleteProject, getProjects } from '../api/projects';
import { listSagasForProject } from '../api/orchestrator';
import { PROJECT_STATUS, SAGA_STATUS, formatDate } from '../utils/status';

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [sagasByProject, setSagasByProject] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [toast, setToast] = useState('');
  const navigate = useNavigate();

  const loadProjects = async () => {
    setLoading(true);
    try {
      const items = await getProjects();
      setProjects(items);
      const results = await Promise.allSettled(items.map((p) => listSagasForProject(p.id)));
      const map = {};
      results.forEach((res, idx) => {
        if (res.status === 'fulfilled') map[items[idx].id] = res.value[0] || null;
      });
      setSagasByProject(map);
    } catch (e) {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleDelete = async (id, event) => {
    event.stopPropagation();
    if (!window.confirm('Удалить проект и все его результаты?')) return;
    try {
      await deleteProject(id);
      setProjects((current) => current.filter((item) => item.id !== id));
      setToast('Проект удалён');
    } catch {
      setToast('Не удалось удалить проект');
    } finally {
      setTimeout(() => setToast(''), 3000);
    }
  };

  const filteredProjects = projects.filter((project) => {
    const source = `${project.name || ''} ${project.repo_url || ''}`.toLowerCase();
    return source.includes(search.toLowerCase());
  });

  const stats = {
    total: projects.length,
    completed: Object.values(sagasByProject).filter((s) => s?.status === 'completed').length,
    running: Object.values(sagasByProject).filter(
      (s) => s?.status === 'running' || s?.status === 'pending',
    ).length,
  };

  const renderStatus = (project) => {
    const saga = sagasByProject[project.id];
    if (saga) {
      const meta = SAGA_STATUS[saga.status] || { label: saga.status, cls: 'pill-neutral' };
      return <span className={`pill ${meta.cls}`}>{meta.label}</span>;
    }
    const meta = PROJECT_STATUS[project.status] || { label: project.status || '—', cls: 'pill-neutral' };
    return <span className={`pill ${meta.cls}`}>{meta.label}</span>;
  };

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--muted)' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загрузка проектов...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="topbar">
        <div className="page-title">
          <h1>Проекты</h1>
          <p>Управляйте проектами и запускайте анализ качества кода</p>
        </div>
        <div className="top-actions" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search">
            <Search size={16} />
            <input placeholder="Найти проект..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <button className="btn btn-secondary" onClick={loadProjects}>
            <RefreshCw size={15} style={{ marginRight: 6 }} />Обновить
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/projects/add')}>
            <Plus size={15} style={{ marginRight: 6 }} />Добавить проект
          </button>
        </div>
      </div>

      <div className="stats">
        <div className="stat-card">
          <div className="stat-label">Всего проектов</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-note">В вашем workspace</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Завершённых анализов</div>
          <div className="stat-value" style={{ color: 'var(--success-text)' }}>{stats.completed}</div>
          <div className="stat-note">Доступны результаты</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Выполняется сейчас</div>
          <div className="stat-value" style={{ color: 'var(--primary)' }}>{stats.running}</div>
          <div className="stat-note">Активных запусков</div>
        </div>
      </div>

      <div className="table-card">
        <div className="table-toolbar">
          <strong>Все проекты ({filteredProjects.length})</strong>
        </div>

        {filteredProjects.length === 0 ? (
          <div className="empty-state">
            <FolderOpen size={48} />
            <h3>Нет проектов</h3>
            <p>Добавьте первый проект для анализа</p>
            <button className="btn btn-primary" onClick={() => navigate('/projects/add')}>
              <Plus size={15} style={{ marginRight: 6 }} />Добавить проект
            </button>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Проект</th>
                <th>Источник</th>
                <th>Статус</th>
                <th>Загружен</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((project) => (
                <tr key={project.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/projects/${project.id}`)}>
                  <td>
                    <div className="project-cell">
                      <div className="project-icon"><Code2 size={18} /></div>
                      <div>
                        <div className="project-name">{project.name || 'Без названия'}</div>
                        <div className="project-meta">{project.repo_url || project.storage_path || '—'}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ color: 'var(--muted)', fontSize: 13 }}>{project.source_type === 'git' ? 'Git URL' : 'ZIP'}</td>
                  <td>{renderStatus(project)}</td>
                  <td style={{ color: 'var(--muted)', fontSize: 13 }}>{formatDate(project.created_at)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        className="btn btn-ghost"
                        style={{ padding: '7px 10px' }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/projects/${project.id}`); }}
                        title="Открыть"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        className="btn btn-danger"
                        style={{ padding: '7px 10px' }}
                        onClick={(e) => handleDelete(project.id, e)}
                        title="Удалить"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </>
  );
}
