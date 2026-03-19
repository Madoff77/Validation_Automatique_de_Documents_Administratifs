from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application
    app_name: str = "DocPlatform API"
    app_version: str = "2.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # MongoDB
    mongo_uri: str = "mongodb://root:rootpassword@localhost:27017"
    mongo_db: str = "docplatform"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket_raw: str = "raw"
    minio_bucket_clean: str = "clean"
    minio_bucket_curated: str = "curated"

    # Auth JWT
    jwt_secret_key: str = "supersecretkey_change_in_production_please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Airflow
    airflow_url: str = "http://localhost:8080"
    airflow_username: str = "admin"
    airflow_password: str = "admin"
    airflow_dag_id: str = "document_pipeline"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ML Model
    model_path: str = "/app/models/trained/classifier.joblib"
    vectorizer_path: str = "/app/models/trained/vectorizer.joblib"
    classification_confidence_threshold: float = 0.6

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
