# docker-local-fixes — Design do Bugfix

## Overview

Quatro bugs independentes impedem um estudante de executar o ambiente Docker do Moodle localmente pela primeira vez.
As correções estão estritamente contidas em quatro arquivos: `docker/Dockerfile`, `docker/docker-compose.yml`, `.gitignore`
e `.github/workflows/docker-lint.yml`. Cada correção é uma mudança mínima e cirúrgica; nenhuma refatoração ou
funcionalidade nova é introduzida.

| # | Arquivo | Sintoma |
|---|---------|---------|
| 1 | `docker/Dockerfile` | O instalador do Moodle exibe "database driver problem" — extensão `pgsql` ausente |
| 2 | `docker/docker-compose.yml` | Credenciais do `.env` personalizado são ignoradas; ambos os serviços apontam para `.env.example` |
| 3 | `.gitignore` | A árvore `.kiro/` inteira fica bloqueada para o rastreamento pelo Git |
| 4 | `.github/workflows/docker-lint.yml` | O passo `docker compose config --quiet` falha porque `docker/.env` está ausente no runner |

---

## Glossário

- **Bug_Condition (C)**: A condição que identifica um artefato com bug — o padrão de texto específico ou
  elemento ausente que causa o comportamento incorreto.
- **Property (P)**: O comportamento esperado após a condição de bug ser resolvida.
- **Preservation (Preservação)**: Comportamentos existentes que a correção deve deixar completamente inalterados.
- **isBugCondition_N**: Função em pseudocódigo que avalia se o artefato X dispara o bug N.
- **`docker-php-ext-install`**: Instrução do Dockerfile que compila e habilita uma extensão PHP a partir do fonte.
- **`env_file`**: Chave do Docker Compose que injeta variáveis de um arquivo no ambiente de um contêiner.
- **`pg_isready`**: Ferramenta cliente do PostgreSQL usada no healthcheck para verificar se o servidor aceita conexões.
- **`.env.example`**: Template versionado com valores de placeholder; nunca contém segredos reais.
- **`docker/.env`**: Arquivo de override local com credenciais reais; excluído do Git pelo `.gitignore`.

---

## Detalhes dos Bugs

### Bug 1 — Extensão `pgsql` ausente no Dockerfile

O bug se manifesta quando o instalador web do Moodle tenta conectar ao PostgreSQL. O Moodle utiliza
exclusivamente o driver nativo `pgsql` para conectar ao PostgreSQL. A extensão `pdo_pgsql` não é
utilizada pelo Moodle — ela permanece no Dockerfile apenas porque `tests/test_dockerfile_extensions.py`
a inclui em `MANDATORY_EXTENSIONS` e os testes existentes não devem ser quebrados.

**Especificação Formal:**
```
FUNCTION isBugCondition_1(X)
  ENTRADA: X do tipo DockerfileContent
  SAÍDA: boolean

  RETORNA NOT contains_install_instruction(X, "pgsql")
          AND contains_install_instruction(X, "pdo_pgsql")
END FUNCTION
```

**Exemplos:**
- Executar `docker compose exec moodle php -m | grep pgsql` retorna apenas `pdo_pgsql` → bug presente.
- Visitar o instalador do Moodle exibe "Error: database driver problem detected" → bug presente.
- Após a correção: `php -m` lista tanto `pgsql` quanto `pdo_pgsql` — `pgsql` para o Moodle, `pdo_pgsql` para os testes.
- Caso extremo: Dockerfile sem nenhuma das duas extensões — build inválido, fora do escopo.

---

### Bug 2 — `env_file` aponta para `.env.example` em vez de `.env`

O bug se manifesta quando um estudante personaliza as credenciais. Ambos os serviços `db` e `moodle` usam
`env_file: .env.example`, portanto as alterações feitas no arquivo `.env` local do estudante são silenciosamente ignoradas.

**Especificação Formal:**
```
FUNCTION isBugCondition_2(X)
  ENTRADA: X do tipo ComposeServiceConfig
  SAÍDA: boolean

  RETORNA X.env_file = ".env.example"
END FUNCTION
```

