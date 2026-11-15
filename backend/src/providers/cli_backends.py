"""
Vendor CLI backends: Claude Code, Codex CLI, Gemini CLI.

Assay runs the official binary in headless mode with the user's own login.
It never reads or copies their token files. These are off unless the user
sets ASSAY_ENABLE_<ID>=1 (or enables them in the Models screen), and they are
for personal use only: subscription logins are not for shared servers or
bulk indexing. Prompts go in on stdin so long contexts don't hit argv limits.

Model strings: "claude_code/<model>", "codex_cli/<model>", "gemini_cli/<model>".
The part after the slash is optional ("claude_code/" uses the CLI default).
"""

from __future__ import annotations

import asyncio
import os
import shutil

TIMEOUT = float(os.getenv("ASSAY_CLI_TIMEOUT", "300"))

_COMMANDS = {
    "claude_code": lambda m: ["claude", "-p", "--output-format", "text"] + (["--model", m] if m else []),
    "codex_cli": lambda m: ["codex", "exec", "--skip-git-repo-check"] + (["-m", m] if m else []) + ["-"],
    "gemini_cli": lambda m: ["gemini", "-p", ""] + (["-m", m] if m else []),
}


def handles(model: str) -> bool:
    return model.split("/", 1)[0] in _COMMANDS


def _flatten(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m["role"]
        tag = {"system": "Instructions", "user": "User", "assistant": "Assistant"}.get(role, role)
        parts.append(f"## {tag}\n{m['content']}")
    return "\n\n".join(parts)


async def complete(model: str, messages: list[dict]) -> str:
    backend, _, name = model.partition("/")
    if os.getenv(f"ASSAY_ENABLE_{backend.upper()}", "0") != "1":
        raise PermissionError(f"{backend} is installed but not enabled. Set ASSAY_ENABLE_{backend.upper()}=1.")
    cmd = _COMMANDS[backend](name or None)
    exe = shutil.which(cmd[0])
    if not exe:
        raise FileNotFoundError(f"'{cmd[0]}' is not on PATH")
    proc = await asyncio.create_subprocess_exec(
        exe, *cmd[1:], stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(_flatten(messages).encode()), TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError(f"{backend} timed out after {TIMEOUT:.0f}s")
    if proc.returncode != 0:
        raise RuntimeError(f"{backend} exited {proc.returncode}: {err.decode(errors='ignore')[:400]}")
    return out.decode(errors="ignore").strip()
