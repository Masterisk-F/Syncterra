import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

// ベースURLを動的に取得するための変数
let _baseUrl = '';
let _initialized = false;

/**
 * ベースURLを初期化する
 * Electron環境ではIPCでポート番号を取得
 */
async function initializeBaseUrl(): Promise<string> {
  if (_initialized) return _baseUrl;

  if (window.electronAPI) {
    try {
      const port = await window.electronAPI.getBackendPort();
      _baseUrl = `http://127.0.0.1:${port}`;
    } catch (e) {
      console.warn('Failed to get backend port from Electron', e);
      _baseUrl = '';
    }
  } else {
    // 非Electron環境（ブラウザ直接アクセス時）: 環境変数 or Viteプロキシ
    _baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  }

  _initialized = true;
  console.log('API Base URL initialized:', _baseUrl || '(empty, using proxy)');
  return _baseUrl;
}

// 即時初期化を試みる
initializeBaseUrl();

/**
 * ベースURLを取得（初期化完了を待つ）
 */
export async function getBaseUrl(): Promise<string> {
  return initializeBaseUrl();
}

/**
 * WebSocket URLを取得
 */
export async function getWebSocketUrl(path: string): Promise<string> {
  const base = await getBaseUrl();
  if (base) {
    // http://127.0.0.1:PORT -> ws://127.0.0.1:PORT
    const wsBase = base.replace(/^http/, 'ws');
    return `${wsBase}${path}`;
  } else {
    // 非Electron環境（Viteプロキシ使用時）
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }
}

// Axiosインスタンスの作成
export const apiClient: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// リクエストインターセプター: 動的にbaseURLを設定
apiClient.interceptors.request.use(async (config) => {
  if (!_initialized) {
    await initializeBaseUrl();
  }
  config.baseURL = _baseUrl;
  return config;
});

// レスポンスインターセプター（エラーハンドリング）
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      data: error.response?.data,
    });

    if (error.response?.data) {
      const errorData = error.response.data as any;
      if (errorData.detail) {
        const message = Array.isArray(errorData.detail)
          ? errorData.detail.map((d: any) => d.msg).join(', ')
          : errorData.detail;
        throw new Error(message);
      }
    }

    throw error;
  }
);
