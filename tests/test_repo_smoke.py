import importlib

import pytest


MODULES = [
    "src.main",
    "src.api.auth",
    "src.core.database",
    "src.core.redis",
    "src.models.user",
    "src.schemas.auth_schemas",
    "src.services.auth_service",
    "src.services.totp_service",
    "src.temporal.activities",
    "src.temporal.client",
    "src.temporal.worker",
    "src.temporal.workflows",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_source_modules_import(module_name):
    importlib.import_module(module_name)