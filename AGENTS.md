# Agent instructions

## Formatting

- Every file must be formatted with the IDE auto-formatter. Always let auto-format run when editing; never switch it off
  to keep a diff small.
- If the formatter's rules have changed and re-formatting touches code you did not otherwise change, commit that
  formatting in its own `style:` commit, separate from functional changes.

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org) (`feat:`, `fix:`, `docs:`, `ci:`, `style:`, ...). The
  release version is derived from them, see "Releases and versioning" in the README.
- Commits made by an agent must use a clearly non-human author, "AgentBridge Bot (AI-generated)", and say in the message
  that the code is AI-generated.
- Never commit credentials, keys or temporary manifest URLs.
