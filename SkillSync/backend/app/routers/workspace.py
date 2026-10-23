from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/teams", tags=["workspace"])

def team_access(db: Session, team_id: int, user: models.User):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found.")
    member = db.query(models.TeamMember).filter_by(team_id=team.id, user_id=user.id).first()
    if member:
        return team, member
    comp = db.get(models.Competition, team.competition_id)
    if user.role == "coordinator" and comp and comp.coordinator_id == user.id:
        return team, None
    raise HTTPException(404, "Team not found.")

def can_manage(team, member) -> bool:
    # the leader manages; if the team has no leader yet, any member can
    return member is not None and (team.leader_id is None or team.leader_id == member.user_id)

@router.get("/mine")
def my_teams(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (db.query(models.Team, models.Competition)
              .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)
              .join(models.Competition, models.Competition.id == models.Team.competition_id)
              .filter(models.TeamMember.user_id == user.id).all())
    return [{"team_id": t.id, "team_no": t.team_no, "competition": c.name} for t, c in rows]

@router.get("/{team_id}/dashboard")
def dashboard(team_id: int, db: Session = Depends(get_db),
              user: models.User = Depends(get_current_user)):
    team, member = team_access(db, team_id, user)
    comp = db.get(models.Competition, team.competition_id)
    people = (db.query(models.TeamMember, models.User)
                .join(models.User, models.User.id == models.TeamMember.user_id)
                .filter(models.TeamMember.team_id == team.id).all())
    names = {u.id: u.name for _, u in people}
    tasks = db.query(models.Task).filter_by(team_id=team.id).order_by(models.Task.id).all()
    miles = (db.query(models.Milestone).filter_by(team_id=team.id)
               .order_by(models.Milestone.due_date, models.Milestone.id).all())
    manage = can_manage(team, member)
    hours = {}
    for t in tasks:
        if t.assignee_id:
            hours[t.assignee_id] = hours.get(t.assignee_id, 0) + (t.estimated_hours or 0)
    done = sum(1 for t in tasks if t.status == "done")
    return {
        "team": {"id": team.id, "team_no": team.team_no, "competition": comp.name if comp else "",
                 "leader_id": team.leader_id},
        "me": {"user_id": user.id, "is_member": member is not None, "can_manage": manage},
        "members": [{"user_id": u.id, "name": u.name, "is_leader": m.is_leader,
                     "hours": hours.get(u.id, 0)} for m, u in people],
        "tasks": [{"id": t.id, "title": t.title, "description": t.description, "status": t.status,
                   "assignee_id": t.assignee_id, "assignee": names.get(t.assignee_id),
                   "estimated_hours": t.estimated_hours, "deadline": t.deadline,
                   "can_edit": manage or (member is not None and t.assignee_id == user.id)} for t in tasks],
        "milestones": [{"id": m.id, "title": m.title, "due_date": m.due_date, "done": m.done} for m in miles],
        "progress": {"done": done, "total": len(tasks),
                     "percent": round(100 * done / len(tasks)) if tasks else 0},
    }

@router.post("/{team_id}/tasks", status_code=201)
def create_task(team_id: int, body: schemas.TaskIn, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    team, member = team_access(db, team_id, user)
    if not member:
        raise HTTPException(403, "Only team members can add tasks.")
    if body.assignee_id is not None and not db.query(models.TeamMember).filter_by(
            team_id=team.id, user_id=body.assignee_id).first():
        raise HTTPException(400, "The assignee is not in this team.")
    t = models.Task(team_id=team.id, title=body.title.strip(), description=body.description,
                    assignee_id=body.assignee_id, estimated_hours=body.estimated_hours,
                    deadline=body.deadline, created_by=user.id)
    db.add(t)
    db.commit()
    return {"id": t.id}

@router.patch("/{team_id}/tasks/{task_id}")
def update_task(team_id: int, task_id: int, body: schemas.TaskStatusIn,
                db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    team, member = team_access(db, team_id, user)
    t = db.get(models.Task, task_id)
    if not t or t.team_id != team.id:
        raise HTTPException(404, "Task not found.")
    if not member or not (can_manage(team, member) or t.assignee_id == user.id):
        raise HTTPException(403, "Only the assignee or the team leader can change this task.")
    t.status = body.status
    db.commit()
    return {"id": t.id, "status": t.status}

@router.post("/{team_id}/milestones", status_code=201)
def create_milestone(team_id: int, body: schemas.MilestoneIn, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    team, member = team_access(db, team_id, user)
    if not can_manage(team, member):
        raise HTTPException(403, "Only the team leader can add milestones.")
    m = models.Milestone(team_id=team.id, title=body.title.strip(), due_date=body.due_date)
    db.add(m)
    db.commit()
    return {"id": m.id}

@router.patch("/{team_id}/milestones/{mid}")
def toggle_milestone(team_id: int, mid: int, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    team, member = team_access(db, team_id, user)
    if not can_manage(team, member):
        raise HTTPException(403, "Only the team leader can update milestones.")
    m = db.get(models.Milestone, mid)
    if not m or m.team_id != team.id:
        raise HTTPException(404, "Milestone not found.")
    m.done = not m.done
    db.commit()
    return {"id": m.id, "done": m.done}