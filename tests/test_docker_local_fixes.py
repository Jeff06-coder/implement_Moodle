# =============================================================================
# Feature: docker-local-fixes
# Property 1: Bug Condition — Quatro Defeitos de Configuração
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
#
# Estes testes codificam a CONDIÇÃO DE BUG de cada um dos quatro defeitos.
# Eles devem FALHAR no código não corrigido (isso confirma que os bugs
# existem) e PASSAR depois que as correções forem aplicadas.
#
# Bug 1 — `pgsql` ausente no docker/Dockerfile
# Bug 2 — `env_file` aponta para `.env.example` em docker/docker-compose.yml
# Bug 3 — `.kiro/` bloqueado no .gitignore
# Bug 4 — CI docker-lint.yml sem etapa `cp` antes de `docker compose config`
# =============================================================================
#
# Property 2: Preservation — Comportamentos Inalterados nos Quatro Arquivos
# Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
#
# Estes testes verificam que os comportamentos corretos pré-existentes não
# regridem após a aplicação das quatro correções.
# =============================================================================

import pathlib
import re

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Caminhos compartilhados
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DOCKERFILE_PATH = _REPO_ROOT / "docker" / "Dockerfile"
_COMPOSE_PATH = _REPO_ROOT / "docker" / "docker-compose.yml"
_GITIGNORE_PATH = _REPO_ROOT / ".gitignore"
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "docker-lint.yml"

# ---------------------------------------------------------------------------
# Helpers — carregamento de artefatos
# ---------------------------------------------------------------------------


def _load_dockerfile() -> str:
    assert _DOCKERFILE_PATH.exists(), (
        f"Dockerfile não encontrado em: {_DOCKERFILE_PATH}"
    )
    return _DOCKERFILE_PATH.read_text(encoding="utf-8")


def _load_compose_yaml() -> dict:
    assert _COMPOSE_PATH.exists(), (
        f"docker-compose.yml não encontrado em: {_COMPOSE_PATH}"
    )
    with _COMPOSE_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_gitignore_lines() -> list[str]:
    assert _GITIGNORE_PATH.exists(), (
        f".gitignore não encontrado em: {_GITIGNORE_PATH}"
    )
    return _GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()


def _load_workflow() -> str:
    assert _WORKFLOW_PATH.exists(), (
        f"docker-lint.yml não encontrado em: {_WORKFLOW_PATH}"
    )
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


# Cache dos artefatos para evitar releituras redundantes
_DOCKERFILE_CONTENT = _load_dockerfile()
_COMPOSE_DATA = _load_compose_yaml()
_GITIGNORE_LINES = _load_gitignore_lines()
_WORKFLOW_CONTENT = _load_workflow()

# ---------------------------------------------------------------------------
# Helper — coleta de extensões PHP em blocos RUN do Dockerfile
# (mesma lógica de test_dockerfile_extensions.py, reutilizável aqui)
# ---------------------------------------------------------------------------


def _collect_run_block_extensions(dockerfile: str) -> set[str]:
    r"""
    Percorre o Dockerfile linha a linha e coleta todos os tokens de extensão
    PHP listados em blocos ``RUN docker-php-ext-install`` ou ``pecl install``,
    respeitando continuações de linha (\) e ignorando comentários (#).
    """
    extensions: set[str] = set()
    lines = dockerfile.splitlines()
    n = len(lines)
    i = 0

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if stripped.startswith("#"):
            i += 1
            continue

        is_install = (
            "docker-php-ext-install" in stripped
            or "pecl install" in stripped
        )

        if is_install:
            last_noncomment_continues = raw.rstrip().endswith("\\")

            line_payload = stripped.rstrip("\\").strip()
            for cmd in ("RUN", "docker-php-ext-install", "pecl", "install", "&&"):
                line_payload = re.sub(r"\b" + cmd + r"\b", " ", line_payload)
            for token in line_payload.split():
                if token and not token.startswith("#"):
                    extensions.add(token)

            while last_noncomment_continues and i + 1 < n:
                i += 1
                raw = lines[i]
                stripped = raw.strip()

                if stripped.startswith("#"):
                    continue

                last_noncomment_continues = raw.rstrip().endswith("\\")

                token_line = stripped.rstrip("\\").strip()
                comment_pos = token_line.find("#")
                if comment_pos != -1:
                    token_line = token_line[:comment_pos].strip()

                for token in token_line.split():
                    if token and not token.startswith("#"):
                        extensions.add(token)

        i += 1

    return extensions


