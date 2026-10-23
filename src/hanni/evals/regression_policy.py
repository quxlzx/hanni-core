"""Coverage check for capabilities added after the frozen V1 registry snapshot."""
from __future__ import annotations


def new_capability_gaps(names, baseline_names, routing_cases, llm_cases):
    """Return missing minimum coverage for each newly registered capability.

    An LLM scenario counts only if it requires or forbids the capability. Mere
    mention in a mock-result menu is not evidence that use was evaluated.
    """
    gaps = {}
    for name in sorted(set(names) - set(baseline_names)):
        routing = sum(
            name == case.primary or name in case.required or name in case.blocked_capabilities
            for case in routing_cases
        )
        llm = sum(
            name in case.get('required_tools', ())
            or name in case.get('forbidden_tools', ())
            or any(name in group for group in case.get('required_any_tools', ()))
            for case in llm_cases
        )
        if routing < 2 or llm < 2:
            gaps[name] = {'routing_probes': routing, 'llm_scenarios': llm}
    return gaps
