import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pwdlib import PasswordHash
from app.database import SessionLocal, Base, engine
from app import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()
hasher = PasswordHash.recommended()
random.seed(42)

SKILLS = [
    ("Python", "programming"), ("Java", "programming"), ("C++", "programming"),
    ("DSA", "problem solving"), ("SQL", "database"), ("HTML/CSS", "web"),
    ("JavaScript", "web"), ("React", "web"), ("FastAPI", "web"),
    ("Machine Learning", "ai"), ("Data Analysis", "ai"), ("Deep Learning", "ai"),
    ("Electronics", "hardware"), ("Embedded C", "hardware"), ("IoT Sensors", "hardware"),
]
NAMES = ("Aarav Diya Kabir Meera Rohan Isha Arjun Sana Vivaan Anaya Dev Tara Ishaan "
         "Riya Neil Kiara Yash Zoya Ayaan Pooja Kunal Naina Rahul Mira Samar Tanvi "
         "Veer Alia Om Pari").split()

if db.query(models.User).count() > 0:
    print("Data already exists, skipping seed.")
    sys.exit()

for name, cat in SKILLS:
    db.add(models.Skill(name=name, category=cat))
db.commit()
skill_ids = [s.id for s in db.query(models.Skill).all()]

db.add(models.User(name="Prof. Sharma", email="coordinator@skillsync.test",
                   password_hash=hasher.hash("Demo@1234"), role="coordinator"))

for i, n in enumerate(NAMES, start=1):
    u = models.User(name=n, email=f"student{i}@skillsync.test",
                    password_hash=hasher.hash("Demo@1234"), role="student")
    db.add(u)
    db.flush()
    db.add(models.StudentProfile(user_id=u.id, availability_hours=random.randint(5, 20),
                                 preferred_role=random.choice(["backend", "frontend", "ml", "hardware", "coordinator"])))
    for sid in random.sample(skill_ids, random.randint(5, 8)):
        db.add(models.StudentSkill(user_id=u.id, skill_id=sid,
                                   proficiency=random.randint(1, 5),
                                   experience_score=round(random.uniform(2, 9), 1),
                                   assessment_score=round(random.uniform(2, 9), 1)))
db.commit()
print("Seeded: 15 skills, 1 coordinator, 30 students")