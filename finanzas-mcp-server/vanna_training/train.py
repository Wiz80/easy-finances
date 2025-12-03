"""
Vanna Training Script.

Trains the NL-to-SQL system by populating Qdrant collections with:
1. DDL statements (schema context)
2. Documentation (business context)
3. SQL examples (NL to SQL pairs)

Usage:
    cd finanzas-mcp-server
    python -m vanna_training.train
"""

import json
import logging
from pathlib import Path
from uuid import uuid4

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy import create_engine, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load training configuration."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_settings():
    """Get settings from environment."""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    return {
        "postgres_url": os.getenv(
            "DATABASE_URL",
            f"postgresql://{os.getenv('POSTGRES_USER', 'finanzas_user')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'finanzas_password')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'finanzas_db')}"
        ),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "qdrant_host": os.getenv("QDRANT_HOST", "localhost"),
        "qdrant_port": int(os.getenv("QDRANT_PORT", "6333")),
        "ddl_collection": os.getenv("QDRANT_DDL_COLLECTION", "vanna_ddl"),
        "doc_collection": os.getenv("QDRANT_DOC_COLLECTION", "vanna_documentation"),
        "sql_collection": os.getenv("QDRANT_SQL_COLLECTION", "vanna_sql"),
    }


class VannaTrainer:
    """Trainer for Vanna NL-to-SQL system."""
    
    def __init__(self):
        self.settings = get_settings()
        self.config = load_config()
        
        # Clients
        self.openai = OpenAI(api_key=self.settings["openai_api_key"])
        self.qdrant = QdrantClient(
            host=self.settings["qdrant_host"],
            port=self.settings["qdrant_port"],
        )
        self.db_engine = create_engine(self.settings["postgres_url"])
        
    def setup_collections(self):
        """Create Qdrant collections if they don't exist."""
        collections = [
            self.settings["ddl_collection"],
            self.settings["doc_collection"],
            self.settings["sql_collection"],
        ]
        
        existing = {c.name for c in self.qdrant.get_collections().collections}
        
        for name in collections:
            if name not in existing:
                self.qdrant.create_collection(
                    collection_name=name,
                    vectors_config=qdrant_models.VectorParams(
                        size=1536,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created collection: {name}")
            else:
                logger.info(f"Collection exists: {name}")
    
    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding using OpenAI."""
        response = self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
    
    def train_ddl(self):
        """Extract and store DDL from database."""
        logger.info("Training DDL...")
        
        inspector = inspect(self.db_engine)
        tables = inspector.get_table_names()
        
        enabled_tables = {t["name"] for t in self.config["tables"] if t.get("enabled", True)}
        
        for table_name in tables:
            if table_name not in enabled_tables:
                continue
                
            # Get DDL
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            
            ddl_parts = [f"CREATE TABLE {table_name} ("]
            col_defs = []
            for col in columns:
                col_def = f"  {col['name']} {col['type']}"
                if not col.get("nullable", True):
                    col_def += " NOT NULL"
                col_defs.append(col_def)
            
            if pk and pk.get("constrained_columns"):
                pk_cols = ", ".join(pk["constrained_columns"])
                col_defs.append(f"  PRIMARY KEY ({pk_cols})")
            
            ddl_parts.append(",\n".join(col_defs))
            ddl_parts.append(");")
            ddl = "\n".join(ddl_parts)
            
            # Store in Qdrant
            doc_id = str(uuid4())
            embedding = self.generate_embedding(ddl)
            
            self.qdrant.upsert(
                collection_name=self.settings["ddl_collection"],
                points=[
                    qdrant_models.PointStruct(
                        id=doc_id,
                        vector=embedding,
                        payload={
                            "content": ddl,
                            "table_name": table_name,
                            "type": "ddl",
                        },
                    )
                ],
            )
            logger.info(f"  Added DDL for: {table_name}")
    
    def train_documentation(self):
        """Store documentation from config."""
        logger.info("Training documentation...")
        
        for table in self.config["tables"]:
            if not table.get("enabled", True):
                continue
            
            # Build documentation
            doc_parts = [
                f"Tabla: {table['name']}",
                f"Descripción: {table['description']}",
                f"Contexto: {table['business_context']}",
                "",
                "Columnas principales:",
            ]
            
            for col in table.get("key_columns", []):
                doc_parts.append(f"  - {col['name']}: {col['description']}")
            
            doc = "\n".join(doc_parts)
            
            # Store in Qdrant
            doc_id = str(uuid4())
            embedding = self.generate_embedding(doc)
            
            self.qdrant.upsert(
                collection_name=self.settings["doc_collection"],
                points=[
                    qdrant_models.PointStruct(
                        id=doc_id,
                        vector=embedding,
                        payload={
                            "content": doc,
                            "table_name": table["name"],
                            "type": "documentation",
                        },
                    )
                ],
            )
            logger.info(f"  Added documentation for: {table['name']}")
        
        # Add global rules
        rules_doc = "REGLAS GLOBALES:\n" + "\n".join(f"- {r}" for r in self.config["global_rules"])
        doc_id = str(uuid4())
        embedding = self.generate_embedding(rules_doc)
        
        self.qdrant.upsert(
            collection_name=self.settings["doc_collection"],
            points=[
                qdrant_models.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload={
                        "content": rules_doc,
                        "table_name": None,
                        "type": "rules",
                    },
                )
            ],
        )
        logger.info("  Added global rules")
    
    def train_sql_examples(self):
        """Generate and store SQL examples using LLM."""
        logger.info("Training SQL examples...")
        
        for table in self.config["tables"]:
            if not table.get("enabled", True):
                continue
            
            for question in table.get("example_questions", []):
                # Generate SQL using LLM
                sql = self._generate_sql_example(question, table)
                
                if sql:
                    doc_id = str(uuid4())
                    embedding = self.generate_embedding(question)
                    
                    self.qdrant.upsert(
                        collection_name=self.settings["sql_collection"],
                        points=[
                            qdrant_models.PointStruct(
                                id=doc_id,
                                vector=embedding,
                                payload={
                                    "question": question,
                                    "sql": sql,
                                    "content": sql,
                                    "table_name": table["name"],
                                    "type": "sql_example",
                                },
                            )
                        ],
                    )
                    logger.info(f"  Added: {question[:40]}...")
    
    def _generate_sql_example(self, question: str, table: dict) -> str | None:
        """Generate SQL for a question using LLM."""
        prompt = f"""Genera una consulta SQL para esta pregunta sobre finanzas personales.

Tabla principal: {table['name']}
Descripción: {table['description']}
Columnas: {', '.join(c['name'] for c in table.get('key_columns', []))}

REGLAS:
- Solo SELECT
- SIEMPRE incluir WHERE user_id = :user_id
- Usar occurred_at para fechas
- Montos en amount_original con currency_original

Pregunta: {question}

Responde SOLO con el SQL, sin explicaciones."""

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            
            sql = response.choices[0].message.content.strip()
            
            # Clean
            if sql.startswith("```"):
                sql = sql.split("```")[1]
                if sql.startswith("sql"):
                    sql = sql[3:]
            sql = sql.strip()
            
            # Basic validation
            if not sql.upper().startswith("SELECT"):
                return None
            if "user_id" not in sql.lower():
                return None
                
            return sql
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return None
    
    def train_all(self):
        """Run complete training."""
        logger.info("=" * 60)
        logger.info("VANNA TRAINING")
        logger.info("=" * 60)
        
        self.setup_collections()
        self.train_ddl()
        self.train_documentation()
        self.train_sql_examples()
        
        logger.info("=" * 60)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    trainer = VannaTrainer()
    trainer.train_all()


if __name__ == "__main__":
    main()

