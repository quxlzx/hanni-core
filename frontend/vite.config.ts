import { defineConfig } from "vite";
import { readFileSync } from "node:fs";
export default defineConfig({
  plugins: [
    {
      name: "runtime-license-notices",
      generateBundle() {
        const runtimeLicenses = ["react", "react-dom"]
          .map(
            (name) =>
              `${name}\n\n${readFileSync(new URL(`node_modules/${name}/LICENSE`, import.meta.url), "utf8")}`,
          )
          .join("\n\n");
        const fontLicenses = ["Geist-LICENSE.txt", "Geist-OFL.txt"]
          .map((name) =>
            readFileSync(new URL(`src/fonts/${name}`, import.meta.url), "utf8"),
          )
          .join("\n\n");
        this.emitFile({
          type: "asset",
          fileName: "THIRD_PARTY_NOTICES.txt",
          source: `${runtimeLicenses}\n\nGeist Sans\n\n${fontLicenses}`,
        });
      },
    },
  ],
  build: {
    outDir: "../src/hanni/dashboard/static",
    emptyOutDir: false,
    rollupOptions: {
      output: { entryFileNames: "app.js", assetFileNames: "style.css" },
    },
  },
});
