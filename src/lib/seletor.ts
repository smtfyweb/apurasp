// Menu próprio (select-only combobox): mesma aparência da busca de município, sem campo de digitação.
// Aproveita o <select> da página (que fica oculto e sincronizado), então o resto do código não muda.
const sem = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' } as Record<string, string>)[c]);
const valorDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value') as PropertyDescriptor;
type Op = { tipo: 'op'; v: string; t: string; d: boolean; nota: string };
type Gr = { tipo: 'gr'; t: string };
let contador = 0;

export function melhorarSeletores(raiz: ParentNode = document): void {
  if (matchMedia('(pointer: coarse)').matches) return; // no celular, o seletor nativo é melhor
  raiz.querySelectorAll<HTMLSelectElement>('select:not([data-nativo])').forEach((s) => {
    if (s.dataset.sl) return;
    s.dataset.sl = '1';
    montar(s);
  });
}

function montar(sel: HTMLSelectElement): void {
  const id = `sl${++contador}`;
  const wrap = document.createElement('div');
  wrap.className = 'sl';
  sel.parentNode?.insertBefore(wrap, sel);
  wrap.appendChild(sel);
  sel.hidden = true; sel.setAttribute('aria-hidden', 'true'); sel.tabIndex = -1;

  const btn = document.createElement('button');
  btn.type = 'button'; btn.id = `${id}-btn`; btn.className = 'sl-btn';
  btn.setAttribute('role', 'combobox'); btn.setAttribute('aria-haspopup', 'listbox');
  btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', `${id}-lista`);
  btn.innerHTML = '<span class="sl-txt"></span><svg class="sl-chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
  const txt = btn.querySelector('.sl-txt') as HTMLElement;
  const ul = document.createElement('ul');
  ul.id = `${id}-lista`; ul.className = 'cb-lista sl-lista'; ul.setAttribute('role', 'listbox'); ul.hidden = true;
  wrap.append(btn, ul);

  const rotulo = sel.id ? document.querySelector<HTMLLabelElement>(`label[for="${sel.id}"]`) : null;
  if (rotulo) {
    if (!rotulo.id) rotulo.id = `${id}-rot`;
    rotulo.htmlFor = btn.id;
    btn.setAttribute('aria-labelledby', `${rotulo.id} ${btn.id}`);
    ul.setAttribute('aria-labelledby', rotulo.id);
  }

  let aberto = false, ativo = -1, ops: Op[] = [], buffer = '', tbuf = 0;
  const valor = () => valorDesc.get!.call(sel) as string;

  const coletar = (): (Op | Gr)[] => {
    const out: (Op | Gr)[] = [];
    const add = (o: HTMLOptionElement) => { if (!o.hidden) out.push({ tipo: 'op', v: o.value, t: (o.textContent ?? '').trim(), d: o.disabled, nota: o.dataset.nota ?? '' }); };
    for (const c of Array.from(sel.children)) {
      if (c instanceof HTMLOptGroupElement) {
        const filhos = Array.from(c.children).filter((x) => x instanceof HTMLOptionElement && !(x as HTMLOptionElement).hidden) as HTMLOptionElement[];
        if (filhos.length) { out.push({ tipo: 'gr', t: c.label }); filhos.forEach(add); }
      } else if (c instanceof HTMLOptionElement) add(c);
    }
    return out;
  };
  const atualizarTexto = () => {
    const o = sel.options[sel.selectedIndex];
    txt.textContent = o ? (o.textContent ?? '').trim() : '';
    btn.disabled = sel.disabled;
  };
  const marcar = (rolar: boolean) => {
    const lis = Array.from(ul.querySelectorAll<HTMLElement>('li[role=option]'));
    if (ativo >= lis.length) ativo = lis.length - 1;
    lis.forEach((li, i) => li.classList.toggle('sl-ativo', i === ativo));
    const li = lis[ativo];
    if (li) {
      btn.setAttribute('aria-activedescendant', li.id);
      if (rolar) {
        const t = li.offsetTop, b = t + li.offsetHeight;
        if (t < ul.scrollTop) ul.scrollTop = t - 4; else if (b > ul.scrollTop + ul.clientHeight) ul.scrollTop = b - ul.clientHeight + 4;
      }
    } else btn.removeAttribute('aria-activedescendant');
  };
  const desenhar = () => {
    const itens = coletar();
    ops = itens.filter((i) => i.tipo === 'op') as Op[];
    let k = -1;
    ul.innerHTML = itens.map((i) => {
      if (i.tipo === 'gr') return `<li role="presentation" class="sl-grupo">${esc(i.t)}</li>`;
      k++;
      return `<li role="option" id="${id}-${k}" data-k="${k}" aria-selected="${i.v === valor()}"${i.d ? ' aria-disabled="true" class="sl-desab"' : ''}>${esc(i.t)}${i.nota ? ` <small>${esc(i.nota)}</small>` : ''}</li>`;
    }).join('');
    marcar(false);
  };
  const abrir = () => {
    if (btn.disabled) return;
    aberto = true; ul.hidden = false; btn.setAttribute('aria-expanded', 'true');
    desenhar(); ul.scrollTop = 0;
    ativo = ops.findIndex((o) => o.v === valor() && !o.d);
    if (ativo < 0) ativo = ops.findIndex((o) => !o.d);
    marcar(true);
  };
  const fechar = () => { aberto = false; ul.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.removeAttribute('aria-activedescendant'); };
  const escolher = (k: number) => {
    const o = ops[k];
    if (!o || o.d) return;
    const mudou = o.v !== valor();
    valorDesc.set!.call(sel, o.v);
    atualizarTexto(); fechar(); btn.focus();
    if (mudou) sel.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const mover = (passo: number) => {
    if (!ops.length) return;
    let i = ativo;
    for (let n = 0; n < ops.length; n++) { i = (i + passo + ops.length) % ops.length; if (!ops[i].d) { ativo = i; break; } }
    marcar(true);
  };
  const digitar = (ch: string) => {
    window.clearTimeout(tbuf); buffer += sem(ch); tbuf = window.setTimeout(() => { buffer = ''; }, 700);
    const ini = Math.max(ativo, 0);
    for (let n = 0; n < ops.length; n++) {
      const i = (ini + (buffer.length > 1 ? n : n + 1)) % ops.length;
      if (!ops[i].d && sem(ops[i].t).startsWith(buffer)) { ativo = i; marcar(true); return; }
    }
  };

  btn.addEventListener('click', () => (aberto ? fechar() : abrir()));
  btn.addEventListener('keyup', (e) => { if (e.key === ' ') e.preventDefault(); });
  btn.addEventListener('keydown', (e) => {
    const k = e.key;
    if (!aberto) {
      if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'Enter' || k === ' ') { e.preventDefault(); abrir(); }
      return;
    }
    if (k === 'ArrowDown') { e.preventDefault(); mover(1); }
    else if (k === 'ArrowUp') { e.preventDefault(); mover(-1); }
    else if (k === 'Home') { e.preventDefault(); ativo = ops.findIndex((o) => !o.d); marcar(true); }
    else if (k === 'End') { e.preventDefault(); for (let i = ops.length - 1; i >= 0; i--) if (!ops[i].d) { ativo = i; break; } marcar(true); }
    else if (k === 'Enter' || k === ' ') { e.preventDefault(); escolher(ativo); }
    else if (k === 'Escape') { e.preventDefault(); fechar(); }
    else if (k === 'Tab') fechar();
    else if (k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) digitar(k);
  });
  btn.addEventListener('blur', () => { window.setTimeout(() => { if (aberto && !wrap.contains(document.activeElement)) fechar(); }, 100); });
  document.addEventListener('mousedown', (e) => { if (aberto && !wrap.contains(e.target as Node)) fechar(); });
  ul.addEventListener('mousedown', (e) => e.preventDefault());
  ul.addEventListener('click', (e) => {
    const li = (e.target as HTMLElement).closest('li[data-k]') as HTMLElement | null;
    if (li) escolher(Number(li.dataset.k));
  });
  ul.addEventListener('mousemove', (e) => {
    const li = (e.target as HTMLElement).closest('li[data-k]') as HTMLElement | null;
    if (li && !li.classList.contains('sl-desab')) { const k = Number(li.dataset.k); if (k !== ativo) { ativo = k; marcar(false); } }
  });

  // mudanças feitas pelo código da página (value, opções, disabled) refletem no menu
  Object.defineProperty(sel, 'value', {
    configurable: true,
    get() { return valorDesc.get!.call(this); },
    set(v) { valorDesc.set!.call(this, v); atualizarTexto(); if (aberto) desenhar(); },
  });
  new MutationObserver(() => { atualizarTexto(); if (aberto) desenhar(); })
    .observe(sel, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'hidden', 'label', 'data-nota'] });
  atualizarTexto();
}
