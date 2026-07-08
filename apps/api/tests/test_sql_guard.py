from app.sql_guard import validate_sql


def test_allows_safe_select_and_injects_limit():
    report = validate_sql("SELECT sku FROM products", require_tenant_scope=False)
    assert report.valid
    assert report.limit_injected
    assert "LIMIT" in report.normalized_sql


def test_allows_safe_cte_with_tenant_binding():
    report = validate_sql("WITH scoped AS (SELECT sku FROM products WHERE organization_id = :organization_id) SELECT * FROM scoped LIMIT 10", require_tenant_scope=True)
    assert report.valid, report.reasons


def test_blocks_mutation_multistatement_and_hidden_ddl():
    assert not validate_sql("UPDATE products SET name = 'x'", require_tenant_scope=False).valid
    assert not validate_sql("SELECT * FROM products; DROP TABLE products", require_tenant_scope=False).valid
    assert not validate_sql("WITH x AS (DELETE FROM products RETURNING id) SELECT * FROM x", require_tenant_scope=False).valid


def test_blocks_dangerous_function_and_unapproved_table():
    assert not validate_sql("SELECT pg_read_file('/etc/passwd')", require_tenant_scope=False).valid
    assert not validate_sql("SELECT * FROM users LIMIT 10", require_tenant_scope=False).valid


def test_blocks_cross_tenant_template_without_bind_parameter_and_large_limit():
    assert not validate_sql("SELECT * FROM products LIMIT 10", require_tenant_scope=True).valid
    assert not validate_sql("SELECT * FROM products WHERE organization_id = :organization_id LIMIT 900", require_tenant_scope=True).valid
