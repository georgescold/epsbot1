from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import shutil
import os
import uuid
import json
from datetime import datetime, timedelta

from .database import engine, Base, get_db, SessionLocal
from .models import Source, Argument, Proof, DefinitionSource, DefinitionExtraction, Flashcard, User, DissertationFolder, SavedDissertation
from .services.pdf_processing import extract_text_from_pdf
from .services.ai_analyzer import analyze_full_text, analyze_full_definition_text, set_api_key
from .services.dissertation_generator import generate_dissertation_content, generate_plan_content
from .services.flashcard_generator import generate_flashcards_from_argument
from .services.auth import (
    UserCreate, UserLogin, Token, UserResponse, ForgotPasswordRequest, ResetPasswordRequest,
    create_user, authenticate_user, create_access_token, get_user_by_email,
    get_current_user, get_current_user_required, create_reset_token, verify_reset_token,
    reset_password, send_reset_email, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EPS Bot API")

# Simple in-memory job store
# Structure: job_id -> {"status": "processing"|"completed"|"failed", "progress": "0/X", "message": "..."}
analysis_jobs = {}

def update_job_progress(job_id, current, total, message):
    if job_id in analysis_jobs:
        # progress is now just the percentage number or string
        analysis_jobs[job_id]["progress"] = current 
        analysis_jobs[job_id]["message"] = message

def background_analyze_source(job_id: str, source_id: int, filepath: str, filename: str):
    print(f"[{datetime.now()}] Starting background analysis for: {filename}")
    analysis_jobs[job_id] = {"status": "processing", "progress": 0, "message": "Démarrage...", "filename": filename}
    
    db = next(get_db()) # Manually get session
    try:
        # Check if cancelled before starting
        if analysis_jobs.get(job_id, {}).get("status") == "cancelled":
            print(f"[{datetime.now()}] Job {job_id} was cancelled before starting.")
            return
        
        text = extract_text_from_pdf(filepath)
        text_length = len(text)
        print(f"[{datetime.now()}] Text extracted ({text_length} chars)")
        
        # Callback wrapper with cancellation check
        def callback(c, t, m):
            # Check if cancelled
            if analysis_jobs.get(job_id, {}).get("status") == "cancelled":
                raise InterruptedError("Job cancelled by user")
            percent = int((c / t) * 100) if t > 0 else 0
            msg = f"{percent}%"
            update_job_progress(job_id, percent, t, msg)
            
        analysis_result = analyze_full_text(text, progress_callback=callback)
        
        print(f"[{datetime.now()}] AI analysis complete. Saving to DB...")
        analysis_jobs[job_id]["message"] = "Enregistrement..."
        analysis_jobs[job_id]["progress"] = 100 # Ensure 100% at end
        
        for item in analysis_result.get("analysis", []):
            arg = Argument(
                source_id=source_id,
                theme=item.get("theme"),
                chronology_period=item.get("period"),
                content=item.get("argument")
            )
            db.add(arg)
            db.commit()
            db.refresh(arg)
            
            for p in item.get("proofs", []):
                proof = Proof(
                    argument_id=arg.id,
                    content=p.get("content"),
                    specific_year=p.get("year"),
                    citation_complement=p.get("complement"),
                    is_nuance=p.get("is_nuance", False)
                )
                db.add(proof)

            # --- AUTO-GENERATE FLASHCARDS ---
            try:
                # Prepare text context
                proofs_txt = "\n".join([f"- {p.get('content')} ({p.get('year')}) {'[NUANCE]' if p.get('is_nuance') else ''}" for p in item.get("proofs", [])])
                
                cards_data = generate_flashcards_from_argument(arg.theme, arg.chronology_period, arg.content, proofs_txt)
                for c in cards_data:
                    fc = Flashcard(
                        argument_id=arg.id,
                        front=c['front'],
                        back=c['back']
                    )
                    db.add(fc)
            except Exception as fe:
                print(f"Flashcard gen error for arg {arg.id}: {fe}")
            # -------------------------------
        
        source = db.query(Source).filter(Source.id == source_id).first()
        if source:
            source.is_analyzed = True
            db.commit()
            
        analysis_jobs[job_id]["status"] = "completed"
        analysis_jobs[job_id]["message"] = "Analysis complete"
        
    except InterruptedError as e:
        print(f"[{datetime.now()}] Analysis cancelled: {filename}")
        analysis_jobs[job_id]["status"] = "cancelled"
        analysis_jobs[job_id]["message"] = "Annulé par l'utilisateur"
    except Exception as e:
        print(f"[{datetime.now()}] Background Analysis Failed: {e}")
        analysis_jobs[job_id]["status"] = "failed"
        analysis_jobs[job_id]["message"] = str(e)
    finally:
        db.close()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploaded_sources"
CONFIG_FILE = "config.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper functions for API key management
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def get_api_key():
    config = load_config()
    return config.get("anthropic_api_key", "")

# Pydantic model for API key
class ApiKeyRequest(BaseModel):
    api_key: str

class DissertationRequest(BaseModel):
    subject: str

# API Key Endpoints
@app.get("/api-key/status")
def api_key_status():
    key = get_api_key()
    return {"is_set": bool(key and len(key) > 10)}

@app.post("/api-key")
def set_api_key_endpoint(request: ApiKeyRequest):
    if not request.api_key or not request.api_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="Clé API invalide. Elle doit commencer par 'sk-'")
    
    config = load_config()
    config["anthropic_api_key"] = request.api_key
    save_config(config)
    
    # Update the analyzer module with the new key
    set_api_key(request.api_key)
    
    return {"message": "Clé API enregistrée"}

