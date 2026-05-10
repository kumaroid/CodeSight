import { createContext, useContext, useEffect, useState } from 'react';
import { loginRequest, meRequest, registerRequest } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      return;
    }

    meRequest()
      .then((response) => setUser(response.data))
      .catch(() => {
        localStorage.removeItem('access_token');
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const response = await loginRequest(email, password);
    localStorage.setItem('access_token', response.data.access_token);
    if (response.data.user) {
      setUser(response.data.user);
    } else {
      setUser({ email });
    }
    return response.data;
  };

  const register = async (email, password) => {
    const response = await registerRequest(email, password);
    localStorage.setItem('access_token', response.data.access_token);
    if (response.data.user) {
      setUser(response.data.user);
    } else {
      setUser({ email });
    }
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