# ---------------------------------------------------------------------------
# Helper — extrai valores de env_file de cada serviço do compose
# ---------------------------------------------------------------------------


def _env_file_values_for_service(compose: dict, service: str) -> list[str]:
    """
    Retorna a lista de valores de ``env_file`` para ``service``.
    Normaliza cada entrada (string ou dict com chave ``path``) para string.
    """
    svc = compose.get("services", {}).get(service, {})
    raw = svc.get("env_file", [])
    if isinstance(raw, str):
        raw = [raw]
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append(item.get("path", ""))
        else:
            result.append(str(item))
    return result


# ---------------------------------------------------------------------------
# Helper — índice da primeira etapa de CI que contém um fragmento de texto
# ---------------------------------------------------------------------------


def _step_index(workflow_content: str, fragment: str) -> int:
    """
    Retorna o índice (0-based) da primeira etapa de ``jobs.<job>.steps``
    cujo campo ``run`` contém ``fragment``.  Retorna -1 se não encontrada.

    Usa parsing YAML para robustez em vez de busca textual pura.
    """
    data = yaml.safe_load(workflow_content)
    for job in data.get("jobs", {}).values():
        for idx, step in enumerate(job.get("steps", [])):
            run_text = step.get("run", "")
            if fragment in run_text:
                return idx
    return -1


# =============================================================================
# PROPERTY 1 — BUG CONDITION TESTS
# Estes testes DEVEM FALHAR no código não corrigido.
# =============================================================================

# ---------------------------------------------------------------------------
# Bug 1 — `pgsql` ausente no Dockerfile
# ---------------------------------------------------------------------------

BUG1_EXTENSIONS = ["pgsql"]


@given(extension=st.sampled_from(BUG1_EXTENSIONS))
@settings(max_examples=10)
def test_bug1_pgsql_present_in_dockerfile(extension: str) -> None:
    """
    Property 1 / Bug 1: O Dockerfile deve instalar a extensão `pgsql`
    (driver nativo PostgreSQL) além de `pdo_pgsql`.

    Validates: Requirements 1.1, 1.2
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    Contraexemplo: apenas `pdo_pgsql` presente; `pgsql` ausente.
    """
    installed = _collect_run_block_extensions(_DOCKERFILE_CONTENT)
    assert extension in installed, (
        f"Extensão PHP '{extension}' ausente no Dockerfile. "
        f"Extensões encontradas: {sorted(installed)}"
    )


@pytest.mark.parametrize("extension", BUG1_EXTENSIONS)
def test_bug1_pgsql_present_in_dockerfile_parametrized(extension: str) -> None:
    """
    Teste determinístico complementar ao property test para Bug 1.
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    """
    installed = _collect_run_block_extensions(_DOCKERFILE_CONTENT)
    assert extension in installed, (
        f"Bug 1 confirmado: extensão '{extension}' ausente no Dockerfile "
        f"(contraexemplo: somente `pdo_pgsql` presente)."
    )


# ---------------------------------------------------------------------------
# Bug 2 — `env_file` aponta para `.env.example`
# ---------------------------------------------------------------------------

BUG2_SERVICES = ["db", "moodle"]


@given(service=st.sampled_from(BUG2_SERVICES))
@settings(max_examples=20)
def test_bug2_env_file_points_to_dotenv(service: str) -> None:
    """
    Property 1 / Bug 2: Os serviços `db` e `moodle` devem ter `env_file`
    apontando para `.env`, não para `.env.example`.

    Validates: Requirements 1.3, 1.4
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    Contraexemplo: `db.env_file == ".env.example"` e
                   `moodle.env_file == ".env.example"`.
    """
    values = _env_file_values_for_service(_COMPOSE_DATA, service)
    assert values, (
        f"Serviço '{service}' não possui chave `env_file` no compose."
    )
    for val in values:
        assert val == ".env", (
            f"Bug 2 confirmado no serviço '{service}': "
            f"`env_file` é '{val}' em vez de '.env'."
        )


