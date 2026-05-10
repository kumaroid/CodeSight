import { NavLink, useNavigate } from 'react-router-dom';
import { BarChart2, FolderOpen, LogOut, Play, Settings } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const navItems = [
  { to: '/projects', icon: FolderOpen, label: 'Проекты' },
  { to: '/reports', icon: BarChart2, label: 'Отчёты' },
  { to: '/runs', icon: Play, label: 'Запуски анализа' },
  { to: '/settings', icon: Settings, label: 'Настройки' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initials = user?.email?.slice(0, 2).toUpperCase() || 'CS';

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">CS</div>
        <div>
          <div className="brand-name">CodeSight</div>
          <div className="brand-sub">Workspace</div>
        </div>
      </div>

      <nav className="nav">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span className="nav-icon"><Icon size={18} /></span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-spacer" />

      <div className="sidebar-user">
        <div className="user-avatar">{initials}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="user-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.email || 'Пользователь'}
          </div>
          <div className="user-email">Аналитик</div>
        </div>
        <button className="btn btn-ghost" style={{ padding: '6px', borderRadius: '10px' }} onClick={handleLogout} title="Выйти">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
