from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..security import get_current_user, require_role
from ..scoring import skill_score, general_score

router = APIRouter(prefix="/api", tags=["students"])

def build_me(db: Session, user: models.User) -> dict:
    profile = db.query(models.StudentProfile).filter_by(user_id=user.id).first()
    rows = (db.query(models.StudentSkill, models.Skill)
              .join(models.Skill, models.Skill.id == models.StudentSkill.skill_id)
              .filter(models.StudentSkill.user_id == user.id).all())
    skills = [{
        "skill_id": s.id, "name": s.name, "category": s.category,
        "proficiency": ss.proficiency, "experience_score": ss.experience_score,
        "assessment_score": ss.assessment_score,
        "score": skill_score(ss.proficiency, ss.experience_score, ss.assessment_score),
    } for ss, s in rows]
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "profile": {
            "interests": profile.interests if profile else None,
            "availability_hours": profile.availability_hours if profile else 0,
            "preferred_role": profile.preferred_role if profile else None,
            "github_url": profile.github_url if profile else None,
        },
        "skills": sorted(skills, key=lambda x: -x["score"]),
        "general_score": general_score([ss for ss, _ in rows]),
    }

@router.get("/skills", response_model=list[schemas.SkillOut])
def list_skills(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Skill).order_by(models.Skill.category, models.Skill.name).all()

@router.get("/students/me")
def get_me(db: Session = Depends(get_db), user: models.User = Depends(require_role("student"))):
    return build_me(db, user)

@router.put("/students/me")
def update_profile(body: schemas.ProfileIn, db: Session = Depends(get_db),
                   user: models.User = Depends(require_role("student"))):
    profile = db.query(models.StudentProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = models.StudentProfile(user_id=user.id)
        db.add(profile)
    profile.interests = body.interests
    profile.availability_hours = body.availability_hours
    profile.preferred_role = body.preferred_role
    profile.github_url = body.github_url
    db.commit()
    return build_me(db, user)

@router.put("/students/me/skills")
def save_skills(body: list[schemas.SkillRatingIn], db: Session = Depends(get_db),
                user: models.User = Depends(require_role("student"))):
    ids = [r.skill_id for r in body]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Each skill can only be rated once.")
    valid = {s.id for s in db.query(models.Skill).filter(models.Skill.id.in_(ids)).all()}
    if set(ids) - valid:
        raise HTTPException(400, "One or more skills do not exist.")
    existing = {r.skill_id: r for r in db.query(models.StudentSkill).filter_by(user_id=user.id)}
    for r in body:
        row = existing.get(r.skill_id)
        if row:
            row.proficiency = r.proficiency
            row.experience_score = r.experience_score
        else:
            db.add(models.StudentSkill(user_id=user.id, skill_id=r.skill_id,
                                       proficiency=r.proficiency,
                                       experience_score=r.experience_score))
    db.commit()
    return build_me(db, user)