import os
import unittest
from unittest.mock import patch

from scripts.test_database_guard import (
    TestDatabaseConfigurationError,
    activate_test_database,
    validate_test_database_url,
)

VALID_TEST_URL = "postgresql+asyncpg://test-user:test-password@localhost:55432/rotas_test_unit"


class ValidateTestDatabaseUrlTests(unittest.TestCase):
    def test_rejects_missing_test_database_url(self) -> None:
        with self.assertRaisesRegex(TestDatabaseConfigurationError, "TEST_DATABASE_URL is required"):
            validate_test_database_url({})

    def test_rejects_operational_database_name(self) -> None:
        environment = {
            "TEST_DATABASE_URL": "postgresql+asyncpg://user:secret@localhost:55432/rotas",
        }

        with self.assertRaisesRegex(TestDatabaseConfigurationError, "rotas_test_"):
            validate_test_database_url(environment)

    def test_rejects_host_outside_default_allowlist(self) -> None:
        environment = {
            "TEST_DATABASE_URL": (
                "postgresql+asyncpg://user:secret@database.example.com:5432/rotas_test_unit"
            ),
        }

        with self.assertRaisesRegex(TestDatabaseConfigurationError, "allowlist"):
            validate_test_database_url(environment)

    def test_rejects_same_physical_database_with_different_credentials(self) -> None:
        environment = {
            "TEST_DATABASE_URL": VALID_TEST_URL,
            "DATABASE_URL": (
                "postgresql+asyncpg://another-user:another-password@localhost:55432/rotas_test_unit"
            ),
        }

        with self.assertRaisesRegex(TestDatabaseConfigurationError, "operational database target"):
            validate_test_database_url(environment)

    def test_accepts_explicitly_allowlisted_test_host(self) -> None:
        environment = {
            "TEST_DATABASE_URL": (
                "postgresql+asyncpg://user:secret@test-postgres:5432/rotas_test_worker_1"
            ),
            "TEST_DATABASE_ALLOWED_HOSTS": "test-postgres",
        }

        self.assertEqual(validate_test_database_url(environment), environment["TEST_DATABASE_URL"])

    def test_activate_rebinds_every_database_role_before_application_imports(self) -> None:
        environment = {
            "TEST_DATABASE_URL": VALID_TEST_URL,
            "DATABASE_URL": "postgresql+asyncpg://user:secret@localhost:55432/rotas",
            "ADMIN_DATABASE_URL": "postgresql+asyncpg://admin:secret@localhost:55432/rotas",
            "ALEMBIC_DATABASE_URL": "postgresql+asyncpg://admin:secret@localhost:55432/rotas",
        }

        activated = activate_test_database(environment)

        self.assertEqual(activated, VALID_TEST_URL)
        self.assertEqual(environment["DATABASE_URL"], VALID_TEST_URL)
        self.assertEqual(environment["ADMIN_DATABASE_URL"], VALID_TEST_URL)
        self.assertEqual(environment["ALEMBIC_DATABASE_URL"], VALID_TEST_URL)

    def test_errors_never_disclose_database_password(self) -> None:
        secret = "do-not-disclose-this-password"
        environment = {
            "TEST_DATABASE_URL": (
                f"postgresql+asyncpg://user:{secret}@remote.example:5432/rotas_test_unit"
            ),
        }

        with self.assertRaises(TestDatabaseConfigurationError) as captured:
            validate_test_database_url(environment)

        self.assertNotIn(secret, str(captured.exception))

    def test_activate_can_safely_update_the_process_environment(self) -> None:
        with patch.dict(os.environ, {"TEST_DATABASE_URL": VALID_TEST_URL}, clear=True):
            activate_test_database(os.environ)

            self.assertEqual(os.environ["DATABASE_URL"], VALID_TEST_URL)


if __name__ == "__main__":
    unittest.main()