**Exemplos:**
- O estudante define `POSTGRES_PASSWORD=minha_senha` em `docker/.env`, recria os contêineres — senha não muda → bug presente.
- `docker compose exec db env | grep POSTGRES_PASSWORD` ainda exibe `changeme_strong_password` → bug presente.
- Após a correção: recriar os contêineres com `docker/.env` atualizado aplica a nova senha → bug resolvido.
- Caso extremo: o volume `db_data` já existe — o PostgreSQL ignora variáveis de inicialização em dados existentes; estudantes
  devem executar `docker compose down -v` primeiro (comportamento documentado, não um bug).

---

### Bug 3 — `.kiro/` completamente bloqueado no `.gitignore`

O bug se manifesta quando um estudante tenta commitar o entregável de spec do Kiro. O padrão `.kiro/` no
`.gitignore` bloqueia todo arquivo sob esse diretório, fazendo `git add .kiro/specs/` falhar silenciosamente.

**Especificação Formal:**
```
FUNCTION isBugCondition_3(X)
  ENTRADA: X do tipo GitignoreContent
  SAÍDA: boolean

  RETORNA contains_exact_line(X, ".kiro/")
END FUNCTION
```

**Exemplos:**
- `git status` após criar `.kiro/specs/docker-local-fixes/bugfix.md` não mostra arquivos não rastreados → bug presente.
- `git check-ignore -v .kiro/specs/` reporta `.kiro/` como a regra correspondente → bug presente.
- Após a correção: `git status` exibe `.kiro/specs/` como não rastreado → bug resolvido.
- Caso extremo: remover `.kiro/` mantendo arquivos locais do IDE sem versionar —
  tratado não adicionando nenhum padrão substituto (specs em `.kiro/specs/` devem ser rastreadas).

---

### Bug 4 — CI falha porque `docker/.env` está ausente no runner

O bug se manifesta no GitHub Actions após a correção do Bug 2. O arquivo compose agora referencia `docker/.env`,
que é ignorado pelo git e portanto nunca está presente no runner de CI. O passo `docker compose config --quiet`
falha com erro de arquivo não encontrado.

**Especificação Formal:**
```
FUNCTION isBugCondition_4(X)
  ENTRADA: X do tipo WorkflowContent
  SAÍDA: boolean

  RETORNA has_step(X, "docker compose config --quiet")
          AND NOT has_step_before(X, "docker compose config --quiet",
                                     "cp docker/.env.example docker/.env")
END FUNCTION
```

**Exemplos:**
- Execução de CI falha em "Validar docker-compose.yml" com `no such file or directory: docker/.env` → bug presente.
- Log do workflow exibe código de saída 1 no passo de config → bug presente.
- Após a correção: um passo anterior cria `docker/.env` a partir de `.env.example`; `config --quiet` tem sucesso → bug resolvido.
- Caso extremo: `.env.example` em si está ausente — isso seria um problema separado; esta correção assume que `.env.example` está sempre commitado.

---

## Architecture

### Requisitos de Preservação

**Comportamentos inalterados:**
- `test_dockerfile_extensions.py` deve continuar passando: todas as extensões em `MANDATORY_EXTENSIONS`
  (`mbstring`, `curl`, `zip`, `simplexml`, `intl`, `pdo_pgsql`, `gd`, `opcache`, `sodium`) permanecem instaladas.
- `docker compose config --quiet` deve continuar validando o arquivo compose sem erros.
- `docker/.env` deve permanecer ignorado pelo git; `git check-ignore docker/.env` deve continuar retornando correspondência.
- Todos os outros padrões de segurança no `.gitignore` (`.env`, `*.tfvars`, `terraform.tfstate`, `*.pem`, `*.key`,
  `id_rsa`) devem permanecer intactos e inalterados.
- `.env.example` deve permanecer commitado e não modificado — é o template de referência para os estudantes.
- O healthcheck do PostgreSQL (`pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`) deve continuar funcionando.
- O workflow `docker-lint.yml` deve continuar executando em push/PR para `docker/**`.

**Escopo:**
Todas as entradas que NÃO correspondam a nenhuma das quatro condições de bug acima devem ser completamente
não afetadas. Isso inclui:
- Outras extensões PHP já instaladas no Dockerfile.
- Outras chaves de configuração do Docker Compose (`ports`, `volumes`, `depends_on`, `healthcheck`, etc.).
- Todos os padrões do `.gitignore` não relacionados a `.kiro/`.
- Todos os passos do workflow além do passo de validação `config --quiet`.

---

## Causa Raiz Hipotética

