import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  clearApiKey,
  getApiKey,
  onAuth401,
  setApiKey,
  validateApiKey,
} from "../api/client";

interface AuthState {
  authRequired: boolean | null;
  authenticated: boolean;
  checking: boolean;
  login: (key: string, persist: boolean) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authRequired, setAuthRequired] = useState<boolean | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const mountedRef = useRef(true);

  // Probe /health (raw fetch, no Bearer)
  useEffect(() => {
    mountedRef.current = true;
    (async () => {
      try {
        const res = await fetch("/health");
        const data = await res.json();
        if (!mountedRef.current) return;

        const required = data.auth_required === true;
        setAuthRequired(required);

        if (!required) {
          setAuthenticated(true);
          setChecking(false);
          return;
        }

        const storedKey = getApiKey();
        if (storedKey) {
          const valid = await validateApiKey(storedKey);
          if (!mountedRef.current) return;
          setAuthenticated(valid);
          if (!valid) clearApiKey();
        }
      } catch {
        // API unreachable — degrade gracefully, don't lock out
        if (mountedRef.current) {
          setAuthRequired(false);
          setAuthenticated(true);
        }
      } finally {
        if (mountedRef.current) setChecking(false);
      }
    })();
    return () => { mountedRef.current = false; };
  }, []);

  // Subscribe to 401 events from the api() client
  useEffect(() => onAuth401(() => setAuthenticated(false)), []);

  const login = useCallback(async (key: string, persist: boolean): Promise<boolean> => {
    const valid = await validateApiKey(key);
    if (valid) {
      setApiKey(key, persist);
      setAuthenticated(true);
    }
    return valid;
  }, []);

  const logout = useCallback(() => {
    clearApiKey();
    setAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ authRequired, authenticated, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
