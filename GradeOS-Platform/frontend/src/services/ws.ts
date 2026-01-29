const stripTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const resolveFromApiBase = (apiBase: string, fallbackOrigin: string) => {
    const base = apiBase.startsWith('http')
        ? new URL(apiBase)
        : new URL(apiBase, fallbackOrigin);
    const wsProtocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = base.pathname.replace(/\/api(?:\/.*)?$/, '');
    base.protocol = wsProtocol;
    base.pathname = path || '/';
    base.search = '';
    base.hash = '';
    return stripTrailingSlash(base.toString());
};

export const resolveWsBaseUrl = () => {
    const explicit = process.env.NEXT_PUBLIC_WS_BASE_URL;
    if (explicit) {
        return stripTrailingSlash(explicit);
    }
    const legacy = process.env.NEXT_PUBLIC_WS_URL;
    if (legacy) {
        return stripTrailingSlash(legacy);
    }

    const fallbackOrigin = typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost:8001';
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    if (apiBase) {
        return resolveFromApiBase(apiBase, fallbackOrigin);
    }

    // 生产环境检测：Railway 部署
    if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        if (hostname.includes('railway.app')) {
            return 'wss://gradeos-production.up.railway.app';
        }
    }

    return resolveFromApiBase(fallbackOrigin, fallbackOrigin);
};

export const buildWsUrl = (path: string) => {
    const base = resolveWsBaseUrl();
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${base}${normalized}`;
};

type WebSocketStatus = 'CONNECTING' | 'OPEN' | 'CLOSED' | 'ERROR';

class WSClient {
    private socket: WebSocket | null = null;
    private status: WebSocketStatus = 'CLOSED';
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectInterval = 1000;
    private maxReconnectInterval = 15000;
    private listeners = new Map<string, ((data: any) => void)[]>();
    private url: string = '';
    private statusChangeCallback: ((status: WebSocketStatus) => void) | null = null;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private manualClose = false;

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
        const hasActiveSocket = this.socket
            && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING);
        if (hasActiveSocket && url === this.url) {
            return;
        }
        if (hasActiveSocket && url !== this.url) {
            this.disconnect();
        }

        this.url = url;
        this.manualClose = false;
        this.updateStatus('CONNECTING');

        try {
            this.socket = new WebSocket(url);

            this.socket.onopen = () => {
                console.log('WS Connected');
                this.updateStatus('OPEN');
                this.reconnectAttempts = 0;
            };

            this.socket.onclose = (event) => {
                console.warn('WS Closed', {
                    url: this.url,
                    code: event.code,
                    reason: event.reason,
                    wasClean: event.wasClean,
                });
                this.socket = null;
                this.updateStatus('CLOSED');
                if (this.manualClose) {
                    return;
                }
                this.handleReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('WS Error', {
                    url: this.url,
                    readyState: this.socket?.readyState,
                    error,
                });
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
        if (!this.url) {
            console.error('WS Reconnect skipped: missing URL');
            return;
        }
        if (this.reconnectTimer) {
            return;
        }
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const baseDelay = Math.min(
                this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
                this.maxReconnectInterval
            );
            const jitter = baseDelay * 0.2;
            const timeout = Math.round(baseDelay - jitter + Math.random() * jitter * 2);
            console.log(`Reconnecting in ${timeout}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect(this.url);
            }, timeout);
        } else {
            console.error('Max reconnect attempts reached');
        }
    }

    disconnect() {
        this.manualClose = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    send(type: string, payload: Record<string, unknown>) {
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
