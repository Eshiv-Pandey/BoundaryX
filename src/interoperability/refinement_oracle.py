"""Independent forward relational reference and proof checker for recipe/1.

No candidate implementation is imported. The reference uses a memoized finite
product of graph location, depth and public binding frame. This is a strong
same-evidence comparator, not an alleged new algorithm or a live-route oracle.
"""
from __future__ import annotations

from copy import deepcopy
from collections import deque
import itertools
import json
from typing import Any

from . import oracle as finite_oracle


DEFAULT_BUDGET = 100_000
CHECK_BUDGET = 2_000_000
_ABSENT = object()
_UNKNOWN = object()
_SCALARS = (str, bool, int, type(None))


def _require(test, message):
    if not test:
        raise ValueError(message)


def _keys(value, keys, label):
    _require(type(value) is dict and set(value) == set(keys), label)


def _name(value):
    _require(type(value) is str and 0 < len(value) <= 16_384, 'Bounded nonempty string required')
    value.encode('utf-8')


def _scalar(value):
    _require(type(value) in _SCALARS, 'Public bindings/literals must be JSON scalars')
    if type(value) is str:
        value.encode('utf-8')


def _expression(value, args, allow_emit, count, depth=0):
    count[0] += 1
    _require(depth <= 16 and count[0] <= 4096 and type(value) is dict and len(value) == 1,
             'An expression must have one recognized constructor')
    tag, operand = next(iter(value.items()))
    if tag == 'const':
        _scalar(operand)
    elif tag in ('binding', 'unknown'):
        _name(operand)
    elif tag == 'arg':
        _name(operand)
        _require(operand in args, 'Expression names an undeclared caller argument')
    elif tag == 'object':
        _require(type(operand) is dict and len(operand) <= 128, 'Object expression requires a bounded dictionary')
        for key, item in operand.items():
            _name(key)
            _expression(item, args, allow_emit, count, depth + 1)
    elif tag == 'array':
        _require(type(operand) is list and len(operand) <= 128, 'Array expression requires a bounded list')
        for item in operand:
            _expression(item, args, allow_emit, count, depth + 1)
    elif tag == 'emit_path':
        _require(allow_emit and type(operand) is list and len(operand) <= 16, 'Invalid emitted-path expression')
        for component in operand:
            _require(type(component) is str or (type(component) is int and component >= 0),
                     'Emitted path components are strings or nonnegative integers')
            if type(component) is str:
                _name(component)
    else:
        raise ValueError('Unknown expression constructor: ' + str(tag))


def validate_profile(profile):
    """Validate the explicit finite legal recipe domain, without source claims."""
    _keys(profile, {'schema_version', 'id', 'model', 'initial_bindings', 'relations', 'coverage'},
          'Invalid recipe profile fields')
    _require(profile['schema_version'] == 'recipe-continuation/1', 'Unsupported recipe schema')
    _name(profile['id'])
    finite_oracle._validate(profile['model'], 0)
    _require(len(profile['model']['states']) <= 128 and len(profile['model']['transitions']) <= 256,
             'Prototype graph limit exceeded')
    _require(type(profile['initial_bindings']) is dict and len(profile['initial_bindings']) <= 128,
             'Initial bindings must be a bounded object')
    for name, value in profile['initial_bindings'].items():
        _name(name)
        _scalar(value)
    _keys(profile['coverage'], {'complete', 'scope'}, 'Invalid coverage declaration')
    _require(type(profile['coverage']['complete']) is bool, 'Coverage completeness must be Boolean')
    _name(profile['coverage']['scope'])
    relations = profile['relations']
    expected = {edge['id'] for edge in profile['model']['transitions']}
    _require(type(relations) is dict and set(relations) == expected,
             'Every and only declared graph edge requires a relation')
    binding_names = set(profile['initial_bindings'])
    for relation in relations.values():
        _keys(relation, {'source_ref', 'arguments', 'emit', 'guards', 'updates'},
              'Invalid edge relation fields')
        _name(relation['source_ref'])
        args = relation['arguments']
        _require(type(args) is dict and len(args) <= 8, 'Arguments must be a bounded object')
        for name, recipes in args.items():
            _name(name)
            _require(type(recipes) is list and len(recipes) <= 16, 'Argument recipes must be a bounded finite list')
            for recipe in recipes:
                _require(type(recipe) is dict and len(recipe) == 1, 'Invalid argument recipe')
                if 'literal' in recipe:
                    _scalar(recipe['literal'])
                elif 'binding' in recipe:
                    _name(recipe['binding'])
                else:
                    raise ValueError('Caller recipes are literal or public-binding references')
        expression_count = [0]
        _expression(relation['emit'], args, False, expression_count)
        _require(type(relation['guards']) is list and len(relation['guards']) <= 128, 'Guards must be a bounded list')
        for guard in relation['guards']:
            _require(type(guard) is dict and guard.get('op') in ('eq', 'ne', 'present'),
                     'Unrecognized relation guard')
            fields = {'op', 'left'} if guard['op'] == 'present' else {'op', 'left', 'right'}
            _keys(guard, fields, 'Invalid guard fields')
            for field in fields - {'op'}:
                _expression(guard[field], args, True, expression_count)
        _require(type(relation['updates']) is dict and len(relation['updates']) <= 128, 'Updates must be a bounded object')
        for name, expression in relation['updates'].items():
            _name(name)
            binding_names.add(name)
            _expression(expression, args, True, expression_count)
    _require(len(binding_names) <= 128, 'Total declared binding-name limit exceeded')
    return profile


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _unresolved(value):
    if value is _UNKNOWN or value is _ABSENT:
        return True
    if type(value) is dict:
        return any(_unresolved(item) for item in value.values())
    if type(value) is list:
        return any(_unresolved(item) for item in value)
    return False


