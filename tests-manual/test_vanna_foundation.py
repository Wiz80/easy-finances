"""
Manual tests for Vanna AI Foundation (Phase 2A).

These tests verify:
1. Vanna configuration is correct
2. Qdrant collections can be created
3. SQL validation works correctly
4. Basic Vanna operations work

Prerequisites:
- Qdrant running (docker-compose up qdrant)
- OpenAI API key configured
- Virtual environment activated

Run:
    python tests-manual/test_vanna_foundation.py
"""

import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import configure_logging

configure_logging()


def test_vanna_config():
    """Test Vanna configuration loading."""
    print("\n" + "=" * 60)
    print("TEST: Vanna Configuration")
    print("=" * 60)

    from app.vanna.config import get_vanna_config, VannaConfig

    config = get_vanna_config()

    print(f"✓ Config loaded: {type(config).__name__}")
    print(f"  - Qdrant URL: {config.qdrant_url}")
    print(f"  - DDL Collection: {config.ddl_collection.name}")
    print(f"  - Doc Collection: {config.doc_collection.name}")
    print(f"  - SQL Collection: {config.sql_collection.name}")
    print(f"  - Vector Dimension: {config.vector_dimension}")
    print(f"  - LLM Provider: {config.llm_provider}")
    print(f"  - Query Timeout: {config.query_timeout_seconds}s")
    print(f"  - Max Result Rows: {config.max_result_rows}")

    assert config.qdrant_url.startswith("http://")
    assert config.vector_dimension == 1536
    print("\n✅ Vanna configuration test PASSED")


def test_sql_validator():
    """Test SQL validation functions."""
    print("\n" + "=" * 60)
    print("TEST: SQL Validator")
    print("=" * 60)

    from app.vanna.security import (
        validate_sql,
        is_select_only,
        contains_user_id_filter,
        inject_user_id_filter,
        SQLValidationError,
    )

    # Test valid SELECT
    print("\n1. Testing valid SELECT statements...")

    valid_queries = [
        "SELECT * FROM expense WHERE user_id = :user_id",
        "SELECT e.amount_original, c.name FROM expense e JOIN category c ON e.category_id = c.id WHERE e.user_id = :user_id",
        "SELECT SUM(amount_original) as total FROM expense WHERE user_id = :user_id GROUP BY category_id",
    ]

    for sql in valid_queries:
        result = validate_sql(sql)
        assert result.valid, f"Expected valid: {sql}"
        print(f"  ✓ Valid: {sql[:50]}...")

    # Test invalid queries
    print("\n2. Testing invalid statements (should be rejected)...")

    invalid_queries = [
        ("DELETE FROM expense", "DML not allowed"),
        ("DROP TABLE expense", "DDL not allowed"),
        ("UPDATE expense SET amount = 0", "DML not allowed"),
        ("INSERT INTO expense VALUES (1)", "DML not allowed"),
        ("SELECT * FROM expense", "Missing user_id filter"),
        ("SELECT * FROM expense; DELETE FROM expense", "Multiple statements"),
    ]

    for sql, reason in invalid_queries:
        result = validate_sql(sql)
        assert not result.valid, f"Expected invalid ({reason}): {sql}"
        print(f"  ✓ Rejected ({reason}): {sql[:40]}...")

    # Test is_select_only
    print("\n3. Testing is_select_only...")
    assert is_select_only("SELECT * FROM expense") == True
    assert is_select_only("DELETE FROM expense") == False
    print("  ✓ is_select_only works correctly")

    # Test contains_user_id_filter
    print("\n4. Testing contains_user_id_filter...")
    assert contains_user_id_filter("SELECT * FROM expense WHERE user_id = :user_id") == True
    assert contains_user_id_filter("SELECT * FROM expense") == False
    print("  ✓ contains_user_id_filter works correctly")

    # Test inject_user_id_filter
    print("\n5. Testing inject_user_id_filter...")
    user_id = uuid4()
    sql = "SELECT * FROM expense"
    injected = inject_user_id_filter(sql, user_id)
    assert str(user_id) in injected
    assert "WHERE" in injected
    print(f"  ✓ Injected SQL: {injected}")

    # Test with existing WHERE
    sql_with_where = "SELECT * FROM expense WHERE amount > 100"
    injected_with_where = inject_user_id_filter(sql_with_where, user_id)
    assert "AND" in injected_with_where
    print(f"  ✓ Injected with WHERE: {injected_with_where}")

    print("\n✅ SQL Validator test PASSED")


def test_qdrant_collections():
    """Test Qdrant collection setup."""
    print("\n" + "=" * 60)
    print("TEST: Qdrant Collections")
    print("=" * 60)

    try:
        from app.vanna.collections import (
            setup_collections,
            verify_collections,
            get_qdrant_client,
        )

        # Test connection
        print("\n1. Testing Qdrant connection...")
        client = get_qdrant_client()
        collections = client.get_collections()
        print(f"  ✓ Connected to Qdrant (existing collections: {len(collections.collections)})")

        # Setup collections
        print("\n2. Setting up Vanna collections...")
        results = setup_collections(recreate=False)

        for name, created in results.items():
            status = "created" if created else "already exists"
            print(f"  ✓ Collection '{name}': {status}")

        # Verify collections
        print("\n3. Verifying collections...")
        status = verify_collections()

        for name, info in status.items():
            print(f"  ✓ {name}:")
            print(f"      exists: {info['exists']}")
            print(f"      points: {info['point_count']}")
            print(f"      vector_size: {info['vector_size']}")

        print("\n✅ Qdrant Collections test PASSED")

    except Exception as e:
        print(f"\n❌ Qdrant Collections test FAILED: {e}")
        print("   Make sure Qdrant is running: docker-compose up -d qdrant")
        raise


