# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this site is

Personal author website for Tay Marais, a fiction author. Plain HTML, inline CSS,
vanilla JS. No npm, no bundler, no linter, no test runner.

🔴 **Deployment is NOT git-based, and pushing to `main` publishes nothing.** The site is served by
**Cloudflare Pages** at **https://taymarais.com**, from a project with no git connection. What goes
live is also **not identical to what is in git**: fonts are embedded at build time. Publishing is
two commands, both in the studio repo:

```
bash scripts/monta-site-autora.sh <path-to-this-clone> -o dist/site-autora
bash scripts/publica-site.sh taymarais dist/site-autora
```

`taymarais.github.io` is now the pin image store. Its pages redirect to the domain by a
hostname-guarded script; `/pins/` is left alone, because 24 published pins depend on those files.

**The root is the book page:** `/` serves `books/where-the-ocean-ends.html` by a 200 rewrite in
`_redirects`, without changing the URL. Both old homes (`index.html`, `pt/index.html`) carry
`noindex` and are linked from nowhere until the new home is built.

## Site structure

```
index.html              # EN home
contact.html            # EN contact form
books/
  where-the-ocean-ends.html   # EN book page (Chapter 1 + email gate)
pt/
  index.html            # PT-BR home
  contact.html          # PT-BR contact form
  books/
    onde-o-oceano-acaba.html  # PT-BR book page
assets/                 # Images (WebP) and favicon (PNG)
```

Every English page has a Portuguese counterpart and vice versa. Cross-language links use the `.lang-selector` pill-style anchor.

## Pinterest — a máquina de pin mora aqui

O site não é só as páginas: ele é também o **servidor de feed** que o Pinterest lê para publicar pin
sozinho, sem PC, sem celular e sem API. O manual completo (boards, cadência, copy, medição) fica no
repo do estúdio, em `projetos/tay-marais/marketing/maquina-de-pin.md` — aqui ficam as peças.

```
pins/                      # as artes e fotos, 1200x1800. Nome de arquivo é PÚBLICO
pins-<algo>.xml            # os feeds RSS, um por board. Conectados em Configurações -> Publicar automaticamente
pinterest/publicar.py      # o robô: uma peça por execução, da fila para o feed
pinterest/fila.txt         # o que ainda vai sair, em ordem de PUBLICAÇÃO (o inverso da grade)
pinterest/publicados.txt   # o que já saiu, com data. Cruza com utm_content no Analytics
pinterest/painel.py        # desenha a grade do painel a partir das duas listas acima
.github/workflows/publicar-pin.yml   # cron seg/qua/sex às 09h, 12h e 15h (BRT)
```

🔴 **O painel dela não se edita à mão.** A tela Feed do painel é a GRADE — as fileiras do jeito
que a aba Criados desenha — e ela é **derivada** de `publicados.txt` + `fila.txt`, nunca escrita.
Em 02/09 uma troca de bloco feita à mão engoliu 24 fileiras inteiras de um artifact de 7 MB, sem
erro nenhum: a autora só descobriu porque olhou. Quem gera é `pinterest/painel.py --grade`, e
`--conferir painel.html` confere peça por peça se o que está na tela bate com as fontes. **Rodar
o `--conferir` antes de publicar o painel**, sempre.

⚠️ **A grade é o inverso da fila nos DOIS sentidos** — entre fileiras e dentro da fileira. A
primeira peça da fila é a da **direita** da última fileira. Inverter só as fileiras, e não as
peças, desenha uma grade que não existe.

🔴 **O nome do arquivo do feed não diz o board.** `pins-adam-madeleine.xml` está conectado ao board
**`Where The Ocean Ends`** — é herança do lote 1 e **renomear quebra a conexão dela**. O mapa de
verdade é o dicionário `FEEDS` em `pinterest/publicar.py`, e é o único lugar de onde tirar essa
informação. O board do casal é o **`pins-couple.xml`**, batizado assim depois que o nome anterior
(`pins-adam-e-madeleine.xml`, um `-e-` de diferença) fez a autora conectar o feed errado.

⚠️ **Nome de feed novo tem que ser inconfundível na tela do celular**, não só correto. Nunca criar um
que compartilhe prefixo com outro já conectado.

🔴 **A grade não tem fileira, tem contagem.** A aba Criados é fluxo contínuo de três colunas, mais
novo primeiro: cada pin novo empurra todos os outros uma casa, e **fileira só existe enquanto o total
de pins criados for múltiplo de 3.** Publicar 1 ou 2 peças soltas desalinha tudo que está embaixo, e
pin publicado não se reordena. Por isso o robô **passa o dia inteiro** quando perde o primeiro horário
(09h) — meia fileira é pior que nenhuma. `--forcar` fura essa regra, e só se usa de propósito.

