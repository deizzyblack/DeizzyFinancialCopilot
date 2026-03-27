# Global Claude Config

## Permissions
- Read: * (all files)
- Bash: git:* (all git operations)
- Deny: Read:env:, Bash:sudo:

## Workflow
1. Always read before edit
2. Commit CLAUDE.md and .claude/ with every structural change
3. Keep CLAUDE.md files under 200 lines
4. Lower-level CLAUDE.md adds context, never overrides parent

## Skills Location
`.claude/skills/<skill_name>/SKILL.md`

## Hooks Location
`.claude/hooks/`