def _contains_unknown(value):
    if value is _UNKNOWN:
        return True
    if type(value) is dict:
        return any(_contains_unknown(item) for item in value.values())
    if type(value) is list:
        return any(_contains_unknown(item) for item in value)
    return False


def _same(left, right):
    if left is _ABSENT or right is _ABSENT:
        return left is right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


class _Limit(Exception):
    pass


class _Meter:
    def __init__(self, budget):
        self.limit = DEFAULT_BUDGET if budget is None else budget
        _require(type(self.limit) is int and self.limit > 0, 'Budget must be a positive integer')
        self.stats = {'work_units': 0, 'budget': self.limit, 'state_expansions': 0, 'graph_edges': 0,
                      'argument_assignments': 0, 'expression_evaluations': 0,
                      'product_states': 0, 'cached_relation_outcomes': 0,
                      'certificate_checks': 0}

    def tick(self, kind):
        if self.stats['work_units'] >= self.limit:
            raise _Limit()
        self.stats['work_units'] += 1
        self.stats[kind] += 1


def _eval(expression, arguments, frame, request, meter):
    meter.tick('expression_evaluations')
    tag, value = next(iter(expression.items()))
    if tag == 'const':
        return value
    if tag == 'arg':
        return arguments[value]
    if tag == 'binding':
        return frame.get(value, _UNKNOWN)
    if tag == 'unknown':
        return _UNKNOWN
    if tag == 'object':
        return {key: _eval(item, arguments, frame, request, meter) for key, item in value.items()}
    if tag == 'array':
        return [_eval(item, arguments, frame, request, meter) for item in value]
    current = request
    for component in value:
        if current is _UNKNOWN:
            return _UNKNOWN
        if type(component) is str and type(current) is dict:
            current = current.get(component, _ABSENT)
        elif type(component) is int and type(current) is list and component < len(current):
            current = current[component]
        else:
            return _ABSENT
    return current


def _assignments(relation, frame):
    names, choices = [], []
    for name in sorted(relation['arguments']):
        values = {}
        for recipe in relation['arguments'][name]:
            if 'literal' in recipe:
                value = recipe['literal']
            elif recipe['binding'] in frame:
                value = frame[recipe['binding']]
            else:
                continue
            values.setdefault(_key(value), value)
        if not values:
            return
        names.append(name)
        choices.append(list(values.values()))
    for selected in itertools.product(*choices):
        yield dict(zip(names, selected))


def _permitted_arguments(relation, frame, arguments, meter):
    """Check one supplied tuple without enumerating its Cartesian domain."""
    domains = relation['arguments']
    if (type(arguments) is not dict or len(arguments) != len(domains)
            or set(arguments) != set(domains)):
        return False
    for name, recipes in domains.items():
        found = False
        for recipe in recipes:
            meter.tick('argument_assignments')
            if 'literal' in recipe:
                value = recipe['literal']
            elif recipe['binding'] in frame:
                value = frame[recipe['binding']]
            else:
                continue
            if _same(arguments[name], value):
                found = True
                break
        if not found:
            return False
    return True