**Para segurar a publicação** (fileira anterior ainda no ar, copy em dúvida, lote sendo remontado):
primeira linha viva de `pinterest/fila.txt` igual a `PAUSA` — o robô passa a vez, quieto e sem erro.
Apagar a linha volta a publicar. **O motivo vai em comentário, nunca na mesma linha continuada**, ou a
continuação vira item de fila quando a pausa sair.

🔴 **O feed é fila, não catálogo.** O `pubDate` não segura nada: o Pinterest publica tudo que estiver
no arquivo, na hora que lê. Nunca escrever um lote inteiro de uma vez — é o que o robô existe para
evitar. O `<guid>` é a URL da imagem e o Pinterest deduplica por ele, então os feeds podem acumular
histórico sem republicar nada.

⚠️ **Nunca reescrever o `<item>` de um pin que já publicou** (link ou texto). Acrescentar no fim é
seguro; editar o que já virou pin não é território conhecido.

## Design system

All CSS is **inline per page** (inside `<style>` tags) — there is no shared stylesheet.
The palette was replaced on 2026-09-05/06: **the wall of the story is black and white.** No rose,
which is the author's own colour and not the book's.

```css
:root {
    --bg-deep: #010204;    /* the black measured on the EDGE of cover.webp */
    --surface: #0F1218;    /* cards, modals, raised areas */
    --accent:  #EDEFF2;    /* ice white: CTAs, highlights, active borders */
    --text-main: #EDEFF2;
    --text-muted: #98A0A9;
    --fio: 237, 239, 241;  /* used as rgba(var(--fio), .20) on borders */
    --font-heading: 'Playfair Display SC', serif;
    --font-ui: 'Montserrat', sans-serif;
    --font-reading: 'Lora', serif; /* book pages only, and it IS the chapter text */
}
```

⚠️ **The old palette (`#1A1210`, `#261C19`, `#D4A396`, `#EAE5DE`, `#A8A29E`) is still in the files**,
in a first `:root` that the new one overrides by the cascade. A grep for the old colours gives false
positives: check which `:root` comes last before concluding a page was left behind.

The rose `#E7AEB8` survives as a border thread on the author's own pages only: contact and privacy.

Responsive breakpoints: `900px` (layout reflows) and `600px` (hamburger menu appears, nav hides).

## Third-party integrations

- **Google Apps Script** — single endpoint used for both the contact form and the email capture (tide gate) on book pages. The same URL is used across EN and PT pages. A hidden `name="lang"` field (`"en"` or `"pt"`) distinguishes submissions.
- **Pinterest Tag** — conversion tracking pixel present on home and book pages. The `pintrk('track', 'lead')` call fires on email capture form submission.
- **Fonts** — Playfair Display SC, Montserrat, Lora (Lora only on book pages, and it is
  the chapter text itself). The `<link>` in the source still points at Google Fonts, but **the build
  replaces it with a single self-hosted `/fontes.css`**: nothing goes live calling Google. The build
  fails if any page still does.

## Key interaction patterns

**Hamburger menu** (mobile `<600px`): a `<button class="menu-toggle">` toggles `.active` on itself and `.open` on the `<nav>` element. Clicking any nav link closes it. Replicate this exact JS block on every new page.

**Book page "Open Book" flow**: clicking `#btn-open` sets `#reading-section` to `display: block`, fades it to `opacity: 1`, scrolls to it, and dims `#book-hero` to `opacity: 0.3`. The reading content is hidden by default.

**Tide gate**: a `.tide-gate` div uses a CSS gradient overlay to visually cut off the reading content midway. The `#lead-form` posts to the Google Apps Script endpoint; on success the `#success-modal` appears and `pintrk('track', 'lead')` fires.

## Adding new pages

1. Copy the nearest equivalent page (EN or PT) as a starting point.
2. Keep all CSS inline in the `<style>` block.
3. Create both EN and PT versions with `.lang-selector` links pointing to each other.
4. Update navigation links in existing pages to include the new page if it warrants a nav entry.
5. Asset paths use relative references — mind the nesting depth (`../assets/` from `books/`, `../../assets/` from `pt/books/`).

## Adding a new book

- Add a card to `index.html` and `pt/index.html` following the `.book-card-vertical` pattern.
- Create `books/<slug>.html` (EN) and `pt/books/<slug-pt>.html` (PT) following the existing book page structure.
- Provide a separate cover image in `assets/` (WebP preferred).
- Use a separate Spotify playlist link if applicable; update the `href` in the `.playlist-link` anchor.
