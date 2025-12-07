import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketMessage {
    type: 'log' | 'progress' | 'status';
    message?: string;
    progress?: number;
    status?: 'started' | 'completed' | 'error';
}

interface UseWebSocketReturn {
    isConnected: boolean;
    sendMessage: (message: string) => void;
}

export const useWebSocket = (
    onMessage: (message: string) => void,
    onProgress?: (progress: number) => void,
    url: string = 'ws://localhost:8000/ws/status'
): UseWebSocketReturn => {
    const [isConnected, setIsConnected] = useState(false);
    const ws = useRef<WebSocket | null>(null);
    const reconnectTimeout = useRef<number | undefined>(undefined);

    const connect = useCallback(() => {
        try {
            ws.current = new WebSocket(url);

            ws.current.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
            };

            ws.current.onmessage = (event) => {
                const data = event.data;

                // Try to parse as JSON first
                try {
                    const parsed: WebSocketMessage = JSON.parse(data);
                    if (parsed.type === 'log' && parsed.message) {
                        onMessage(parsed.message);
                    } else if (parsed.type === 'progress' && parsed.progress !== undefined && onProgress) {
                        onProgress(parsed.progress);
                    }
                } catch {
                    // If not JSON, treat as plain log message
                    onMessage(data);
                }
            };

            ws.current.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.current.onclose = () => {
                console.log('WebSocket disconnected');
                setIsConnected(false);

                // Attempt to reconnect after 3 seconds
                reconnectTimeout.current = setTimeout(() => {
                    console.log('Attempting to reconnect...');
                    connect();
                }, 3000);
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
        }
    }, [url, onMessage, onProgress]);

    useEffect(() => {
        connect();

        return () => {
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
            }
            if (ws.current) {
                ws.current.close();
            }
        };
    }, [connect]);

    const sendMessage = useCallback((message: string) => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(message);
        }
    }, []);

    return { isConnected, sendMessage };
};
