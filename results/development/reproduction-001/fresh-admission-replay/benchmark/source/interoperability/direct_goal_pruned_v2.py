"""Goal-pruned forward relational comparator, preserving the v1 implementation.

This is a conventional comparator improvement, not a novelty claim. It retains
the exact recipe language, freshness/coverage rules, correlated frames, relation
cache, conservative contracted-observable uncertainty and first-feasible tuple
return on a goal edge. A relation is expanded only if its target can still reach
a possible safe goal in the remaining horizon. Topology analysis is still run
and charged in full; inspecting a pruned edge still incurs its existing edge
tick. ``goal_pruned_edges`` is an auxiliary count, not another work-unit type.

Positive witnesses use the existing independent checker. Negative certificates
have an explicit new kind: their layers close only the goal-relevant product.
The checker below reconstructs that closure independently, without calling this
solver or the old solver. It shares the preserved recipe-language operations,
not the candidate's implementation. The old checker is not silently changed.
"""
from __future__ import annotations

from . import refinement_oracle as language


INPUT_SCHEMA = 'recipe-continuation/1'
NEGATIVE_KIND = 'goal-pruned-relational-exhaustion/2'


def evaluate(profile, now, budget=None):
    """Search the bounded known-frame product after safe may-goal pruning."""
    language.validate_profile(profile)
    language._require(type(now) is int, 'now must be integer epoch seconds')
    meter = language._Meter(budget)
    meter.stats['goal_pruned_edges'] = 0
    model, evidence = profile['model'], profile['model']['evidence']

    def unknown(reason):
        return {'decision': 'unknown', 'reason': reason, 'certificate': None,
                'stats': dict(meter.stats)}

    def supported(steps):
        certificate = dict(language._header(profile, now), kind='recipe-path',
                           transition_ids=[row['edge'] for row in steps], steps=steps)
        return {'decision': 'supported', 'reason': 'concrete_recipe_path',
                'certificate': certificate, 'stats': dict(meter.stats)}

    if not evidence['observed_at'] <= now <= evidence['valid_until']:
        return unknown('evidence_not_fresh')
    try:
        # Keep the full conservative observable pass. Dead relation branches
        # may be pruned, but unknown contracted observables are not erased.
        safe, goal, outgoing, uncertain, viable = language._topology(profile, meter)
        first, horizon = model['initial'], model['horizon']
        frame = dict(profile['initial_bindings'])
        current = {(first, language._key(frame)): (frame, [])}
        if safe[first] is not True or first not in viable[horizon]:
            current = {}
        layers, relation_cache = [], {}
        for depth in range(horizon + 1):
            layers.append([{'state': state, 'bindings': dict(value[0])}
                           for (state, _), value in sorted(current.items())])
            following = {}
            for (state, _), (bindings, steps) in sorted(current.items()):
                meter.tick('state_expansions')
                meter.stats['product_states'] += 1
                if goal[state] is True:
                    return supported(steps)
                if depth == horizon:
                    continue
                for edge in outgoing[state]:
                    # Preserve the v1 charge for inspecting each outgoing edge.
                    meter.tick('graph_edges')
                    target = edge['target']
                    if safe[target] is not True:
                        continue
                    if target not in viable[horizon - depth - 1]:
                        meter.stats['goal_pruned_edges'] += 1
                        continue
                    cache_key = (edge['id'], language._key(bindings))
                    cached = cache_key in relation_cache
                    if cached:
                        outcomes = iter(relation_cache[cache_key])
                    else:
                        relation = profile['relations'][edge['id']]
                        outcomes = (language._step(relation, bindings, arguments, meter)
                                    for arguments in language._assignments(relation, bindings))
                    retained = []
                    for truth, step in outcomes:
                        if cached:
                            meter.tick('cached_relation_outcomes')
                        else:
                            retained.append((truth, step))
                        if truth is None:
                            # This target is in the remaining-horizon cone.
                            uncertain = True
                        elif truth:
                            step = dict(step, edge=edge['id'])
                            # Already present in v1: do not consume the rest of
                            # a Cartesian domain after one goal witness works.
                            if goal[target] is True:
                                return supported(steps + [step])
                            key = (target, language._key(step['bindings_after']))
                            following.setdefault(key, (step['bindings_after'], steps + [step]))
                    if not cached:
                        relation_cache[cache_key] = retained
            current = following
        if uncertain:
            return unknown('indeterminate_observables_or_relations')
        if not evidence['complete'] or not profile['coverage']['complete']:
            return unknown('incomplete_model_or_relation_coverage')
        certificate = dict(language._header(profile, now), kind=NEGATIVE_KIND, product_layers=layers)
        return {'decision': 'unsupported', 'reason': 'goal_relevant_relational_product_exhausted',
                'certificate': certificate, 'stats': dict(meter.stats)}
    except language._Limit:
        return unknown('work_budget_exhausted')


