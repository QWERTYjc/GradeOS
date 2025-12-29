import React from 'react';
import { Session, ScannedImage } from './types';

export interface AppContextType {
  sessions: Session[];
  currentSessionId: string | null;
  createNewSession: (name?: string) => void;
  addImageToSession: (img: ScannedImage) => void;
  addImagesToSession: (imgs: ScannedImage[]) => void;
  deleteSession: (id: string) => void;
  deleteImages: (sessionId: string, imageIds: string[]) => void;
  setCurrentSessionId: (id: string) => void;
  updateImage: (sessionId: string, imageId: string, newUrl: string, isOptimizing?: boolean) => void;
  reorderImages: (sessionId: string, fromIndex: number, toIndex: number) => void;
}

export const AppContext = React.createContext<AppContextType | null>(null);

export const useAppContext = () => {
  const context = React.useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppContext.Provider');
  }
  return context;
};
