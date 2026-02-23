const configured = import.meta.env.VITE_API_BASE;
const runtimeHost = (typeof window !== 'undefined' && window.location?.hostname) ? window.location.hostname : 'localhost';
const runtimeProto = (typeof window !== 'undefined' && window.location?.protocol) ? window.location.protocol : 'http:';
const runtimePort = import.meta.env.VITE_API_PORT || '8088';

export const API_BASE = configured || `${runtimeProto}//${runtimeHost}:${runtimePort}`;