@app.delete("/api-key")
def delete_api_key():
    config = load_config()
    config["anthropic_api_key"] = ""
    save_config(config)
    set_api_key("")
    return {"message": "Clé API supprimée"}

@app.get("/")
def read_root():
    return {"message": "EPS Bot Backend is running"}


# --- AUTHENTICATION ENDPOINTS ---

@app.post("/auth/register", response_model=Token)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if email already exists
    existing = get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est deja utilise")

    # Validate password length
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caracteres")

    # Create user
    user = create_user(db, user_data)

    # Check if this is the first user - migrate existing data
    user_count = db.query(User).count()
    if user_count == 1:
        # Migrate orphan flashcards and folders to first user
        db.query(Flashcard).filter(Flashcard.user_id == None).update({"user_id": user.id})
        db.query(DissertationFolder).filter(DissertationFolder.user_id == None).update({"user_id": user.id})
        db.commit()
        print(f"[{datetime.now()}] Migrated existing data to first user: {user.email}")

    # Generate token
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token"""
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user_required)):
    """Get current user info"""
    return current_user


@app.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request password reset email"""
    user = get_user_by_email(db, request.email)
    if not user:
        # Don't reveal if email exists
        return {"message": "Si cet email existe, un lien de reinitialisation a ete envoye"}

    token = create_reset_token(db, user)
    await send_reset_email(user.email, token)

    return {"message": "Si cet email existe, un lien de reinitialisation a ete envoye"}


@app.post("/auth/reset-password")
def reset_password_endpoint(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password with token"""
    user = verify_reset_token(db, request.token)
    if not user:
        raise HTTPException(status_code=400, detail="Token invalide ou expire")

    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caracteres")

    reset_password(db, user, request.new_password)
    return {"message": "Mot de passe reinitialise avec succes"}


@app.post("/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Check for duplicate by filename
    existing_source = db.query(Source).filter(Source.filename == file.filename).first()
    if existing_source:
        print(f"[{datetime.now()}] WARNING: Duplicate detected: {file.filename}")
        return {
            "id": existing_source.id, 
            "filename": file.filename, 
            "status": "duplicate",
            "message": f"Le fichier '{file.filename}' a déjà été analysé."
        }
    
    # Save file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create DB entry
    db_source = Source(
        filename=file.filename,
        title=file.filename, # Temporary
        is_analyzed=False
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    # Trigger Async Analysis
    job_id = str(uuid.uuid4())
    background_tasks.add_task(background_analyze_source, job_id, db_source.id, filepath, file.filename)
    
    # Initialize job status immediately
    analysis_jobs[job_id] = {"status": "pending", "progress": 0, "message": "En attente...", "filename": file.filename}

    return {
        "id": db_source.id, 
        "filename": db_source.filename, 
        "status": "pending",
        "job_id": job_id
    }

@app.get("/jobs/active")
def get_active_jobs():
    """Return all jobs that are not completed or failed, to restore state on frontend."""
    return {k: v for k, v in analysis_jobs.items() if v["status"] in ["pending", "processing"]}

@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = analysis_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job

@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancel an active analysis job."""
    job = analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] in ["completed", "failed", "cancelled"]:
        return {"message": "Job already finished", "status": job["status"]}
    
    analysis_jobs[job_id]["status"] = "cancelled"
    analysis_jobs[job_id]["message"] = "Annulation en cours..."
    print(f"[{datetime.now()}] Job {job_id} marked for cancellation")
    return {"message": "Job cancellation requested", "status": "cancelled"}

