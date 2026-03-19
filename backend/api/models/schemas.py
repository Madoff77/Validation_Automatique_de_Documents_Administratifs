from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


# Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class DocumentType(str, Enum):
    FACTURE = "FACTURE"
    DEVIS = "DEVIS"
    SIRET = "SIRET"
    URSSAF = "URSSAF"
    KBIS = "KBIS"
    RIB = "RIB"
    UNKNOWN = "UNKNOWN"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    OCR_DONE = "ocr_done"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    PROCESSED = "processed"
    ERROR = "error"


class ValidationStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    PENDING = "pending"
    INFO = "info"


class AnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AnomalyType(str, Enum):
    SIRET_MISMATCH = "SIRET_MISMATCH"
    DATE_EXPIRED = "DATE_EXPIRED"
    TVA_INCOHERENCE = "TVA_INCOHERENCE"
    MISSING_FIELD = "MISSING_FIELD"
    FORMAT_ERROR = "FORMAT_ERROR"
    KBIS_EXPIRED = "KBIS_EXPIRED"
    URSSAF_EXPIRED = "URSSAF_EXPIRED"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    NON_COMPLIANT = "non_compliant"
    PENDING = "pending"


# AUTH SCHEMAS

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.OPERATOR
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: UserRole
    full_name: Optional[str]
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# SUPPLIER SCHEMAS

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    siret: Optional[str] = Field(None, pattern=r"^\d{14}$")
    siren: Optional[str] = Field(None, pattern=r"^\d{9}$")
    tva_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    siret: Optional[str] = Field(None, pattern=r"^\d{14}$")
    siren: Optional[str] = Field(None, pattern=r"^\d{9}$")
    tva_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    supplier_id: str
    name: str
    siret: Optional[str]
    siren: Optional[str]
    tva_number: Optional[str]
    address: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    document_count: int
    compliance_status: ComplianceStatus


# DOCUMENT SCHEMAS

class ExtractedFields(BaseModel):
    siret: Optional[str] = None
    siren: Optional[str] = None
    tva_number: Optional[str] = None
    montant_ht: Optional[float] = None
    montant_tva: Optional[float] = None
    montant_ttc: Optional[float] = None
    taux_tva: Optional[float] = None
    date_emission: Optional[str] = None
    date_echeance: Optional[str] = None
    date_expiration: Optional[str] = None
    numero_document: Optional[str] = None
    raison_sociale: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    banque: Optional[str] = None
    adresse: Optional[str] = None
    raw_fields: Dict[str, Any] = {}


class ValidationCheck(BaseModel):
    rule: str
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class DocumentValidation(BaseModel):
    status: ValidationStatus
    checks: List[ValidationCheck] = []


class DocumentResponse(BaseModel):
    document_id: str
    supplier_id: str
    filename: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    upload_timestamp: datetime
    status: DocumentStatus
    zone: str
    doc_type: Optional[DocumentType]
    classification_confidence: Optional[float]
    ocr_quality_score: Optional[float]
    extracted: Optional[ExtractedFields]
    validation: Optional[DocumentValidation]
    processing_duration_ms: Optional[int]
    error_message: Optional[str]
    airflow_run_id: Optional[str]


class DocumentListItem(BaseModel):
    document_id: str
    supplier_id: str
    original_filename: str
    doc_type: Optional[DocumentType]
    status: DocumentStatus
    upload_timestamp: datetime
    classification_confidence: Optional[float]
    validation_status: Optional[str]


# ANOMALY SCHEMAS

class AnomalyResponse(BaseModel):
    anomaly_id: str
    supplier_id: str
    document_id: Optional[str]
    related_document_id: Optional[str]
    type: AnomalyType
    severity: AnomalySeverity
    message: str
    details: Optional[Dict[str, Any]]
    detected_at: datetime
    resolved: bool
    resolved_at: Optional[datetime]
    supplier_name: Optional[str] = None


class AnomalyResolve(BaseModel):
    resolved: bool


# PIPELINE SCHEMAS

class PipelineStatus(BaseModel):
    document_id: str
    airflow_run_id: Optional[str]
    status: str
    message: str


class PipelineTriggerResponse(BaseModel):
    document_id: str
    airflow_run_id: str
    message: str


# DASHBOARD / STATS SCHEMAS

class DashboardStats(BaseModel):
    total_documents: int
    documents_processed: int
    documents_pending: int
    documents_error: int
    total_suppliers: int
    active_suppliers: int
    total_anomalies: int
    unresolved_anomalies: int
    critical_anomalies: int
    documents_expiring_soon: int


class ComplianceOverview(BaseModel):
    supplier_id: str
    supplier_name: str
    compliance_status: ComplianceStatus
    anomaly_count: int
    critical_anomalies: int
    expired_documents: int
    expiring_soon: int
    last_check: Optional[datetime]
