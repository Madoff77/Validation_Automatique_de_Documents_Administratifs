// Initialisation MongoDB — création utilisateur app + indexes
db = db.getSiblingDB('docplatform');

// Création des collections avec indexes
db.createCollection('users');
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ username: 1 }, { unique: true });

db.createCollection('suppliers');
db.suppliers.createIndex({ supplier_id: 1 }, { unique: true });
db.suppliers.createIndex({ siret: 1 });
db.suppliers.createIndex({ name: "text" });

db.createCollection('documents');
db.documents.createIndex({ document_id: 1 }, { unique: true });
db.documents.createIndex({ supplier_id: 1 });
db.documents.createIndex({ status: 1 });
db.documents.createIndex({ doc_type: 1 });
db.documents.createIndex({ upload_timestamp: -1 });

db.createCollection('anomalies');
db.anomalies.createIndex({ anomaly_id: 1 }, { unique: true });
db.anomalies.createIndex({ supplier_id: 1 });
db.anomalies.createIndex({ document_id: 1 });
db.anomalies.createIndex({ severity: 1 });
db.anomalies.createIndex({ resolved: 1 });

db.createCollection('refresh_tokens');
db.refresh_tokens.createIndex({ token: 1 }, { unique: true });
db.refresh_tokens.createIndex({ user_id: 1 });
db.refresh_tokens.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });

print('MongoDB docplatform initialisé avec succès');
