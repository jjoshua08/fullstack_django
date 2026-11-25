# Biblioteca — Aula 14: multi-organização

## Aula 17 — Etapa 7: dashboard por papel (slide 36)

Commits das etapas 1–6 confirmados: `b23e681`, `ee82f95`, `bbb6b95`, `b5c2589`,
`2a81da4` e `64efb8a`. Esta seção substitui as restrições temporárias descritas
nos registros históricos abaixo para CSV e série na API.

`Perfil.papel` é `CharField(max_length=8)` com choices `admin`/`operador`, padrão
`operador`. A propriedade `eh_admin` verifica exclusivamente o papel de negócio.
Migração: `core.0003_perfil_papel`. Perfis existentes recebem operador, inclusive
perfis de staff/superusuário, sem mudança de vínculos ou promoção automática.
A preservação foi validada em banco de testes; a migração NÃO foi aplicada ao
banco persistente. Após autorização, executar:

```bash
.venv/bin/python -B manage.py migrate core
```

Até aplicar a migração, o banco local não possui a coluna necessária ao código.
Banco e backup não foram alterados nesta etapa.

| Recurso | Administrador | Operador |
|---|---|---|
| KPIs e ranking HTML/API | Sim | Sim |
| Distribuição HTML | Sim | Sim |
| Série HTML/API (`por_mes`) | Sim | Não |
| Download CSV | Sim | HTTP 403 |

`core/decorators.py` implementa `papel_requerido(papel)` com `functools.wraps`,
autenticação, verificação de perfil/papel e 403 para autenticados sem autorização.
Anônimos são redirecionados ao login. `exportar_csv` conserva `login_required`,
usa `@papel_requerido('admin')` e chama o gerador existente, mantendo filtros e
proteção contra fórmulas. O bloqueio temporário foi removido.

O HTML usa `mostra_series = request.user.perfil.eh_admin`; operador não calcula
nem recebe `serie_mensal`/`por_mes` no contexto, JSON, canvas ou scripts do gráfico.
O JavaScript também verifica a existência dos elementos antes de criar Chart.
O link CSV só aparece para administrador e preserva início/fim. A API mantém
`IsAuthenticated` e só acrescenta `por_mes` para administrador, reutilizando
`serie_mensal()` e o filtro por período. Não foram duplicadas agregações.
`org_atual()` agora converte perfil ausente em 403, inclusive em HTML/API/CSV.
Flags `is_staff`/`is_superuser` não concedem acesso à série ou ao CSV.

### Administração e teste manual após aplicar a migração

1. Entrar no Django Admin com responsável autorizado a alterar Perfil.
2. Em Perfis, selecionar usuários de teste com organização definida e atribuir
   `Administrador` a um e `Operador` a outro. Repetir em outra organização para
   verificar isolamento. Nenhuma atribuição persistente foi feita nesta etapa.
3. Entrar como administrador de organização em `/accounts/login/`, abrir
   `/dashboard/`, filtrar período e conferir gráfico e download CSV.
4. Abrir `/api/dashboard/?format=json`: a resposta deve incluir `por_mes`.
5. Entrar como operador: conferir KPIs/ranking/distribuição, sem gráfico/link;
   acessar `/dashboard/exportar-csv/` diretamente deve retornar 403, e a API
   não deve conter `por_mes`. Parâmetros `papel=admin` não alteram permissões.
6. Sem perfil, dashboard/API/CSV devem responder 403, sem erro 500.

`PerfilAdmin` expõe usuário, organização e papel, preservando as permissões nativas
do Django Admin. Administrador de organização não recebe status staff nem acesso
administrativo automaticamente. Atribuir permissão de alteração de Perfil é uma
responsabilidade administrativa e permite gerenciar os papéis; não deve ser
concedida a quem não pode administrá-los. Formulários comuns não expõem esse campo.

### Testes e consultas

A cobertura dos 62 testes anteriores foi preservada. Fixtures dos testes de série
HTML/gráfico/desempenho passaram a usar explicitamente papel admin para manter
as verificações anteriores; os testes de restrição de CSV/API usam o padrão operador.
Nenhum teste foi excluído. Novos testes cobrem propriedade/padrão, migração,
decorator, matriz de acesso em duas organizações, filtro, ausência de série no
backend, usuário sem perfil, flags de staff/superusuário e acesso administrativo.

O dashboard de administrador continua em **8 consultas**, com 3 e 30 livros,
conforme os testes da etapa 4. Operador usa **7 consultas**, antes e depois de
adicionar 20 livros, pois a consulta da série não é executada. Não há nova
otimização nem N+1. A ausência de chamada à série para operador é testada no HTML
e na API. Não houve validação visual em navegador nem antecipação da etapa 8.
Resultado: **71 testes aprovados**, com a cobertura dos 62 anteriores e nove
novos testes. `check`, `makemigrations --check --dry-run`, `pip check` e
`git diff --check` passaram. A migração foi validada somente no banco de testes.

