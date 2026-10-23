# Routing architecture V4 development checkpoint

HANNI still uses one resident Qwen3.5-4B model. The Python router only selects a
bounded MCP capability menu; it never chooses or executes a tool on the model's
behalf. The model prompt and tool descriptions were not changed in this work.

1. `conceptual_query` and `normalize` normalize casual speech, history
   references, and a few unambiguous hardware terms.
2. The host rejects general educational questions, unsafe requests and
   unbound follow-ups before retrieving live tools.
3. `clauses` separates complete requests and conservative topic shifts, such
   as an agenda fragment followed by disk-space language. The host routes each
   part and reserves a tool from each clause before filling the remaining slots.
4. Calendar and clock resolvers fix dates and times before the model sees the
   menu. Existing explicit media and operation/object rules remain authoritative.
5. Diagnostic scopes and lexical intent prototypes complement those rules.
   `rank_intents` scores every eligible prototype using canonical token overlap
   and character trigrams. Anchor matches add evidence instead of being a
   mandatory prerequisite. An intent needs a minimum score and a margin over
   its runner-up. Ambiguous diagnostic matches receive a bounded general
   diagnostic menu; unrelated ambiguous language receives no tool.
6. The host checks registry permissions and the configured menu ceiling
   (currently eight). This layer never bypasses execution-time validation.

The prototype library is small and its static features are precomputed. Runtime
code computes features only for the owner clause. It does not cache owner text.
No embedding model or network inference was adopted: there was no suitable tiny
local embedding model available to benchmark in this environment. The optional
semantic fallback phases remain unimplemented, rather than silently adding a
large dependency or using Qwen as the router.

Inspect routing without calling tools:

```powershell
hanni eval routing-debug "Friday agenda, remaining disk space"
```

The debug output includes normalized clauses, concepts, known app entities,
hard-rule and diagnostic candidates, ranked prototype scores, anchor boosts,
confidence margin, final families, selected tools and blocked capabilities.
This is deterministic router state, not model reasoning.

Known limitations: lexical prototypes still miss genuinely new metaphors, and
some no-tool questions require explicit educational-question detection. The
first untouched V4B development check scored only 80%, so this architecture is
a development checkpoint, **not** a Tool Intelligence V1 freeze.
