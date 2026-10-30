import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ViewportMode, UiState } from '../types/ui';

interface ViewportContextType {
  mode: ViewportMode;
  setMode: (mode: ViewportMode) => void;
  uiState: UiState;
  setUiState: (state: UiState) => void;
  currentPath: string;
  navigate: (path: string) => void;
  goBack: () => void;
  activeOverlay: string | null;
  openOverlay: (overlayId: string, payload?: any) => void;
  closeOverlay: () => void;
  overlayPayload: any;
}

const ViewportContext = createContext<ViewportContextType | undefined>(undefined);

export const ViewportProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<ViewportMode>('desktop');
  const [uiState, setUiState] = useState<UiState>('normal');
  const [currentPath, setCurrentPath] = useState<string>('/dashboard');
  const [history, setHistory] = useState<string[]>(['/dashboard']);
  const [activeOverlay, setActiveOverlay] = useState<string | null>(null);
  const [overlayPayload, setOverlayPayload] = useState<any>(null);

  // Sync with browser hash if present
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash && hash !== currentPath) {
        setCurrentPath(hash);
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const navigate = (path: string) => {
    window.location.hash = path;
    setHistory((prev) => [...prev, path]);
    setCurrentPath(path);
    // Reset state override on normal page navigation
    setUiState('normal');
    // Scroll container to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const goBack = () => {
    if (history.length > 1) {
      const newHistory = [...history];
      newHistory.pop(); // remove current
      const prevPath = newHistory[newHistory.length - 1];
      setHistory(newHistory);
      window.location.hash = prevPath;
      setCurrentPath(prevPath);
    } else {
      navigate('/dashboard');
    }
  };

  const openOverlay = (overlayId: string, payload?: any) => {
    setActiveOverlay(overlayId);
    setOverlayPayload(payload || null);
  };

  const closeOverlay = () => {
    setActiveOverlay(null);
    setOverlayPayload(null);
  };

  return (
    <ViewportContext.Provider
      value={{
        mode,
        setMode,
        uiState,
        setUiState,
        currentPath,
        navigate,
        goBack,
        activeOverlay,
        openOverlay,
        closeOverlay,
        overlayPayload,
      }}
    >
      {children}
    </ViewportContext.Provider>
  );
};

export const useViewport = () => {
  const context = useContext(ViewportContext);
  if (!context) {
    throw new Error('useViewport must be used within a ViewportProvider');
  }
  return context;
};