## Aula 17 — Etapa 6: API do dashboard (slide 35)

Commits anteriores confirmados: `b23e681`, `ee82f95`, `bbb6b95`, `b5c2589`
e `2a81da4`. DRF **3.18.3** já estava instalado, fixado em `requirements.txt`
e registrado em `INSTALLED_APPS`; não foi necessário reinstalar ou alterar
configurações, inclusive a Debug Toolbar. A versão declara compatibilidade com
Python 3.14 e Django 6.1: https://pypi.org/project/djangorestframework/3.18.3/

`acervo/api.py` define `DashboardApi(APIView)`,
`permission_classes = [IsAuthenticated]`, `get()` e `Response()`.
A rota `/api/dashboard/` usa `DashboardApi.as_view()` e retorna somente
`kpis` (total/disponiveis) e `ranking` (até cinco autores).
Reutiliza `org_atual()`, `filtrar_periodo()`, `kpis()` e `ranking_autores()`;
não duplica agregações nem adiciona serializers, routers ou ViewSets.
Parâmetros `organizacao`/`organizacao_id` não substituem a organização do perfil.

Períodos usam `inicio`/`fim` inclusivos. Datas inválidas preservam o comportamento
anterior: nenhum limite é aplicado, mas o escopo da organização permanece.
Período sem registros retorna KPIs zero e ranking vazio. A API não expõe série
mensal, mesmo para staff/superusuário ou por parâmetros enviados pelo cliente.
A exportação CSV continua bloqueada. A autorização por papel pertence à etapa 7.
O usuário autenticado deve possuir Perfil, como nas views anteriores; o tratamento
geral de usuário sem perfil continua uma pendência anterior, sem refatoração aqui.

### Testes e reprodução

Nove testes novos em `acervo/tests_api.py` cobrem autenticação, isolamento entre
duas organizações, período, igualdade com HTML, ranking, vazio, datas inválidas,
restrições temporárias e recusa de POST. As fixtures não alteram dados persistentes.

```bash
API_REPORT=1 .venv/bin/python -B manage.py test acervo.tests_api
```

Resposta JSON efetivamente obtida no teste:

```json
{"kpis": {"total": 21, "disponiveis": 12}, "ranking": [{"autor": "Autor 0", "total": 6}, {"autor": "Autor 1", "total": 5}, {"autor": "Autor 2", "total": 4}, {"autor": "Autor 3", "total": 3}, {"autor": "Autor 4", "total": 2}]}
```

Para testar no navegador:

1. Executar `.venv/bin/python -B manage.py runserver`.
2. Autenticar em `/accounts/login/` com usuário que tenha Perfil.
3. Acessar `/api/dashboard/` (API navegável) ou `/api/dashboard/?format=json`.
4. Testar `/api/dashboard/?inicio=2025-01-01&fim=2025-12-31&format=json`
   e comparar com `/dashboard/` usando o mesmo período.
5. Repetir com outra organização e em janela sem sessão: anônimos recebem 403
   pelo mecanismo padrão SessionAuthentication, sem redirecionamento de login.

Não houve validação visual em navegador. Nenhuma dependência, papel, model ou
migração foi acrescentado nesta etapa.
Resultado: **62 testes aprovados**, preservando os 53 anteriores. `check`,
`makemigrations --check --dry-run`, `pip check` e `git diff --check` passaram.
Banco persistente e backup mantiveram seus hashes iniciais.

## Aula 17 — Etapa 5: exportação CSV (slide 34)

Commits anteriores confirmados: `b23e681`, `ee82f95`, `bbb6b95` e `b5c2589`.
A geração foi implementada em `gerar_csv_livros(request)`, função interna de
`acervo/views.py` sem URL própria. Usa `org_atual()`,
`Livro.objects.filter(organizacao=org)` e o mesmo `filtrar_periodo()` do dashboard.
Preserva limites inclusivos e o comportamento anterior: qualquer data inválida
faz com que nenhum limite de período seja aplicado, mantendo o escopo da organização.

Segue a técnica do slide: biblioteca nativa `csv`,
`HttpResponse(content_type='text/csv')`,
`Content-Disposition: attachment; filename="livros.csv"`, `csv.writer()` e
`writerow()`. Campos: `titulo`, `autor`, `ano`, `tipo_acervo`, `categoria`,
`disponivel` e `data_cadastro`. Tipo/categoria são apresentados pelos rótulos dos
choices, disponibilidade como Disponível/Indisponível e data em AAAA-MM-DD.
O conteúdo usa UTF-8 e o escritor padrão trata vírgulas, aspas e quebras de linha.

### Geração implementada; liberação pendente da etapa 7

