// Read original TypeScript syntax without importing or running application code.
const fs = require('fs');
const path = require('path');
const Module = require('module');
const repo = path.resolve(__dirname, '..', '..');
const ts = Module.createRequire(path.join(repo, 'frontend/package.json'))('typescript');
const sourceRoot = path.join(repo, 'frontend/src');
const tags = new Set(['button', 'input', 'select', 'textarea', 'a', 'summary', 'dialog']);
const methods = new Set(['write', 'request', 'usePrivateResource', 'useResource']);
const modules = [];
let routes = [];

function bounded(text) { return text.length > 1600 ? text.slice(0, 1600) + ' [truncated]' : text; }
for (const filename of fs.readdirSync(sourceRoot).filter(n => n.endsWith('.tsx'))) {
  const text = fs.readFileSync(path.join(sourceRoot, filename), 'utf8');
  const source = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const controls = [], apis = [], declarations = [], stateTemplates = [], dialogTemplates = [];
  function location(node) {
    const p = source.getLineAndCharacterOfPosition(node.getStart(source));
    return {line: p.line + 1, column: p.character + 1};
  }
  function scope(node) {
    let p = node.parent;
    while (p) {
      if (ts.isFunctionDeclaration(p) && p.name) return p.name.getText(source);
      if (ts.isVariableDeclaration(p) && p.initializer && (ts.isArrowFunction(p.initializer) || ts.isFunctionExpression(p.initializer)))
        return p.name.getText(source);
      p = p.parent;
    }
    return '<module>';
  }
  function renderBoundaries(node) {
    const boundaries = [];
    let p = node.parent;
    while (p && !ts.isFunctionDeclaration(p)) {
      if (ts.isConditionalExpression(p)) boundaries.push({kind:'conditional',
        branch:node.getStart(source) >= p.whenTrue.getStart(source) && node.end <= p.whenTrue.end ? 'then' : 'else',
        expression:bounded(p.condition.getText(source)), ...location(p)});
      if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken)
        boundaries.push({kind:'condition', expression:bounded(p.left.getText(source)), ...location(p)});
      if (ts.isCallExpression(p) && ts.isPropertyAccessExpression(p.expression) && p.expression.name.text === 'map')
        boundaries.push({kind:'repeated', expression:bounded(p.expression.expression.getText(source)), ...location(p)});
      p = p.parent;
    }
    return boundaries;
  }
  function routeValue(expression, route) {
    if (ts.isParenthesizedExpression(expression)) return routeValue(expression.expression, route);
    if (ts.isPrefixUnaryExpression(expression) && expression.operator === ts.SyntaxKind.ExclamationToken) {
      const inner = routeValue(expression.operand, route); return inner === undefined ? undefined : !inner;
    }
    if (!ts.isBinaryExpression(expression)) return undefined;
    const op = expression.operatorToken.kind;
    if ([ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(op)) {
      const pairs = [[expression.left, expression.right], [expression.right, expression.left]];
      for (const [variable, literal] of pairs) {
        if (ts.isIdentifier(variable) && ['view', 'screen'].includes(variable.text) && ts.isStringLiteral(literal))
          return op === ts.SyntaxKind.EqualsEqualsEqualsToken ? route === literal.text : route !== literal.text;
      }
    }
    const left = routeValue(expression.left, route), right = routeValue(expression.right, route);
    if (op === ts.SyntaxKind.AmpersandAmpersandToken)
      return left === false || right === false ? false : left === true && right === true ? true : undefined;
    if (op === ts.SyntaxKind.BarBarToken)
      return left === true || right === true ? true : left === false && right === false ? false : undefined;
    return undefined;
  }
  function routeConstraints(node) {
    // Three-valued route predicates narrow only provable branches. Data/editor
    // flags remain unknown; they never manufacture a route or execution result.
    const candidates = ['home','chat','voice','planner','workflows','tasks','calendar','projects','memory','mission','cluster','models','model-routing','agents','activity','screen','notifications','settings','mcp','mini'];
    return candidates.filter(route => {
      let p = node.parent;
      while (p && !ts.isFunctionDeclaration(p)) {
        if (ts.isConditionalExpression(p)) {
          const value = routeValue(p.condition, route);
          const thenBranch = node.getStart(source) >= p.whenTrue.getStart(source) && node.end <= p.whenTrue.end;
          if (value !== undefined && value !== thenBranch) return false;
        }
        if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && routeValue(p.left, route) === false)
          return false;
        p = p.parent;
      }
      return true;
    });
  }
  function visit(node) {
    if (filename === 'workspace.tsx' && ts.isVariableDeclaration(node) && node.name.getText(source) === 'screens'
        && node.initializer && ts.isObjectLiteralExpression(node.initializer)) {
      routes = node.initializer.properties.filter(ts.isPropertyAssignment).map(property => {
        const key = ts.isStringLiteral(property.name) ? property.name.text : property.name.getText(source);
        const fields = {};
        if (ts.isObjectLiteralExpression(property.initializer)) {
          for (const field of property.initializer.properties.filter(ts.isPropertyAssignment))
            fields[field.name.getText(source)] = ts.isStringLiteral(field.initializer) ? field.initializer.text : field.initializer.getText(source);
        }
        return {route: key, hash: '#' + key, ...fields, ...location(property)};
      });
    }
    if (ts.isFunctionDeclaration(node) && node.name) declarations.push({name: node.name.text, ...location(node)});
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(source);
      if (['Empty', 'Skeleton', 'FeatureDialog', 'Modal'].includes(tag)) {
        const item = {component: scope(node), tag, attributes: node.attributes.getText(source), ...location(node), outcome: 'NOT_RUN'};
        (['FeatureDialog', 'Modal'].includes(tag) ? dialogTemplates : stateTemplates).push(item);
      }
    }
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && tags.has(node.tagName.getText(source))) {
      const attrs = {};
      for (const a of node.attributes.properties) {
        if (ts.isJsxAttribute(a)) attrs[a.name.getText(source)] = a.initializer ? bounded(a.initializer.getText(source)) : true;
        else attrs['spread'] = bounded(a.getText(source));
      }
      const element = ts.isJsxOpeningElement(node) ? node.parent : node;
      const childText = ts.isJsxElement(element) ? element.children.filter(ts.isJsxText).map(n => n.text).join(' ').replace(/\s+/g,' ').trim() : '';
      const position = location(node);
      controls.push({id: `${filename}:${position.line}:${position.column}`, ...position, tag: node.tagName.getText(source),
        component: scope(node), attributes: attrs, static_child_text: childText,
        source_excerpt:bounded(element.getText(source)), render_boundaries:renderBoundaries(node), route_predicate_candidates:routeConstraints(node),
        observation_class: 'SOURCE_TEMPLATE_ONLY', outcome: 'NOT_RUN',
        evidence_file: 'frontend/src/' + filename, reason: 'Awaiting native observation and action/readback evidence.',
        scope: 'Conditional or repeated JSX slot; native visibility, concrete label and control behavior are unobserved.'});
    }
    if (ts.isCallExpression(node) && methods.has(node.expression.getText(source))) {
      const arg = node.arguments[0];
      apis.push({method: node.expression.getText(source), path_expression: arg ? bounded(arg.getText(source)) : null,
        component: scope(node), ...location(node), evidence_class: 'SOURCE_DEPENDENCY_ONLY'});
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  modules.push({file: 'frontend/src/' + filename, declarations, controls, api_dependencies: apis,
    empty_loading_state_templates: stateTemplates, dialog_templates: dialogTemplates});
}
const css = fs.readFileSync(path.join(sourceRoot, 'style.css'), 'utf8');
const fontFace = css.match(/@font-face\s*\{[\s\S]*?\}/)?.[0] || null;
const fontTokens = Object.fromEntries([...css.matchAll(/(--sans|--mono):\s*([^;]+);/g)].map(m => [m[1],m[2]]));
process.stdout.write(JSON.stringify({scope:'Original source AST only; neither native desktop execution nor coverage acceptance',
  routes, auxiliary_surfaces:[{surface:'mini',query:'?view=mini',source:'frontend/src/mini.tsx'}],
  typography:{font_face:fontFace,font_tokens:fontTokens,loaded_font_verified:false,alternatives_evaluated:false},modules},null,2));
