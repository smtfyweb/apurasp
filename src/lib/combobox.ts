// Troca a lista nativa (datalist) por uma lista própria, com busca sem acento e navegação por teclado.
// Aproveita o <datalist> que já existe na página e dispara "change" ao escolher, então o resto do código não muda.
const sem = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' } as Record<string, string>)[c]);
const MAX = 200;
let contador = 0;

export function melhorarCaixas(raiz: ParentNode = document): void {
  raiz.querySelectorAll<HTMLInputElement>('input[list]').forEach((inp) => {
    const listaId = inp.getAttribute('list');
    if (!listaId || inp.dataset.cb) return;
    inp.dataset.cb = '1';
    inp.removeAttribute('list');
    montar(inp, listaId);
  });
}

function montar(inp: HTMLInputElement, listaId: string): void {
  const id = `cb${++contador}`;
  const vazio = inp.dataset.opcaoVazia ?? '';
  const envolt = document.createElement('div');
  envolt.className = 'cb';
  inp.parentNode?.insertBefore(envolt, inp);
  envolt.appendChild(inp);
  inp.classList.add('cb-input');

  const seta = document.createElement('span');
  seta.className = 'cb-seta'; seta.setAttribute('aria-hidden', 'true');
  seta.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
  const ul = document.createElement('ul');
  ul.id = `${id}-lista`; ul.className = 'cb-lista'; ul.setAttribute('role', 'listbox'); ul.hidden = true;
  const rotulo = inp.id ? document.querySelector(`label[for="${inp.id}"]`)?.textContent?.trim() : '';
  if (rotulo) ul.setAttribute('aria-label', rotulo);
  const aviso = document.createElement('div');
  aviso.className = 'sr'; aviso.setAttribute('role', 'status'); aviso.setAttribute('aria-live', 'polite');
  envolt.append(seta, ul, aviso);

  inp.setAttribute('role', 'combobox');
  inp.setAttribute('aria-autocomplete', 'list');
  inp.setAttribute('aria-expanded', 'false');
  inp.setAttribute('aria-controls', ul.id);
  inp.setAttribute('autocomplete', 'off');

  let confirmado = inp.value, ativo = -1, aberto = false, digitando = false, itens: string[] = [];

  const todas = (): string[] => {
    const dl = document.getElementById(listaId) as HTMLDataListElement | null;
    const ops = dl ? Array.from(dl.options).map((o) => o.value).filter(Boolean) : [];
    return vazio ? [vazio, ...ops] : ops;
  };
  const filtrar = (q: string): string[] => {
    const base = todas(), n = sem(q);
    if (!n) return base;
    const ini: string[] = [], pal: string[] = [], dentro: string[] = [];
    for (const o of base) {
      const s = sem(o);
      if (s.startsWith(n)) ini.push(o); else if (s.includes(' ' + n)) pal.push(o); else if (s.includes(n)) dentro.push(o);
    }
    return [...ini, ...pal, ...dentro];
  };

  const marcarAtivo = (rolar: boolean) => {
    const lis = Array.from(ul.querySelectorAll<HTMLElement>('li[role=option]'));
    lis.forEach((li, i) => li.setAttribute('aria-selected', i === ativo ? 'true' : 'false'));
    const li = lis[ativo];
    if (li) {
      inp.setAttribute('aria-activedescendant', li.id);
      if (rolar) {
        const t = li.offsetTop, b = t + li.offsetHeight;
        if (t < ul.scrollTop) ul.scrollTop = t - 4; else if (b > ul.scrollTop + ul.clientHeight) ul.scrollTop = b - ul.clientHeight + 4;
      }
    } else inp.removeAttribute('aria-activedescendant');
  };

  const desenhar = () => {
    itens = filtrar(digitando ? inp.value : '');
    const mostra = itens.slice(0, MAX), atual = sem(confirmado || vazio);
    ul.innerHTML = (mostra.length
      ? mostra.map((o, i) => `<li role="option" id="${id}-${i}" data-i="${i}" aria-selected="false"${sem(o) === atual ? ' class="cb-atual"' : ''}>${esc(o)}</li>`).join('')
      : '<li class="cb-vazio" role="presentation">Nenhum resultado. Confira a grafia.</li>')
      + (itens.length > MAX ? `<li class="cb-vazio" role="presentation">Mostrando as ${MAX} primeiras. Digite para filtrar.</li>` : '');
    ativo = mostra.length ? (digitando ? 0 : Math.max(0, mostra.findIndex((o) => sem(o) === atual))) : -1;
    marcarAtivo(true);
    aviso.textContent = itens.length ? `${itens.length} ${itens.length === 1 ? 'opção' : 'opções'}` : 'Nenhum resultado';
  };

  const abrir = () => {
    if (!digitando) confirmado = inp.value;
    if (!aberto) { aberto = true; ul.hidden = false; inp.setAttribute('aria-expanded', 'true'); }
    desenhar();
  };
  const fechar = () => {
    aberto = false; digitando = false; ul.hidden = true;
    inp.setAttribute('aria-expanded', 'false'); inp.removeAttribute('aria-activedescendant');
  };
  const escolher = (o: string) => {
    inp.value = vazio && o === vazio ? '' : o;
    confirmado = inp.value;
    fechar();
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  };

  inp.addEventListener('focus', () => { if (!digitando) confirmado = inp.value; inp.select(); });
  inp.addEventListener('click', () => { if (!digitando) inp.select(); if (!aberto) { digitando = false; abrir(); } });
  inp.addEventListener('input', () => { digitando = true; abrir(); });
  inp.addEventListener('keydown', (e) => {
    const topo = Math.min(itens.length, MAX) - 1;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!aberto) { digitando = false; abrir(); } else { ativo = Math.min(ativo + 1, topo); marcarAtivo(true); }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (aberto) { ativo = Math.max(ativo - 1, 0); marcarAtivo(true); }
    } else if (e.key === 'Enter') {
      if (aberto && ativo >= 0 && itens[ativo] != null) { e.preventDefault(); escolher(itens[ativo]); }
    } else if (e.key === 'Escape') {
      if (aberto) { e.preventDefault(); fechar(); inp.value = confirmado; }
    } else if (e.key === 'Tab') {
      if (aberto) fechar();
    }
  });
  inp.addEventListener('blur', () => {
    setTimeout(() => {
      if (document.activeElement === inp) return;
      if (aberto) fechar();
      if (sem(inp.value) !== sem(confirmado) && !todas().some((o) => sem(o) === sem(inp.value))) inp.value = confirmado;
    }, 120);
  });
  // "change" nativo (ao sair do campo): só vale se o texto for exatamente uma opção e for diferente do que já estava
  inp.addEventListener('change', (e) => {
    if (!e.isTrusted) return;
    if (sem(inp.value) === sem(confirmado)) { e.stopImmediatePropagation(); return; }
    const ok = todas().find((o) => sem(o) === sem(inp.value));
    if (!ok) { e.stopImmediatePropagation(); return; }
    inp.value = vazio && ok === vazio ? '' : ok;
    confirmado = inp.value;
  }, true);

  ul.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const li = (e.target as HTMLElement).closest('li[data-i]') as HTMLElement | null;
    if (li) escolher(itens[Number(li.dataset.i)]);
  });
  ul.addEventListener('mousemove', (e) => {
    const li = (e.target as HTMLElement).closest('li[data-i]') as HTMLElement | null;
    if (li && Number(li.dataset.i) !== ativo) { ativo = Number(li.dataset.i); marcarAtivo(false); }
  });
}