A rota `/dashboard/exportar-csv/` (`exportar_csv`) exige login e lança
`PermissionDenied` para todos os autenticados, inclusive staff/superusuários.
Não existe flag de cliente que autorize a exportação. A view do dashboard fixa
`pode_exportar_csv=False`; o link preparado no template permanece oculto e
preserva `inicio`/`fim` com codificação de URL. Não foram criados papéis ou
decorators definitivos. Na etapa 7, a autorização por papel deverá substituir
esse bloqueio antes de chamar o gerador interno e de disponibilizar o link.

Essa separação permite testar o CSV sem desativar a proteção da rota.
Não há download utilizável pelo navegador nesta etapa: anônimos são enviados ao
login e autenticados recebem 403. A geração interna não é uma view pública.

### Proteção e desempenho

Campos textuais iniciados por `=`, `+`, `-` ou `@` recebem um apóstrofo somente
na saída. Os valores persistidos não são modificados. A proteção implementa o
alerta específico do slide; não depende apenas das aspas usadas pelo CSV.
Todos os campos exportados são locais a Livro, portanto não há `select_related`
nem JOIN artificial. Medição do gerador com usuário carregado e cache relacional
vazio: **3 consultas com 3 livros e 3 consultas com 30 livros** (perfil,
organização e livros). Essa contagem não inclui autenticação HTTP; a rota pública
permanece bloqueada. Os testes de desempenho anteriores foram preservados.

### Validação e reprodução

Dez testes em `acervo/tests_csv.py` verificam campos/cabeçalhos, isolamento,
limites inclusivos e KPI, vazio, datas inválidas, caracteres especiais,
neutralização de fórmulas, consultas e bloqueios. Um teste renderiza isoladamente
o ramo futuro do link para conferir os parâmetros sem liberar a rota.

```bash
CSV_REPORT=1 .venv/bin/python -B manage.py test acervo.tests_csv
.venv/bin/python -B manage.py check
.venv/bin/python -B manage.py makemigrations --check --dry-run
.venv/bin/python -B manage.py test
git diff --check
```

O primeiro comando reproduz o CSV e imprime o SQL em banco de testes, sem gravar
no banco persistente. Exemplo efetivamente gerado:

```csv
Título,Autor,Ano,Tipo de acervo,Categoria,Disponibilidade,Data de cadastro
"Programação, ""Django""",João,2020,Físico,800 - Literatura,Disponível,2025-01-10
```

Nenhum model, migração, dependência, API ou papel foi criado nesta etapa.
Resultado: **53 testes aprovados** (43 anteriores e dez novos); `check`,
`makemigrations --check --dry-run` e `git diff --check` passaram.
Os hashes do banco persistente e do backup permaneceram iguais aos iniciais.

## Aula 17 — Etapa 4: consultas e N+1 (slides 19–33)

Commits anteriores confirmados: `b23e681`, `ee82f95`, `bbb6b95`.
Foram adicionados instrumentos de desenvolvimento e cinco testes em
`acervo/tests_performance.py`. Nenhuma consulta funcional, model, migração,
regra de negócio ou interface foi alterada. DRF já estava presente nesta revisão;
não foi implementada API nesta etapa.

### Medições reais: demonstração versus telas

Demonstração didática em SQLite de testes: três livros da mesma organização,
acessando `livro.organizacao.nome` em cada iteração, com limite de 50 e escopo
por organização. Sem `select_related`: **4 consultas**; com
`select_related('organizacao')`: **1 consulta com INNER JOIN**. Esse é um exemplo
controlado, não uma correção aplicada às views.

| Tela medida por GET | 3 livros próprios | 30 livros próprios |
|---|---:|---:|
| Listagem | 5 | 5 |
| Dashboard | 8 | 8 |
| Cadastro | 4 | 4 |
| Edição | 5 | 5 |
| Admin de livros (4 e 31 livros globais) | 6 | 6 |
| Admin de perfis | 5 | 5 |

As telas foram percorridas pelo cliente Django, com log SQL habilitado, usando
banco de testes e perfil autenticado. Os quatro acessos constantes de sessão,
usuário, perfil e organização não são N+1. O dashboard executa outras quatro
consultas, uma por métrica. Nenhuma tela ultrapassou dez consultas.
O Admin de livros já aplica JOIN automaticamente por exibir a ForeignKey.
Os dois COUNTs repetidos no Admin são constantes (contagem filtrada e total),
não N+1; não alteramos essa funcionalidade padrão. O Admin mantém sua visão global.
Não foi identificado N+1 real nos fluxos medidos. Não há M2M nem acesso reverso
em loops que justifique `prefetch_related()`; não foram criadas relações artificiais.

### Sete métodos, na ordem dos slides

