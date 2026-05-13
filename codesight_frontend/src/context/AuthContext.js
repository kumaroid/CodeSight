import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { loginRequest, meRequest, registerRequest } from '../api/auth';

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  access: 'access_token',
  refresh: 'refresh_token',
};

const persistTokens = (data) => {
  if (data?.access_token) {
    localStorage.setItem(STORAGE_KEYS.access, data.access_token);
  }
  if (data?.refresh_token) {
    localStorage.setItem(STORAGE_KEYS.refresh, data.refresh_token);
  }
};

const clearTokens = () => {
  localStorage.removeItem(STORAGE_KEYS.access);
  localStorage.removeItem(STORAGE_KEYS.refresh);
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const token = localStorage.getItem(STORAGE_KEYS.access);
    if (!token) {
      setUser(null);
      return null;
    }
    try {
      const response = await meRequest();
      setUser(response.data);
      return response.data;
    } catch {
      clearTokens();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      await refreshMe();
      if (isMounted) setLoading(false);
    })();
    return () => {
      isMounted = false;
    };
  }, [refreshMe]);

  const login = async (email, password) => {
    const response = await loginRequest(email, password);
    persistTokens(response.data);
    const me = await refreshMe();
    if (!me) setUser({ email });
    return response.data;
  };

  const register = async (email, password) => {
    const response = await registerRequest(email, password);
    persistTokens(response.data);
    const me = await refreshMe();
    if (!me) setUser({ email });
    return response.data;
  };

  const logout = () => {
    clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
