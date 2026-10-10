# Security reporting

Please report suspected vulnerabilities through this repository's GitHub private
vulnerability reporting feature when enabled. Do not include live session tokens,
credentials or private project data in public issues. If private reporting is not
available, open an issue requesting a private contact without disclosing exploit
details or secrets.

ForgeMCP is development software, not a security sandbox. Endpoints authenticate
local clients, but an authorized client can make the supported application changes.
Use explicit sessions, review previews, keep backups and save existing work before
updating loaded adapters. Administrators or software running as the same operating
system user can access local application state.

See [the security boundaries](Documentation/Security.md) for protocol limits,
credential storage, native execution and recovery behavior. No production support
window or external security audit is currently claimed.
