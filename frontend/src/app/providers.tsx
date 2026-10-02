import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearAuth, readAuth, writeAuth } from "@/lib/session";
import { api, setUnauthorizedHandler } from "@/services/api";
import type { MeResponse, RegisterBody, TokenResponse } from "@/types/api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 },
  },
});

interface AuthContextValue {
  auth: TokenResponse | null;
  login: (email: string, password: string) => Promise<void>;
  register: (body: RegisterBody) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth phải nằm trong AuthProvider.");
  return value;
}

function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<TokenResponse | null>(() => readAuth());

  useEffect(() => {
    setUnauthorizedHandler(() => setAuth(null));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      auth,
      async login(email, password) {
        const token = await api.login(email, password);
        writeAuth(token);
        setAuth(token);
      },
      async register(body) {
        const token = await api.register(body);
        writeAuth(token);
        setAuth(token);
      },
      async logout() {
        const current = readAuth();
        if (current?.refresh_token) {
          try {
            await api.logout(current.refresh_token);
          } catch {
            /* Local session still ends if the refresh call fails. */
          }
        }
        clearAuth();
        setAuth(null);
        queryClient.clear();
      },
    }),
    [auth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useMe() {
  const { auth } = useAuth();
  return useQuery<MeResponse>({
    queryKey: ["me", auth?.user_id],
    queryFn: () => api.me(),
    enabled: Boolean(auth),
  });
}

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
