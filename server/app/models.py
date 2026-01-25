from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_analyzed = Column(Boolean, default=False)

    arguments = relationship("Argument", back_populates="source")

class Argument(Base):
    __tablename__ = "arguments"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    theme = Column(String, index=True)  # e.g., "citoyennete", "conceptions"
    chronology_period = Column(String, index=True) # e.g., "1850-1918"
    content = Column(Text) # The general trend/truth

    source = relationship("Source", back_populates="arguments")
    proofs = relationship("Proof", back_populates="argument")
    flashcards = relationship("Flashcard", back_populates="argument", cascade="all, delete-orphan")

class Proof(Base):
    __tablename__ = "proofs"

    id = Column(Integer, primary_key=True, index=True)
    argument_id = Column(Integer, ForeignKey("arguments.id"))
    content = Column(Text) # Factual details
    specific_year = Column(String, nullable=True)
    citation_complement = Column(Text, nullable=True)  # Citation with reference
    
    # New field: is_nuance
    is_nuance = Column(Boolean, default=False)

    argument = relationship("Argument", back_populates="proofs")

class DefinitionSource(Base):
    __tablename__ = "definition_sources"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_analyzed = Column(Boolean, default=False)

    extractions = relationship("DefinitionExtraction", back_populates="source")

class DefinitionExtraction(Base):
    __tablename__ = "definition_extractions"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("definition_sources.id"))
    
    # 'definition' or 'citation'
    type = Column(String, index=True)
    
    # For definition: the term (e.g. "Sport Scolaire")
    # For citation: the author/concept key
    key_term = Column(String, index=True)
    
    # The content text
    content = Column(Text)
    
    source = relationship("DefinitionSource", back_populates="extractions")

class DissertationFolder(Base):
    __tablename__ = "dissertation_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dissertations = relationship("SavedDissertation", back_populates="folder", cascade="all, delete-orphan")

class SavedDissertation(Base):
    __tablename__ = "saved_dissertations"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("dissertation_folders.id"))
    subject = Column(String)
    content = Column(Text)
    type = Column(String) # 'plan' or 'dissertation'
    created_at = Column(DateTime, default=datetime.utcnow)

    folder = relationship("DissertationFolder", back_populates="dissertations")

class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    argument_id = Column(Integer, ForeignKey("arguments.id"))

    front = Column(Text)  # Question
    back = Column(Text)   # Answer

    # FSRS Algorithm Fields (Free Spaced Repetition Scheduler - Anki's modern algorithm)
    # State: 0=New, 1=Learning, 2=Review, 3=Relearning
    state = Column(Integer, default=0)

    # Stability: Expected number of days to retain 90% recall probability
    # Higher stability = longer intervals
    stability = Column(Integer, default=0)  # Stored as days * 100 for precision (e.g., 250 = 2.5 days)

    # Difficulty: Card difficulty from 1 (easy) to 10 (hard)
    # Affects how stability grows with each review
    difficulty = Column(Integer, default=0)  # Stored as value * 100 (e.g., 500 = 5.0)

    # Scheduled days: Current interval in days
    scheduled_days = Column(Integer, default=0)

    # Due date: When the card is due for review
    due_date = Column(DateTime, default=datetime.utcnow)

    # Last review: When the card was last reviewed
    last_review = Column(DateTime, nullable=True)

    # Reps: Number of successful reviews (without Again)
    reps = Column(Integer, default=0)

    # Lapses: Number of times card went from Review to Relearning (forgot after learning)
    lapses = Column(Integer, default=0)

    # Learning/Relearning step: Current step in learning phase (0, 1, 2...)
    step = Column(Integer, default=0)

    argument = relationship("Argument", back_populates="flashcards")
