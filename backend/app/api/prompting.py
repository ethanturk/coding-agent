from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.llm_rewrite import rewrite_prompt

router = APIRouter(prefix="/prompting", tags=["prompting"])


@router.post("/rewrite")
def rewrite_prompt_route(payload: dict, db: Session = Depends(get_db)):
    text = payload.get('text', '').strip()
    if not text:
        raise HTTPException(status_code=400, detail='Missing text')
    try:
        return rewrite_prompt(db, text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
