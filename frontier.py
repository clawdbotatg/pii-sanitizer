"""The frontier call. Picked by FRONTIER=<backend>:<model>:

  ollama:glm-5.3-flash:cloud           any ollama model (":cloud" ones run remotely)
  claude:sonnet                        the claude CLI on your subscription; needs
                                       CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`)
  anthropic:claude-sonnet-5-5          needs ANTHROPIC_API_KEY
  openai:<model>                       any OpenAI-compatible API (NEAR AI, OpenRouter, ...):
                                       needs OPENAI_API_KEY, optional OPENAI_BASE_URL

Unset = mocked reply (no network).
"""
import json, os, re, subprocess, urllib.request

SYSTEM = ("Text in square brackets like [PERSON_1] or [DATE_2] stands for a removed private "
          "detail. Copy every such placeholder exactly as written, brackets and all, whenever "
          "you refer to it. Never invent new placeholders and never guess what they stand for.")


def _post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    return json.load(urllib.request.urlopen(req, timeout=300))


def ask(prompt):
    spec = os.environ.get("FRONTIER", "")
    if not spec:
        phs = re.findall(r"\[[A-Z]+_\d+\]", prompt)
        return f"Summary for {phs[0]}: plan reviewed." if phs else "Plan reviewed."
    backend, model = spec.split(":", 1)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    if backend == "ollama":
        r = _post("http://127.0.0.1:11434/api/chat", {"model": model, "stream": False, "think": True,  # keeps reasoning out of content
                                                       "messages": msgs}, {})
        return r["message"]["content"]
    if backend == "claude":
        # Clean env: a parent Claude Code session's variables make the child misbehave.
        env = {k: os.environ[k] for k in ("HOME", "PATH", "CLAUDE_CODE_OAUTH_TOKEN") if k in os.environ}
        r = subprocess.run(["claude", "-p", prompt, "--model", model, "--system-prompt", SYSTEM,
                            "--tools", ""], capture_output=True, text=True, env=env, timeout=300)
        if r.returncode:
            raise RuntimeError(r.stderr or r.stdout)
        return r.stdout.strip()
    if backend == "anthropic":
        r = _post("https://api.anthropic.com/v1/messages",
                  {"model": model, "max_tokens": 1024, "system": SYSTEM, "messages": msgs[1:]},
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r["content"])
    if backend == "openai":
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        r = _post(base + "/chat/completions", {"model": model, "messages": msgs},
                  {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
        return r["choices"][0]["message"]["content"]
    raise ValueError(f"unknown FRONTIER backend {backend!r}")


def mangled(sent, reply):
    """Placeholders we sent that came back in a broken form ("Person 1", "[PERSON 1]")."""
    out = []
    for ph in set(re.findall(r"\[([A-Z]+)_(\d+)\]", sent)):
        exact = f"[{ph[0]}_{ph[1]}]"
        loose = re.compile(r"\[?\s*%s[\s_]*%s\s*\]?" % (ph[0], ph[1]), re.I)
        if exact not in reply and loose.search(reply):
            out.append(exact)
    return out
