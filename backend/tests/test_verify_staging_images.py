import pytest

from scripts.validate_staging_manifest import StagingManifestError
from scripts.verify_staging_images import validate_image_inspection

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_REFERENCE = (
    "registry.internal/rotas/backend@sha256:"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)


def _inspection(
    *,
    reference: str = IMAGE_REFERENCE,
    user: str = "10001:10001",
    revision: str = RELEASE_SHA,
    version: str = "2026.07-rc1",
):
    return {
        "RepoDigests": [reference],
        "Config": {
            "User": user,
            "Labels": {
                "org.opencontainers.image.revision": revision,
                "org.opencontainers.image.version": version,
            },
        },
    }


def test_image_inspection_accepts_exact_digest_revision_and_non_root_user():
    result = validate_image_inspection(
        "ROTAS_BACKEND_IMAGE",
        IMAGE_REFERENCE,
        RELEASE_SHA,
        _inspection(),
    )

    assert result == {
        "reference": IMAGE_REFERENCE,
        "user": "10001:10001",
        "revision": RELEASE_SHA,
        "version": "2026.07-rc1",
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"reference": "registry.invalid/other@sha256:" + "b" * 64}, "RepoDigest"),
        ({"user": "root"}, "runtime user"),
        ({"revision": "f" * 40}, "OCI revision"),
        ({"version": "dev"}, "non-development release"),
    ],
)
def test_image_inspection_rejects_metadata_drift(overrides, message):
    with pytest.raises(StagingManifestError, match=message):
        validate_image_inspection(
            "ROTAS_BACKEND_IMAGE",
            IMAGE_REFERENCE,
            RELEASE_SHA,
            _inspection(**overrides),
        )
