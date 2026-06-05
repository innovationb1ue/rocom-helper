const API_PORT = import.meta.env.VITE_API_PORT ?? '18731';

export function apiBaseUrl(): string {
  return '/api';
}

export function backendWsUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${protocol}//${window.location.hostname}:${API_PORT}${normalizedPath}`;
}
