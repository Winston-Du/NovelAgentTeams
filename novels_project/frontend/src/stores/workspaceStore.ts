import { create } from 'zustand';
import { workspaceApi } from '../services/api';

export interface Workspace {
  name: string;
  path: string;
  is_current: boolean;
  chapters_count: number;
  is_ready: boolean;
}

interface WorkspaceStore {
  workspaces: Workspace[];
  currentWorkspace: Workspace | null;
  loading: boolean;
  fetchWorkspaces: () => Promise<void>;
  createWorkspace: (name: string) => Promise<void>;
  deleteWorkspace: (name: string) => Promise<void>;
  renameWorkspace: (name: string, newName: string) => Promise<void>;
  switchWorkspace: (name: string) => Promise<void>;
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  workspaces: [],
  currentWorkspace: null,
  loading: false,

  fetchWorkspaces: async () => {
    set({ loading: true });
    try {
      const res = await workspaceApi.list();
      const workspaces = res.data;
      set({
        workspaces,
        currentWorkspace: workspaces.find((w: Workspace) => w.is_current) || null,
      });
    } finally {
      set({ loading: false });
    }
  },

  createWorkspace: async (name) => {
    await workspaceApi.create({ name });
    await get().fetchWorkspaces();
  },

  deleteWorkspace: async (name) => {
    await workspaceApi.delete(name);
    await get().fetchWorkspaces();
  },

  renameWorkspace: async (name, newName) => {
    await workspaceApi.rename(name, newName);
    await get().fetchWorkspaces();
  },

  switchWorkspace: async (name) => {
    await workspaceApi.switch(name);
    await get().fetchWorkspaces();
  },
}));