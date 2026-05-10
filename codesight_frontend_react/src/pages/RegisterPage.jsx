import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
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
      await register(email, password);
      navigate('/projects');
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка регистрации');
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
            Создайте аккаунт, чтобы загружать репозитории, отслеживать качество и получать рекомендации по улучшению.
          </p>
        </div>
        <div className="intro-footer">
          <span className="mini-card">⬡ Git URL и ZIP</span>
          <span className="mini-card">⬡ OWASP / CWE</span>
          <span className="mini-card">⬡ Архитектурные метрики</span>
        </div>
      </div>

      <div className="auth-wrap">
        <div className="auth-card">
          <h2>Создать аккаунт</h2>
          <p>Зарегистрируйтесь, чтобы начать анализ</p>
          {error && <div style={{ marginBottom: 16, padding: '12px 14px', borderRadius: 12, background: 'var(--error-bg)', color: 'var(--error-text)', fontSize: 14 }}>{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" className="input" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="password">Пароль</label>
              <input id="password" className="input" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} disabled={loading}>
              {loading ? 'Создаём...' : 'Зарегистрироваться'}
            </button>
          </form>
          <p style={{ marginTop: 20, textAlign: 'center', fontSize: 14, color: 'var(--muted)' }}>
            Уже есть аккаунт? <Link to="/login" style={{ color: 'var(--primary)', fontWeight: 600 }}>Войти</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
