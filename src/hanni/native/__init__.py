"""Native HANNI agent core: the resident loop that speaks OpenAI-compatible
chat/completions directly to the configured model endpoint.

This replaces the Hermes AIAgent as the loop engine while keeping the
security architecture identical: bounded tool menus, JSON-Schema validation,
durable action requests, and receipt-producing execution authority.
"""