1. **Slide 23 — `str(qs.query)`:** SQL compilado sob `assertNumQueries(0)`.
2. **Slide 24 — `connection.queries`:** `reset_queries()` seguido de `list(qs)`
   em queryset novo, com `override_settings(DEBUG=True)`: uma consulta registrada.
   Sem DEBUG (ou cursor de diagnóstico), esse histórico não é habilitado;
   reusar queryset avaliado ocultaria a execução por causa do cache de resultados.
3. **Slide 25 — `CaptureQueriesContext`:** quatro consultas sem JOIN versus uma
   com JOIN; o comando abaixo imprime todo o SQL efetivamente executado.
4. **Slide 26 — LOGGING:** logger `django.db.backends`, handler console e nível
   DEBUG, restritos à ativação local. O teste também captura e verifica um SELECT
   nesse logger. O percurso das telas foi repetido com `SQL_LOGGING=1`.
5. **Slide 27 — `qs.explain()`:** SQLite retornou `SCAN acervo_livro` sem filtro;
   organização + período retornou
   `SEARCH acervo_livro USING INDEX acervo_livro_organizacao_id_4d062d61 (organizacao_id=?)`.
6. **Slides 28–30 — Debug Toolbar 8.0.0:** instalada sem downgrade. PyPI declara
   suporte a Python 3.14 e Django 6.1; `pip check` e `check` com Toolbar passaram.
   Em banco em memória, uma requisição local ao dashboard retornou HTTP 200 com
   Toolbar inserida no HTML. **Não houve inspeção visual em navegador.**
7. **Slide 31 — `assertNumQueries`:** asserts de 4/1 na relação, orçamentos fixos
   das telas e comparação de 3/30 registros. A expectativa didática incorreta
   de uma consulta sem JOIN produz `4 != 1 : 4 queries executed, 1 expected`,
   capturada por `assertRaises(AssertionError)`; nenhum teste falho fica na suíte.

Referência de compatibilidade: https://pypi.org/project/django-debug-toolbar/8.0.0/

### SQL efetivamente capturado na demonstração

Sem `select_related` (o ID 2 pertence à organização temporária dessa execução):

```sql
SELECT "acervo_livro"."id", "acervo_livro"."organizacao_id", "acervo_livro"."tipo_acervo", "acervo_livro"."categoria", "acervo_livro"."titulo", "acervo_livro"."autor", "acervo_livro"."ano", "acervo_livro"."disponivel", "acervo_livro"."data_cadastro" FROM "acervo_livro" WHERE "acervo_livro"."organizacao_id" = 2 ORDER BY "acervo_livro"."id" ASC LIMIT 50
SELECT "core_organizacao"."id", "core_organizacao"."nome", "core_organizacao"."criada_em" FROM "core_organizacao" WHERE "core_organizacao"."id" = 2 LIMIT 21
SELECT "core_organizacao"."id", "core_organizacao"."nome", "core_organizacao"."criada_em" FROM "core_organizacao" WHERE "core_organizacao"."id" = 2 LIMIT 21
SELECT "core_organizacao"."id", "core_organizacao"."nome", "core_organizacao"."criada_em" FROM "core_organizacao" WHERE "core_organizacao"."id" = 2 LIMIT 21
```

Com `select_related('organizacao')`:

```sql
SELECT "acervo_livro"."id", "acervo_livro"."organizacao_id", "acervo_livro"."tipo_acervo", "acervo_livro"."categoria", "acervo_livro"."titulo", "acervo_livro"."autor", "acervo_livro"."ano", "acervo_livro"."disponivel", "acervo_livro"."data_cadastro", "core_organizacao"."id", "core_organizacao"."nome", "core_organizacao"."criada_em" FROM "acervo_livro" INNER JOIN "core_organizacao" ON ("acervo_livro"."organizacao_id" = "core_organizacao"."id") WHERE "acervo_livro"."organizacao_id" = 2 ORDER BY "acervo_livro"."id" ASC LIMIT 50
```

Não foi feito benchmark de tempo. O registro individual exibiu `0.000` segundos,
resolução insuficiente para alegar ganho temporal; a comparação é de consultas.

### Índices — slide 33

A introspecção confirmou o índice existente da FK `organizacao_id`:
`acervo_livro_organizacao_id_4d062d61`. A busca por organização e período usa esse
índice. `data_cadastro` não possui índice próprio. Não há evidência, nesta carga
pequena, que justifique adicionar índice isolado ou composto; planos/volume reais
maiores podem justificar reavaliação futura. Não foram criados índices redundantes,
migrações ou cache. Dados e backup persistentes mantiveram seus hashes.

### Reprodução e ativação local

Demonstração completa, na ordem dos sete métodos, com SQL e contagens das telas
(exclusivamente banco de testes; não cria registros no banco persistente):

