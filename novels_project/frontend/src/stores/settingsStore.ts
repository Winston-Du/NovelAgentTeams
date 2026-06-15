import { create } from 'zustand';
import { settingsApi } from '../services/api';

interface SettingsStore {
  theme: 'light' | 'dark';
  language: 'zh' | 'en';
  notifications: { enabled: boolean };
  setTheme: (theme: 'light' | 'dark') => void;
  setLanguage: (lang: 'zh' | 'en') => void;
  toggleNotifications: (enabled: boolean) => void;
  loadSettings: () => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  theme: 'light',
  language: 'zh',
  notifications: { enabled: true },

  setTheme: (theme) => set({ theme }),
  setLanguage: (language) => set({ language }),
  toggleNotifications: (enabled) => set({ notifications: { enabled } }),

  loadSettings: async () => {
    try {
      const res = await settingsApi.get();
      const data = res.data;
      if (data.theme) set({ theme: data.theme });
      if (data.language) set({ language: data.language });
      if (data.notifications) set({ notifications: data.notifications });
    } catch {
      // Keep defaults if API fails
    }
  },
}));