@pytest.mark.parametrize("service", BUG2_SERVICES)
def test_bug2_env_file_points_to_dotenv_parametrized(service: str) -> None:
    """
    Teste determinístico complementar ao property test para Bug 2.
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    """
    values = _env_file_values_for_service(_COMPOSE_DATA, service)
    assert values, (
        f"Serviço '{service}' não possui chave `env_file`."
    )
    for val in values:
        assert val == ".env", (
            f"Bug 2 confirmado: serviço '{service}' usa `env_file: {val}` "
            f"em vez de `.env`."
        )


# ---------------------------------------------------------------------------
# Bug 3 — `.kiro/` bloqueado no .gitignore
# ---------------------------------------------------------------------------

BUG3_FORBIDDEN_LINES = [".kiro/"]


@given(forbidden=st.sampled_from(BUG3_FORBIDDEN_LINES))
@settings(max_examples=10)
def test_bug3_kiro_not_in_gitignore(forbidden: str) -> None:
    """
    Property 1 / Bug 3: O `.gitignore` não deve conter a linha `.kiro/`
    (isso impede o versionamento dos arquivos de spec).

    Validates: Requirements 1.5, 1.6
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    Contraexemplo: linha exata `.kiro/` encontrada no `.gitignore`.
    """
    exact_lines = [line.strip() for line in _GITIGNORE_LINES]
    assert forbidden not in exact_lines, (
        f"Bug 3 confirmado: linha exata '{forbidden}' encontrada no "
        f".gitignore (impede rastreamento de .kiro/specs/)."
    )


def test_bug3_kiro_not_in_gitignore_deterministic() -> None:
    """
    Teste determinístico complementar ao property test para Bug 3.
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    """
    exact_lines = [line.strip() for line in _GITIGNORE_LINES]
    assert ".kiro/" not in exact_lines, (
        "Bug 3 confirmado: linha exata '.kiro/' encontrada no .gitignore."
    )


# ---------------------------------------------------------------------------
# Bug 4 — CI sem etapa `cp` antes de `docker compose config --quiet`
# ---------------------------------------------------------------------------

def test_bug4_cp_step_exists_before_compose_config() -> None:
    """
    Property 1 / Bug 4: O workflow `docker-lint.yml` deve conter uma etapa
    com `cp docker/.env.example docker/.env` **antes** da etapa que executa
    `docker compose config --quiet`.

    Validates: Requirements 1.7
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    Contraexemplo: etapa `config --quiet` presente sem etapa `cp` precedente.
    """
    cp_idx = _step_index(_WORKFLOW_CONTENT, "cp docker/.env.example docker/.env")
    config_idx = _step_index(_WORKFLOW_CONTENT, "config --quiet")

    assert config_idx != -1, (
        "Etapa `docker compose config --quiet` não encontrada no workflow "
        "(comportamento inesperado — a etapa de validação deveria existir)."
    )
    assert cp_idx != -1, (
        "Bug 4 confirmado: nenhuma etapa com "
        "`cp docker/.env.example docker/.env` encontrada no workflow "
        "docker-lint.yml."
    )
    assert cp_idx < config_idx, (
        f"Bug 4 confirmado: etapa `cp` (índice {cp_idx}) não aparece antes "
        f"de `docker compose config --quiet` (índice {config_idx})."
    )


@given(cp_fragment=st.just("cp docker/.env.example docker/.env"))
@settings(max_examples=10)
def test_bug4_cp_step_exists_property(cp_fragment: str) -> None:
    """
    Property 1 / Bug 4 (versão PBT): Para o fragmento de comando `cp`
    esperado, deve existir uma etapa no workflow que o contenha.

    Validates: Requirements 1.7
    RESULTADO ESPERADO ANTES DA CORREÇÃO: **FALHA**
    """
    cp_idx = _step_index(_WORKFLOW_CONTENT, cp_fragment)
    config_idx = _step_index(_WORKFLOW_CONTENT, "config --quiet")

    assert cp_idx != -1, (
        f"Bug 4 confirmado: etapa com '{cp_fragment}' ausente no workflow."
    )
    assert cp_idx < config_idx, (
        f"Bug 4 confirmado: etapa `cp` (índice {cp_idx}) deveria aparecer "
        f"antes de `config --quiet` (índice {config_idx})."
    )


# =============================================================================
# PROPERTY 2 — PRESERVATION TESTS
# Estes testes DEVEM PASSAR tanto no código não corrigido quanto após as
# correções, garantindo que nenhuma regressão seja introduzida.
# =============================================================================

