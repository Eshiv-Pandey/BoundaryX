"""Conventional finite constraint-pruning comparator, not a novelty claim.

Only a fully assigned guard with a definitely false value prunes an argument
prefix. Uncertainty is preserved, correlated whole frames are retained, and
every final tuple uses the unchanged exact relation interpreter. Negative cuts
are checked by the unchanged exhaustive goal-pruned v2 checker.
"""
from __future__ import annotations

from . import direct_goal_pruned_v2 as direct
from . import refinement_oracle as language

CATEGORIES = ("dependency_nodes", "domain_recipes", "domain_keys", "argument_prefixes", "partial_guard_checks")


def _dependencies(expression, meter):
    meter.tick("dependency_nodes")
    tag, value = next(iter(expression.items()))
    if tag == "arg":
        return {value}, False
    if tag == "emit_path":
        return set(), True
    names, emitted = set(), False
    if tag in ("array", "object"):
        for child in (value if tag == "array" else value.values()):
            dependency, request = _dependencies(child, meter)
            names |= dependency
            emitted |= request
    return names, emitted


def _assignments(relation, frame, meter):
    """Finite ordered DFS with conservative guard dependency checks."""
    domains = []
    for name in sorted(relation["arguments"]):
        values = {}
        for recipe in relation["arguments"][name]:
            meter.tick("domain_recipes")
            if "literal" in recipe:
                value = recipe["literal"]
            elif recipe["binding"] in frame:
                value = frame[recipe["binding"]]
            else:
                continue
            meter.tick("domain_keys")
            values.setdefault(language._key(value), value)
        if not values:
            return
        domains.append((name, list(values.values())))
    emitted_dependencies, _ = _dependencies(relation["emit"], meter)
    guards = []
    for guard in relation["guards"]:
        dependencies, uses_request = _dependencies(guard["left"], meter)
        if guard["op"] != "present":
            right, request = _dependencies(guard["right"], meter)
            dependencies |= right
            uses_request |= request
        if uses_request:
            dependencies |= emitted_dependencies
        guards.append((guard, dependencies, uses_request))

    def fails(arguments, available, previous):
        # Evaluate a closed guard once along this DFS branch. A missing binding
        # or explicit unknown remains indeterminate and cannot prune a prefix.
        closed = set(previous)
        request = None
        for index, (guard, dependencies, uses_request) in enumerate(guards):
            if index in closed or not dependencies <= available:
                continue
            closed.add(index)
            meter.tick("partial_guard_checks")
            if uses_request and request is None:
                request = language._eval(relation["emit"], arguments, frame, language._ABSENT, meter)
            emitted = request if uses_request else language._ABSENT
            left = language._eval(guard["left"], arguments, frame, emitted, meter)
            if guard["op"] == "present":
                truth = None if left is language._UNKNOWN else left is not language._ABSENT
            else:
                right = language._eval(guard["right"], arguments, frame, emitted, meter)
                truth = (None if language._contains_unknown(left) or language._contains_unknown(right)
                         else language._same(left, right))
                if truth is not None and guard["op"] == "ne":
                    truth = not truth
            if truth is False:
                return True, closed
        return False, closed

    def visit(index, arguments, closed):
        rejected, closed = fails(arguments, set(arguments), closed)
        if rejected:
            return
        if index == len(domains):
            yield dict(arguments)
            return
        name, values = domains[index]
        for value in values:
            meter.tick("argument_prefixes")
            arguments[name] = value
            yield from visit(index + 1, arguments, closed)
        arguments.pop(name, None)

    yield from visit(0, {}, set())


def evaluate(profile, now, budget=None):
    language.validate_profile(profile)
    language._require(type(now) is int, "now must be integer epoch seconds")
    meter = language._Meter(budget)
    meter.stats.update({name: 0 for name in CATEGORIES})
    meter.stats["goal_pruned_edges"] = 0
    model, evidence = profile["model"], profile["model"]["evidence"]

    def unknown(reason):
        return {"decision": "unknown", "reason": reason, "certificate": None, "stats": dict(meter.stats)}

    def supported(steps):
        certificate = dict(language._header(profile, now), kind="recipe-path",
                           transition_ids=[step["edge"] for step in steps], steps=steps)
        return {"decision": "supported", "reason": "concrete_recipe_path", "certificate": certificate,
                "stats": dict(meter.stats)}

    if not evidence["observed_at"] <= now <= evidence["valid_until"]:
        return unknown("evidence_not_fresh")
    try:
        safe, goal, outgoing, uncertain, viable = language._topology(profile, meter)
        first, horizon = model["initial"], model["horizon"]
        frame = dict(profile["initial_bindings"])
        current = {(first, language._key(frame)): (frame, [])}
        if safe[first] is not True or first not in viable[horizon]:
            current = {}
        layers, cache = [], {}
        for depth in range(horizon + 1):
            layers.append([{"state": state, "bindings": dict(value[0])}
                           for (state, _), value in sorted(current.items())])
            following = {}
            for (state, _), (bindings, steps) in sorted(current.items()):
                meter.tick("state_expansions")
                meter.stats["product_states"] += 1
                if goal[state] is True:
                    return supported(steps)
                if depth == horizon:
                    continue
                for edge in outgoing[state]:
                    meter.tick("graph_edges")
                    target = edge["target"]
                    if safe[target] is not True:
                        continue
                    if target not in viable[horizon - depth - 1]:
                        meter.stats["goal_pruned_edges"] += 1
                        continue
                    key = edge["id"], language._key(bindings)
                    cached = key in cache
                    relation = profile["relations"][edge["id"]]
                    outcomes = (iter(cache[key]) if cached else
                                (language._step(relation, bindings, arguments, meter)
                                 for arguments in _assignments(relation, bindings, meter)))
                    retained = []
                    for truth, step in outcomes:
                        if cached:
                            meter.tick("cached_relation_outcomes")
                        else:
                            retained.append((truth, step))
                        if truth is None:
                            uncertain = True
                        elif truth:
                            step = dict(step, edge=edge["id"])
                            if goal[target] is True:
                                return supported(steps + [step])
                            after = step["bindings_after"]
                            following.setdefault((target, language._key(after)), (after, steps + [step]))
                    if not cached:
                        cache[key] = retained
            current = following
        if uncertain:
            return unknown("indeterminate_observables_or_relations")
        if not evidence["complete"] or not profile["coverage"]["complete"]:
            return unknown("incomplete_model_or_relation_coverage")
        certificate = dict(language._header(profile, now), kind=direct.NEGATIVE_KIND, product_layers=layers)
        return {"decision": "unsupported", "reason": "guard_pruned_goal_relevant_product_exhausted",
                "certificate": certificate, "stats": dict(meter.stats)}
    except language._Limit:
        return unknown("work_budget_exhausted")


def check_certificate(profile, result, now):
    return direct.check_certificate(profile, result, now)
