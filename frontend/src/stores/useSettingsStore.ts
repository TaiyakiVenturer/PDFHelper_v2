import { create } from "zustand";
import type { AppConfig } from "../types/settings";
import {
  getSettings,
  saveSettings,
  getLocalModels,
  probeRemote,
} from "../services/settingsService";

type ProbeStatus = "idle" | "loading" | "ok" | "error";

interface SettingsState {
  config: AppConfig | null;
  localModels: string[];
  remoteModels: string[];
  probeStatus: ProbeStatus;
  probeError: string;
  loading: boolean;
  saving: boolean;
  dirty: boolean;

  fetchSettings: () => Promise<void>;
  updateConfig: (patch: Partial<AppConfig["llm"]>) => void;
  updateLlamaCpp: (patch: Partial<AppConfig["llm"]["llama_cpp"]>) => void;
  updateOpenAICompat: (patch: Partial<AppConfig["llm"]["openai_compat"]>) => void;
  saveSettings: () => Promise<void>;
  fetchLocalModels: () => Promise<void>;
  probeRemote: (base_url: string, api_key: string) => Promise<void>;
  resetProbe: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  config: null,
  localModels: [],
  remoteModels: [],
  probeStatus: "idle",
  probeError: "",
  loading: false,
  saving: false,
  dirty: false,

  fetchSettings: async () => {
    set({ loading: true });
    try {
      const config = await getSettings();
      set({ config, dirty: false });
    } finally {
      set({ loading: false });
    }
  },

  updateConfig: (patch) => {
    const { config } = get();
    if (!config) return;
    set({
      config: { ...config, llm: { ...config.llm, ...patch } },
      dirty: true,
    });
  },

  updateLlamaCpp: (patch) => {
    const { config } = get();
    if (!config) return;
    set({
      config: {
        ...config,
        llm: {
          ...config.llm,
          llama_cpp: { ...config.llm.llama_cpp, ...patch },
        },
      },
      dirty: true,
    });
  },

  updateOpenAICompat: (patch) => {
    const { config } = get();
    if (!config) return;
    set({
      config: {
        ...config,
        llm: {
          ...config.llm,
          openai_compat: { ...config.llm.openai_compat, ...patch },
        },
      },
      dirty: true,
    });
  },

  saveSettings: async () => {
    const { config } = get();
    if (!config) return;
    set({ saving: true });
    try {
      const updated = await saveSettings(config);
      set({ config: updated, dirty: false });
    } finally {
      set({ saving: false });
    }
  },

  fetchLocalModels: async () => {
    const files = await getLocalModels();
    set({ localModels: files });
  },

  probeRemote: async (base_url, api_key) => {
    set({ probeStatus: "loading", remoteModels: [], probeError: "" });
    try {
      const result = await probeRemote(base_url, api_key);
      if (result.ok) {
        set({ probeStatus: "ok", remoteModels: result.models });
      } else {
        set({ probeStatus: "error", probeError: result.error ?? "連線失敗" });
      }
    } catch (err) {
      set({
        probeStatus: "error",
        probeError: err instanceof Error ? err.message : "連線失敗",
      });
    }
  },

  resetProbe: () => set({ probeStatus: "idle", remoteModels: [], probeError: "" }),
}));
