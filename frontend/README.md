# HANNI OS frontend

React + TypeScript + Vite, served by the existing Python loopback dashboard.

Run `npm ci`, then `npm run build`. The build writes the three packaged assets
to `../src/hanni/dashboard/static`. Commit the source, lockfile and generated
assets together. Normal HANNI users do not need Node or npm.

`npm run check` checks the TypeScript contracts without rebuilding. Source uses
custom CSS tokens, semantic HTML, native dialogs and SVG/canvas charts. There
are no runtime CDN, font or image dependencies. Geist Sans is bundled into the
generated CSS and works offline; its licenses are included in the packaged
`THIRD_PARTY_NOTICES.txt`. See [font provenance](src/fonts/README.md).

See [the verified integration map and limitations](../docs/HANNI_OS.md).
