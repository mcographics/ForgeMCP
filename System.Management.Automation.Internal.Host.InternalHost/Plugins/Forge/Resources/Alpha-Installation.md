# ForgeMCP alpha for Unreal Engine 5.6

Target: UE 5.6.1, Win64 Development Editor. This is an actively developed alpha.
The binary engine BuildId must match `package-manifest.json`. Other platforms,
engine builds and packaged game targets require separate builds and acceptance.

Close the target editor before replacing a plugin. For engine-wide availability,
place the `MajesticForge` folder inside `<EngineRoot>/Engine/Plugins/Marketplace`.
Keep the folder and module names. Enable **ForgeMCP** in **Edit > Plugins** for the
chosen project, restart it, then open **Window > ForgeMCP**. The alpha is disabled
by default. Existing project-local copies can take precedence over the engine
copy; back them up outside plugin search directories before migrating.

The engine-wide installer in the ForgeMCP source checkout validates the archive
and exact engine BuildId and supports backed-up updates. Prefer it over manual
copying. Preserve the previous installation outside plugin search directories for
rollback. Save work and close editors before updating or restoring a backup.

The external ForgeMCP Python MCP server is installed separately. Configure it to
launch the checkout's Python environment with `-m server.main` and set
`FORGE_UNREAL_SESSION_DIR` to the target project's `Saved/MajesticForge` folder.
Discover sessions and inspect the intended project's identity before edits.
Never distribute session registration files; they contain credentials.

The source checkout's `Documentation/UE56_Alpha.md` records full setup, update,
rollback, acceptance and feature limits. This package retains the existing
license notice. Installation does not establish all-feature or visual acceptance.