```bash
PERFORMANCE_REPORT=1 .venv/bin/python -B manage.py test acervo.tests_performance
DJANGO_ENV=development SQL_LOGGING=1 PERFORMANCE_REPORT=1 .venv/bin/python -B manage.py test acervo.tests_performance
```

Toolbar local:

```bash
DJANGO_ENV=development DEBUG_TOOLBAR=1 .venv/bin/python -B manage.py runserver
```

Log SQL local como alternativa:

```bash
DJANGO_ENV=development SQL_LOGGING=1 .venv/bin/python -B manage.py runserver
```

Abrir `http://127.0.0.1:8000/`, autenticar com usuário com perfil e percorrer
listagem, cadastro, edição e `/dashboard/`; para staff autorizado, visitar o
Admin de livros e perfis. Abrir o painel SQL, comparar consultas repetidas e JOINs.
Não salvar formulários para apenas inspecionar consultas. Login normal pode gravar
sessão: para reprodução sem qualquer escrita persistente, usar os comandos de testes.

A ativação exige `DJANGO_ENV=development` e `DJANGO_DEBUG=1` (padrão local anterior
preservado), mais a flag específica. Sem flags, ambos ficam desligados. Em produção,
definir `DJANGO_ENV=production DJANGO_DEBUG=0`; verificou-se que app, middleware,
rota e log SQL ficam desativados mesmo com as flags de instrumentos em 1.
A Toolbar usa `INTERNAL_IPS=['127.0.0.1']` e rota `__debug__/`.

### Validação

**43 testes passaram**: 38 anteriores e cinco novos. Os testes novos também
verificam métricas, período e isolamento com orçamento de oito consultas no dashboard.
`check`, `makemigrations --check --dry-run`, `git diff --check`, `pip check`,
e `check` com Toolbar habilitada passaram. A interface visual não foi validada.


## Aula 17 — Etapa 3: gráfico de barras

Pré-requisitos confirmados: commits `b23e681` (etapa 1) e `ee82f95` (etapa 2).
O dashboard inclui o gráfico **Livros cadastrados por mês** (slides 14–18).
A view reutiliza o mesmo queryset da série mensal, já restrito à organização
e ao período, e formata os meses com `strftime('%m/%Y')` na lista `por_mes`.
O contexto anterior `serie_mensal` é preservado com o mesmo queryset avaliado,
sem repetir a consulta. O JavaScript apenas mapeia os resultados recebidos.

O template usa `json_script` com ID `dados-mes`, canvas `graf` e carrega os
scripts locais, na ordem, após o canvas. `dashboard.js` usa `JSON.parse()` e
`new Chart()` com `type: 'bar'`. Sem dados, envia `[]` e exibe a mensagem de
ausência de dados, sem inventar valores. As regras anteriores de datas inválidas
e isolamento continuam em vigor.

Biblioteca: **Chart.js 4.4.8**, distribuição UMD oficial, sem alteração do
conteúdo, em `acervo/static/js/chart.umd.js`. Origem fixada:
https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.js
Licença MIT incluída em `acervo/static/js/Chart.js.LICENSE.md`.
A documentação oficial descreve esse modo de integração:
https://www.chartjs.org/docs/latest/getting-started/integration.html
Não é necessário acesso ao CDN no navegador, nem alterar `settings.py`.

Validação automatizada: **38 testes aprovados**, preservando os 31 anteriores.
Os sete novos testes cobrem formato/ordem dos meses, serialização, soma igual
ao KPI, período, isolamento, vazio, JSON/canvas/scripts e datas inválidas.
Os comandos `check`, `makemigrations --check --dry-run`,
`findstatic js/chart.umd.js js/dashboard.js` e `git diff --check` passaram.

**Validação visual em navegador não executada nesta etapa.** Para realizá-la:

1. Executar `.venv/bin/python -B manage.py runserver` e entrar com usuário com perfil.
2. Abrir `http://127.0.0.1:8000/dashboard/` e conferir título, barras e meses.
3. Comparar a soma das barras com o total de livros e a distribuição.
4. Aplicar início/fim, limpar o período e testar uma data inválida.
5. Escolher um período sem livros: mensagem de ausência e nenhum valor fictício.
6. Repetir em outra organização e conferir o isolamento.
7. Verificar no console/rede do navegador que os dois scripts carregam sem erros.

O banco e o backup mantiveram os hashes anteriores ao trabalho. Nenhum commit,
model, migração, API, CSV ou papel foi criado nesta etapa.

## Aula 17 — Etapa 2: dashboard e período

A etapa 1 está registrada no commit `b23e681`. A etapa 2 acrescenta `/dashboard/`,
protegido por login, com acesso na navegação, cartões de total/disponíveis,
distribuição por tipo e tabela dos cinco autores. O template herda `base.html`
e apresenta `Sem dados no período.` quando não há resultados.

