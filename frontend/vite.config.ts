import { defineConfig } from "vite";
import { readFileSync, readdirSync } from "node:fs";
export default defineConfig({
  plugins: [
    {
      name: "runtime-license-notices",
      generateBundle() {
        const packages = JSON.parse(
          readFileSync(new URL("package-lock.json", import.meta.url), "utf8"),
        ).packages;
        const runtimeLicenses = Object.keys(packages)
          .filter(
            (name) => name.startsWith("node_modules/") && !packages[name].dev,
          )
          .sort()
          .map((name) => {
            const directory = new URL(`${name}/`, import.meta.url);
            const licenses = readdirSync(directory).filter((file) =>
              /^(licen[sc]e|copying)(\.|$)/i.test(file),
            );
            if (!licenses.length)
              throw new Error(`Missing runtime license for ${name}`);
            return `${name.slice("node_modules/".length)}\n\n${licenses.map((file) => readFileSync(new URL(file, directory), "utf8")).join("\n\n")}`;
          })
          .join("\n\n");
        const fontLicenses = ["Geist-LICENSE.txt", "Geist-OFL.txt"]
          .map((name) =>
            readFileSync(new URL(`src/fonts/${name}`, import.meta.url), "utf8"),
          )
          .join("\n\n");
        this.emitFile({
          type: "asset",
          fileName: "THIRD_PARTY_NOTICES.txt",
          source: `${runtimeLicenses}\n\nGeist Sans\n\n${fontLicenses}`.replace(/[ \t]+$/gm, ""),
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
