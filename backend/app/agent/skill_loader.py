"""
Skill loader.

Reads SKILL.md files from the agent/skills directory at runtime.
This is what wires the .md files into the Python skill system.

Flow:
  1. SkillLoader.load("outfit-pairing")
  2. Opens app/agent/skills/outfit-pairing/SKILL.md
  3. Returns the content as a string
  4. The skill's build_prompt_addon() injects it into the LLM prompt

Skills are loaded on first use and cached in memory.
Changes to SKILL.md files take effect on next process restart.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from app.core.logging import get_logger

logger = get_logger(__name__)

# Root of the agent directory
_AGENT_ROOT = Path(__file__).parent


@lru_cache(maxsize=None)
def _read_file(path: str) -> str:
    """Read a file from disk; result is cached by absolute path."""
    return Path(path).read_text(encoding="utf-8")


class SkillLoader:
    """
    Loads skill, agent, and command markdown files from disk.

    All content is cached after first load — no repeated file IO.
    """

    def __init__(self, agent_root: Path = _AGENT_ROOT):
        self._root    = agent_root
        self._cache:  dict[str, str] = {}

    def load_skill(self, skill_name: str) -> str:
        """
        Load a skill's SKILL.md content.

        Args:
            skill_name: Directory name under agent/skills/
                        e.g. "outfit-pairing", "tdd-workflow"

        Returns:
            Content of the SKILL.md file.

        Raises:
            FileNotFoundError: if the skill directory or SKILL.md doesn't exist.
        """
        cache_key = f"skill:{skill_name}"
        if cache_key not in self._cache:
            path = self._root / "skills" / skill_name / "SKILL.md"
            self._cache[cache_key] = self._read(path, f"skill/{skill_name}")
        return self._cache[cache_key]

    def load_agent(self, agent_name: str) -> str:
        """
        Load an agent definition.

        Args:
            agent_name: Filename without extension under agent/agents/
                        e.g. "stylist-agent", "tdd-guide"
        """
        cache_key = f"agent:{agent_name}"
        if cache_key not in self._cache:
            path = self._root / "agents" / f"{agent_name}.md"
            self._cache[cache_key] = self._read(path, f"agent/{agent_name}")
        return self._cache[cache_key]

    def load_command(self, command_name: str) -> str:
        """
        Load a command definition.

        Args:
            command_name: Filename without extension under agent/commands/
                          e.g. "style", "gift", "tdd"
        """
        cache_key = f"command:{command_name}"
        if cache_key not in self._cache:
            path = self._root / "commands" / f"{command_name}.md"
            self._cache[cache_key] = self._read(path, f"command/{command_name}")
        return self._cache[cache_key]

    def load_skill_for_prompt(self, skill_name: str) -> str:
        """
        Load a skill and format it for injection into an LLM prompt.
        Wraps the content in a clear section marker.
        """
        content = self.load_skill(skill_name)
        return f"\n--- SKILL: {skill_name} ---\n{content}\n--- END SKILL ---\n"

    def list_skills(self) -> list[str]:
        """Return names of all available skills."""
        skills_dir = self._root / "skills"
        if not skills_dir.exists():
            return []
        return [
            d.name
            for d in skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]

    def list_agents(self) -> list[str]:
        """Return names of all available agents."""
        agents_dir = self._root / "agents"
        if not agents_dir.exists():
            return []
        return [f.stem for f in agents_dir.glob("*.md")]

    def list_commands(self) -> list[str]:
        """Return names of all available commands."""
        commands_dir = self._root / "commands"
        if not commands_dir.exists():
            return []
        return [f.stem for f in commands_dir.glob("*.md")]

    def clear_cache(self) -> None:
        """Force reload of all files on next access. Useful in development."""
        self._cache.clear()
        _read_file.cache_clear()
        logger.info("skill_loader.cache_cleared")

    def _read(self, path: Path, label: str) -> str:
        if not path.exists():
            raise FileNotFoundError(
                f"Skill file not found: {path}. "
                f"Create {path} to define the '{label}' skill."
            )
        content = _read_file(str(path.resolve()))
        logger.debug("skill_loader.loaded", path=str(path), size=len(content))
        return content


# Module-level singleton — shared across the application
skill_loader = SkillLoader()
