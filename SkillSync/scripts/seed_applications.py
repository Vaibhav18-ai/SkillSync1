import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.database import SessionLocal
from app import models

comp_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
random.seed(7)
db = SessionLocal()
students = db.query(models.User).filter_by(role="student").all()
volunteers = {u.id for u in random.sample(students, 8)}
db.query(models.CompetitionApplication).filter_by(competition_id=comp_id).delete()
db.query(models.TeammatePreference).filter_by(competition_id=comp_id).delete()
for u in students:
    db.add(models.CompetitionApplication(competition_id=comp_id, user_id=u.id,
                                         status="confirmed", wants_to_lead=u.id in volunteers))
ids = [u.id for u in students]
pairs = set()
while len(pairs) < 13:
    a, b = random.sample(ids, 2)
    pairs.add((a, b))
for n, (a, b) in enumerate(pairs):
    db.add(models.TeammatePreference(competition_id=comp_id, user_id=a, other_user_id=b,
                                     kind="prefer" if n < 10 else "avoid"))
db.commit()
print(f"{len(students)} students applied, 8 volunteer leaders, 10 prefer and 3 avoid requests")