# ---------------------------------------------------------------------------
# Preservação 3.1 — Extensões obrigatórias do Moodle permanecem no Dockerfile
# ---------------------------------------------------------------------------

MANDATORY_EXTENSIONS = [
    "mbstring",
    "curl",
    "zip",
    "simplexml",
    "intl",
    "pdo_pgsql",
    "gd",
    "opcache",
    "sodium",
]


@given(extension=st.sampled_from(MANDATORY_EXTENSIONS))
@settings(max_examples=100)
def test_preservation_mandatory_extensions_remain(extension: str) -> None:
    """
    Property 2: As nove extensões obrigatórias do Moodle 4.x devem
    continuar instaladas no Dockerfile após qualquer correção.

    Validates: Requirements 3.1
    RESULTADO ESPERADO: **PASSA** (antes e depois da correção)
    """
    installed = _collect_run_block_extensions(_DOCKERFILE_CONTENT)
    assert extension in installed, (
        f"Regressão detectada: extensão obrigatória '{extension}' ausente "
        f"no Dockerfile. Extensões encontradas: {sorted(installed)}"
    )


@pytest.mark.parametrize("extension", MANDATORY_EXTENSIONS)
def test_preservation_mandatory_extensions_parametrized(extension: str) -> None:
    """
    Teste determinístico de preservação para cada extensão obrigatória.
    Validates: Requirements 3.1
    """
    installed = _collect_run_block_extensions(_DOCKERFILE_CONTENT)
    assert extension in installed, (
        f"Extensão obrigatória '{extension}' ausente no Dockerfile."
    )


# ---------------------------------------------------------------------------
# Preservação 3.3 / 3.4 — Padrões de segurança permanecem no .gitignore
# ---------------------------------------------------------------------------

SECURITY_PATTERNS = [
    ".env",
    "*.tfvars",
    "terraform.tfstate",
    "*.pem",
    "*.key",
    "id_rsa",
]


@given(pattern=st.sampled_from(SECURITY_PATTERNS))
@settings(max_examples=100)
def test_preservation_security_patterns_in_gitignore(pattern: str) -> None:
    """
    Property 2: Os padrões de segurança devem permanecer no .gitignore
    após a remoção da linha `.kiro/`.

    Validates: Requirements 3.3, 3.4
    RESULTADO ESPERADO: **PASSA** (antes e depois da correção)
    """
    exact_lines = [line.strip() for line in _GITIGNORE_LINES]
    assert pattern in exact_lines, (
        f"Regressão detectada: padrão de segurança '{pattern}' ausente "
        f"no .gitignore."
    )


@pytest.mark.parametrize("pattern", SECURITY_PATTERNS)
def test_preservation_security_patterns_parametrized(pattern: str) -> None:
    """
    Teste determinístico de preservação para cada padrão de segurança.
    Validates: Requirements 3.3, 3.4
    """
    exact_lines = [line.strip() for line in _GITIGNORE_LINES]
    assert pattern in exact_lines, (
        f"Padrão de segurança '{pattern}' ausente no .gitignore."
    )


# ---------------------------------------------------------------------------
# Preservação 3.3 — `docker/.env` ainda é ignorado pelo .gitignore
# (via o padrão ".env" ou ".env.*")
# ---------------------------------------------------------------------------

def _gitignore_matches(pattern: str, filepath: str) -> bool:
    """
    Verifica de forma simples se um padrão do .gitignore corresponde
    ao caminho informado (somente o nome do arquivo ou padrão glob básico).
    Suporta `*` como coringa de segmento.
    """
    filename = pathlib.Path(filepath).name
    # Converte padrão glob simples em regex
    regex_pat = re.escape(pattern).replace(r"\*", "[^/]*")
    return bool(re.fullmatch(regex_pat, filename))


DOCKER_ENV_PATHS = ["docker/.env", "secret.pem", "credentials.key"]


