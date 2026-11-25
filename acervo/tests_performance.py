"""Medições reproduzíveis somente no banco de testes; nenhum dado persistente."""
import logging
import os
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Organizacao, Perfil
from .models import Livro


class DesempenhoTests(TestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(nome='Organização de desempenho')
        self.outra = Organizacao.objects.create(nome='Outra organização')
        self.usuario = get_user_model().objects.create_user(username='desempenho')
        Perfil.objects.create(usuario=self.usuario, organizacao=self.org)
        self.criar_livros(3)
        Livro.objects.create(organizacao=self.outra, titulo='Externo', autor='Externo', ano=2020)
        self.livro = Livro.objects.filter(organizacao=self.org).first()
        self.client.force_login(self.usuario)

    def criar_livros(self, quantidade):
        Livro.objects.bulk_create([
            Livro(organizacao=self.org, titulo=f'Livro {i}', autor='Autora', ano=2020)
            for i in range(quantidade)
        ])
        Livro.objects.filter(organizacao=self.org).update(data_cadastro=date(2025, 1, 15))

    def base(self):
        return Livro.objects.filter(organizacao=self.org).order_by('pk')

    def relatar(self, *valores, **opcoes):
        if os.getenv('PERFORMANCE_REPORT') == '1':
            print(*valores, **opcoes)

    def test_relacao_sem_select_related(self):
        with self.assertNumQueries(4):
            nomes = [livro.organizacao.nome for livro in self.base()[:50]]
        self.assertEqual(nomes, [self.org.nome] * 3)

    def test_relacao_com_select_related(self):
        with self.assertNumQueries(1):
            nomes = [livro.organizacao.nome for livro in self.base().select_related('organizacao')[:50]]
        self.assertEqual(nomes, [self.org.nome] * 3)

    def test_sete_metodos_de_analise(self):
        # 1. Compilar SQL não executa a consulta.
        with self.assertNumQueries(0):
            sql = str(self.base().query)
        self.relatar('1. str(qs.query):', sql)

        # 2. DEBUG habilitado só neste bloco e queryset novo, sem cache de resultados.
        with override_settings(DEBUG=True):
            reset_queries()
            list(self.base())
            self.assertEqual(len(connection.queries), 1)
            self.relatar('2. connection.queries:', connection.queries)

        # 3. Demonstração equivalente com três livros da mesma organização.
        for otimizado in [False, True]:
            qs = self.base()
            if otimizado:
                qs = qs.select_related('organizacao')
            with CaptureQueriesContext(connection) as ctx:
                nomes = [livro.organizacao.nome for livro in qs[:50]]
            self.assertEqual(nomes, [self.org.nome] * 3)
            self.assertEqual(len(ctx), 1 if otimizado else 4)
            self.relatar('3. CaptureQueriesContext; select_related =', otimizado, 'consultas =', len(ctx))
            for consulta in ctx.captured_queries:
                self.relatar(consulta['sql'])
            self.assertEqual('INNER JOIN' in ctx[0]['sql'], otimizado)

        # 4. Mesmo logger da configuração local, capturado sem ruído na suíte.
        logger = logging.getLogger('django.db.backends')
        saida = StringIO()
        handler = logging.StreamHandler(saida)
        nivel = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            with override_settings(DEBUG=True):
                list(self.base())
        finally:
            logger.removeHandler(handler)
            logger.setLevel(nivel)
        self.assertIn('SELECT', saida.getvalue())
        self.relatar('4. django.db.backends:', saida.getvalue().strip())

        # 5. Plano real do SQLite; não fixamos texto/plano dependente da versão.
        self.relatar('5. EXPLAIN sem filtro:', Livro.objects.all().explain())
        self.relatar('5. EXPLAIN organização + período:', self.base().filter(
            data_cadastro__gte=date(2025, 1, 1), data_cadastro__lte=date(2025, 1, 31),
        ).explain())
        with connection.cursor() as cursor:
            indices = connection.introspection.get_constraints(cursor, Livro._meta.db_table)
        self.relatar('5. Índices:', {nome: info['columns'] for nome, info in indices.items() if info['index']})

        # 6. A UI é inspecionada manualmente; não alegamos validação visual.
        from importlib.metadata import version
        self.relatar('6. Debug Toolbar instalada:', version('django-debug-toolbar'), '; validação visual pendente')

        # 7. A falha didática é esperada e capturada; a suíte continua verde.
        with self.assertRaises(AssertionError) as falha:
            with self.assertNumQueries(1):
                for livro in self.base()[:50]:
                    livro.organizacao.nome
        self.relatar('7. Falha didática controlada:', str(falha.exception).splitlines()[0])
        with self.assertNumQueries(1):
            for livro in self.base().select_related('organizacao')[:50]:
                livro.organizacao.nome

    def test_telas_nao_crescem_com_quantidade_de_livros(self):
        rotas = ['lista', 'dashboard', 'novo_livro', 'editar_livro',
                 'admin:acervo_livro_changelist', 'admin:core_perfil_changelist']
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=['is_staff', 'is_superuser'])
        contagens = {}
        esperadas = dict(zip(rotas, [5, 8, 4, 5, 6, 5]))
        for tamanho in [3, 30]:
            if tamanho == 30:
                self.criar_livros(27)
            for rota in rotas:
                url = reverse(rota, args=[self.livro.pk]) if rota == 'editar_livro' else reverse(rota)
                with CaptureQueriesContext(connection) as ctx:
                    resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(len(ctx), esperadas[rota], rota)
                self.relatar('TELA', rota, 'livros =', tamanho, 'consultas =', len(ctx))
                if tamanho == 3:
                    contagens[rota] = len(ctx)
                    self.relatar('SQL DA TELA', rota, *[q['sql'] for q in ctx], sep='\n')
                else:
                    self.assertEqual(len(ctx), contagens[rota], rota)
                    with self.assertNumQueries(contagens[rota]):
                        self.client.get(url)
                if rota == 'dashboard':
                    self.assertEqual(resposta.context['kpis'], {'total': tamanho, 'disponiveis': tamanho})
                    self.assertEqual(sum(r['total'] for r in resposta.context['por_mes']), tamanho)
                    self.assertNotContains(resposta, 'Externo')
                if rota == 'lista':
                    self.assertEqual(len(resposta.context['livros']), tamanho)
                    self.assertNotContains(resposta, 'Externo')

    def test_dashboard_filtrado_preserva_metricas_e_isolamento(self):
        for periodo, total in [
            ({'inicio': '2025-01-15', 'fim': '2025-01-15'}, 3),
            ({'inicio': '2025-02-01'}, 0),
        ]:
            with self.subTest(periodo=periodo):
                with self.assertNumQueries(8):
                    resposta = self.client.get(reverse('dashboard'), periodo)
                self.assertEqual(resposta.context['kpis'], {'total': total, 'disponiveis': total})
                for chave in ['ranking', 'distribuicao', 'por_mes']:
                    self.assertEqual(sum(r['total'] for r in resposta.context[chave]), total)
                self.assertNotContains(resposta, 'Externo')
