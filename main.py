from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn

from database import get_db, engine, Base
from models import User, QRun, QAnswer
from auth import router as auth_router, get_current_user
from rag import RAGEngine
from export import export_to_docx
import schemas
import os, json, shutil, uuid

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RAG Questionnaire Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

rag = RAGEngine()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── Reference Documents ────────────────────────────────────────────────────

@app.post("/reference-docs/upload")
async def upload_reference_doc(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".txt", ".pdf", ".md"]:
        raise HTTPException(400, "Only .txt, .pdf, .md allowed")
    dest = os.path.join(UPLOAD_DIR, f"ref_{uuid.uuid4().hex}_{file.filename}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    rag.index_document(dest, file.filename)
    return {"message": f"Indexed: {file.filename}"}


@app.get("/reference-docs")
async def list_reference_docs(current_user: User = Depends(get_current_user)):
    return {"docs": rag.list_docs()}


@app.post("/reference-docs/load-defaults")
async def load_default_docs(current_user: User = Depends(get_current_user)):
    """Index the bundled reference docs from reference_documents/ folder."""
    folder = "reference_documents"
    loaded = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        rag.index_document(path, fname)
        loaded.append(fname)
    return {"loaded": loaded}


# ─── Questionnaire Upload & Run ─────────────────────────────────────────────

@app.post("/runs/create", response_model=schemas.RunOut)
async def create_run(
    file: UploadFile = File(...),
    run_name: str = Form("Untitled Run"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".csv", ".txt", ".pdf"]:
        raise HTTPException(400, "Upload a .csv, .txt, or .pdf questionnaire")

    dest = os.path.join(UPLOAD_DIR, f"q_{uuid.uuid4().hex}_{file.filename}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    questions = parse_questionnaire(dest, ext)
    if not questions:
        raise HTTPException(400, "Could not parse any questions from the file")

    run = QRun(name=run_name, user_id=current_user.id, status="pending",
               question_file=dest, questions_json=json.dumps(questions))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@app.post("/runs/{run_id}/generate", response_model=List[schemas.AnswerOut])
async def generate_answers(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(QRun).filter(QRun.id == run_id, QRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(404, "Run not found")

    questions = json.loads(run.questions_json)
    # Clear old answers
    db.query(QAnswer).filter(QAnswer.run_id == run_id).delete()

    # Answer all questions in ONE API call to avoid rate limits
    results = rag.answer_all_questions(questions)

    answers = []
    for q, result in zip(questions, results):
        ans = QAnswer(
            run_id=run_id,
            question_id=q["id"],
            question_text=q["text"],
            answer_text=result["answer"],
            citations=json.dumps(result["citations"]),
        )
        db.add(ans)
        answers.append(ans)

    run.status = "done"
    db.commit()
    for a in answers:
        db.refresh(a)
    return answers


@app.get("/runs", response_model=List[schemas.RunOut])
async def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(QRun).filter(QRun.user_id == current_user.id).order_by(QRun.id.desc()).all()


@app.get("/runs/{run_id}/answers", response_model=List[schemas.AnswerOut])
async def get_answers(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(QRun).filter(QRun.id == run_id, QRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return db.query(QAnswer).filter(QAnswer.run_id == run_id).order_by(QAnswer.question_id).all()


@app.patch("/answers/{answer_id}", response_model=schemas.AnswerOut)
async def edit_answer(
    answer_id: int,
    payload: schemas.AnswerEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ans = db.query(QAnswer).filter(QAnswer.id == answer_id).first()
    if not ans:
        raise HTTPException(404, "Answer not found")
    ans.answer_text = payload.answer_text
    db.commit()
    db.refresh(ans)
    return ans


@app.get("/runs/{run_id}/export")
async def export_run(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(QRun).filter(QRun.id == run_id, QRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    answers = db.query(QAnswer).filter(QAnswer.run_id == run_id).order_by(QAnswer.question_id).all()
    out_path = export_to_docx(run, answers)
    return FileResponse(out_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        filename=f"{run.name}_answers.docx")


# ─── Helpers ────────────────────────────────────────────────────────────────

def parse_questionnaire(path: str, ext: str) -> List[dict]:
    questions = []
    if ext == ".csv":
        import csv
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = row.get("question_id", row.get("id", "")).strip()
                text = row.get("question", row.get("Question", "")).strip()
                if text:
                    questions.append({"id": qid or str(len(questions)+1), "text": text})
    elif ext in [".txt", ".md"]:
        with open(path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        for i, line in enumerate(lines):
            questions.append({"id": str(i+1), "text": line})
    elif ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            lines = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend([l.strip() for l in text.split("\n") if l.strip()])
        for i, line in enumerate(lines):
            if "?" in line or line[0].isdigit():
                questions.append({"id": str(i+1), "text": line})
    return questions


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)