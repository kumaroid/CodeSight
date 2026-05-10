import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/projects');
    } catch (e) {
      setError(e.response?.data?.detail || 'Неверный email или пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-intro">
        <div className="brand">
          <div className="brand-mark">CS</div>
          <div><div className="brand-name">CodeSight</div></div>
        </div>
        <div style={{ maxWidth: 560, padding: '24px 0' }}>
          <div className="tag">✦ Платформа анализа кода</div>
          <h1 style={{ margin: '0 0 18px', fontSize: 'clamp(42px, 5vw, 70px)', lineHeight: 0.98, letterSpacing: '-0.055em', maxWidth: '9ch' }}>
            Code
            <br />
            Quality
            <br />
            Insight
          </h1>
          <p style={{ margin: 0, maxWidth: '48ch', fontSize: 18, lineHeight: 1.65, color: 'var(--muted)' }}>
            Комплексный анализ качества кода: статика, безопасность, архитектурная связность и AI-рекомендации — всё в одном окне.
          </p>
        </div>
        <div className="intro-footer">
          <span className="mini-card">⬡ Статический анализ</span>
          <span className="mini-card">⬡ Безопасность OWASP</span>
          <span className="mini-card">⬡ Архитектура</span>
          <span className="mini-card">⬡ AI-рекомендации</span>
        </div>
      </div>

      <div className="auth-wrap">
        <div className="auth-card">
          <h2>Добро пожаловать</h2>
          <p>Войдите, чтобы начать анализ проектов</p>
          {error && <div style={{ marginBottom: 16, padding: '12px 14px', borderRadius: 12, background: 'var(--error-bg)', color: 'var(--error-text)', fontSize: 14 }}>{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" className="input" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="password">Пароль</label>
              <input id="password" className="input" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} disabled={loading}>
              {loading ? 'Входим...' : 'Войти'}
            </button>
          </form>
          <p style={{ marginTop: 20, textAlign: 'center', fontSize: 14, color: 'var(--muted)' }}>
            Нет аккаунта? <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 600 }}>Зарегистрироваться</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