@given(filepath=st.sampled_from(DOCKER_ENV_PATHS))
@settings(max_examples=30)
def test_preservation_sensitive_files_still_ignored(filepath: str) -> None:
    """
    Property 2: Arquivos sensíveis (`.env`, `.pem`, `.key`) devem continuar
    sendo correspondidos por algum padrão do .gitignore.

    Validates: Requirements 3.3
    RESULTADO ESPERADO: **PASSA** (antes e depois da correção)
    """
    exact_lines = [line.strip() for line in _GITIGNORE_LINES]
    matched = any(
        _gitignore_matches(pat, filepath)
        for pat in exact_lines
        if pat and not pat.startswith("#") and not pat.startswith("!")
    )
    assert matched, (
        f"Regressão detectada: '{filepath}' não é correspondido por nenhum "
        f"padrão do .gitignore."
    )


# ---------------------------------------------------------------------------
# Preservação 3.2 / 3.6 — Estrutura do compose intacta
# ---------------------------------------------------------------------------

COMPOSE_STRUCTURAL_KEYS = ["healthcheck", "depends_on", "ports", "volumes"]


@given(key=st.sampled_from(COMPOSE_STRUCTURAL_KEYS))
@settings(max_examples=50)
def test_preservation_compose_structural_keys(key: str) -> None:
    """
    Property 2: As chaves estruturais do docker-compose.yml devem
    permanecer presentes após a correção do `env_file`.

    Validates: Requirements 3.2, 3.6
    RESULTADO ESPERADO: **PASSA** (antes e depois da correção)
    """
    services = _COMPOSE_DATA.get("services", {})
    # Algumas chaves (depends_on, ports) existem apenas no serviço `moodle`;
    # `healthcheck` e `volumes` existem em `db`. Verificamos que pelo menos
    # um dos dois serviços possui a chave.
    found_in_any = any(key in svc for svc in services.values())
    assert found_in_any, (
        f"Regressão detectada: chave `{key}` ausente em todos os serviços "
        f"do docker-compose.yml."
    )


def test_preservation_compose_db_has_healthcheck() -> None:
    """Serviço `db` mantém o bloco `healthcheck`. Validates: Requirements 3.6"""
    assert "healthcheck" in _COMPOSE_DATA["services"]["db"], (
        "Chave `healthcheck` ausente no serviço `db`."
    )


def test_preservation_compose_moodle_has_depends_on() -> None:
    """Serviço `moodle` mantém `depends_on`. Validates: Requirements 3.2"""
    assert "depends_on" in _COMPOSE_DATA["services"]["moodle"], (
        "Chave `depends_on` ausente no serviço `moodle`."
    )


def test_preservation_compose_moodle_has_ports() -> None:
    """Serviço `moodle` mantém `ports`. Validates: Requirements 3.2"""
    assert "ports" in _COMPOSE_DATA["services"]["moodle"], (
        "Chave `ports` ausente no serviço `moodle`."
    )


# ---------------------------------------------------------------------------
# Preservação 3.7 — Triggers do workflow permanecem inalterados
# ---------------------------------------------------------------------------

def test_preservation_workflow_triggers_unchanged() -> None:
    """
    Property 2: Os triggers do workflow (`on.push.paths` e
    `on.pull_request.paths`) devem continuar apontando para `docker/**`.

    Validates: Requirements 3.7
    RESULTADO ESPERADO: **PASSA** (antes e depois da correção)
    """
    data = yaml.safe_load(_WORKFLOW_CONTENT)
    on_block = data.get("on", data.get(True, {}))  # 'on' pode ser parsed como True

    push_paths = on_block.get("push", {}).get("paths", [])
    pr_paths = on_block.get("pull_request", {}).get("paths", [])

    assert "docker/**" in push_paths, (
        "Trigger `on.push.paths` não contém `docker/**`."
    )
    assert "docker/**" in pr_paths, (
        "Trigger `on.pull_request.paths` não contém `docker/**`."
    )


def test_preservation_workflow_has_hadolint_step() -> None:
    """
    Etapa de lint do Dockerfile (hadolint) permanece no workflow.
    Validates: Requirements 3.7
    """
    assert "hadolint" in _WORKFLOW_CONTENT, (
        "Etapa com `hadolint` ausente no workflow docker-lint.yml."
    )


def test_preservation_workflow_has_compose_config_step() -> None:
    """
    Etapa de validação do compose permanece no workflow.
    Validates: Requirements 3.7
    """
    config_idx = _step_index(_WORKFLOW_CONTENT, "config --quiet")
    assert config_idx != -1, (
        "Etapa `docker compose config --quiet` ausente no workflow."
    )