@app.get("/sources")
def get_sources(db: Session = Depends(get_db)):
    return db.query(Source).all()

@app.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    # Note: source_id in DB is UUID (string in python model?)
    # Let's check model type. It's likely Integer or String. 
    # Usually in SQLAlchemy it's int unless specified. 
    # Wait, the models.py was using Integer primary key by default in typical setup?
    # Let's check models.py first? No, I'll assume standard auto-increment INT for now or check.
    # Actually, looking at main.py, return {"id": db_source.id...} 
    # If I check models.py it would be safer. But often it's int.
    # Let's cast to int if it's int. 
    # To be safe, I will fetch model first.
    pass # Replaced below logic
    
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Optimized Bulk Delete
    # 1. Delete all proofs related to arguments of this source
    db.query(Proof).filter(Proof.argument_id.in_(
        db.query(Argument.id).filter(Argument.source_id == source.id)
    )).delete(synchronize_session=False)

    # 2. Delete arguments
    db.query(Argument).filter(Argument.source_id == source.id).delete(synchronize_session=False)
    
    # 4. Delete source
    db.delete(source)
    db.commit()
    return {"message": "Source deleted successfully"}

@app.post("/sources/{source_id}/retry")
async def retry_source_analysis(source_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    # Sanitize filename for printing to console (Windows cp1252 issue)
    safe_filename = source.filename.encode('ascii', 'replace').decode('ascii')
    print(f"[{datetime.now()}] Retrying analysis for: {safe_filename}")
    
    # 1. Clean existing data (Optimized Bulk Delete)
    db.query(Proof).filter(Proof.argument_id.in_(
        db.query(Argument.id).filter(Argument.source_id == source.id)
    )).delete(synchronize_session=False)
    db.query(Argument).filter(Argument.source_id == source.id).delete(synchronize_session=False)
    
    # Reset status
    source.is_analyzed = False
    db.commit()
    
    # 2. Find file
    # We rely on the filename being consistent with upload logic
    # Filename in DB is original filename
    # File on disk is {uuid}_{filename}
    # We need to find the file on disk. 
    # Since we don't store the exact disk filename in Source model (only original filename), we have to search.
    # Ideally we should have stored the disk path, but we can stick to the search pattern used in refresh_all.
    
    pdf_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(f"_{source.filename}")]
    if not pdf_files:
         raise HTTPException(status_code=404, detail="Original PDF file not found on disk")
         
    filepath = os.path.join(UPLOAD_DIR, pdf_files[0])
    
    # 3. Trigger background job
    job_id = str(uuid.uuid4())
    background_tasks.add_task(background_analyze_source, job_id, source.id, filepath, source.filename)
    
    # Initialize job status
    analysis_jobs[job_id] = {"status": "pending", "progress": 0, "message": "En attente (Retry)...", "filename": source.filename}
    
    return {"message": "Retry started", "job_id": job_id}

