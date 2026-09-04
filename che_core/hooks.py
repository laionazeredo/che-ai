import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from che_core.paths import get_che_home, get_workspaces_root
from che_core.registry import get_registry_path, registry_lookup_last


def _extract_paths(tool_args: Dict[str, Any]) -> List[str]:
    paths = []

    fp = tool_args.get("file_path")
    if fp and isinstance(fp, str):
        paths.append(fp)

    td = tool_args.get("target_directories")
    if isinstance(td, list):
        paths.extend([p for p in td if isinstance(p, str)])

    p = tool_args.get("path")
    if p and isinstance(p, str):
        paths.append(p)

    fps = tool_args.get("file_paths")
    if isinstance(fps, list):
        paths.extend([p for p in fps if isinstance(p, str)])

    cwd = tool_args.get("cwd")
    if cwd and isinstance(cwd, str):
        paths.append(cwd)

    ignores = tool_args.get("ignore")
    if isinstance(ignores, list):
        paths.extend([p for p in ignores if isinstance(p, str)])

    return paths


def _git_worktree_root(candidate: str) -> str:
    probe = Path(candidate).resolve()
    if probe.is_file():
        probe = probe.parent

    while not probe.is_dir():
        parent = probe.parent
        if parent == probe:
            return ""
        probe = parent

    try:
        res = subprocess.run(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def pretooluse_worktree_binding(input_json: Dict[str, Any]) -> Dict[str, Any]:
    session_id = input_json.get("sessionId") or input_json.get("session_id", "")
    tool_name = input_json.get("toolName") or input_json.get("tool_name", "")
    tool_args = input_json.get("toolArgs") or input_json.get("tool_input", {})

    guarded_tools = {"Read", "Glob", "Grep", "Edit", "Write", "RunCommand", "DeleteFile", "LS", "SearchCodebase", "Bash", "exec_command", "apply_patch"}
    if tool_name not in guarded_tools:
        return {"decision": "allow", "reason": "Tool not in guarded list"}

    workspaces_root = str(get_workspaces_root())
    candidate_paths = _extract_paths(tool_args)

    for p in candidate_paths:
        if str(p).startswith(workspaces_root):
            return {
                "decision": "allow",
                "reason": "§19 EXCEÇÃO CHE_SESSIONS_ROOT: path alvo é pasta de dados gerados/efêmeros che.",
            }

    bound_root = ""
    if session_id:
        entry = registry_lookup_last(session_id)
        if entry and entry.get("status") == "BOUND":
            bound_root = entry.get("worktree_root", "")

    if not bound_root:
        return {"decision": "allow", "reason": "§19: Nenhuma entrada BOUND para SESSION_ID no Level 1 registry.jsonl"}

    bound_normalized = _git_worktree_root(bound_root)
    if not bound_normalized:
        bound_normalized = str(Path(bound_root).resolve())

    violations = set()
    project_paths = 0
    session_paths = 0

    for p in candidate_paths:
        if p == workspaces_root or p.startswith(workspaces_root + "/"):
            session_paths += 1
            continue

        proj_root = _git_worktree_root(p)
        if not proj_root:
            continue

        project_paths += 1
        if proj_root != bound_normalized:
            violations.add(proj_root)

    if violations:
        uniq = ",".join(sorted(violations))
        registry_file = get_registry_path()
        reason = f"§19 WORKTREE SESSION BINDING VIOLATION (Level 1 Registry). sessionId={session_id} is BOUND in Level 1 registry ({registry_file}) to WORKTREE_ROOT={bound_normalized}. Tool={tool_name} tentou acessar paths FORA worktree vinculada: {uniq}. Action: (1) cancelar; (2) AskUserQuestion re-bind explícito."
        return {"decision": "block", "reason": reason}

    return {
        "decision": "allow",
        "reason": f"§19 OK Level 1 Registry: all detected project paths match BOUND_WORKTREE_ROOT={bound_normalized}",
    }


def posttooluse_lang_pt_check(input_json: Dict[str, Any]) -> Dict[str, Any]:
    session_id = input_json.get("sessionId") or input_json.get("session_id", "")
    tool_name = input_json.get("toolName") or input_json.get("tool_name", "")
    tool_args = input_json.get("toolArgs") or input_json.get("tool_input", {})

    if tool_name not in {"Edit", "Write", "apply_patch"}:
        return {"decision": "allow", "reason": "Hook3 lang-pt: tool not Edit/Write, skip."}

    file_path = tool_args.get("file_path", "")
    if not file_path:
        return {"decision": "allow", "reason": "Hook3 lang-pt: no file_path in toolArgs, skip."}

    lang_docs = "en"
    if session_id:
        entry = registry_lookup_last(session_id)
        if entry:
            flags = entry.get("flags", {})
            ld = flags.get("LANG_DOCS")
            if not ld:
                pt_check = flags.get("LANG_PT_CHECK", "ENABLED")
                ld = "pt-BR" if pt_check == "DISABLED" else "en"
            lang_docs = ld

    if lang_docs != "en":
        return {
            "decision": "allow",
            "reason": f"Hook3 lang-pt: SKIP per session LANG_DOCS={lang_docs} (≠en). sessionId={session_id}.",
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {"decision": "allow", "reason": "Hook3 lang-pt: target file not readable post-write, skip."}

    pt_stopwords = [
        "não",
        "sim",
        "que",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "para",
        "com",
        "sem",
        "por",
        "per",
        "este",
        "esta",
        "estes",
        "estas",
        "esse",
        "essa",
        "esses",
        "essas",
        "nós",
        "você",
        "vocês",
        "tem",
        "têm",
        "são",
        "foi",
        "fui",
        "ser",
        "estar",
        "estou",
        "é",
        "e",
        "ou",
        "mas",
        "porém",
        "todavia",
        "contudo",
        "portanto",
        "logo",
        "já",
        "até",
        "mais",
        "menos",
        "muito",
        "pouco",
        "hoje",
        "ontem",
        "amanhã",
        "trabalho",
        "trabalhar",
        "projeto",
        "ticket",
        "tarefa",
        "sessão",
        "usuário",
        "arquivo",
        "código",
        "erro",
        "sucesso",
        "falha",
        "mudança",
        "alteração",
        "implementação",
        "verificação",
        "validação",
        "execução",
        "criar",
        "criado",
        "remover",
        "removido",
        "adicionar",
        "adicionado",
        "atualizar",
        "atualizado",
        "corrigir",
        "corrigido",
        "testar",
        "testado",
        "aprovar",
        "aprovado",
        "rejeitar",
        "rejeitado",
        "problema",
        "solução",
        "resultado",
        "esperado",
        "obtido",
        "função",
        "método",
        "classe",
        "variável",
        "parâmetro",
        "retorno",
        "entrada",
        "saída",
    ]

    words = re.findall(r"\b\w+\b", content.lower())
    pt_hits = sum(1 for w in words if w in pt_stopwords)

    lines = content.split("\n")
    diacritic_lines = sum(1 for line in lines if re.search(r"[çãõÇÃÕáàâéêíóôúÁÀÂÉÊÍÓÔÚ]", line))

    if pt_hits >= 4 or (diacritic_lines >= 2 and pt_hits >= 2):
        sample_lines = []
        for i, line in enumerate(lines):
            if re.search(r"[çãõÇÃÕáàâéêíóôúÁÀÂÉÊÍÓÔÚ]", line) or any(w in line.lower() for w in pt_stopwords):
                sample_lines.append(f"  L{i + 1}: {line.strip()}")
                if len(sample_lines) >= 3:
                    break

        reason = f"PT-BR text detected in written file (stopword_hits={pt_hits}, diacritic_lines={diacritic_lines}). Signal only — NO auto-correction performed."
        addl = f"""ACTION REQUIRED by AGENT: AskUserQuestion to user BEFORE PROCEEDING further: Texto em português detectado no arquivo {file_path}.
Current project LANG_DOCS=en (padrão). O que deseja fazer?
(A) Traduzir conteúdo detectado para inglês (recomendado p/ manter LANG_DOCS=en)
(B) Manter em português — NESTE ARQUIVO ESPECÍFICO (justificar, e se for padrão novo aplicar em (C))
(C) CONFIGURAR ESTE PROJETO/SESSÃO com LANG_DOCS=pt-BR. Adiciona via helper `che_registry_append_jsonl` com {{"flags":{{"LANG_DOCS":"pt-BR"}}}} Level 1 registry.jsonl.
Sample lines: {"; ".join(sample_lines)}
File analyzed: {file_path}"""
        return {"decision": "warn", "reason": reason, "additionalContext": addl}

    return {
        "decision": "allow",
        "reason": f"Hook3 lang-pt: OK no PT-BR content detected in {file_path} (stopword_hits={pt_hits} diacritic_lines={diacritic_lines})",
    }


def posttooluse_3layer_dedup(input_json: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = input_json.get("toolName") or input_json.get("tool_name", "")
    tool_args = input_json.get("toolArgs") or input_json.get("tool_input", {})

    if tool_name not in {"Edit", "Write", "apply_patch"}:
        return {"decision": "allow"}

    file_path = tool_args.get("file_path", "")
    if not file_path:
        return {"decision": "allow"}

    che_home = get_che_home()
    skills_dir = che_home / "skills"

    filename = Path(file_path).name
    dirname = Path(file_path).parent

    is_layer1 = dirname.name == "user_rules" and filename.endswith(".md")
    is_layer2 = filename in {"CHE_RULES.md", "CHE_COMMANDS.md"} and dirname == che_home

    if not (is_layer1 or is_layer2):
        return {"decision": "allow"}

    new_content = ""
    if Path(file_path).is_file():
        with open(file_path, "r", encoding="utf-8") as f:
            new_content = f.read()
    else:
        new_content = tool_args.get("content", "")

    if not new_content:
        return {"decision": "allow"}

    filtered_lines = []
    for line in new_content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s", line):
            continue
        if re.match(r"^[-|]{3,}$", line):
            continue
        if "file:///" in line:
            continue
        if re.match(r"^\|\s*---", line):
            continue
        filtered_lines.append(line)

    if not filtered_lines:
        return {"decision": "allow"}

    # Check duplicates in SKILL.md files
    dup_hits = []
    for skill_file in skills_dir.rglob("SKILL.md"):
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                skill_content = f.read()
                for line in filtered_lines:
                    if line in skill_content:
                        dup_hits.append(f"{skill_file}: {line}")
        except Exception:
            pass

    if len(dup_hits) < 4:
        return {"decision": "allow"}

    top_hits = dup_hits[:6]
    camada = f"Layer 1 (user_rules/{filename})" if is_layer1 else f"Layer 2 ({filename})"

    layer_desc = f"{camada} contém conteúdo que já existe em Layer 3 skills/*/SKILL.md."
    action_needed = f"Arquitetura 3 camadas HARD STOP: Layer 3 é DONO do corpo de regra. Mova o corpo duplicado para a skill; deixe em {camada} APENAS título + link para SKILL.md. Duplicates >=4 linhas detectadas: {len(dup_hits)} linhas idênticas já presentes em skills/"
    warning_msg = f"{layer_desc} | {action_needed} | Top hits: {top_hits}"

    return {"decision": "allow", "additionalContext": warning_msg}
