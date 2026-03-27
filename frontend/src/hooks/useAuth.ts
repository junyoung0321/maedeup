"use client";

import { useState, useEffect } from "react";

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  picture?: string;
  calendar_consent: boolean;
}

function decodeJwt(token: string): AuthUser & { exp: number } {
  const payload = token.split(".")[1];
  return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (token) {
      try {
        const decoded = decodeJwt(token);
        if (decoded.exp * 1000 > Date.now()) {
          setUser({
            sub: decoded.sub,
            email: decoded.email,
            name: decoded.name,
            picture: decoded.picture,
            calendar_consent: decoded.calendar_consent ?? false,
          });
        } else {
          localStorage.removeItem("auth_token");
        }
      } catch {
        localStorage.removeItem("auth_token");
      }
    }
    setLoading(false);
  }, []);

  const logout = () => {
    localStorage.removeItem("auth_token");
    setUser(null);
    window.location.href = "/";
  };

  return { user, loading, logout };
}
