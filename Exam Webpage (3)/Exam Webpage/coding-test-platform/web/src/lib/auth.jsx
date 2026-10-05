import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, auth as store, homeFor, onUnauthorized } from "./api.js";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => store.user());
  const navigate = useNavigate();

  // A 401 anywhere drops the session and returns to the login screen.
  useEffect(() => {
    onUnauthorized.handler = () => {
      setUser(null);
      navigate("/login?expired=1", { replace: true });
    };
    return () => { onUnauthorized.handler = null; };
  }, [navigate]);

  const login = useCallback(async (body) => {
    const data = await api("POST", "/api/reios/auth/login", body, { retry: true });
    store.save(data.access_token, data.user);
    setUser(data.user);
    return data.user;
  }, []);

  const loginWithFirebase = useCallback(async (idToken) => {
    const data = await api("POST", "/api/reios/auth/firebase", { id_token: idToken }, { retry: true });
    store.save(data.access_token, data.user);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    store.clear();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  /** Refresh the cached user after a profile or password change. */
  const refresh = useCallback((token, nextUser) => {
    if (token) store.save(token, nextUser);
    setUser(nextUser);
  }, []);

  const value = useMemo(() => ({ user, login, loginWithFirebase, logout, refresh }),
    [user, login, loginWithFirebase, logout, refresh]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function RequireRole({ roles, children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!store.token() || !user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return children;
}
