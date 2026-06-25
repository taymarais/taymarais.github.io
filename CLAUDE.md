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
