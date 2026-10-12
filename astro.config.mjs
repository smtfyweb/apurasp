import { defineConfig } from 'astro/config';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

// Plugin local opcional (apenas no servidor de desenvolvimento). Sem o arquivo, nada acontece.
const require = createRequire(import.meta.url);
const arquivoLocal = path.resolve('analises_privadas', 'dev', 'interno.cjs');
const plugin = fs.existsSync(arquivoLocal) ? require(arquivoLocal) : null;

// No GitHub Actions, o endereço e o prefixo vêm do próprio repositório (dono/nome).
// Domínio próprio: defina SITE_URL e SITE_BASE=/ no ambiente de build.
const [dono, repo] = (process.env.GITHUB_REPOSITORY ?? '').split('/');
const paginaDoUsuario = !!repo && repo.toLowerCase() === `${(dono ?? '').toLowerCase()}.github.io`;

export default defineConfig({
  server: { port: 4321 },
  vite: { server: { strictPort: true }, plugins: plugin ? [plugin()] : [] },
  site: process.env.SITE_URL || (dono ? `https://${dono.toLowerCase()}.github.io` : undefined),
  base: process.env.SITE_BASE ?? (repo && !paginaDoUsuario ? `/${repo}` : '/'),
});