`PeriodoForm` e `filtrar_periodo(request, qs)` em `acervo/forms.py` seguem o
slide 11: datas opcionais, validação por `is_valid()` e limites inclusivos
`data_cadastro__gte`/`data_cadastro__lte`. Se qualquer data for inválida, nenhum
limite é aplicado; o formulário exibe os erros e a página explica que os valores
correspondem a todo o acervo da organização. Datas válidas em ordem invertida
produzem um resultado vazio, preservando a lógica do exemplo do professor.

A view usa uma única base filtrada por organização e período. As quatro funções
da etapa 1 aceitam agora um queryset opcional, mantendo as chamadas anteriores
e reaplicando a restrição por organização. Nenhuma agregação foi duplicada.
A série mensal está no contexto, sem gráfico ou preparação de dados JavaScript.
Não foram implementados CSV, API, papéis ou otimizações de consultas.

Validação: **31 testes aprovados**, incluindo os 21 anteriores e dez novos testes
de acesso, autenticação, isolamento, limites inclusivos, consistência das quatro
métricas, datas inválidas e ausência de dados. `check`,
`makemigrations --check --dry-run` e `git diff --check` também passaram.

Para validar manualmente, executar `.venv/bin/python -B manage.py runserver`,
entrar com usuário que tenha perfil e acessar `http://127.0.0.1:8000/dashboard/`.
Comparar o total sem filtros, testar início/fim em formato `AAAA-MM-DD`,
limpar o período, enviar data inválida e escolher período sem livros.
Repetir com outra organização e em sessão sem login. Não é necessário criar
ou editar dados persistentes. A migração 0007 já estava aplicada ao iniciar
esta etapa; o banco local já tinha alteração no Git e foi preservado.

## Aula 17 — Etapa 1: perguntas de negócio e métricas

Implementação limitada aos slides 5–10: campo de data, métricas ORM e testes.
Não inclui dashboard HTML, filtro por período, gráficos, CSV, API ou papéis.
As seções anteriores da Aula 14, abaixo, registram o estado daquela entrega;
suas contagens de testes e migrações são históricas.

| Pergunta | Função em `acervo/dashboard.py` | Técnica / slide |
|---|---|---|
| Quantos livros existem e quantos estão disponíveis? | `kpis(organizacao)` | `aggregate`, `Count('id')` e `Count('id', filter=Q(disponivel=True))` — slide 8 |
| Quais são os cinco autores com mais livros? | `ranking_autores(organizacao)` | `values('autor')`, `annotate`, `order_by('-total')`, `[:5]` — slide 9 |
| Quantos livros foram cadastrados por mês? | `serie_mensal(organizacao)` | `TruncMonth('data_cadastro')`, agrupamento e ordenação por `mes` — slide 10 |
| Quantos livros são físicos e digitais? | `distribuicao_acervo(organizacao)` | `values('tipo_acervo')` e `annotate(total=Count('id'))` — slide 6 |

Todas as funções partem de `livros_da_organizacao(organizacao)`, que filtra
`Livro.objects` pelo relacionamento existente. Na futura view/API, a organização
deve vir de `request.user.perfil.organizacao`, nunca de um parâmetro enviado pelo
cliente. As funções não dependem de HTTP e podem ser reutilizadas por ambas.
Não há joins que multipliquem linhas: `distinct=True` não é necessário aqui.
O ranking agrupa o texto de `autor`; empates não têm ordem secundária definida.
Categorias de distribuição sem livros não produzem uma linha de valor zero.
Sem livros, os KPIs retornam zero e os outros resultados ficam vazios.

### Data de cadastro e preservação do legado

`Livro.data_cadastro` é um `DateField(auto_now_add=True)`: novos livros recebem
a data corrente do ambiente de execução no cadastro, preservada nas edições.
A migração `acervo.0007_livro_data_cadastro` fornece `datetime.date.today` como
default temporário (`preserve_default=False`) para os livros existentes.

**Limitação:** registros antigos receberão a data em que a migração for aplicada,
como referência de importação. Essa data não representa seu cadastro histórico,
que não foi armazenado. Assim, a série mensal concentrará esses livros no mês da
migração. Nenhuma data histórica foi inferida a partir de `ano` ou da organização.
Os demais campos e registros são preservados.

A migração foi gerada e validada em banco de testes, mas **não foi aplicada ao
banco persistente nesta etapa**. Após autorização, aplicar localmente com:

```bash
.venv/bin/python -B manage.py migrate acervo
```

Até essa aplicação, o esquema persistente não possui a nova coluna; o código
atualizado que consulta `Livro` depende da migração para funcionar nesse banco.
Não incluir `biblioteca_db` nem `biblioteca_db.backup` no commit.

### Validação da etapa 1

```bash
.venv/bin/python -B manage.py check
.venv/bin/python -B manage.py makemigrations --check --dry-run
.venv/bin/python -B manage.py test
git diff --check
```

