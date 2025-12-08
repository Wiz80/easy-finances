"""
Vanna 2.x Training Orchestrator.

Trains Vanna AI with DDL, documentation, and SQL examples using
the new Agent Memory architecture.

Usage:
    python -m app.agents.coach_agent.training.trainer
    
    # Force retrain all
    python -m app.agents.coach_agent.training.trainer --force
    
    # Only train DDL
    python -m app.agents.coach_agent.training.trainer --ddl-only
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.agents.coach_agent.services.database import DatabaseService
from app.agents.coach_agent.services.vanna_service import get_vanna_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Training configuration path
CONFIG_PATH = Path(__file__).parent / "config.json"


class VannaTrainer:
    """
    Orchestrates Vanna 2.x AI training.
    
    Training data is stored in Qdrant via AgentMemory:
    1. DDL: CREATE TABLE statements as text memories
    2. Documentation: Table descriptions and business context
    3. SQL: Question → SQL pairs as tool usage patterns
    """

    def __init__(self):
        """Initialize trainer."""
        self.db = DatabaseService()
        self.vanna_service = get_vanna_service()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load training configuration."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f)
        else:
            logger.warning(f"Config not found at {CONFIG_PATH}, using defaults")
            return {"tables": [], "global_rules": []}

    async def train_ddl(self) -> int:
        """
        Train with DDL statements from database.
        
        Returns:
            Number of DDL statements added
        """
        logger.info("Training DDL...")
        count = 0

        # Get enabled tables from config
        enabled_tables = {
            t["name"]
            for t in self.config.get("tables", [])
            if t.get("enabled", True)
        }

        # Get all tables from database
        db_tables = self.db.get_table_names()

        for table_name in db_tables:
            # Skip if not in enabled list (when config has tables)
            if enabled_tables and table_name not in enabled_tables:
                logger.debug(f"Skipping table: {table_name}")
                continue

            # Get DDL
            ddl = self.db.get_table_ddl(table_name)

            if ddl:
                success = await self.vanna_service.add_training_data(ddl=ddl)
                if success:
                    count += 1
                    logger.info(f"  Added DDL for: {table_name}")
                else:
                    logger.warning(f"  Failed to add DDL for: {table_name}")

        logger.info(f"DDL training complete: {count} tables")
        return count

    async def train_documentation(self) -> int:
        """
        Train with documentation from config.
        
        Returns:
            Number of documentation entries added
        """
        logger.info("Training documentation...")
        count = 0

        for table in self.config.get("tables", []):
            if not table.get("enabled", True):
                continue

            # Build documentation text
            doc_parts = [
                f"Tabla: {table['name']}",
                f"Descripción: {table.get('description', '')}",
                f"Contexto de negocio: {table.get('business_context', '')}",
                "",
                "Columnas principales:",
            ]

            for col in table.get("key_columns", []):
                doc_parts.append(f"  - {col['name']}: {col['description']}")

            doc = "\n".join(doc_parts)

            success = await self.vanna_service.add_training_data(documentation=doc)
            if success:
                count += 1
                logger.info(f"  Added documentation for: {table['name']}")
            else:
                logger.warning(f"  Failed to add documentation for: {table['name']}")

        # Add global rules
        rules = self.config.get("global_rules", [])
        if rules:
            rules_doc = "REGLAS GLOBALES PARA QUERIES:\n" + "\n".join(f"- {r}" for r in rules)
            success = await self.vanna_service.add_training_data(documentation=rules_doc)
            if success:
                count += 1
                logger.info("  Added global rules")

        logger.info(f"Documentation training complete: {count} entries")
        return count

    async def train_sql_examples(self) -> int:
        """
        Train with SQL examples from config.
        
        Returns:
            Number of SQL examples added
        """
        logger.info("Training SQL examples...")
        count = 0

        for table in self.config.get("tables", []):
            if not table.get("enabled", True):
                continue

            for example in table.get("sql_examples", []):
                question = example.get("question")
                sql = example.get("sql")

                if question and sql:
                    success = await self.vanna_service.add_training_data(
                        question=question,
                        sql=sql,
                    )
                    if success:
                        count += 1
                        logger.info(f"  Added: {question[:40]}...")
                    else:
                        logger.warning(f"  Failed: {question[:40]}...")

        logger.info(f"SQL examples training complete: {count} pairs")
        return count

    async def train_all(self) -> dict:
        """
        Run complete training pipeline.
        
        Returns:
            Training summary
        """
        logger.info("=" * 60)
        logger.info("VANNA 2.x TRAINING PIPELINE")
        logger.info("=" * 60)

        ddl_count = await self.train_ddl()
        doc_count = await self.train_documentation()
        sql_count = await self.train_sql_examples()

        # Get final stats
        stats = await self.vanna_service.get_training_data()

        summary = {
            "ddl_added": ddl_count,
            "documentation_added": doc_count,
            "sql_examples_added": sql_count,
            "total_ddl": stats.get("ddl_count", 0),
            "total_documentation": stats.get("documentation_count", 0),
            "total_sql": stats.get("sql_count", 0),
        }

        logger.info("=" * 60)
        logger.info("TRAINING COMPLETE")
        logger.info(f"  DDL: {summary['total_ddl']}")
        logger.info(f"  Documentation: {summary['total_documentation']}")
        logger.info(f"  SQL Examples: {summary['total_sql']}")
        logger.info("=" * 60)

        return summary

    async def verify_training(self, test_questions: list[str] | None = None) -> dict:
        """
        Verify training by testing sample questions.
        
        Args:
            test_questions: List of questions to test
            
        Returns:
            Verification results
        """
        if not test_questions:
            test_questions = [
                "¿Cuánto gasté este mes?",
                "¿Cuáles son mis gastos por categoría?",
                "Muéstrame los gastos de la última semana",
            ]

        logger.info("Verifying training...")
        results = []

        for question in test_questions:
            result = await self.vanna_service.generate_sql(question)
            results.append({
                "question": question,
                "success": result["success"],
                "sql": result.get("sql"),
                "error": result.get("error"),
            })

            status = "✓" if result["success"] else "✗"
            logger.info(f"  {status} {question[:40]}...")
            if result["success"]:
                logger.info(f"    SQL: {result['sql'][:60]}...")

        passed = sum(1 for r in results if r["success"])
        total = len(results)

        return {
            "passed": passed,
            "total": total,
            "success_rate": passed / total if total > 0 else 0,
            "results": results,
        }


async def async_main(args):
    """Async main entry point."""
    trainer = VannaTrainer()

    if args.ddl_only:
        await trainer.train_ddl()
    elif args.docs_only:
        await trainer.train_documentation()
    else:
        await trainer.train_all()

    if args.verify:
        await trainer.verify_training()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Train Vanna 2.x AI")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force complete retraining",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification after training",
    )
    parser.add_argument(
        "--ddl-only",
        action="store_true",
        help="Train only DDL",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Train only documentation",
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()

