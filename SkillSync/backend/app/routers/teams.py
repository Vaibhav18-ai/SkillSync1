import csv
import io
import random

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..security import require_role, get_current_user
from ..scoring import leadership_score
from ..balancer import generate_options, evaluate
from .competitions import own_comp, get_comp, get_reqs, fit_for

router = APIRouter(prefix="/api/competitions", tags=["teams"])

def collect(db: Session, c: models.Competition):
    reqs = get_reqs(db, c.id)
    total_w = sum(r.weight for r, _ in reqs) or 1
    req_w = {s.name: r.weight / total_w for r, s in reqs}
    apps = (db.query(models.CompetitionApplication, models.User)
              .join(models.User, models.User.id == models.CompetitionApplication.user_id)
              .filter(models.CompetitionApplication.competition_id == c.id,
                      models.CompetitionApplication.status == "confirmed").all())
    S, volunteers = {}, []
    for app, u in apps:
        fit = fit_for(db, u.id, reqs)
        S[u.id] = {"name": u.name, "score": fit["score"],
                   "skills": {b["skill"]: b["score"] for b in fit["breakdown"]}}
        if app.wants_to_lead and fit["eligible"]:
            rows = db.query(models.StudentSkill).filter_by(user_id=u.id).all()
            prof = db.query(models.StudentProfile).filter_by(user_id=u.id).first()
            volunteers.append((leadership_score(rows, prof.availability_hours if prof else 0), u.id))
    volunteers.sort(reverse=True)
    prefs = db.query(models.TeammatePreference).filter_by(competition_id=c.id).all()
    prefer = [(p.user_id, p.other_user_id) for p in prefs
              if p.kind == "prefer" and p.user_id in S and p.other_user_id in S]
    avoid = [(p.user_id, p.other_user_id) for p in prefs
             if p.kind == "avoid" and p.user_id in S and p.other_user_id in S]
    return S, [uid for _, uid in volunteers], prefer, avoid, req_w