def _step(relation, frame, arguments, meter):
    """Return a known step, known rejection, or indeterminate assignment."""
    meter.tick('argument_assignments')
    request = _eval(relation['emit'], arguments, frame, _ABSENT, meter)
    indeterminate = False
    for guard in relation['guards']:
        left = _eval(guard['left'], arguments, frame, request, meter)
        if guard['op'] == 'present':
            truth = None if left is _UNKNOWN else left is not _ABSENT
        else:
            right = _eval(guard['right'], arguments, frame, request, meter)
            truth = None if _contains_unknown(left) or _contains_unknown(right) else _same(left, right)
            if truth is not None and guard['op'] == 'ne':
                truth = not truth
        if truth is False:
            return False, None
        indeterminate |= truth is None
    updated = {}
    if _unresolved(request) or indeterminate:
        return None, None
    for name, expression in relation['updates'].items():
        updated[name] = _eval(expression, arguments, frame, request, meter)
    if any(type(value) not in _SCALARS for value in updated.values()):
        return None, None
    after = dict(frame, **updated)
    return True, {'args': deepcopy(arguments), 'request': deepcopy(request),
                  'bindings_before': dict(frame), 'bindings_after': after}


def _topology(profile, meter):
    model = profile['model']
    states, contract = model['states'], model['runtime_contract']
    safe = {name: finite_oracle._all_truth(value, contract['invariants']) for name, value in states.items()}
    goal = {name: finite_oracle._all_truth(value, contract['goal']) for name, value in states.items()}
    outgoing = {name: [] for name in states}
    for edge in model['transitions']:
        meter.tick('graph_edges')
        outgoing[edge['source']].append(edge)
    for edges in outgoing.values():
        edges.sort(key=lambda edge: edge['id'])
    # Preserve finite/1's deliberately conservative observable uncertainty.
    pending = deque([(model['initial'], 0)]) if safe[model['initial']] is not False else deque()
    seen = {model['initial']} if pending else set()
    uncertainty = False
    while pending:
        state, depth = pending.popleft()
        meter.tick('state_expansions')
        uncertainty |= safe[state] is None or goal[state] is None
        if depth < model['horizon']:
            for edge in outgoing[state]:
                meter.tick('graph_edges')
                target = edge['target']
                if safe[target] is not False and target not in seen:
                    seen.add(target)
                    pending.append((target, depth + 1))
    # This cone filters only relation uncertainty, never contract uncertainty.
    reverse = {state: [] for state in states}
    for edge in model['transitions']:
        meter.tick('graph_edges')
        if safe[edge['source']] is not False and safe[edge['target']] is not False:
            reverse[edge['target']].append(edge['source'])
    distances = {s: 0 for s in states if safe[s] is not False and goal[s] is not False}
    pending = deque(distances)
    while pending:
        state = pending.popleft()
        meter.tick('state_expansions')
        if distances[state] >= model['horizon']:
            continue
        for source in reverse[state]:
            meter.tick('graph_edges')
            if source not in distances:
                distances[source] = distances[state] + 1
                pending.append(source)
    viable = [{s for s, distance in distances.items() if distance <= remaining}
              for remaining in range(model['horizon'] + 1)]
    return safe, goal, outgoing, uncertainty, viable


def _header(profile, now):
    return {'profile_sha256': finite_oracle._digest(profile), 'checked_at': now,
            'horizon': profile['model']['horizon'],
            'valid_until': profile['model']['evidence']['valid_until']}


