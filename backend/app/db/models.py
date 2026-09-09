from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailNotice(Base):
    __tablename__ = "email_notices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender = Column(String(255), nullable=False, index=True)
    recipient = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=False)
    body_text = Column(Text, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    
    # Attachments and URLs
    has_attachments = Column(Boolean, default=False)
    attachment_paths = Column(Text, nullable=True) # JSON list or comma-separated paths
    extracted_urls = Column(Text, nullable=True) # JSON list or comma-separated URLs
    
    # LLM Triage Results
    is_relevant = Column(Boolean, default=False)
    relevance_score = Column(Float, default=0.0)
    triage_summary = Column(Text, nullable=True)
    triage_reasoning = Column(Text, nullable=True)
    target_program = Column(String(100), default="Ingeniería de Sistemas")
    
    # Status: PENDING_REVIEW, APPROVED_INDEXED, REJECTED, AUTO_INDEXED
    status = Column(String(50), default="PENDING_REVIEW", index=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Documents derived from this email
    documents = relationship("DocumentItem", back_populates="email", cascade="all, delete-orphan")

class DocumentItem(Base):
    __tablename__ = "document_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), default="pdf") # pdf, markdown, text
    source_type = Column(String(50), default="MANUAL_UPLOAD") # SEED, MANUAL_UPLOAD, EMAIL_ATTACHMENT, EMAIL_BODY
    
    email_id = Column(Integer, ForeignKey("email_notices.id"), nullable=True)
    resolution_number = Column(String(100), nullable=True) # e.g. "Acuerdo 038 de 2015"
    effective_date = Column(String(50), nullable=True)
    
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="INDEXED") # INDEXED, PENDING, ERROR
    validity_status = Column(String(50), default="VIGENTE") # VIGENTE, MODIFICADO, DEROGADO
    supersedes_id = Column(Integer, ForeignKey("document_items.id"), nullable=True)
    superseded_by_title = Column(String(255), nullable=True)
    markdown_content = Column(Text, nullable=True)
    scan_image_path = Column(String(500), nullable=True)
    original_pdf_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    email = relationship("EmailNotice", back_populates="documents")

class StudentQueryLog(Base):
    __tablename__ = "student_query_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    topic_category = Column(String(100), default="General", index=True) # Modalidades, Pasantías, Inglés B2, Paz y Salvos, Matrícula
    citations_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=1.0)
    has_knowledge_gap = Column(Boolean, default=False, index=True)
    device_type = Column(String(50), default="desktop")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class SessionFeedback(Base):
    __tablename__ = "session_feedbacks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    feedback_type = Column(String(50), default="general") # sugerencia, informacion_imprecisa, error_tecnico, general
    rating = Column(Integer, nullable=True)
    comments = Column(Text, nullable=False)
    has_transcript = Column(Boolean, default=False)
    transcript_json = Column(Text, nullable=True)
    target_email = Column(String(255), default="canigraduateud@gmail.com")
    status = Column(String(50), default="RECEIVED")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


