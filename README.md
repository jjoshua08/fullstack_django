# Biblioteca

Projeto acadêmico de Engenharia de Software desenvolvido em Django para gerenciar acervos de diferentes organizações.

## Funcionalidades

- Cadastro e edição de livros com título, autor, ano, tipo (físico ou digital) e categoria, sem permitir anos futuros.
- Listagem com disponibilidade e filtros por título, tipo e categoria.
- Autenticação e acesso ao acervo restrito à organização do usuário.
- Dashboard, API de métricas, exportação CSV e administração pelo Django Admin.

Administradores e operadores consultam, cadastram e editam livros da própria organização e acessam totais, ranking de autores e distribuição por tipo. Apenas administradores acessam a série mensal e exportam CSV. Novos perfis são operadores; usuários sem perfil não acessam o acervo. O papel de administrador é independente das permissões globais do Django Admin: mesmo superusuários precisam de perfil e papel adequado.

## Tecnologias

Python, Django, SQLite, Django REST Framework, HTML, CSS, JavaScript, Chart.js, python-dotenv e Django Debug Toolbar (opcional). Dependências em `requirements.txt`.

## Perguntas de negócio e métricas do dashboard

Conforme o slide 5 da Aula 17:

1. **Quantos livros estão cadastrados e quantos estão disponíveis?** Cartões com o total de livros e a quantidade marcada como disponível.
2. **Quais autores possuem mais livros no acervo?** Ranking dos cinco autores com mais livros, em ordem decrescente de quantidade.
3. **Quantos livros foram cadastrados por mês?** Série mensal em gráfico de barras, ordenada cronologicamente e disponível para administradores.
4. **Como os livros estão distribuídos por tipo de acervo?** Contagem de livros físicos e digitais.

As métricas consideram a organização do usuário autenticado. Dashboard, API e CSV aceitam `inicio` e `fim` opcionais e inclusivos (`AAAA-MM-DD`), pela data de cadastro. Datas inválidas impedem a aplicação do período e geram erros no formulário do dashboard.

**Observação:** novos livros recebem a data de cadastro automaticamente; livros anteriores à migração receberam a data de sua aplicação, sem representar o cadastro histórico.

## API e exportação CSV

- `/api/dashboard/`: API autenticada com `kpis`, `ranking` e, para administradores, `por_mes`. Após o login, use `?format=json` para visualizar JSON.
- `/dashboard/exportar-csv/`: exporta `livros.csv` com título, autor, ano, tipo, categoria, disponibilidade e data de cadastro, conforme organização e período.

## Instalação e execução

Na pasta do projeto:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows, ative com `.venv\Scripts\activate`.

Crie ou ajuste o `.env` na raiz, com chave secreta própria e banco SQLite:

```dotenv
SECRET_KEY=substitua-por-uma-chave-secreta-local
DB_NAME=biblioteca_db
DJANGO_DEBUG=1
DJANGO_ENV=development
```

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Em `http://127.0.0.1:8000/admin/`, cadastre uma organização e um perfil para o usuário, incluindo o superusuário, com organização e papel desejados.

Faça login em `http://127.0.0.1:8000/accounts/login/`. Rotas principais: `/` (acervo), `/livros/novo/` (cadastro), `/livros/<id>/editar/` (edição pelo identificador) e `/dashboard/` (indicadores e período).

## Testes

Com o ambiente virtual ativo e o `.env` configurado:

```bash
python manage.py test
```

A suíte cobre cadastro, edição, formulários, isolamento entre organizações, métricas, filtros, permissões, API, CSV e consultas ao banco.
