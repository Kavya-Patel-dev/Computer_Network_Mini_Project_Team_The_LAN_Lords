import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { ApiUser, api, toUserProfile } from '../api/client';
import { UserProfile, UserRole } from '../types/user';

interface AuthContextType {
  currentUser: UserProfile | null;
  role: UserRole | 'public';
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<UserProfile>;
  register: (name: string, email: string, password: string) => Promise<UserProfile>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  canReviewPlan: (ownerEmail: string) => boolean;
  canEditPlan: (ownerEmail: string, status: string) => boolean;
  canRunSimulation: (ownerEmail: string, status: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = async () => {
    try {
      const response = await api.get<{ user: ApiUser }>('/auth/me');
      setCurrentUser(toUserProfile(response.user) as UserProfile);
      setError(null);
    } catch (err) {
      setCurrentUser(null);
      if (err instanceof Error && 'status' in err && (err as { status: number }).status !== 401) setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { void refreshUser(); }, []);

  const login = async (email: string, password: string) => {
    setError(null);
    const response = await api.post<{ user: ApiUser }>('/auth/login', { email, password });
    const user = toUserProfile(response.user) as UserProfile;
    setCurrentUser(user);
    return user;
  };

  const register = async (name: string, email: string, password: string) => {
    setError(null);
    const response = await api.post<{ user: ApiUser }>('/auth/register', { name, email, password });
    const user = toUserProfile(response.user) as UserProfile;
    setCurrentUser(user);
    return user;
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); }
    finally { setCurrentUser(null); }
  };

  const role = currentUser ? currentUser.role : 'public';

  // Section 4 capability logic:
  // Admin can review any plan EXCEPT their own
  const canReviewPlan = (ownerEmail: string) => {
    if (!currentUser || currentUser.role !== 'admin') return false;
    return currentUser.email.toLowerCase() !== ownerEmail.toLowerCase();
  };

  const canEditPlan = (ownerEmail: string, status: string) => {
    if (!currentUser) return false;
    const isOwner = currentUser.email.toLowerCase() === ownerEmail.toLowerCase();
    return isOwner && (status === 'Draft' || status === 'Changes Requested');
  };

  const canRunSimulation = (ownerEmail: string, status: string) => {
    if (!currentUser) return false;
    const isOwner = currentUser.email.toLowerCase() === ownerEmail.toLowerCase();
    return isOwner && status === 'Approved';
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        role,
        isLoading,
        error,
        login,
        register,
        logout,
        refreshUser,
        canReviewPlan,
        canEditPlan,
        canRunSimulation,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
