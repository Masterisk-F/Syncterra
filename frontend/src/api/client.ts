import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

// 開発環境のベースURL
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// Axiosインスタンスの作成
export const apiClient: AxiosInstance = axios.create({
    baseURL: BASE_URL,
    timeout: 30000, // 30秒
    headers: {
        'Content-Type': 'application/json',
    },
});

// レスポンスインターセプター（エラーハンドリング）
apiClient.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        // エラーログ
        console.error('API Error:', {
            url: error.config?.url,
            method: error.config?.method,
            status: error.response?.status,
            data: error.response?.data,
        });

        // エラーメッセージの整形
        if (error.response?.data) {
            const errorData = error.response.data as any;
            if (errorData.detail) {
                // FastAPI Validation Error
                const message = Array.isArray(errorData.detail)
                    ? errorData.detail.map((d: any) => d.msg).join(', ')
                    : errorData.detail;
                throw new Error(message);
            }
        }

        throw error;
    }
);
