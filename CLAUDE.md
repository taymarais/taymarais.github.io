# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this site is

Personal author website for Tay Marais, a fiction author. It is a **static site with no build system** — plain HTML, inline CSS, and vanilla JS. No npm, no bundler, no linter, no test runner. Deployment is via GitHub Pages (pushing to `main` is sufficient).

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
.github/workflows/publicar-pin.yml   # cron seg/qua/sex às 09h, 12h e 15h (BRT)
```

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

All CSS is **inline per page** (inside `<style>` tags) — there is no shared stylesheet. When editing or creating pages, replicate the same CSS custom properties:

```css
:root {
    --bg-color / --bg-deep: #1A1210;      /* near-black background */
    --surface / --surface-color: #261C19; /* card/surface background */
    --accent / --accent-color: #D4A396;   /* dusty rose — CTAs, borders, highlights */
    --text-main: #EAE5DE;                 /* cream body text */
    --muted-text / --text-muted: #A8A29E; /* secondary text */
    --border-color: rgba(234, 229, 222, 0.1);
    --font-heading: 'Playfair Display SC', serif;
    --font-ui: 'Montserrat', sans-serif;
    --font-reading: 'Lora', serif; /* book pages only */
}
```

Responsive breakpoints: `900px` (layout reflows) and `600px` (hamburger menu appears, nav hides).

## Third-party integrations

- **Google Apps Script** — single endpoint used for both the contact form and the email capture (tide gate) on book pages. The same URL is used across EN and PT pages. A hidden `name="lang"` field (`"en"` or `"pt"`) distinguishes submissions.
- **Pinterest Tag** — conversion tracking pixel present on home and book pages. The `pintrk('track', 'lead')` call fires on email capture form submission.
- **Google Fonts** — Playfair Display SC, Montserrat, Lora (Lora only on book pages).

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