A suíte executada nesta etapa passou com **21 testes**: os 14 existentes,
seis testes novos de métricas/data e um teste de migração. As quatro métricas
usam fixtures determinísticas, com organizações distintas, seis autores,
meses em anos diferentes e organização vazia. Verificam isolamento, limite
de cinco autores, ordem mensal e somas da série/distribuição iguais ao total.
O teste de migração retrocede somente o banco de testes à migração 0006,
cria dois registros legados em organizações distintas e aplica a 0007,
comparando todos os campos anteriores e a data de referência da execução.
Nenhum dado de demonstração foi criado no banco persistente.

O projeto Django mantém livros de organizações distintas no mesmo banco, isolando
as views de negócio pela organização do usuário autenticado. Não implementa DRF,
papéis ou permissões adicionais da Aula 15.

## Modelagem e isolamento

- `core.Organizacao`: nome, data de criação e representação textual.
- `core.DaOrganizacao`: modelo abstrato com FK obrigatória e `on_delete=PROTECT`.
- `acervo.Livro`: herda a base e conserva título, autor, ano, disponibilidade,
  tipo de acervo e categoria.
- `core.Perfil`: OneToOne com o usuário padrão do Django e FK para organização.
- `org_atual(request)` obtém a organização de `request.user.perfil`.
- Listagem, cadastro e edição exigem login. A listagem filtra por organização
  antes dos filtros originais de título, categoria e tipo de acervo.
- O cadastro usa `save(commit=False)`, atribui a organização no servidor e salva.
- A edição usa `get_object_or_404` com PK **e** organização: GET e POST para um
  livro alheio retornam 404. O formulário não permite transferir a organização.
- O Admin registra organizações, perfis e livros; `LivroAdmin` exibe e filtra a
  organização. O superusuário tem visão global. O filtro administrativo não é
  uma barreira de isolamento para usuários staff com permissões.

## Migração em três fases

1. `acervo.0004_livro_organizacao`: adiciona a FK com `null=True`.
2. `acervo.0005_dados_org`: usa `RunPython` e `apps.get_model()` para criar/obter
   `Organização padrão` e associar os livros sem organização.
3. `acervo.0006_alter_livro_organizacao`: torna a FK obrigatória.

`core.0002_perfil` cria o perfil. As migrações existentes não foram alteradas.
Todas estão aplicadas no banco local inspecionado. Os três livros originais
coincidem com `biblioteca_db.backup` nos IDs e campos originais; estão na
Organização padrão e nenhum está sem organização. O backup serve como referência
de preservação, não deve ser restaurado sobre o banco atual.

## Execução local

Com o ambiente virtual existente e a configuração local já preparada:

```bash
source .venv/bin/activate
python3 manage.py check
python3 manage.py runserver
```

Acesse `/accounts/login/`, `/`, `/livros/novo/` e `/livros/<id>/editar/`.
O Admin fica em `/admin/`. As senhas e o conteúdo do `.env` não são documentados
aqui. O usuário das views de negócio precisa de um Perfil.

## Cenário de demonstração — cadastro confirmado

Consulta somente leitura ao banco existente em 25/11/2026 confirmou:

| Organização | Usuário e Perfil | Livros |
|---|---|---|
| Organização padrão | `usuario_a` vinculado à organização | 3 originais preservados |
| Organização B | `usuario_b` vinculado à organização | 1 livro para demonstração |

Os dois usuários estão ativos, sem status staff ou superusuário. Na verificação
anterior também foram confirmados senhas configuradas e ausência de grupos e
permissões individuais adicionais. As senhas reais não foram expostas nem usadas
em testes de login. Não existe livro sem organização; os três originais foram
novamente comparados ao backup e permanecem preservados.

Esses registros existem no banco persistente, independentemente das fixtures
temporárias dos testes. Não é necessário recriá-los. Para manutenção dos cadastros,
priorizar o Django Admin (slide 11), preservando os registros existentes. Definir
senhas somente no formulário seguro do Admin, sem registrá-las no código, README
ou chat. Esta atualização documental não realizou gravações no banco.

## Testes e roteiro de isolamento

```bash
python3 manage.py check
python3 manage.py showmigrations
python3 manage.py makemigrations --check --dry-run
python3 manage.py test
```

`acervo/tests.py` preserva os quatro testes originais e adiciona dez testes.
As fixtures criam organizações, usuários, perfis e livros no banco de testes;
o cliente autentica o usuário A. A senha usada no teste de login é gerada
aleatoriamente em memória, sem credencial fixa no código.

Roteiro manual com o cenário preparado, usando sessões separadas (execução manual
com as contas reais ainda não comprovada nesta auditoria):