@app.get("/sheets/{sheet_name}")
def get_sheet_data(sheet_name: str, db: Session = Depends(get_db)):
    # Map sheet_name to theme key
    theme_map = {
        "citoyennete": "citoyennete",
        "conceptions": "conceptions",
        "contexte": "contexte",
        "evaluation": "evaluation",
        "formation_enseignants": "formation_enseignants",
        "orthodoxie_scolaire": "orthodoxie_scolaire",
        "pratiques_enseignantes": "pratiques_enseignantes",
        "representations_corps": "representations_corps",
        "sciences": "sciences",
        "sport_scolaire": "sport_scolaire",
        "systeme_scolaire": "systeme_scolaire",
        "textes_institutionnels": "textes_institutionnels",
        "effort": "effort"
    }
    
    db_theme = theme_map.get(sheet_name)
    if not db_theme:
        return {"error": "Invalid sheet name"}
        
    arguments = db.query(Argument).filter(Argument.theme == db_theme).all()
    
    periods_order = [
         "1850-1918", "1918-1936", "1936-1944", "1945-1959",
         "1959-1967", "1967-1981", "1981-2007", "2007-today"
    ]
    
    # Helper to bucket years strictly
    def get_period_from_year(y_val):
        try:
            # Extract first 4 digit number if string
            import re
            match = re.search(r'\d{4}', str(y_val))
            if not match: return None
            y = int(match.group(0))
            
            if y < 1918: return "1850-1918"
            if y <= 1936: return "1918-1936"
            if y <= 1944: return "1936-1944"
            if y <= 1959: return "1945-1959"
            if y <= 1967: return "1959-1967"
            if y <= 1981: return "1967-1981"
            if y <= 2007: return "1981-2007"
            return "2007-today"
        except:
            return None

    result = {period: [] for period in periods_order}
    
    for arg in arguments.copy(): # Copy list to be safe
        # Determine strict period from proofs
        years = []
        for p in arg.proofs:
            if p.specific_year:
                years.append(p.specific_year)
        
        target_period = arg.chronology_period
        
        # If we have years, use the median year to find proper period
        if years:
            import statistics
            try:
                # extracted ints
                y_ints = []
                for y_str in years:
                    import re
                    match = re.search(r'\d{4}', str(y_str))
                    if match: y_ints.append(int(match.group(0)))
                
                if y_ints:
                    median_year = statistics.median(y_ints)
                    calculated_period = get_period_from_year(median_year)
                    if calculated_period: 
                        target_period = calculated_period
            except Exception as e:
                print(f"Error calcuating period: {e}")

        # Fallback for old/empty
        if target_period not in result:
             # Try to find partial match
             found = False
             for p in periods_order:
                 if p in str(target_period):
                     target_period = p
                     found = True
                     break
             if not found:
                 # Default or separate bucket? 
                 # For now, put in the first one or skip? 
                 # User wants strictness. Let's put in '1850-1918' if unknown, or skip.
                 # Let's skip to avoid garbage.
                 continue

        if target_period in result:
            sorted_proofs = sorted(arg.proofs, key=lambda pr: (pr.citation_complement is None or pr.citation_complement == ""), reverse=False)
            result[target_period].append({
                "id": arg.id,
                "content": arg.content,
                "proofs": [
                    {
                        "content": pr.content, 
                        "year": pr.specific_year,
                        "complement": pr.citation_complement,
                        "is_nuance": pr.is_nuance
                    } for pr in sorted_proofs
                ],
                "source": arg.source.filename
            })
            
    return result

