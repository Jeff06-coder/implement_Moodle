# Bugfix Requirements Document

## Introduction

Quatro bugs impedem que o ambiente local do Moodle Docker AWS Challenge funcione corretamente quando o aluno executa `docker compose up -d --build` pela primeira vez. O primeiro bug causa falha de conexão com o banco de dados no instalador web do Moodle; o segundo faz com que alterações de senha no `.env` sejam ignoradas; o terceiro impede que a spec do Kiro seja versionada no repositório, comprometendo a entrega da disciplina; o quarto faz o workflow de CI falhar no GitHub Actions após a correção do Bug 2, porque `docker/.env` não existe no runner. Os arquivos afetados são `docker/Dockerfile`, `docker/docker-compose.yml`, `.gitignore` e `.github/workflows/docker-lint.yml`. O Bug 5 foi identificado durante a verificação manual no WSL (hadolint exit 1 por avisos pré-existentes sem threshold configurado) e registrado após a execução dos demais.

## Bug Analysis

### Current Behavior (Defect)

**Bug 1 — Driver PostgreSQL ausente no Dockerfile**

1.1 WHEN o aluno executa `docker compose up -d --build` e acessa o instalador web do Moodle THEN o sistema exibe "Error: database driver problem detected" porque a extensão PHP `pgsql` (driver nativo) não está instalada no contêiner — apenas `pdo_pgsql` está presente.

1.2 WHEN o PHP é inspecionado com `docker compose exec moodle php -m` THEN o sistema lista `pdo_pgsql` mas não lista `pgsql`.

**Bug 2 — Variáveis do .env não chegam aos contêineres**

1.3 WHEN o aluno copia `.env.example` para `.env`, altera as senhas e recria os contêineres THEN o sistema ignora o arquivo `.env` e os contêineres continuam usando as senhas do `.env.example`, porque `env_file` em ambos os serviços aponta para `.env.example`.

1.4 WHEN o banco de dados PostgreSQL é iniciado THEN o sistema usa as credenciais do `.env.example` em vez das credenciais definidas no `.env` do aluno.

**Bug 3 — Pasta .kiro/ no .gitignore**

1.5 WHEN o aluno faz `git add .kiro/specs/` para versionar a spec de entrega THEN o sistema recusa o rastreamento do diretório porque a linha `.kiro/` no `.gitignore` bloqueia todo o conteúdo dessa pasta.

1.6 WHEN o aluno executa `git status` após criar arquivos em `.kiro/specs/` THEN o sistema não exibe esses arquivos como untracked, ocultando a spec da entrega.

**Bug 4 — Workflow docker-lint.yml falha após correção do env_file**

1.7 WHEN o workflow `docker-lint.yml` executa o step "Validar docker-compose.yml" em um runner do GitHub Actions após a correção do `env_file` para `.env` THEN o sistema falha com erro porque `docker/.env` não existe no runner (o arquivo é ignorado pelo Git e nunca é commitado).

**Bug 5 — hadolint falha por avisos pré-existentes sem threshold configurado**

1.8 WHEN o workflow `docker-lint.yml` executa o step "Lint do Dockerfile com hadolint" THEN o sistema termina com exit code 1 porque os avisos pré-existentes `DL3008` (warning, linha 17) e `DL3059` (info, linhas 59 e 147) fazem o hadolint retornar erro, sem que haja `--failure-threshold` ou `--ignore` configurados.

### Expected Behavior (Correct)

**Bug 1 — Driver PostgreSQL ausente no Dockerfile**

2.1 WHEN o aluno executa `docker compose up -d --build` e acessa o instalador web do Moodle THEN o sistema SHALL exibir a tela de instalação sem erros de driver de banco de dados, porque tanto `pgsql` quanto `pdo_pgsql` estão instalados no contêiner.

2.2 WHEN o PHP é inspecionado com `docker compose exec moodle php -m` THEN o sistema SHALL listar tanto `pgsql` quanto `pdo_pgsql` na saída.

**Bug 2 — Variáveis do .env não chegam aos contêineres**

2.3 WHEN o aluno copia `.env.example` para `.env`, altera as senhas e recria os contêineres THEN o sistema SHALL injetar as variáveis do `.env` nos contêineres `db` e `moodle`, aplicando as credenciais configuradas pelo aluno.

2.4 WHEN o banco de dados PostgreSQL é iniciado com o volume `db_data` **inexistente ou vazio** THEN o sistema SHALL usar as credenciais definidas no `docker/.env` do aluno para criar o usuário e o banco de dados.

2.4a WHEN o aluno altera senhas no `docker/.env` com o volume `db_data` **já existente** THEN o sistema SHALL requerer `docker compose down -v` para destruir e recriar o volume antes que as novas credenciais sejam aplicadas pelo PostgreSQL.

**Bug 3 — Pasta .kiro/ no .gitignore**

2.5 WHEN o aluno executa `git add .kiro/specs/docker-local-fixes/` THEN o sistema SHALL aceitar o rastreamento dos arquivos da spec porque a linha `.kiro/` foi removida do `.gitignore`.

2.6 WHEN o aluno executa `git status` após criar arquivos em `.kiro/specs/` THEN o sistema SHALL exibir esses arquivos como untracked ou staged, tornando a spec visível para versionamento.

**Bug 4 — Workflow docker-lint.yml falha após correção do env_file**

2.7 WHEN o workflow `docker-lint.yml` executa em um runner do GitHub Actions THEN o sistema SHALL executar `cp docker/.env.example docker/.env` em um step anterior ao "Validar docker-compose.yml", garantindo que o arquivo `.env` exista no runner antes da validação do compose.

**Bug 5 — hadolint falha por avisos pré-existentes sem threshold configurado**