**Bug 1 — `pgsql` ausente**
O autor do Dockerfile instalou `pdo_pgsql` presumindo que seria suficiente para o Moodle. Na prática, o
instalador web do Moodle verifica a presença do driver nativo `pgsql` (não PDO) e exibe "Error: database
driver problem detected" quando ele está ausente. `pdo_pgsql` não é utilizado pelo Moodle; permanece no
Dockerfile por ser exigido por `test_dockerfile_extensions.py`.

**Bug 2 — `env_file` incorreto**
Durante o scaffolding, `.env.example` foi usado como padrão conveniente para que o ambiente pudesse ser
testado sem nenhuma etapa de configuração extra. A referência nunca foi atualizada para apontar para o
arquivo `.env` real antes de o projeto ser entregue aos estudantes.

**Bug 3 — Padrão `.gitignore` abrangente demais**
A linha `.kiro/` foi provavelmente gerada por uma IDE ou ferramenta de scaffolding que trata todos os
arquivos do workspace do Kiro como locais/não compartilháveis. O padrão é correto para arquivos de estado
da IDE, mas não deve bloquear o subdiretório `specs/`, que é um entregável explícito do estudante.

**Bug 4 — CI assume que `.env` existe**
Após a correção do Bug 2, o arquivo compose referencia corretamente `docker/.env`, mas o workflow de CI foi
escrito assumindo tanto a referência antiga a `.env.example` quanto um `.env` commitado manualmente. Nenhum
passo foi adicionado para criar o arquivo a partir de `.env.example` antes que o comando de validação execute.

---

## Correctness Properties

Property 1: Condição de Bug — Todos os Quatro Bugs Corrigidos

_Para qualquer_ artefato (Dockerfile, docker-compose.yml, .gitignore ou YAML de workflow) onde qualquer condição
de bug se aplique (`isBugCondition_1`, `isBugCondition_2`, `isBugCondition_3` ou `isBugCondition_4` retorna true),
o artefato corrigido SHALL eliminar a condição: `pgsql` está instalado junto com `pdo_pgsql`; `env_file`
referencia `.env`; a linha `.kiro/` está ausente do `.gitignore`; e um passo `cp` precede `config --quiet`.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

Property 2: Preservação — Comportamentos Inalterados

_Para qualquer_ entrada que NÃO dispare nenhuma condição de bug (`isBugCondition_1` a `isBugCondition_4` todas
retornam false), os artefatos corrigidos SHALL produzir o mesmo comportamento que os originais, preservando todas
as extensões PHP obrigatórias, validade do docker-compose, padrões de segurança do git-ignore e execução do
workflow em mudanças em `docker/**`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

---

## Error Handling

Como esta spec é uma correção de configuração e não introduz lógica de execução nova, não há caminhos de erro de runtime criados. Os cenários relevantes de falha são todos de tempo de desenvolvimento:

- **`docker/.env` ausente localmente**: `docker compose up` e `docker compose config --quiet` falham com "no such file". Instruir o estudante a executar `cp docker/.env.example docker/.env` antes de qualquer comando Compose.
- **Volume `db_data` existente após troca de senha**: O PostgreSQL ignora `POSTGRES_PASSWORD` em volumes já inicializados. Instruir o estudante a executar `docker compose down -v` para destruir o volume e recriá-lo com as novas credenciais.
- **`.env.example` ausente no runner de CI**: O passo `cp docker/.env.example docker/.env` (Bug 4) pressupõe que `.env.example` está versionado. Se estiver ausente, o CI falhará com um erro diferente — esse caso está fora do escopo desta correção.

## Components and Interfaces

### Bug 1 — `docker/Dockerfile`

**Função / Bloco:** bloco `RUN docker-php-ext-install`

**Mudança específica:**
Adicionar `pgsql` imediatamente após `pdo_pgsql` no mesmo bloco `docker-php-ext-install` para que ambos os
drivers sejam compilados juntos.

```diff
     # Driver PDO para PostgreSQL — mantido por exigência dos testes (test_dockerfile_extensions.py)
     pdo_pgsql \
+    # Driver nativo PostgreSQL — exigido pelo instalador web do Moodle 4.1
+    pgsql \
```

---

### Bug 2 — `docker/docker-compose.yml`

**Serviços afetados:** `db` e `moodle`

