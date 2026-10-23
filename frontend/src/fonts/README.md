# Bundled interface font

The interface uses Geist Sans for a clean, neutral sans-serif appearance.
Technical measurements and code retain the existing monospace font.

`GeistSans-Variable.woff2` is an unmodified copy of
[`fonts/Geist/webfonts/Geist[wght].woff2`](https://github.com/vercel/geist-font/blob/10dc7658f13c38a474cde201bb09a4617267545b/fonts/Geist/webfonts/Geist%5Bwght%5D.woff2)
from Vercel's Geist repository, pinned to revision
`10dc7658f13c38a474cde201bb09a4617267545b`.

SHA-256: `2ffebe993e969069a9789d15164b7715d42491b5835516c5e3b935d5f81b05f1`.

The upstream `LICENSE.txt` and `OFL.txt` are preserved here as
`Geist-LICENSE.txt` and `Geist-OFL.txt`, and included in the generated runtime
notices. The font is distributed under the SIL Open Font License 1.1.

The CSS URL's `?inline` suffix tells Vite to embed the font in the packaged CSS.
The original loopback dashboard serves it without additional font routes or
network access. All interface weights share the same variable font file.
