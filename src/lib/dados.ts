import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
const DIR = path.join(process.cwd(), 'public', 'data', 'municipios');
export async function listarIbge(): Promise<string[]> {
  return (await readdir(DIR)).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
}
export async function carregar(ibge: string): Promise<any> {
  return JSON.parse(await readFile(path.join(DIR, `${ibge}.json`), 'utf-8'));
}
export async function simbolos(): Promise<Record<string, any>> {
  try { return JSON.parse(await readFile(path.join(process.cwd(), 'public', 'data', 'simbolos.json'), 'utf-8')); } catch { return {}; }
}
