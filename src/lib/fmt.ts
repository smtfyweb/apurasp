const PARTICULAS = new Set(['de', 'da', 'do', 'das', 'dos', 'e']);
export const num = (x: number | null | undefined): string => (x == null ? '—' : Math.round(x).toLocaleString('pt-BR'));
export const dec = (x: number | null | undefined, d = 1): string =>
  x == null ? '—' : x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
export const pct = (x: number | null | undefined, d = 1): string => (x == null ? '—' : `${dec(x, d)}%`);
export const cap = (s: string): string => {
  const t = (s ?? '').toLocaleLowerCase('pt-BR');
  return t.charAt(0).toLocaleUpperCase('pt-BR') + t.slice(1);
};
export const titulo = (s: string): string =>
  (s ?? '').toLocaleLowerCase('pt-BR').split(' ')
    .map((p, i) => (i > 0 && PARTICULAS.has(p) ? p : p.charAt(0).toLocaleUpperCase('pt-BR') + p.slice(1))).join(' ');
export const reais = (milReais: number | null | undefined): string => {
  if (milReais == null) return '—';
  const v = milReais * 1000;
  if (v >= 1e9) return `R$ ${dec(v / 1e9)} bilhões`;
  if (v >= 1e6) return `R$ ${dec(v / 1e6)} milhões`;
  return `R$ ${num(v)}`;
};
