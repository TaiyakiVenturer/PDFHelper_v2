import { useEffect, useState } from "react";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useToastStore } from "../stores/useToastStore";
import type { LLMBackend } from "../types/settings";

const PROVIDER_PRESETS: Array<{
  label: string;
  backend: LLMBackend;
  base_url?: string;
  needsKey: boolean;
}> = [
  { label: "llama.cpp", backend: "llama_cpp", needsKey: false },
  { label: "Ollama", backend: "openai_compat", base_url: "http://localhost:11434/v1", needsKey: false },
  { label: "OpenAI", backend: "openai_compat", base_url: "https://api.openai.com/v1", needsKey: true },
  { label: "Groq", backend: "openai_compat", base_url: "https://api.groq.com/openai/v1", needsKey: true },
  { label: "Custom", backend: "openai_compat", base_url: "", needsKey: false },
];

export function SettingsPage() {
  const {
    config,
    localModels,
    remoteModels,
    probeStatus,
    probeError,
    loading,
    saving,
    dirty,
    fetchSettings,
    updateConfig,
    updateLlamaCpp,
    updateOpenAICompat,
    saveSettings,
    fetchLocalModels,
    probeRemote,
    resetProbe,
  } = useSettingsStore();

  const addToast = useToastStore((s) => s.addToast);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
    fetchLocalModels();
  }, [fetchSettings, fetchLocalModels]);

  if (loading || !config) {
    return (
      <div className="settings-page">
        <p className="settings-loading">載入設定中…</p>
      </div>
    );
  }

  const llm = config.llm;

  function applyPreset(preset: (typeof PROVIDER_PRESETS)[number]) {
    setActivePreset(preset.label);
    updateConfig({ backend: preset.backend });
    if (preset.backend === "openai_compat" && preset.base_url !== undefined) {
      updateOpenAICompat({ base_url: preset.base_url });
    }
    // Reset probe state so stale remote model list from previous provider is cleared
    resetProbe();
  }

  async function handleProbe() {
    await probeRemote(llm.openai_compat.base_url, llm.openai_compat.api_key);
  }

  function handleSelectRemoteModel(model: string) {
    updateOpenAICompat({ model });
  }

  async function handleSave() {
    try {
      await saveSettings();
      addToast("success", "設定已儲存");
    } catch (err) {
      addToast("error", err instanceof Error ? err.message : "儲存失敗");
    }
  }

  const currentPresetLabel =
    activePreset ??
    (llm.backend === "llama_cpp"
      ? "llama.cpp"
      : PROVIDER_PRESETS.find((p) => p.backend === "openai_compat" && p.base_url === llm.openai_compat.base_url)
          ?.label ?? "Custom");

  return (
    <div className="settings-page">
      <div className="settings-card">
        <h2 className="settings-section-title">LLM 模型來源</h2>

        {/* Provider preset buttons */}
        <div className="settings-preset-row">
          {PROVIDER_PRESETS.map((preset) => (
            <button
              key={preset.label}
              className={`settings-preset-btn${currentPresetLabel === preset.label ? " settings-preset-btn-active" : ""}`}
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* llama.cpp settings */}
        {llm.backend === "llama_cpp" && (
          <div className="settings-fields">
            <label className="settings-label">
              本地模型檔案
              <div className="settings-row-inline">
                {localModels.length > 0 ? (
                  <select
                    className="settings-select"
                    style={{ flex: 1 }}
                    value={llm.llama_cpp.filename}
                    onChange={(e) => updateLlamaCpp({ filename: e.target.value })}
                  >
                    {/* Ensure current config value is always present even if not in scanned list */}
                    {!localModels.includes(llm.llama_cpp.filename) && (
                      <option value={llm.llama_cpp.filename}>{llm.llama_cpp.filename}（設定值）</option>
                    )}
                    {localModels.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                ) : (
                  <span className="settings-hint" style={{ flex: 1 }}>
                    未找到 .gguf 檔案，請將模型放入 backend/models/ 目錄
                  </span>
                )}
                <button
                  className="settings-btn-secondary"
                  onClick={fetchLocalModels}
                >
                  重新掃描
                </button>
              </div>
            </label>

            <label className="settings-label">
              GPU 層數（n_gpu_layers）
              <div className="settings-row-inline">
                <input
                  type="number"
                  className="settings-input settings-input-sm"
                  value={llm.llama_cpp.n_gpu_layers}
                  min={-1}
                  onChange={(e) => updateLlamaCpp({ n_gpu_layers: Number(e.target.value) })}
                />
                <span className="settings-hint">-1 = 全 GPU，0 = CPU</span>
              </div>
            </label>

            <label className="settings-label">
              Context 長度（n_ctx）
              <input
                type="number"
                className="settings-input settings-input-sm"
                value={llm.llama_cpp.n_ctx}
                min={512}
                step={512}
                onChange={(e) => updateLlamaCpp({ n_ctx: Number(e.target.value) })}
              />
            </label>
          </div>
        )}

        {/* OpenAI-compatible settings */}
        {llm.backend === "openai_compat" && (
          <div className="settings-fields">
            <label className="settings-label">
              Base URL
              <div className="settings-row-inline">
                <input
                  type="text"
                  className="settings-input"
                  style={{ flex: 1 }}
                  value={llm.openai_compat.base_url}
                  placeholder="http://localhost:11434/v1"
                  onChange={(e) => updateOpenAICompat({ base_url: e.target.value })}
                />
                <button
                  className="settings-btn-secondary"
                  onClick={handleProbe}
                  disabled={probeStatus === "loading"}
                >
                  {probeStatus === "loading" ? "連線中…" : "取得模型列表"}
                </button>
              </div>
              {probeStatus === "ok" && (
                <span className="settings-probe-ok">連線成功，取得 {remoteModels.length} 個可用模型</span>
              )}
              {probeStatus === "error" && (
                <span className="settings-probe-error">{probeError}</span>
              )}
            </label>

            <label className="settings-label">
              API Key
              <input
                type="password"
                className="settings-input"
                value={llm.openai_compat.api_key}
                placeholder="sk-..."
                onChange={(e) => updateOpenAICompat({ api_key: e.target.value })}
              />
            </label>

            <label className="settings-label">
              模型名稱
              {remoteModels.length > 0 ? (
                <select
                  className="settings-select"
                  value={llm.openai_compat.model}
                  onChange={(e) => handleSelectRemoteModel(e.target.value)}
                >
                  {/* Ensure current config value is always present */}
                  {!remoteModels.includes(llm.openai_compat.model) && (
                    <option value={llm.openai_compat.model}>{llm.openai_compat.model}（設定值）</option>
                  )}
                  {remoteModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  className="settings-input"
                  value={llm.openai_compat.model}
                  placeholder="點擊「取得模型列表」或直接輸入模型名稱"
                  onChange={(e) => updateOpenAICompat({ model: e.target.value })}
                />
              )}
            </label>
          </div>
        )}
      </div>

      <div className="settings-card">
        <h2 className="settings-section-title">推理參數</h2>

        <div className="settings-fields">
          <label className="settings-label">
            Temperature（{llm.temperature.toFixed(2)}）
            <div className="settings-row-inline">
              <input
                type="range"
                className="settings-slider"
                min={0}
                max={2}
                step={0.05}
                value={llm.temperature}
                onChange={(e) => updateConfig({ temperature: Number(e.target.value) })}
              />
              <input
                type="number"
                className="settings-input settings-input-xs"
                min={0}
                max={2}
                step={0.05}
                value={llm.temperature}
                onChange={(e) => updateConfig({ temperature: Number(e.target.value) })}
              />
            </div>
          </label>

          <label className="settings-label">
            最大 Token 數（max_tokens）
            <input
              type="number"
              className="settings-input settings-input-sm"
              min={100}
              max={8192}
              step={100}
              value={llm.max_tokens}
              onChange={(e) => updateConfig({ max_tokens: Number(e.target.value) })}
            />
          </label>
        </div>
      </div>

      <div className="settings-footer">
        <button
          className="settings-btn-primary"
          onClick={handleSave}
          disabled={saving || !dirty}
        >
          {saving ? "儲存中…" : dirty ? "儲存設定" : "已是最新"}
        </button>
      </div>
    </div>
  );
}