def evaluate(profile, now, budget=None):
    """Exact known-frame forward product within the declared finite recipe domain."""
    validate_profile(profile)
    _require(type(now) is int, 'now must be integer epoch seconds')
    meter = _Meter(budget)
    model, evidence = profile['model'], profile['model']['evidence']

    def unknown(reason):
        return {'decision': 'unknown', 'reason': reason, 'certificate': None, 'stats': dict(meter.stats)}

    def supported(steps):
        certificate = dict(_header(profile, now), kind='recipe-path',
                           transition_ids=[row['edge'] for row in steps], steps=steps)
        return {'decision': 'supported', 'reason': 'concrete_recipe_path',
                'certificate': certificate, 'stats': dict(meter.stats)}

    if not evidence['observed_at'] <= now <= evidence['valid_until']:
        return unknown('evidence_not_fresh')
    try:
        safe, goal, outgoing, uncertain, viable = _topology(profile, meter)
        first = model['initial']
        frame = dict(profile['initial_bindings'])
        current = {(first, _key(frame)): (frame, [])} if safe[first] is True else {}
        layers = []
        relation_cache = {}
        for depth in range(model['horizon'] + 1):
            layer = [{'state': state, 'bindings': dict(value[0])}
                     for (state, _), value in sorted(current.items())]
            layers.append(layer)
            following = {}
            for (state, _), (bindings, steps) in sorted(current.items()):
                meter.tick('state_expansions')
                meter.stats['product_states'] += 1
                if goal[state] is True:
                    return supported(steps)
                if depth == model['horizon']:
                    continue
                for edge in outgoing[state]:
                    meter.tick('graph_edges')
                    target = edge['target']
                    if safe[target] is not True:
                        continue
                    cache_key = (edge['id'], _key(bindings))
                    cached = cache_key in relation_cache
                    if cached:
                        outcomes = iter(relation_cache[cache_key])
                    else:
                        relation = profile['relations'][edge['id']]
                        outcomes = (_step(relation, bindings, arguments, meter)
                                    for arguments in _assignments(relation, bindings))
                    retained = []
                    for truth, step in outcomes:
                        if cached:
                            meter.tick('cached_relation_outcomes')
                        if not cached:
                            retained.append((truth, step))
                        if truth is None:
                            uncertain |= target in viable[model['horizon'] - depth - 1]
                        elif truth:
                            step = dict(step, edge=edge['id'])
                            if goal[target] is True:
                                return supported(steps + [step])
                            key = (target, _key(step['bindings_after']))
                            following.setdefault(key, (step['bindings_after'], steps + [step]))
                    if not cached:
                        relation_cache[cache_key] = retained
            current = following
        if uncertain:
            return unknown('indeterminate_observables_or_relations')
        if not evidence['complete'] or not profile['coverage']['complete']:
            return unknown('incomplete_model_or_relation_coverage')
        certificate = dict(_header(profile, now), kind='relational-exhaustion', product_layers=layers)
        return {'decision': 'unsupported', 'reason': 'complete_relational_product_exhausted',
                'certificate': certificate, 'stats': dict(meter.stats)}
    except _Limit:
        return unknown('work_budget_exhausted')


def _lift_prefix(profile, prefix, meter):
    """Re-lift every correlated frame of one path; never trust supplied steps."""
    by_id = {edge['id']: edge for edge in profile['model']['transitions']}
    state = profile['model']['initial']
    current = {_key(profile['initial_bindings']): dict(profile['initial_bindings'])}
    unknown = False
    for edge_id in prefix:
        meter.tick('certificate_checks')
        _require(type(edge_id) is str and edge_id in by_id, 'Unknown prefix edge')
        edge = by_id[edge_id]
        _require(edge['source'] == state, 'Nonjoining prefix')
        following = {}
        for frame in current.values():
            for arguments in _assignments(profile['relations'][edge_id], frame):
                truth, step = _step(profile['relations'][edge_id], frame, arguments, meter)
                if truth is None:
                    unknown = True
                elif truth:
                    following[_key(step['bindings_after'])] = step['bindings_after']
        current = following
        state = edge['target']
    return current, unknown


