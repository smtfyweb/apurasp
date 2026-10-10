const b = import.meta.env.BASE_URL;
export const BASE = b.endsWith('/') ? b : b + '/';
export const href = (p: string) => BASE + p.replace(/^\//, '');
