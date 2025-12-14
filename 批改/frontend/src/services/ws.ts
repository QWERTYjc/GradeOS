import { create } from 'zustand';

type WebSocketStatus = 'CONNECTING' | 'OPEN' | 'CLOSED' | 'ERROR';

interface WebSocketService {
    url: string;
    socket: WebSocket | null;
    status: WebSocketStatus;
    reconnectAttempts: number;
    maxReconnectAttempts: number;
    reconnectInterval: number;
    listeners: Map<string, ((data: any) => void)[]>;

    connect: (url: string) => void;
    disconnect: () => void;
    send: (type: string, payload: any) => void;
    on: (type: string, callback: (data: any) => void) => void;
    off: (type: string, callback: (data: any) => void) => void;
}

class WSClient {
    private socket: WebSocket | null = null;
    private status: WebSocketStatus = 'CLOSED';
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectInterval = 1000;
    private listeners = new Map<string, ((data: any) => void)[]>();
    private url: string = '';
    private statusChangeCallback: ((status: WebSocketStatus) => void) | null = null;

    constructor() { }

    setStatusCallback(cb: (status: WebSocketStatus) => void) {
        this.statusChangeCallback = cb;
    }

    private updateStatus(status: WebSocketStatus) {
        this.status = status;
        if (this.statusChangeCallback) {
            this.statusChangeCallback(status);
        }
    }

    connect(url: string) {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.url = url;
        this.updateStatus('CONNECTING');

        try {
            this.socket = new WebSocket(url);

            this.socket.onopen = () => {
                console.log('WS Connected');
                this.updateStatus('OPEN');
                this.reconnectAttempts = 0;
            };

            this.socket.onclose = () => {
                console.log('WS Closed');
                this.updateStatus('CLOSED');
                this.handleReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('WS Error', error);
                this.updateStatus('ERROR');
            };

            this.socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    const { type, ...payload } = message;
                    this.dispatch(type, payload);
                } catch (e) {
                    console.error('Failed to parse WS message', e);
                }
            };
        } catch (e) {
            console.error('WS Connection Failed', e);
            this.handleReconnect();
        }
    }

    private handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const timeout = this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1);
            console.log(`Reconnecting in ${timeout}ms...`);
            setTimeout(() => {
                this.connect(this.url);
            }, timeout);
        } else {
            console.error('Max reconnect attempts reached');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    send(type: string, payload: any) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, ...payload }));
        } else {
            console.warn('WS not connected, cannot send message');
        }
    }

    on(type: string, callback: (data: any) => void) {
        if (!this.listeners.has(type)) {
            this.listeners.set(type, []);
        }
        this.listeners.get(type)?.push(callback);
    }

    off(type: string, callback: (data: any) => void) {
        const callbacks = this.listeners.get(type);
        if (callbacks) {
            this.listeners.set(type, callbacks.filter(cb => cb !== callback));
        }
    }

    private dispatch(type: string, payload: any) {
        const callbacks = this.listeners.get(type);
        if (callbacks) {
            callbacks.forEach(cb => cb(payload));
        }
    }
}

export const wsClient = new WSClient();
