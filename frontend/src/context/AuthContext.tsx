import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { User } from "../api/client";

interface AuthState {
  user: User | null;
  token: string | null;
}

interface AuthContextValue extends AuthState {
  login: (token: string, user: User) => void;
  logout: () => void;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStored(): AuthState {
  try {
    const token = localStorage.getItem("prowl_token");
    const raw = localStorage.getItem("prowl_user");
    if (token && raw) return { token, user: JSON.parse(raw) };
  } catch {}
  return { token: null, user: null };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadStored);

  const login = useCallback((token: string, user: User) => {
    localStorage.setItem("prowl_token", token);
    localStorage.setItem("prowl_user", JSON.stringify(user));
    setState({ token, user });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("prowl_token");
    localStorage.removeItem("prowl_user");
    setState({ token: null, user: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAdmin: !!state.user?.is_admin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