**Mudança específica:**
Substituir `.env.example` por `.env` nas duas declarações `env_file`.

```diff
-      - .env.example
+      - .env
```

Aplicado duas vezes — uma em `db`, outra em `moodle`.

---

### Bug 3 — `.gitignore`

**Mudança específica:**
Remover a linha `.kiro/` completamente. Nenhum padrão substituto é necessário porque `.kiro/specs/` deve
ser rastreado e nenhum outro arquivo em `.kiro/` requer exclusão explícita neste projeto.

```diff
-# TypeScript cache
-*.tsbuildinfo
-.kiro/
+# TypeScript cache
+*.tsbuildinfo
```

---

### Bug 4 — `.github/workflows/docker-lint.yml`

**Job:** `docker-lint`

**Mudança específica:**
Inserir um novo passo entre "Checkout do repositório" e "Lint do Dockerfile com hadolint" que cria
`docker/.env` a partir de `.env.example`:

```yaml
      - name: Criar docker/.env a partir do exemplo (CI)
        run: cp docker/.env.example docker/.env
```

Este passo deve aparecer **antes** de "Validar docker-compose.yml".

---

## Data Models

Não há modelos de dados envolvidos nesta correção. Os quatro bugs são defeitos de configuração em arquivos de texto (Dockerfile, YAML, .gitignore); nenhum esquema de banco de dados, estrutura de dados ou modelo de objeto é criado ou alterado.

---

## Testing Strategy

### Abordagem de Validação

A estratégia executa em duas fases:

1. **Exploratória** — Executar testes existentes e novos contra o código **não corrigido** para confirmar que
   cada condição de bug é observável e para refutar ou confirmar as hipóteses de causa raiz.
2. **Correção + Preservação** — Aplicar as correções, re-executar todos os testes para confirmar que as
   condições de bug foram eliminadas e nenhuma regressão foi introduzida.

---

### Verificação Exploratória da Condição de Bug

**Objetivo:** Surfaçar contraexemplos no código não corrigido, confirmar hipóteses de causa raiz.

**Casos de Teste:**

1. **Bug 1 — `pgsql` ausente**: Parsear `docker/Dockerfile` e afirmar que `pgsql` aparece em um bloco
   `docker-php-ext-install` → falhará no código não corrigido (apenas `pdo_pgsql` está presente).
2. **Bug 2 — alvo do `env_file`**: Parsear `docker/docker-compose.yml` e afirmar que `env_file` lista `.env`
   para ambos os serviços → falhará (`.env.example` é encontrado).
3. **Bug 3 — `.kiro/` bloqueado**: Ler `.gitignore` e afirmar que nenhuma linha é exatamente `.kiro/` →
   falhará (linha presente).
4. **Bug 4 — passo `cp` ausente**: Ler `docker-lint.yml` e afirmar que um passo com `cp docker/.env.example docker/.env`
   existe antes do passo `config --quiet` → falhará (nenhum passo do tipo existe).

**Contraexemplos Esperados:**
- `pgsql` não encontrado em nenhuma instrução `docker-php-ext-install` ou `pecl install`.
- Valores de `env_file` iguais a `.env.example` em ambos os serviços.
- Linha exata `.kiro/` presente no `.gitignore`.
- Nenhum passo contendo `cp docker/.env.example docker/.env` precede o passo de validação do compose.

---

### Verificação da Correção

**Objetivo:** Verificar que para todas as entradas onde uma condição de bug se aplica, o artefato corrigido
satisfaz o comportamento esperado.

```
PARA TODO X ONDE isBugCondition_1(X) FAÇA
  resultado ← dockerfile_corrigido(X)
  AFIRMAR php_extension_installed(resultado, "pgsql")
           AND php_extension_installed(resultado, "pdo_pgsql")
FIM PARA

PARA TODO X ONDE isBugCondition_2(X) FAÇA
  resultado ← compose_corrigido(X)
  AFIRMAR env_file_references(resultado, ".env")
FIM PARA

PARA TODO X ONDE isBugCondition_3(X) FAÇA
  resultado ← gitignore_corrigido(X)
  AFIRMAR NOT contains_exact_line(resultado, ".kiro/")
           AND git_ignores(resultado, "docker/.env")
FIM PARA

PARA TODO X ONDE isBugCondition_4(X) FAÇA
  resultado ← workflow_corrigido(X)
  AFIRMAR step_exists_before(resultado,
            "cp docker/.env.example docker/.env",
            "docker compose config --quiet")
FIM PARA
```

