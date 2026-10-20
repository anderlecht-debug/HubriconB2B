# Fonts for the films

Inter Display, Regular and SemiBold, from the Inter 4.1 release
(https://github.com/rsms/inter/releases/tag/v4.1, `extras/ttf/`), under the SIL Open
Font License 1.1 (`OFL.txt`). Added 2026-10-19.

The site loads Inter from Google Fonts with its optical-size axis, so every line from
about 20px up is drawn in Inter Display (BRAND.md, "Type"). Every piece of text in a
film is 40px or more at 1080p, so a film frame is set in Inter Display only, from these
two files, and `assets/inter.mjs` measures text from the same files' advance widths.

| File | SHA-256 |
|---|---|
| `InterDisplay-Regular.ttf` | `99614bda7ff423aaf470990692dd93613a5971ab4446e4a6d5a83b3d74865074` |
| `InterDisplay-SemiBold.ttf` | `0310d7a325896129730c6c8cf9a6e0f81ee258bedf77b1ff059b2a7b75f74e02` |

Not deployed: `film` is in `.vercelignore`.
