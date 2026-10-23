from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..security import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(models.User).filter_by(email=email).first():
        raise HTTPException(409, "This email is already registered.")
    user = models.User(name=body.name.strip(), email=email,
                       password_hash=hash_password(body.password), role="student")
    db.add(user)
    db.flush()
    db.add(models.StudentProfile(user_id=user.id))
    db.commit()
    return {"access_token": create_token(user), "user": user}

@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"access_token": create_token(user), "user": user}

@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user