// Original React screen component with an isolated status-resource leaf.
const fs = require('fs');
const path = require('path');
const Module = require('module');
const root = path.resolve(__dirname, '..', '..');
const frontend = path.join(root, 'frontend');
const localRequire = Module.createRequire(path.join(frontend, 'package.json'));
const ts = localRequire('typescript');
const React = localRequire('react');
const ReactDOMServer = localRequire('react-dom/server');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const filename = path.join(frontend, 'src', 'awareness.tsx');
const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const calls = [];
const forbidden = () => { throw new Error('Unused UI dependency invoked during screen rendering.'); };
const leafRequire = name => {
  if (name === './feature_types') return { usePrivateResource: (url, token) => {
    calls.push({ url, token_present: Boolean(token) });
    return { data: input.status, error: input.error || '', refresh: forbidden };
  } };
  if (name === './api') return { write: forbidden };
  if (name === './feature_ui') return { FeatureDialog: forbidden };
  if (name === './screens') return { AudioSettings: forbidden };
  if (name.endsWith('.css')) return {};
  return localRequire(name);
};
const loaded = { exports: {} };
new Function('require', 'module', 'exports', output)(leafRequire, loaded, loaded.exports);
const html = ReactDOMServer.renderToStaticMarkup(React.createElement(loaded.exports.ScreenAwarenessPage,
  { token: input.token_present ? 'controlled-screen-projection' : '', prepare: forbidden }));
process.stdout.write(JSON.stringify({ html, resource_calls: calls, scope: 'Original React component; isolated status-resource leaf; no browser or capture.' }));
