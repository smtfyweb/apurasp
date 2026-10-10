// Cores dos partidos no mapa: ajuste à vontade. Partido fora da lista aparece em cinza.
export const CORES_PARTIDO: Record<string, string> = {
  'PL': '#1B3F8B', 'REPUBLICANOS': '#2F80D0', 'UNIÃO': '#D9A400', 'PP': '#7B5EA7', 'PSD': '#E8772E',
  'MDB': '#2A9D5C', 'PODE': '#0F8B8D', 'PSDB': '#6BC3EC', 'PT': '#C8102E', 'PSOL': '#7A1530',
  'PSB': '#D95F8B', 'PDT': '#9C5A2E', 'AVANTE': '#8AB83A', 'SOLIDARIEDADE': '#B07CE0', 'CIDADANIA': '#F08BB0',
  'PRD': '#4B5D7A', 'MISSÃO': '#C9B21A', 'PV': '#4CAF50', 'NOVO': '#E4572E', 'DC': '#6D4C41',
  'MOBILIZA': '#00897B', 'AGIR': '#8D6E63', 'PC do B': '#B71C1C', 'REDE': '#26A69A',
};
export const corPartido = (p?: string | null): string => (p && CORES_PARTIDO[p]) || '#9AA5B5';

const ESQ = [179, 50, 46], MEIO = [237, 233, 228], DIR = [31, 78, 155];
export const NOTA_MIN = 2, NOTA_MAX = 9;
export function corNota(n?: number | null): string {
  if (n == null) return '#D9DEE5';
  const t = Math.max(0, Math.min(1, (n - NOTA_MIN) / (NOTA_MAX - NOTA_MIN)));
  const a = t < 0.5 ? ESQ : MEIO, b = t < 0.5 ? MEIO : DIR, u = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * u));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
export const GRADIENTE = `linear-gradient(90deg, ${corNota(NOTA_MIN)}, ${corNota((NOTA_MIN + NOTA_MAX) / 2)}, ${corNota(NOTA_MAX)})`;
export const CAMPOS = ['extrema-esquerda', 'esquerda', 'centro-esquerda', 'centro', 'centro-direita', 'direita', 'extrema-direita'];
export const NOTA_CAMPO: Record<string, number> = {
  'extrema-esquerda': 0.8, 'esquerda': 2.2, 'centro-esquerda': 3.8, 'centro': 5.5,
  'centro-direita': 6.4, 'direita': 7.7, 'extrema-direita': 9,
};