def check_certificate(profile, result, now):
    """Check old proof kinds or independently reconstruct the new negative cut.

    The fixed checker budget remains the preserved oracle's CHECK_BUDGET. A
    checker exhaustion returns False, never an accepted certificate. Benchmark
    runners must capture the checking invocation and charge its measured costs.
    """
    if type(result) is not dict:
        return False
    certificate = result.get('certificate')
    if type(certificate) is not dict or certificate.get('kind') != NEGATIVE_KIND:
        return language.check_certificate(profile, result, now)
    try:
        language.validate_profile(profile)
        language._require(type(now) is int and result.get('decision') == 'unsupported',
                          'New negative cut requires an unsupported result and integer clock')
        common = {'kind', 'profile_sha256', 'checked_at', 'horizon', 'valid_until'}
        language._keys(certificate, common | {'product_layers'}, 'Invalid goal-pruned certificate fields')
        model, evidence = profile['model'], profile['model']['evidence']
        language._require(certificate['profile_sha256'] == language.finite_oracle._digest(profile),
                          'Profile digest mismatch')
        for key in ('checked_at', 'horizon', 'valid_until'):
            language._require(type(certificate[key]) is int, 'Certificate clock/bound must be integer')
        language._require(certificate['horizon'] == model['horizon']
                          and certificate['valid_until'] == evidence['valid_until'], 'Changed horizon or expiry')
        language._require(evidence['observed_at'] <= certificate['checked_at'] <= now <= evidence['valid_until'],
                          'Certificate freshness mismatch')
        meter = language._Meter(language.CHECK_BUDGET)
        safe, goal, outgoing, uncertain, viable = language._topology(profile, meter)
        language._require(evidence['complete'] and profile['coverage']['complete'] and not uncertain,
                          'Negative requires complete coverage and determinate contracted observables')
        layers, horizon = certificate['product_layers'], model['horizon']
        language._require(type(layers) is list and len(layers) == horizon + 1,
                          'Negative cut must supply every depth through the horizon')
        initial, frame = model['initial'], dict(profile['initial_bindings'])
        expected = {(initial, language._key(frame)): frame}
        if safe[initial] is not True or initial not in viable[horizon]:
            expected = {}
        # Unlike the solver, verification has no relation-result cache and no
        # witness/history objects. It verifies exact successor closure of the
        # supplied cut from the one independently known initial binding frame.
        for depth, claimed in enumerate(layers):
            language._require(type(claimed) is list, 'A product layer must be a list')
            for _ in claimed:
                meter.tick('certificate_checks')
            actual = [{'state': state, 'bindings': dict(bindings)}
                      for (state, _), bindings in sorted(expected.items())]
            language._require(language._same(claimed, actual), 'Missing, duplicated or forged product frame')
            following = {}
            for (state, _), bindings in sorted(expected.items()):
                meter.tick('state_expansions')
                language._require(goal[state] is False, 'Cut contains a possible goal')
                if depth == horizon:
                    continue
                for edge in outgoing[state]:
                    meter.tick('graph_edges')
                    target = edge['target']
                    if safe[target] is not True or target not in viable[horizon - depth - 1]:
                        continue
                    relation = profile['relations'][edge['id']]
                    for arguments in language._assignments(relation, bindings):
                        truth, step = language._step(relation, bindings, arguments, meter)
                        language._require(truth is not None, 'Indeterminate goal-relevant relation')
                        if truth:
                            language._require(goal[target] is False, 'A concrete goal witness disproves the cut')
                            after = step['bindings_after']
                            following[(target, language._key(after))] = after
            expected = following
        return True
    except (ValueError, KeyError, TypeError, UnicodeError, IndexError, RecursionError, language._Limit):
        return False
