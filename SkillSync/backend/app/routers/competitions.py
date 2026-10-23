import secrets
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..security import get_current_user, require_role
from ..scoring import skill_score, competition_fit

router = APIRouter(prefix="/api/competitions", tags=["competitions"])

def get_comp(db: Session, comp_id: int) -> models.Competition:
    c = db.get(models.Competition, comp_id)
    if not c:
        raise HTTPException(404, "Competition not found.")
    return c

def own_comp(db: Session, comp_id: int, user: models.User) -> models.Competition:
    c = get_comp(db, comp_id)
    if c.coordinator_id != user.id:
        raise HTTPException(403, "This is not your competition.")
    return c

def get_reqs(db: Session, comp_id: int):
    return (db.query(models.CompetitionRequirement, models.Skill)
              .join(models.Skill, models.Skill.id == models.CompetitionRequirement.skill_id)
              .filter(models.CompetitionRequirement.competition_id == comp_id).all())

def fit_for(db: Session, user_id: int, reqs) -> dict:
    rows = {r.skill_id: r for r in db.query(models.StudentSkill).filter_by(user_id=user_id)}
    items = []
    for req, skill in reqs:
        ss = rows.get(req.skill_id)
        items.append({
            "skill": skill.name, "weight": req.weight, "min_level": req.min_level,
            "mandatory": req.mandatory,
            "proficiency": ss.proficiency if ss else 0,
            "score": skill_score(ss.proficiency, ss.experience_score, ss.assessment_score) if ss else 0.0,
        })
    return competition_fit(items)

def comp_dict(c: models.Competition, reqs) -> dict:
    return {
        "id": c.id, "name": c.name, "description": c.description, "comp_type": c.comp_type,
        "team_size": c.team_size, "num_teams": c.num_teams,
        "fairness_tolerance": c.fairness_tolerance, "formation_mode": c.formation_mode,
        "status": c.status, "deadline": c.deadline, "join_code": c.join_code,
        "requirements": [{"skill_id": r.skill_id, "skill": s.name, "weight": r.weight,
                          "min_level": r.min_level, "mandatory": r.mandatory} for r, s in reqs],
    }

@router.post("", status_code=201)
def create_competition(body: schemas.CompetitionIn, db: Session = Depends(get_db),
                       user: models.User = Depends(require_role("coordinator"))):
    ids = [r.skill_id for r in body.requirements]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Each skill can only be listed once.")
    found = {s.id for s in db.query(models.Skill).filter(models.Skill.id.in_(ids)).all()}
    if set(ids) - found:
        raise HTTPException(400, "One or more skills do not exist.")
    c = models.Competition(
        coordinator_id=user.id, name=body.name.strip(), description=body.description,
        comp_type=body.comp_type, team_size=body.team_size, num_teams=body.num_teams,
        fairness_tolerance=body.fairness_tolerance, formation_mode=body.formation_mode,
        deadline=body.deadline, status="draft", join_code=secrets.token_hex(3).upper())
    db.add(c)
    db.flush()
    for r in body.requirements:
        db.add(models.CompetitionRequirement(competition_id=c.id, skill_id=r.skill_id,
               weight=r.weight, min_level=r.min_level, mandatory=r.mandatory))
    db.commit()
    return comp_dict(c, get_reqs(db, c.id))

@router.get("")
def list_competitions(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Competition)
    if user.role == "coordinator":
        q = q.filter_by(coordinator_id=user.id)
    else:
        q = q.filter(models.Competition.status != "draft")
    out = []
    for c in q.order_by(models.Competition.id.desc()).all():
        reqs = get_reqs(db, c.id)
        d = comp_dict(c, reqs)
        if user.role == "student":
            f = fit_for(db, user.id, reqs)
            app = db.query(models.CompetitionApplication).filter_by(competition_id=c.id, user_id=user.id).first()
            d.update(my_fit=f["score"], eligible=f["eligible"], missing=f["missing"],
                     my_status=app.status if app else None)
        out.append(d)
    if user.role == "student":
        out.sort(key=lambda x: -x["my_fit"])
    return out

