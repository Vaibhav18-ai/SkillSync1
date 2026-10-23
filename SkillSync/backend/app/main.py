from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from . import models
from .routers import auth, students, competitions, teams, workspace

Base.metadata.create_all(bind=engine)
app = FastAPI(title="SkillSync")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],  # VS Code Live Server
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(competitions.router)
app.include_router(teams.router)
app.include_router(workspace.router)

@app.get("/api/health")
def health():
    return {"status": "ok"}