---

### Verificação de Preservação

**Objetivo:** Verificar que para todas as entradas onde NENHUMA condição de bug se aplica, os artefatos
corrigidos se comportam de forma idêntica aos originais.

```
PARA TODO X ONDE NOT isBugCondition_1(X)
             AND NOT isBugCondition_2(X)
             AND NOT isBugCondition_3(X)
             AND NOT isBugCondition_4(X) FAÇA
  AFIRMAR original(X) = corrigido(X)
FIM PARA
```

**Abordagem de Testes:** Testes baseados em propriedades são adequados aqui porque:
- Geram automaticamente muitas variantes de conteúdo de arquivo, cobrindo casos extremos além dos exemplos manuais.
- Fornecem garantias sólidas de que a preservação vale em todo o espaço de entrada válido.
- A suíte Hypothesis existente em `test_dockerfile_extensions.py` já exercita isso para `MANDATORY_EXTENSIONS`.

**Casos de Teste:**
1. **Extensões PHP preservadas**: Após a correção do Bug 1, todas as nove `MANDATORY_EXTENSIONS` ainda são
   encontradas no Dockerfile — `test_dockerfile_extensions.py` deve passar sem modificação.
2. **Estrutura do Compose preservada**: Após a correção do Bug 2, `docker compose config --quiet` sai com 0;
   todas as outras chaves (`ports`, `volumes`, `depends_on`, `healthcheck`) permanecem inalteradas.
3. **Padrões de segurança do `.gitignore` preservados**: Após a correção do Bug 3, `docker/.env`, `*.tfvars`,
   `terraform.tfstate`, `*.pem`, `*.key` e `id_rsa` ainda são ignorados.
4. **`.kiro/specs/` agora rastreável**: Após a correção do Bug 3, arquivos em `.kiro/specs/` não são mais ignorados pelo git.
5. **Workflow ainda disparado em `docker/**`**: Após a correção do Bug 4, os filtros `on.push.paths` e
   `on.pull_request.paths` permanecem em `docker/**`.

---

### Testes Unitários

- Parsear o Dockerfile corrigido: afirmar que `pgsql` está presente, afirmar que todas as `MANDATORY_EXTENSIONS` estão presentes.
- Parsear o `docker-compose.yml` corrigido: afirmar que `env_file` é `.env` para os serviços `db` e `moodle`.
- Parsear o `.gitignore` corrigido: afirmar que a linha `.kiro/` está ausente; afirmar que `docker/.env` ainda é correspondido pelo padrão `.env`.
- Parsear o `docker-lint.yml` corrigido: afirmar que o passo `cp docker/.env.example docker/.env` existe e precede
  `docker compose config --quiet`.

### Testes Baseados em Propriedades

- **Extensões do Dockerfile**: Gerar subconjuntos aleatórios de `MANDATORY_EXTENSIONS`; para cada um, verificar que o
  Dockerfile corrigido ainda instala todos os membros do subconjunto (estende a suíte Hypothesis existente em
  `test_dockerfile_extensions.py`).
- **`env_file` do Compose**: Gerar strings aleatórias de nomes de serviço; verificar que nenhum serviço usa `.env.example`
  como valor de `env_file` no arquivo compose corrigido.
- **Correspondência de padrões do Gitignore**: Gerar caminhos de arquivo aleatórios em `.kiro/specs/`; verificar que nenhum
  é correspondido pelo `.gitignore` após a correção. Gerar caminhos aleatórios como `docker/.env`, `secret.pem`; verificar
  que todos ainda são correspondidos.

### Testes de Integração

- Executar `docker compose -f docker/docker-compose.yml config --quiet` após as correções dos Bugs 2 e 4, com
  `docker/.env` presente, e afirmar código de saída 0.
- Executar `hadolint` contra o Dockerfile corrigido e afirmar que nenhuma nova violação de regra é introduzida pela
  adição da extensão `pgsql`.
- Executar `git check-ignore docker/.env` e afirmar que ainda é ignorado após a correção do Bug 3.
- Executar `git check-ignore .kiro/specs/docker-local-fixes/bugfix.md` e afirmar que **não** é ignorado
  após a correção do Bug 3.
