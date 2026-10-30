from backend.app.db import postgres_connect_args


def test_neon_pooler_omits_unsupported_startup_options() -> None:
    args = postgres_connect_args(
        "postgresql+psycopg://user:pass@ep-example-pooler.region.aws.neon.tech/app"
    )

    assert args == {"connect_timeout": 5}


def test_direct_postgres_keeps_statement_timeout() -> None:
    args = postgres_connect_args("postgresql+psycopg://user:pass@db.example.com/app")

    assert args == {
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000",
    }