@app.post("/refresh-analysis")
async def refresh_all_analysis(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Re-analyze all sources with the updated prompt.
    Uses background tasks for each source and returns job IDs immediately.
    """
    sources = db.query(Source).all()
    job_ids = []
    
    for source in sources:
        # Find the PDF file
        pdf_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(f"_{source.filename}")]
        if not pdf_files:
            print(f"[{datetime.now()}] Refresh: PDF not found for {source.filename}")
            continue
        
        filepath = os.path.join(UPLOAD_DIR, pdf_files[0])
        
        # Delete existing analysis for this source
        # Delete existing analysis for this source (Optimized Bulk Delete)
        db.query(Proof).filter(Proof.argument_id.in_(
            db.query(Argument.id).filter(Argument.source_id == source.id)
        )).delete(synchronize_session=False)
        db.query(Argument).filter(Argument.source_id == source.id).delete(synchronize_session=False)
        
        source.is_analyzed = False
        db.commit()
        
        # Create a job and add to background
        job_id = str(uuid.uuid4())
        analysis_jobs[job_id] = {
            "status": "pending", 
            "progress": 0, 
            "message": "En attente (Refresh)...", 
            "filename": source.filename
        }
        
        background_tasks.add_task(background_analyze_source, job_id, source.id, filepath, source.filename)
        job_ids.append({"job_id": job_id, "filename": source.filename})
    
    return {"message": f"Refresh started for {len(job_ids)} source(s)", "jobs": job_ids}

@app.post("/generate_dissertation")
def generate_dissertation(request: DissertationRequest, db: Session = Depends(get_db)):
    subject = request.subject
    print(f"[{datetime.now()}] Generating dissertation for subject: {subject}")
    
    # Fetch ALL arguments and proofs to use as context
    # This might be heavy, but it's "Ecrit 1" so we need the knowledge base.
    all_arguments = db.query(Argument).all()
    
    context_data = []
    for arg in all_arguments:
        # We need to serialize this clearly for the AI
        proofs_data = []
        for p in arg.proofs:
            proofs_data.append({
                "content": p.content,
                "year": p.specific_year,
                "complement": p.citation_complement,
                "is_nuance": p.is_nuance
            })
            
        context_data.append({
            "theme": arg.theme,
            "period": arg.chronology_period,
            "argument": arg.content,
            "proofs": proofs_data
        })
    
    # Fetch Definitions & Citations
    extractions = db.query(DefinitionExtraction).all()
    defs_data = []
    for extr in extractions:
        defs_data.append({
            "type": extr.type,
            "key": extr.key_term,
            "content": extr.content
        })

    # Call the service
    dissertation_text = generate_dissertation_content(subject, context_data, defs_data)
    
    return {"dissertation": dissertation_text}

@app.post("/generate_plan")
def generate_plan(request: DissertationRequest, db: Session = Depends(get_db)):
    subject = request.subject
    print(f"[{datetime.now()}] Generating detailed plan for subject: {subject}")
    
    all_arguments = db.query(Argument).all()
    
    context_data = []
    for arg in all_arguments:
        proofs_data = []
        for p in arg.proofs:
            proofs_data.append({
                "content": p.content,
                "year": p.specific_year,
                "complement": p.citation_complement,
                "is_nuance": p.is_nuance
            })
            
        context_data.append({
            "theme": arg.theme,
            "period": arg.chronology_period,
            "argument": arg.content,
            "proofs": proofs_data
        })
    
    # Fetch Definitions & Citations
    extractions = db.query(DefinitionExtraction).all()
    defs_data = []
    for extr in extractions:
        defs_data.append({
            "type": extr.type,
            "key": extr.key_term,
            "content": extr.content
        })

    # Call the plan service
    plan_text = generate_plan_content(subject, context_data, defs_data)
    
    return {"plan": plan_text}

# --- DEFINITIONS ENDPOINTS ---

@app.post("/definitions/upload")
async def upload_definition_source(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Check duplicate
    existing = db.query(DefinitionSource).filter(DefinitionSource.filename == file.filename).first()
    if existing:
         return {"id": existing.id, "status": "duplicate", "message": "Fichier deja analyse"}

    # Save
    import uuid
    file_id = str(uuid.uuid4())
    filename = f"DEF_{file_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    db_source = DefinitionSource(filename=file.filename)
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    
    # Analyze
    try:
        print(f"[{datetime.now()}] Analyzing Definition Source: {file.filename}")
        text = extract_text_from_pdf(filepath)
        result = analyze_full_definition_text(text)
        
        count = 0
        for item in result.get("extractions", []):
            extr = DefinitionExtraction(
                source_id=db_source.id,
                type=item.get("type", "definition"),
                key_term=item.get("key_term", "Inconnu"),
                content=item.get("content", "")
            )
            db.add(extr)
            count += 1
            
        db_source.is_analyzed = True
        db.commit()
        print(f"[{datetime.now()}] Extracted {count} items.")
        
    except Exception as e:
        print(f"Analysis failed: {e}")
        
    return {"id": db_source.id, "filename": db_source.filename, "status": "analyzed"}

# --- REVIEW SYSTEM ENDPOINTS (FSRS Algorithm) ---

from .services.fsrs_algorithm import (
    calculate_next_review,
    get_next_intervals,
    get_card_retrievability,
    state_to_string,
    State
)
from .services.flashcard_generator import generate_flashcards_from_argument

class ReviewSubmission(BaseModel):
    rating: int  # 1=Again, 2=Hard, 3=Good, 4=Easy

@app.get("/revisions/decks")
def get_revision_decks(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Returns stats for each theme using FSRS states:
    - total cards
    - due cards (now)
    - new count (state=0)
    - learning count (state=1)
    - review count (state=2)
    - relearning count (state=3)
    Filtered by current user if authenticated.
    """
    themes = {}

    # Filter by user_id if authenticated
    query = db.query(Flashcard).join(Argument)
    if current_user:
        query = query.filter(Flashcard.user_id == current_user.id)

    cards = query.all()
    now = datetime.utcnow()

    for card in cards:
        t = card.argument.theme
        if t not in themes:
            themes[t] = {
                "theme": t,
                "total": 0,
                "due": 0,
                "new": 0,
                "learning": 0,
                "review": 0,
                "relearning": 0
            }

        themes[t]["total"] += 1

        # FSRS States: 0=New, 1=Learning, 2=Review, 3=Relearning
        if card.state == State.NEW:
            themes[t]["new"] += 1
            themes[t]["due"] += 1  # New cards are always "due"
        elif card.state == State.LEARNING:
            themes[t]["learning"] += 1
            if card.due_date <= now:
                themes[t]["due"] += 1
        elif card.state == State.REVIEW:
            themes[t]["review"] += 1
            if card.due_date <= now:
                themes[t]["due"] += 1
        elif card.state == State.RELEARNING:
            themes[t]["relearning"] += 1
            if card.due_date <= now:
                themes[t]["due"] += 1

    return list(themes.values())

@app.get("/revisions/deck/{theme}/due")
def get_due_cards(
    theme: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get cards due for review for a specific theme.
    Returns cards with FSRS interval previews for each rating.
    Filtered by current user if authenticated.
    """
    now = datetime.utcnow()

    # Base query with user filter
    base_filter = [Argument.theme == theme]
    if current_user:
        base_filter.append(Flashcard.user_id == current_user.id)

    # Get Due Review/Learning/Relearning Cards (state != 0 and due)
    due_cards = db.query(Flashcard).join(Argument).filter(
        *base_filter,
        Flashcard.due_date <= now,
        Flashcard.state != State.NEW
    ).all()

    # Get New Cards (limit to 20 per session - Anki default)
    new_cards = db.query(Flashcard).join(Argument).filter(
        *base_filter,
        Flashcard.state == State.NEW
    ).limit(20).all()

    # Combine and add interval previews
    all_cards = due_cards + new_cards
    result = []

    for card in all_cards:
        # Get interval previews for each rating
        intervals = get_next_intervals(
            current_state=card.state,
            current_stability=card.stability,
            current_difficulty=card.difficulty,
            current_scheduled_days=card.scheduled_days,
            last_review=card.last_review
        )

        # Calculate current retrievability
        retrievability = get_card_retrievability(card.stability, card.last_review)

        result.append({
            "id": card.id,
            "front": card.front,
            "back": card.back,
            "state": card.state,
            "state_name": state_to_string(card.state),
            "stability": card.stability,
            "difficulty": card.difficulty,
            "reps": card.reps,
            "lapses": card.lapses,
            "intervals": intervals,
            "retrievability": round(retrievability * 100, 1)
        })

    return result

@app.post("/revisions/review/{card_id}")
def submit_review(
    card_id: int,
    submission: ReviewSubmission,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Submit a review rating for a card using FSRS algorithm.
    Rating: 1=Again, 2=Hard, 3=Good, 4=Easy
    """
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Verify card belongs to current user if authenticated
    if current_user and card.user_id and card.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cette carte ne vous appartient pas")

    # Validate rating
    if submission.rating < 1 or submission.rating > 4:
        raise HTTPException(status_code=400, detail="Rating must be 1-4")

    # Calculate next review using FSRS
    result = calculate_next_review(
        current_state=card.state,
        current_stability=card.stability,
        current_difficulty=card.difficulty,
        current_scheduled_days=card.scheduled_days,
        current_reps=card.reps,
        current_lapses=card.lapses,
        current_step=card.step,
        last_review=card.last_review,
        rating=submission.rating
    )

    # Update card with FSRS results
    card.state = result["state"]
    card.stability = result["stability"]
    card.difficulty = result["difficulty"]
    card.scheduled_days = result["scheduled_days"]
    card.due_date = result["due_date"]
    card.reps = result["reps"]
    card.lapses = result["lapses"]
    card.step = result["step"]
    card.last_review = result["last_review"]

    db.commit()

    return {
        "status": "ok",
        "next_due": card.due_date,
        "state": state_to_string(card.state),
        "stability": card.stability / 100.0,
        "difficulty": card.difficulty / 100.0,
        "retrievability": result.get("retrievability", 0)
    }

@app.post("/revisions/generate-for-all")
def generate_all_flashcards(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Manually trigger flashcard generation for all existing arguments.
    Useful if arguments already exist but no cards.
    Creates cards for the current user if authenticated.
    """
    arguments = db.query(Argument).all()
    # This might be huge, so we should do it in background
    # Create job for tracking
    job_id = str(uuid.uuid4())
    analysis_jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Demarrage generation...",
        "filename": "Flashcards"
    }

    # Pass IDs only to avoid DetachedInstanceError
    argument_ids = [arg.id for arg in arguments]
    user_id = current_user.id if current_user else None
    background_tasks.add_task(background_generate_flashcards, job_id, argument_ids, user_id)
    return {"message": "Flashcard generation started", "job_id": job_id}

def background_generate_flashcards(job_id: str, argument_ids: List[int], user_id: Optional[int]):
    # Better to create new session in thread, but for simplicity here strictly:
    # We iterate and generate.
    print(f"[{datetime.now()}] Starting Batch Flashcard Generation for {len(argument_ids)} arguments (user_id={user_id})...")

    # Re-create session safer
    local_db = SessionLocal()

    # Update job to processing
    analysis_jobs[job_id]["status"] = "processing"
    analysis_jobs[job_id]["message"] = "Analyse des arguments..."

    try:
        count = 0
        total_args = len(argument_ids)

        for i, arg_id in enumerate(argument_ids):
            # Fetch fresh object with relationship
            arg = local_db.query(Argument).filter(Argument.id == arg_id).first()
            if not arg: continue

            # Check if cards already exist for this user
            existing_query = local_db.query(Flashcard).filter(Flashcard.argument_id == arg.id)
            if user_id:
                existing_query = existing_query.filter(Flashcard.user_id == user_id)
            if existing_query.count() > 0:
                continue

            # Prepare contextual strings
            proofs_txt = "\n".join([f"- {p.content} ({p.specific_year}) {'[NUANCE]' if p.is_nuance else ''}" for p in arg.proofs])

            cards_data = generate_flashcards_from_argument(arg.theme, arg.chronology_period, arg.content, proofs_txt)

            for c in cards_data:
                verification = local_db.query(Flashcard).filter(
                    Flashcard.argument_id == arg.id,
                    Flashcard.front == c['front'],
                    Flashcard.user_id == user_id if user_id else True
                ).first()
                if not verification:
                    fc = Flashcard(
                        argument_id=arg.id,
                        front=c['front'],
                        back=c['back'],
                        user_id=user_id
                    )
                    local_db.add(fc)
                    count += 1

            local_db.commit()

            # Update progress
            current_progress = int(((i + 1) / total_args) * 100)
            analysis_jobs[job_id]["progress"] = current_progress
            analysis_jobs[job_id]["message"] = f"Generation... {current_progress}%"

        print(f"[{datetime.now()}] Batch Generation Complete. Created {count} cards.")
        analysis_jobs[job_id]["status"] = "completed"
        analysis_jobs[job_id]["message"] = f"Termine ! {count} cartes creees."
        analysis_jobs[job_id]["progress"] = 100


    except Exception as e:
        print(f"[{datetime.now()}] Job Failed: {e}")
        analysis_jobs[job_id]["status"] = "failed"
        analysis_jobs[job_id]["message"] = f"Erreur: {str(e)}"
    finally:
        local_db.close()


@app.get("/definitions")
def get_definitions(db: Session = Depends(get_db)):
    return db.query(DefinitionSource).all()

    db.query(DefinitionExtraction).filter(DefinitionExtraction.source_id == id).delete()
    db.delete(source)
    db.commit()
    return {"message": "Deleted"}

# --- LIBRARY ENDPOINTS (Folders & Saved Dissertations) ---

class FolderCreate(BaseModel):
    name: str

class DissertationSave(BaseModel):
    folder_id: int
    subject: str
    content: str
    type: str

@app.get("/folders")
def get_folders(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get folders filtered by current user if authenticated"""
    query = db.query(DissertationFolder)
    if current_user:
        query = query.filter(DissertationFolder.user_id == current_user.id)

    folders = query.all()
    result = []
    for f in folders:
        result.append({
            "id": f.id,
            "name": f.name,
            "created_at": f.created_at,
            "dissertations": [
                {
                    "id": d.id,
                    "subject": d.subject,
                    "type": d.type,
                    "created_at": d.created_at
                } for d in f.dissertations
            ]
        })
    return result

@app.post("/folders")
def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Create a folder for the current user"""
    # Check duplicate name for this user
    query = db.query(DissertationFolder).filter(DissertationFolder.name == folder.name)
    if current_user:
        query = query.filter(DissertationFolder.user_id == current_user.id)
    existing = query.first()
    if existing:
        raise HTTPException(status_code=400, detail="Un dossier avec ce nom existe deja.")

    new_folder = DissertationFolder(
        name=folder.name,
        user_id=current_user.id if current_user else None
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

@app.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Delete a folder (must belong to current user)"""
    folder = db.query(DissertationFolder).filter(DissertationFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier non trouve.")

    # Verify ownership
    if current_user and folder.user_id and folder.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce dossier ne vous appartient pas")

    # Cascade delete is handled by relationship, but we can be explicit
    db.delete(folder)
    db.commit()
    return {"message": "Dossier supprime"}

@app.post("/library/save")
def save_dissertation_to_library(
    item: DissertationSave,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Save a dissertation to a folder (must belong to current user)"""
    folder = db.query(DissertationFolder).filter(DissertationFolder.id == item.folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier cible non trouve.")

    # Verify ownership
    if current_user and folder.user_id and folder.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce dossier ne vous appartient pas")

    new_save = SavedDissertation(
        folder_id=item.folder_id,
        subject=item.subject,
        content=item.content,
        type=item.type
    )
    db.add(new_save)
    db.commit()
    db.refresh(new_save)
    return new_save

@app.get("/library/dissertation/{id}")
def get_saved_dissertation(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get a saved dissertation (must belong to current user)"""
    item = db.query(SavedDissertation).filter(SavedDissertation.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dissertation non trouvee.")

    # Verify ownership via folder
    if current_user and item.folder.user_id and item.folder.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cette dissertation ne vous appartient pas")

    return item

@app.delete("/library/dissertation/{id}")
def delete_saved_dissertation(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Delete a saved dissertation (must belong to current user)"""
    item = db.query(SavedDissertation).filter(SavedDissertation.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trouve.")

    # Verify ownership via folder
    if current_user and item.folder.user_id and item.folder.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cette dissertation ne vous appartient pas")

    db.delete(item)
    db.commit()
    return {"message": "Supprime avec succes"}
