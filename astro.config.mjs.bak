import { defineConfig } from 'astro/config';

// No GitHub Actions, o endereço e o prefixo vêm do próprio repositório (dono/nome).
// Domínio próprio: defina SITE_URL e SITE_BASE=/ no ambiente de build.
const [dono, repo] = (process.env.GITHUB_REPOSITORY ?? '').split('/');
const paginaDoUsuario = !!repo && repo.toLowerCase() === `${(dono ?? '').toLowerCase()}.github.io`;

export default defineConfig({
  server: { port: 4321 },
  vite: { server: { strictPort: true } },
  site: process.env.SITE_URL || (dono ? `https://${dono.toLowerCase()}.github.io` : undefined),
  base: process.env.SITE_BASE ?? (repo && !paginaDoUsuario ? `/${repo}` : '/'),
});