def test_nl_sql_instance():
    """Test NL-to-SQL instance creation."""
    print("\n" + "=" * 60)
    print("TEST: NL-to-SQL Instance")
    print("=" * 60)

    try:
        from app.vanna import get_nl_sql_instance, FinanzasNLToSQL
        from app.config import settings

        # Check OpenAI key
        if not settings.openai_api_key:
            print("  ⚠ OpenAI API key not configured, skipping embedding tests")
            print("\n⏭ NL-to-SQL Instance test SKIPPED")
            return

        print("\n1. Creating NL-to-SQL instance...")
        nl_sql = get_nl_sql_instance()
        print(f"  ✓ Instance created: {type(nl_sql).__name__}")

        # Test embedding generation
        print("\n2. Testing embedding generation...")
        embedding = nl_sql.generate_embedding("¿Cuánto gasté este mes?")
        print(f"  ✓ Embedding generated: {len(embedding)} dimensions")
        assert len(embedding) == 1536, "Expected 1536 dimensions"

        # Test adding DDL
        print("\n3. Testing add_ddl...")
        ddl = """
        CREATE TABLE expense (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            amount_original DECIMAL(12, 2) NOT NULL,
            currency_original VARCHAR(3) NOT NULL,
            occurred_at TIMESTAMP NOT NULL
        );
        """
        doc_id = nl_sql.add_ddl(ddl, table_name="expense")
        print(f"  ✓ DDL added: {doc_id}")

        # Test adding documentation
        print("\n4. Testing add_documentation...")
        doc = """
        La tabla expense almacena todos los gastos del usuario.
        Cada gasto tiene un monto original (amount_original) y su moneda (currency_original).
        El campo occurred_at indica cuando ocurrió el gasto.
        """
        doc_id = nl_sql.add_documentation(doc, table_name="expense")
        print(f"  ✓ Documentation added: {doc_id}")

        # Test adding SQL example
        print("\n5. Testing add_sql_example...")
        question = "¿Cuánto gasté este mes?"
        sql = """
        SELECT SUM(amount_original) as total, currency_original
        FROM expense
        WHERE user_id = :user_id
          AND occurred_at >= date_trunc('month', CURRENT_DATE)
        GROUP BY currency_original
        """
        doc_id = nl_sql.add_sql_example(question, sql, table_name="expense")
        print(f"  ✓ SQL example added: {doc_id}")

        # Test similar questions
        print("\n6. Testing get_similar_questions...")
        similar = nl_sql.get_similar_questions("¿Cuánto he gastado?")
        print(f"  ✓ Found {len(similar)} similar questions")
        if similar:
            print(f"    Top match: {similar[0]['question'][:50]}... (score: {similar[0]['score']:.2f})")

        print("\n✅ NL-to-SQL Instance test PASSED")

    except Exception as e:
        print(f"\n❌ NL-to-SQL Instance test FAILED: {e}")
        raise


def test_invalid_sql_rejection():
    """Test that invalid SQL is rejected when adding examples."""
    print("\n" + "=" * 60)
    print("TEST: Invalid SQL Rejection")
    print("=" * 60)

    from app.vanna.security import SQLValidationError
    from app.vanna import get_nl_sql_instance
    from app.config import settings

    if not settings.openai_api_key:
        print("  ⚠ OpenAI API key not configured, skipping")
        print("\n⏭ Invalid SQL Rejection test SKIPPED")
        return

    nl_sql = get_nl_sql_instance()

    # Try to add invalid SQL
    invalid_examples = [
        ("DELETE query", "DELETE FROM expense WHERE id = 1"),
        ("UPDATE query", "UPDATE expense SET amount = 0 WHERE id = 1"),
        ("DROP query", "DROP TABLE expense"),
    ]

    for name, sql in invalid_examples:
        try:
            nl_sql.add_sql_example("Test question", sql)
            print(f"  ❌ {name} should have been rejected!")
            raise AssertionError(f"{name} was not rejected")
        except SQLValidationError as e:
            print(f"  ✓ {name} correctly rejected: {e.violations[0]}")

    print("\n✅ Invalid SQL Rejection test PASSED")


def run_all_tests():
    """Run all foundation tests."""
    print("\n" + "=" * 60)
    print("VANNA AI FOUNDATION TESTS (Phase 2A)")
    print("=" * 60)

    tests = [
        ("Vanna Configuration", test_vanna_config),
        ("SQL Validator", test_sql_validator),
        ("Qdrant Collections", test_qdrant_collections),
        ("NL-to-SQL Instance", test_nl_sql_instance),
        ("Invalid SQL Rejection", test_invalid_sql_rejection),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            if "SKIPPED" in str(e):
                skipped += 1
            else:
                failed += 1
                print(f"\n❌ Test '{name}' failed with error: {e}")

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()