@router.post("/{comp_id}/team-generation")
def generate(comp_id: int, db: Session = Depends(get_db),
             user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    if c.status not in ("registration_closed", "teams_proposed", "under_review"):
        raise HTTPException(400, "Close registration before generating teams.")
    S, leaders, prefer, avoid, req_w = collect(db, c)
    K = c.num_teams
    if len(S) < K * 2:
        raise HTTPException(400, f"Need at least {K * 2} confirmed students for {K} teams; there are {len(S)}.")
    warnings = []
    if len(S) / K > c.team_size:
        warnings.append(f"Teams will have about {len(S) // K} members, above the configured size of {c.team_size}.")
    if len(leaders) < K:
        warnings.append(f"Only {len(leaders)} volunteer leaders for {K} teams. Teams without a leader choose one in their workspace.")
    options = generate_options(S, K, leaders, prefer, avoid, req_w, c.fairness_tolerance)
    result = {"options": options, "warnings": warnings, "students": len(S)}
    run = models.RecommendationRun(
        competition_id=c.id, result=result,
        settings={"teams": K, "tolerance": c.fairness_tolerance, "weights": req_w,
                  "algorithm": "greedy+swap-search v1"})
    c.status = "teams_proposed"
    db.add(run)
    db.commit()
    return {"run_id": run.id, **result}

@router.get("/{comp_id}/team-generation/{run_id}")
def get_run(comp_id: int, run_id: int, db: Session = Depends(get_db),
            user: models.User = Depends(require_role("coordinator"))):
    own_comp(db, comp_id, user)
    run = db.get(models.RecommendationRun, run_id)
    if not run or run.competition_id != comp_id:
        raise HTTPException(404, "Run not found.")
    return {"run_id": run.id, **run.result}

@router.post("/{comp_id}/finalize-teams")
def finalize(comp_id: int, body: schemas.FinalizeIn, db: Session = Depends(get_db),
             user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    if c.status not in ("teams_proposed", "under_review"):
        raise HTTPException(400, "Generate teams before finalizing.")
    if db.query(models.Team).filter_by(competition_id=c.id).first():
        raise HTTPException(400, "Teams are already finalized.")
    run = db.get(models.RecommendationRun, body.run_id)
    if not run or run.competition_id != c.id:
        raise HTTPException(404, "Run not found.")
    options = run.result["options"]
    if body.option_index >= len(options):
        raise HTTPException(400, "That option does not exist.")
    option = options[body.option_index]
    confirmed = {a.user_id for a in db.query(models.CompetitionApplication)
                 .filter_by(competition_id=c.id, status="confirmed")}
    proposed = {m["user_id"] for t in option["teams"] for m in t["members"]}
    if proposed != confirmed:
        raise HTTPException(409, "The student list changed since this run. Generate teams again.")
    try:
        for t in option["teams"]:
            lead = next((m["user_id"] for m in t["members"] if m["is_leader"]), None)
            team = models.Team(competition_id=c.id, team_no=t["team_no"], leader_id=lead, avg_score=t["avg"])
            db.add(team)
            db.flush()
            for m in t["members"]:
                db.add(models.TeamMember(team_id=team.id, competition_id=c.id, user_id=m["user_id"],
                                         is_leader=m["is_leader"], score=m["score"]))
        c.status = "finalized"
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Could not save the teams. Nothing was changed.")
    return {"status": "finalized", "teams": len(option["teams"]), "metrics": option["metrics"]}

@router.get("/{comp_id}/teams")
def view_teams(comp_id: int, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    c = get_comp(db, comp_id)
    teams = db.query(models.Team).filter_by(competition_id=c.id).order_by(models.Team.team_no).all()
    if not teams:
        raise HTTPException(404, "Teams have not been published yet.")
    if user.role == "coordinator" and c.coordinator_id != user.id:
        raise HTTPException(403, "This is not your competition.")
    mine = None
    if user.role == "student":
        mine = db.query(models.TeamMember).filter_by(competition_id=c.id, user_id=user.id).first()
        if not mine:
            raise HTTPException(404, "You are not in a team for this competition.")
    out = []
    for t in teams:
        if mine and t.id != mine.team_id:
            continue
        members = (db.query(models.TeamMember, models.User)
                     .join(models.User, models.User.id == models.TeamMember.user_id)
                     .filter(models.TeamMember.team_id == t.id).all())
        out.append({"team_id": t.id, "team_no": t.team_no, "avg_score": t.avg_score, "leader_id": t.leader_id,
                    "members": [{"user_id": u.id, "name": u.name, "is_leader": m.is_leader}
                                for m, u in members]})
    return out

@router.get("/{comp_id}/fairness-report")
def fairness_report(comp_id: int, db: Session = Depends(get_db),
                    user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    team_rows = db.query(models.Team).filter_by(competition_id=c.id).order_by(models.Team.team_no).all()
    if not team_rows:
        raise HTTPException(404, "Finalize teams first.")
    S, _, prefer, avoid, req_w = collect(db, c)
    actual = []
    for t in team_rows:
        ids = [m.user_id for m in db.query(models.TeamMember).filter_by(team_id=t.id) if m.user_id in S]
        if ids:
            actual.append(ids)
    if not actual:
        raise HTTPException(404, "No team members found for this report.")
    placed = {i for t in actual for i in t}
    prefer = [p for p in prefer if p[0] in placed and p[1] in placed]
    avoid = [p for p in avoid if p[0] in placed and p[1] in placed]
    tol = c.fairness_tolerance

    ours = evaluate(actual, S, prefer, avoid, req_w, tol)
    sizes = [len(t) for t in actual]
    rng = random.Random(1)
    ids, trials = list(placed), 300
    spreads, met, broken, gaps = [], [], [], []
    for _ in range(trials):
        rng.shuffle(ids)
        pos, teams = 0, []
        for n in sizes:
            teams.append(ids[pos:pos + n])
            pos += n
        m = evaluate(teams, S, prefer, avoid, req_w, tol)
        spreads.append(m["spread"])
        met.append(m["prefer_met"])
        broken.append(m["avoid_violations"])
        gaps.append(sum(m["skill_gaps"].values()))
    avg = lambda v: round(sum(v) / len(v), 2)
    return {
        "competition": c.name, "tolerance": tol, "trials": trials,
        "ours": {"spread": ours["spread"], "within_tolerance": ours["spread"] <= tol,
                 "prefer_met": ours["prefer_met"], "prefer_total": ours["prefer_total"],
                 "avoid_violations": ours["avoid_violations"],
                 "skill_gap": round(sum(ours["skill_gaps"].values()), 2)},
        "random": {"avg_spread": avg(spreads),
                   "pct_within_tolerance": round(100 * sum(1 for s in spreads if s <= tol) / trials),
                   "avg_prefer_met": avg(met), "avg_avoid_violations": avg(broken),
                   "avg_skill_gap": avg(gaps)},
    }

def _safe(v):
    # stop Excel from treating a name or email that starts with = + - @ as a formula
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s

@router.get("/{comp_id}/export")
def export_csv(comp_id: int, db: Session = Depends(get_db),
               user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    rows = (db.query(models.Team, models.TeamMember, models.User)
              .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)
              .join(models.User, models.User.id == models.TeamMember.user_id)
              .filter(models.Team.competition_id == c.id)
              .order_by(models.Team.team_no, models.TeamMember.is_leader.desc()).all())
    if not rows:
        raise HTTPException(404, "Finalize teams first.")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["team_no", "student_id", "name", "email", "role", "competition_score", "team_average"])
    for t, m, u in rows:
        w.writerow([t.team_no, u.id, _safe(u.name), _safe(u.email),
                    "leader" if m.is_leader else "member", m.score, t.avg_score])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="teams_competition_{c.id}.csv"'})