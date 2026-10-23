import random

def _avg(v):
    return sum(v) / len(v) if v else 0.0

def evaluate(teams, S, prefer, avoid, req_w, tol):
    where = {i: k for k, t in enumerate(teams) for i in t}
    avgs = [_avg([S[i]["score"] for i in t]) for t in teams]
    spread = max(avgs) - min(avgs)
    unmet = sum(1 for a, b in prefer if where[a] != where[b])
    viol = sum(1 for a, b in avoid if where[a] == where[b])
    gaps = {}
    for name in req_w:
        m = [_avg([S[i]["skills"].get(name, 0) for i in t]) for t in teams]
        gaps[name] = round(max(m) - min(m), 2)
    cov = sum(req_w[n] * g for n, g in gaps.items())
    j = 10 * max(0.0, spread - tol) + spread + 0.05 * unmet + 0.4 * viol + 0.1 * cov
    return {"objective": j, "spread": round(spread, 3), "avgs": [round(a, 2) for a in avgs],
            "prefer_met": len(prefer) - unmet, "prefer_total": len(prefer),
            "avoid_violations": viol, "skill_gaps": gaps}

def _build(S, K, leaders, prefer, avoid, req_w, tol, rng, iters):
    ids = sorted(S, key=lambda i: -S[i]["score"])
    base, extra = divmod(len(ids), K)
    cap = [base + (1 if k < extra else 0) for k in range(K)]
    teams = [[] for _ in range(K)]
    order = list(range(K))
    rng.shuffle(order)
    lead = leaders[:K]
    for pos, uid in enumerate(lead):
        teams[order[pos]].append(uid)
    locked = set(lead)
    rest = [i for i in ids if i not in locked]
    rest.sort(key=lambda i: -(S[i]["score"] + rng.uniform(-0.15, 0.15)))
    for uid in rest:
        open_ = [k for k in range(K) if len(teams[k]) < cap[k]]
        k = min(open_, key=lambda k: (sum(S[i]["score"] for i in teams[k]), rng.random()))
        teams[k].append(uid)
    cur = evaluate(teams, S, prefer, avoid, req_w, tol)["objective"]
    for _ in range(iters):
        a, b = rng.sample(range(K), 2)
        xa = [x for x in range(len(teams[a])) if teams[a][x] not in locked]
        xb = [y for y in range(len(teams[b])) if teams[b][y] not in locked]
        if not xa or not xb:
            continue
        x, y = rng.choice(xa), rng.choice(xb)
        teams[a][x], teams[b][y] = teams[b][y], teams[a][x]
        new = evaluate(teams, S, prefer, avoid, req_w, tol)["objective"]
        if new <= cur:
            cur = new
        else:
            teams[a][x], teams[b][y] = teams[b][y], teams[a][x]
    return teams

def generate_options(S, K, leaders, prefer, avoid, req_w, tol, restarts=8, iters=2500, seed=42):
    rng = random.Random(seed)
    found = {}
    for _ in range(restarts):
        teams = _build(S, K, leaders, prefer, avoid, req_w, tol, rng, iters)
        found.setdefault(frozenset(frozenset(t) for t in teams), teams)
    ranked = []
    for teams in found.values():
        m = evaluate(teams, S, prefer, avoid, req_w, tol)
        ranked.append((m["objective"], teams, m))
    ranked.sort(key=lambda r: r[0])
    leader_set = set(leaders[:K])
    options = []
    for _, teams, m in ranked[:3]:
        built = []
        for no, t in enumerate(teams, start=1):
            members = sorted(t, key=lambda i: (i not in leader_set, -S[i]["score"]))
            built.append({"team_no": no, "avg": round(_avg([S[i]["score"] for i in t]), 2),
                          "members": [{"user_id": i, "name": S[i]["name"], "score": S[i]["score"],
                                       "is_leader": i in leader_set} for i in members]})
        m = {k: v for k, v in m.items() if k != "objective"}
        m["within_tolerance"] = m["spread"] <= tol
        options.append({"teams": built, "metrics": m})
    return options