2.8 WHEN o workflow `docker-lint.yml` executa o step "Lint do Dockerfile com hadolint" THEN o sistema SHALL retornar exit code 0 ao usar `--failure-threshold warning --ignore DL3008`, porque: `DL3008` é ignorado (fixar versões apt quebra o build quando o Debian remove versões antigas) e `DL3059` é nível info (não atinge o threshold de warning), permanecendo visível no log sem bloquear o workflow.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o Dockerfile é inspecionado pelo teste `test_dockerfile_extensions.py` THEN o sistema SHALL CONTINUE TO instalar `pdo_pgsql` e todas as extensões da lista `MANDATORY_EXTENSIONS`, fazendo o `pytest` continuar passando.

3.2 WHEN `docker compose config --quiet` é executado na pasta `docker/` THEN o sistema SHALL CONTINUE TO validar o compose sem erros.

3.3 WHEN o aluno executa `git check-ignore docker/.env` THEN o sistema SHALL CONTINUE TO retornar `docker/.env` como ignorado pelo Git, mantendo a proteção de credenciais reais.

3.4 WHEN os padrões de segurança do `.gitignore` são verificados (`.env`, `*.tfvars`, `*.pem`, `terraform.tfstate`, `*.key`, `id_rsa`) THEN o sistema SHALL CONTINUE TO ignorar esses arquivos, sem qualquer alteração nesses padrões.

3.5 WHEN o aluno utiliza o `.env.example` como referência para configurar o ambiente THEN o sistema SHALL CONTINUE TO disponibilizar esse arquivo versionado como modelo de configuração, sem alterações em seu conteúdo.

3.6 WHEN o serviço `db` é iniciado com as variáveis corretas THEN o sistema SHALL CONTINUE TO executar o healthcheck `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` com sucesso antes de liberar o serviço `moodle`.

3.7 WHEN um push ou pull request modifica arquivos em `docker/` THEN o workflow `docker-lint.yml` SHALL CONTINUE TO executar com sucesso no GitHub Actions, mesmo sem `docker/.env` versionado no repositório.

3.8 WHEN o hadolint é executado com `--failure-threshold warning --ignore DL3008` THEN o sistema SHALL CONTINUE TO reportar `DL3059` no log (sem suprimi-lo), mantendo a visibilidade do aviso para o desenvolvedor.

---

## Bug Condition Methodology

### Bug Condition Functions

**Bug 1:**
```pascal
FUNCTION isBugCondition_1(X)
  INPUT: X of type DockerfileContent
  OUTPUT: boolean

  RETURN NOT contains(X, "docker-php-ext-install", "pgsql")
         AND contains(X, "docker-php-ext-install", "pdo_pgsql")
END FUNCTION
```

**Bug 2:**
```pascal
FUNCTION isBugCondition_2(X)
  INPUT: X of type ComposeServiceConfig
  OUTPUT: boolean

  RETURN X.env_file = ".env.example"
END FUNCTION
```

**Bug 3:**
```pascal
FUNCTION isBugCondition_3(X)
  INPUT: X of type GitignoreContent
  OUTPUT: boolean

  RETURN contains_line(X, ".kiro/")
END FUNCTION
```

**Bug 4:**
```pascal
FUNCTION isBugCondition_4(X)
  INPUT: X of type WorkflowContent
  OUTPUT: boolean

  RETURN has_step(X, "docker compose", "config --quiet")
         AND NOT has_step_before(X, "docker compose config", "cp docker/.env.example docker/.env")
END FUNCTION
```

**Bug 5:**
```pascal
FUNCTION isBugCondition_5(X)
  INPUT: X of type WorkflowContent
  OUTPUT: boolean

  RETURN has_hadolint_step(X)
         AND NOT has_flag(X, "--failure-threshold")
         AND NOT has_flag(X, "--ignore DL3008")
END FUNCTION
```

### Fix Checking Properties

```pascal
// Property: Fix Checking — Bug 1 (pgsql instalado)
FOR ALL X WHERE isBugCondition_1(X) DO
  result ← buildDockerfile'(X)
  ASSERT php_module_present(result, "pgsql")
         AND php_module_present(result, "pdo_pgsql")
END FOR

// Property: Fix Checking — Bug 2 (env_file correto)
FOR ALL X WHERE isBugCondition_2(X) DO
  result ← startContainer'(X, envFile=".env")
  ASSERT env_vars_from_dotenv_applied(result)
END FOR

// Property: Fix Checking — Bug 3 (.kiro/ rastreável)
FOR ALL X WHERE isBugCondition_3(X) DO
  result ← gitignore'(X)
  ASSERT NOT git_ignores(result, ".kiro/specs/")
         AND git_ignores(result, "docker/.env")
END FOR

// Property: Fix Checking — Bug 4 (step cp antes do config --quiet)
FOR ALL X WHERE isBugCondition_4(X) DO
  result ← workflowStep'(X)
  ASSERT step_exists_before(result, "cp docker/.env.example docker/.env", "docker compose config --quiet")
END FOR

// Property: Fix Checking — Bug 5 (hadolint com threshold e ignore)
FOR ALL X WHERE isBugCondition_5(X) DO
  result ← workflowStep'(X)
  ASSERT hadolint_exit_code(result) = 0
         AND has_flag(result, "--failure-threshold warning")
         AND has_flag(result, "--ignore DL3008")
END FOR
```

### Preservation Checking

```pascal
// Property: Preservation Checking — todos os bugs
FOR ALL X WHERE NOT isBugCondition_1(X)
             AND NOT isBugCondition_2(X)
             AND NOT isBugCondition_3(X)
             AND NOT isBugCondition_4(X)
             AND NOT isBugCondition_5(X) DO
  ASSERT F(X) = F'(X)
END FOR
```
