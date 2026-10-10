import os
import stat

import pytest

from server.core.security import protect_path


def test_private_secret_storage_still_accessible_to_owner(tmp_path):
    private = tmp_path / "sessions"
    private.mkdir()
    protect_path(private)
    secret = private / "test.json"
    secret.write_text("test-secret")
    protect_path(secret)
    assert secret.read_text() == "test-secret"
    if os.name != "nt":
        assert stat.S_IMODE(secret.stat().st_mode) == 0o600
        assert stat.S_IMODE(private.stat().st_mode) == 0o700
    else:
        import win32security

        descriptor = win32security.GetFileSecurity(
            str(secret), win32security.DACL_SECURITY_INFORMATION
        )
        dacl = descriptor.GetSecurityDescriptorDacl()
        sids = {
            win32security.ConvertSidToStringSid(dacl.GetAce(i)[2])
            for i in range(dacl.GetAceCount())
        }
        assert sids == {"S-1-3-4", "S-1-5-18"}  # Owner Rights and SYSTEM only.
        assert descriptor.GetSecurityDescriptorControl()[0] & 0x1000  # Protected DACL.


def test_secret_path_links_are_rejected(tmp_path):
    target = tmp_path / "target"
    target.write_text("data")
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links")
    with pytest.raises(OSError, match="must not be links"):
        protect_path(link)
