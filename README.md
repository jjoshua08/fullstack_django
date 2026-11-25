# Biblioteca — Aula 14: multi-organização

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