1. Entrar como A e verificar somente os livros da Organização padrão.
2. Entrar como B e verificar somente os livros da Organização B.
3. Pesquisar por título, categoria e tipo; combinar os filtros.
4. Cadastrar e editar um livro próprio; verificar o vínculo automático.
5. Como A, acessar a URL de edição de um livro B: esperar 404.
6. Repetir por POST e conferir que o livro B não mudou.
7. Enviar `organizacao` e `organizacao_id` alheios por GET/POST: o escopo e o
   vínculo devem continuar sendo os do perfil autenticado.
8. Sem login, acessar as três views por GET/POST: esperar redirecionamento
   para login com `next`, sem gravação.
9. Como superusuário, verificar organizações e livros no Admin global.

Nos passos que criam/editam dados, usar registros de demonstração, nunca os três
livros originais. Os testes automatizados já exercitam esses fluxos em isolamento.

### Resultados reais — 25/11/2026

| Verificação | Resultado |
|---|---|
| `check` | Exit 0, nenhum problema |
| `showmigrations` | Exit 0, todas aplicadas |
| `makemigrations --check --dry-run` | Exit 0, nenhuma mudança detectada |
| `test` | Exit 0, **14 testes executados e aprovados**, incluindo os quatro originais |
| Repetição funcional da auditoria via stdin | **21/21 verificações aprovadas**, SQLite em memória |

Os quatro comandos foram executados novamente na verificação anterior a esta
atualização: todos retornaram exit 0 e a suíte manteve 14/14 aprovações. As 21
verificações adicionais são resultados da etapa de correção anterior, não uma
nova execução nesta edição documental. Nesta edição, apenas o cenário persistente
e a preservação dos livros foram reconferidos em modo somente leitura.

As verificações adicionais repetiram: migração de três livros legados simulados;
template e POST de login comum; listagem A/B; filtros individuais/combinados;
rótulos/disponibilidade; manipulação por GET; GET/POST de edição alheia; formulário
e gravação de cadastro; formulário e gravação de edição própria; organização
ausente do formulário; choices inválidos sem gravação; acesso anônimo;
Admin global de organizações e livros; bloqueio do Admin para usuário comum;
e `PROTECT`. As contagens da suíte e dessa auditoria não representam cenários
independentes: há sobreposição intencional.

Usuários sem Perfil continuam recebendo HTTP 500 nas três views por
`RelatedObjectDoesNotExist`. O comportamento foi observado novamente, mas sua
definição definitiva pertence à Aula 15; não foi alterado nem contado como teste
de sucesso. Não há alegação de auditoria exaustiva de segurança.

## Requisitos não aplicáveis — slides 15 e 16

Considerando os requisitos informados no pedido (slides integrais não fornecidos):

- Filtro de opções relacionais: `LivroForm` não expõe FK ou M2M. A FK de
  organização é preenchida pelo servidor; não há queryset de escolhas a filtrar.
- Unicidade global de negócio: Livro não tem `unique=True`, `unique_together`
  ou `UniqueConstraint` a adaptar por organização. O OneToOne de Perfil.usuario
  garante um perfil por usuário, não unicidade de dados do acervo entre empresas.

## Matriz atualizada e pendências

Mantido o critério da auditoria: 30 itens, excluindo dois não aplicáveis e o
tratamento de usuário sem Perfil reservado à Aula 15; restam 27 itens com peso igual.

| Itens da matriz anterior | Estado atual |
|---|---|
| 1–11, 13–21, 24–26 e 28: modelos, migrações, dados originais, Admin, isolamento e autenticação | CONFORME, preservados |
| 12: duas organizações e dois usuários comuns com perfis distintos no banco existente | CONFORME, vínculos confirmados; Organização B também possui um livro |
| 22–23: opções relacionais do formulário e unicidade global de negócio | NÃO APLICÁVEL |
| 27: usuário sem Perfil | PARCIAL, HTTP 500 observado; fora do cálculo da Aula 14 |
| 29: suíte existente | CONFORME, 14/14 testes aprovados |
| 30: documentação da implementação e resultados | CONFORME, este README |

**27/27 = 100% de conformidade dos requisitos aplicáveis da matriz da Aula 14.**
**Parecer: APTO para o escopo específico da Aula 14 avaliado**, com base no código,
nos testes automatizados e no cenário persistente confirmado. O login manual com
as senhas reais não foi comprovado; o fluxo de login foi validado com usuários do
banco de testes. O percentual não certifica segurança exaustiva nem a entrega geral
da disciplina, que ainda depende dos pré-requisitos da P1 abaixo.

Pendências da P1, separadas e fora desse percentual:

- API REST com DRF ausente; não implementada nesta etapa.
- `MELHORIAS_P1.md` ausente.
- Backlog da P2 não encontrado no repositório; eventual endereço externo não
  fornecido, portanto não verificado.