def check_certificate(profile, result, now):
    """Independently replay a witness, product cut, or prefix-refutation cover."""
    try:
        validate_profile(profile)
        _require(type(now) is int and type(result) is dict, 'Invalid checker arguments')
        decision = result.get('decision')
        _require(decision in ('supported', 'unsupported'), 'Unknown has no certificate')
        certificate = result.get('certificate')
        common = {'kind', 'profile_sha256', 'checked_at', 'horizon', 'valid_until'}
        _require(type(certificate) is dict and common <= set(certificate), 'Missing certificate header')
        _require(certificate['profile_sha256'] == finite_oracle._digest(profile), 'Profile digest mismatch')
        for name in ('checked_at', 'horizon', 'valid_until'):
            _require(type(certificate[name]) is int, 'Certificate clock/bound must be integer')
        model = profile['model']
        evidence = model['evidence']
        _require(certificate['horizon'] == model['horizon'] and certificate['valid_until'] == evidence['valid_until'],
                 'Changed horizon or expiry')
        _require(evidence['observed_at'] <= certificate['checked_at'] <= now <= evidence['valid_until'],
                 'Certificate freshness mismatch')
        meter = _Meter(CHECK_BUDGET)
        safe, goal, outgoing, uncertainty, _ = _topology(profile, meter)
        if decision == 'supported':
            _keys(certificate, common | {'transition_ids', 'steps'}, 'Invalid path certificate fields')
            _require(certificate['kind'] == 'recipe-path', 'Wrong certificate kind')
            ids, steps = certificate['transition_ids'], certificate['steps']
            _require(type(ids) is list and type(steps) is list and len(ids) == len(steps) <= model['horizon'],
                     'Invalid recipe path length')
            by_id = {edge['id']: edge for edge in model['transitions']}
            state, frame = model['initial'], dict(profile['initial_bindings'])
            _require(safe[state] is True, 'Unsafe initial state')
            for edge_id, row in zip(ids, steps):
                _keys(row, {'edge', 'args', 'request', 'bindings_before', 'bindings_after'}, 'Invalid witness step')
                _require(type(edge_id) is str and row['edge'] == edge_id and edge_id in by_id, 'Step identity mismatch')
                edge = by_id[edge_id]
                _require(edge['source'] == state and safe[edge['target']] is True, 'Invalid or unsafe path edge')
                relation = profile['relations'][edge_id]
                _require(_permitted_arguments(relation, frame, row['args'], meter),
                         'Illegal caller argument assignment')
                truth, expected = _step(relation, frame, row['args'], meter)
                _require(truth is True and _same(row, dict(expected, edge=edge_id)), 'Forged or indeterminate concrete step')
                state, frame = edge['target'], expected['bindings_after']
            _require(goal[state] is True, 'Recipe path does not satisfy goal')
            return True

        _require(evidence['complete'] and profile['coverage']['complete'] and not uncertainty,
                 'Negative needs complete, determinate model and relation coverage')
        if certificate['kind'] == 'relational-exhaustion':
            _keys(certificate, common | {'product_layers'}, 'Invalid product certificate fields')
            independent = evaluate(profile, certificate['checked_at'], CHECK_BUDGET)
            _require(independent['decision'] == 'unsupported', 'Product is not conclusively empty')
            _require(_same(certificate['product_layers'], independent['certificate']['product_layers']),
                     'Incomplete or forged product closure')
            return True
        _require(certificate['kind'] == 'refinement-exhaustion', 'Wrong negative certificate kind')
        _keys(certificate, common | {'refuted_prefixes'}, 'Invalid refutation certificate fields')
        prefixes = certificate['refuted_prefixes']
        _require(type(prefixes) is list, 'Refuted prefixes must be a list')
        canonical = set()
        for prefix in prefixes:
            meter.tick('certificate_checks')
            _require(type(prefix) is list and 0 < len(prefix) <= model['horizon'], 'Invalid refuted prefix length')
            marker = tuple(prefix)
            _require(marker not in canonical, 'Duplicate refuted prefix')
            canonical.add(marker)
            frames, unclear = _lift_prefix(profile, prefix, meter)
            _require(not frames and not unclear, 'Prefix refutation is false or indeterminate')
        # Prove full coverage, including alternative branches and cyclic paths.
        stack = [(model['initial'], ())] if safe[model['initial']] is not False else []
        while stack:
            state, path = stack.pop()
            meter.tick('state_expansions')
            covered = False
            for prefix in canonical:
                meter.tick('certificate_checks')
                if path[:len(prefix)] == prefix:
                    covered = True
                    break
            if covered:
                continue
            _require(goal[state] is False, 'Uncovered possible goal path')
            if len(path) < model['horizon']:
                for edge in outgoing[state]:
                    meter.tick('graph_edges')
                    if safe[edge['target']] is not False:
                        stack.append((edge['target'], path + (edge['id'],)))
        return True
    except (ValueError, KeyError, TypeError, UnicodeError, IndexError, RecursionError, _Limit):
        return False