@router.get("/{comp_id}")
def competition_detail(comp_id: int, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    c = get_comp(db, comp_id)
    if c.status == "draft" and c.coordinator_id != user.id:
        raise HTTPException(404, "Competition not found.")
    reqs = get_reqs(db, c.id)
    d = comp_dict(c, reqs)
    if user.role == "student":
        d["my_fit"] = fit_for(db, user.id, reqs)
        app = db.query(models.CompetitionApplication).filter_by(competition_id=c.id, user_id=user.id).first()
        d["my_application"] = {"status": app.status, "wants_to_lead": app.wants_to_lead} if app else None
    return d

@router.post("/{comp_id}/publish")
def publish(comp_id: int, db: Session = Depends(get_db),
            user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    if c.status != "draft":
        raise HTTPException(400, "Only a draft competition can be published.")
    c.status = "registration_open"
    db.commit()
    return {"id": c.id, "status": c.status}

@router.post("/{comp_id}/close-registration")
def close_registration(comp_id: int, db: Session = Depends(get_db),
                       user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    if c.status != "registration_open":
        raise HTTPException(400, "Registration is not open.")
    c.status = "registration_closed"
    db.commit()
    return {"id": c.id, "status": c.status}

@router.post("/{comp_id}/applications", status_code=201)
def apply(comp_id: int, body: schemas.ApplyIn, db: Session = Depends(get_db),
          user: models.User = Depends(require_role("student"))):
    c = get_comp(db, comp_id)
    if c.status != "registration_open":
        raise HTTPException(400, "Registration is not open for this competition.")
    if c.deadline and c.deadline < date.today():
        raise HTTPException(400, "The registration deadline has passed.")
    fit = fit_for(db, user.id, get_reqs(db, c.id))
    if not fit["eligible"]:
        raise HTTPException(400, "Minimum level not met for: " + ", ".join(fit["missing"]))
    app = db.query(models.CompetitionApplication).filter_by(competition_id=c.id, user_id=user.id).first()
    if app:
        app.status, app.wants_to_lead = "confirmed", body.wants_to_lead
    else:
        db.add(models.CompetitionApplication(competition_id=c.id, user_id=user.id,
                                             status="confirmed", wants_to_lead=body.wants_to_lead))
    db.commit()
    return {"status": "confirmed", "wants_to_lead": body.wants_to_lead, "my_fit": fit["score"]}

@router.delete("/{comp_id}/applications")
def withdraw(comp_id: int, db: Session = Depends(get_db),
             user: models.User = Depends(require_role("student"))):
    c = get_comp(db, comp_id)
    if c.status not in ("registration_open", "registration_closed", "teams_proposed", "under_review"):
        raise HTTPException(400, "You can no longer withdraw from this competition.")
    app = db.query(models.CompetitionApplication).filter_by(competition_id=c.id, user_id=user.id).first()
    if not app:
        raise HTTPException(404, "You have not applied.")
    app.status = "withdrawn"
    db.commit()
    return {"status": "withdrawn"}

@router.post("/{comp_id}/preferences")
def add_preference(comp_id: int, body: schemas.PreferenceIn, db: Session = Depends(get_db),
                   user: models.User = Depends(require_role("student"))):
    get_comp(db, comp_id)
    if body.other_user_id == user.id:
        raise HTTPException(400, "You cannot choose yourself.")
    def joined(uid):
        a = db.query(models.CompetitionApplication).filter_by(competition_id=comp_id, user_id=uid).first()
        return a and a.status == "confirmed"
    if not joined(user.id):
        raise HTTPException(400, "Join the competition first.")
    if not joined(body.other_user_id):
        raise HTTPException(400, "That student has not joined this competition.")
    existing = db.query(models.TeammatePreference).filter_by(
        competition_id=comp_id, user_id=user.id, kind=body.kind).all()
    if any(p.other_user_id == body.other_user_id for p in existing):
        raise HTTPException(409, "You have already added this student.")
    if len(existing) >= 3:
        raise HTTPException(400, "You can add up to 3 students for each type.")
    db.add(models.TeammatePreference(competition_id=comp_id, user_id=user.id,
                                     other_user_id=body.other_user_id, kind=body.kind))
    db.commit()
    return {"saved": True}

@router.get("/{comp_id}/applicants")
def applicants(comp_id: int, db: Session = Depends(get_db),
               user: models.User = Depends(require_role("coordinator"))):
    c = own_comp(db, comp_id, user)
    reqs = get_reqs(db, c.id)
    rows = (db.query(models.CompetitionApplication, models.User)
              .join(models.User, models.User.id == models.CompetitionApplication.user_id)
              .filter(models.CompetitionApplication.competition_id == c.id,
                      models.CompetitionApplication.status == "confirmed").all())
    out = []
    for app, u in rows:
        f = fit_for(db, u.id, reqs)
        out.append({"user_id": u.id, "name": u.name, "score": f["score"],
                    "wants_to_lead": app.wants_to_lead, "eligible": f["eligible"]})
    out.sort(key=lambda x: -x["score"])
    return {"competition": c.name, "count": len(out), "applicants": out}