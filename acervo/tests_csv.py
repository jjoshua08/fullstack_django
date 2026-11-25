import csv
import os
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Organizacao, Perfil
from .models import Livro
from .views import gerar_csv_livros


class ExportacaoCsvTests(TestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(nome='CSV A')
        self.outra = Organizacao.objects.create(nome='CSV B')
        self.usuario = get_user_model().objects.create_user(username='csv_a')
        self.usuario_b = get_user_model().objects.create_user(username='csv_b')
        Perfil.objects.create(usuario=self.usuario, organizacao=self.org)
        Perfil.objects.create(usuario=self.usuario_b, organizacao=self.outra)
        self.livros = []
        for org, titulo, autor, data, tipo, disponivel in [
            (self.org, 'Programação, "Django"', 'João', date(2025, 1, 10), 'fisico', True),
            (self.org, '=1+1', '@Autora', date(2025, 2, 10), 'digital', False),
            (self.org, '+Livro', '-Autor', date(2025, 3, 10), 'fisico', True),
            (self.outra, 'Externo', 'Autor externo', date(2025, 2, 10), 'digital', True),
        ]:
            livro = Livro.objects.create(
                organizacao=org, titulo=titulo, autor=autor, ano=2020,
                tipo_acervo=tipo, categoria='800', disponivel=disponivel,
            )
            Livro.objects.filter(pk=livro.pk).update(data_cadastro=data)
            self.livros.append(livro)
        self.client.force_login(self.usuario)
        self.url = reverse('exportar_csv')
        self.factory = RequestFactory()

    def request(self, parametros=None, usuario=None):
        request = self.factory.get(self.url, parametros or {})
        # Instância nova evita ocultar consultas pelo cache de perfil/organização.
        request.user = get_user_model().objects.get(pk=(usuario or self.usuario).pk)
        return request

    def linhas(self, parametros=None, usuario=None):
        resposta = gerar_csv_livros(self.request(parametros, usuario))
        return list(csv.reader(StringIO(resposta.content.decode('utf-8'))))

    def test_geracao_cabecalhos_campos_e_caracteres_especiais(self):
        resposta = gerar_csv_livros(self.request({'fim': '2025-01-10'}))
        self.assertEqual(resposta['Content-Type'], 'text/csv')
        self.assertEqual(resposta['Content-Disposition'], 'attachment; filename="livros.csv"')
        self.assertEqual(list(csv.reader(StringIO(resposta.content.decode()))), [
            ['Título', 'Autor', 'Ano', 'Tipo de acervo', 'Categoria', 'Disponibilidade', 'Data de cadastro'],
            ['Programação, "Django"', 'João', '2020', 'Físico', '800 - Literatura', 'Disponível', '2025-01-10'],
        ])
        if os.getenv('CSV_REPORT') == '1':
            print('CSV REAL DO TESTE:\n' + resposta.content.decode())

    def test_isolamento(self):
        self.assertEqual(len(self.linhas({'organizacao': self.outra.pk})), 4)
        self.assertNotIn('Externo', str(self.linhas()))
        linhas_b = self.linhas(usuario=self.usuario_b)
        self.assertEqual(len(linhas_b), 2)
        self.assertEqual(linhas_b[1][0], 'Externo')

    def test_periodo_inclusivo_e_consistencia_com_kpi(self):
        for parametros, esperado in [
            ({'inicio': '2025-02-10'}, 2),
            ({'fim': '2025-02-10'}, 2),
            ({'inicio': '2025-02-10', 'fim': '2025-02-10'}, 1),
        ]:
            with self.subTest(parametros=parametros):
                linhas = self.linhas(parametros)
                dashboard = self.client.get(reverse('dashboard'), parametros)
                self.assertEqual(len(linhas) - 1, esperado)
                self.assertEqual(len(linhas) - 1, dashboard.context['kpis']['total'])

    def test_sem_registros_mantem_cabecalho(self):
        linhas = self.linhas({'inicio': '2030-01-01'})
        self.assertEqual(len(linhas), 1)
        self.assertEqual(len(linhas[0]), 7)

    def test_datas_invalidas_nao_aplicam_nenhum_limite(self):
        for parametros in [{'inicio': 'erro', 'fim': '2025-01-10'}, {'fim': '2025-02-30'}]:
            with self.subTest(parametros=parametros):
                self.assertEqual(len(self.linhas(parametros)) - 1, 3)
                dashboard = self.client.get(reverse('dashboard'), parametros)
                self.assertEqual(dashboard.context['kpis']['total'], 3)

    def test_formulas_neutralizadas_sem_modificar_banco(self):
        antes = list(Livro.objects.order_by('pk').values())
        linhas = self.linhas()
        self.assertIn(["'=1+1", "'@Autora", '2020', 'Digital', '800 - Literatura', 'Indisponível', '2025-02-10'], linhas)
        self.assertIn(["'+Livro", "'-Autor", '2020', 'Físico', '800 - Literatura', 'Disponível', '2025-03-10'], linhas)
        self.assertEqual(list(Livro.objects.order_by('pk').values()), antes)

    def test_sem_n_mais_um_ou_join_desnecessario(self):
        for total in [3, 30]:
            if total == 30:
                Livro.objects.bulk_create([
                    Livro(organizacao=self.org, titulo=f'Livro {i}', autor='Autora', ano=2020)
                    for i in range(27)
                ])
            request = self.request()
            with self.assertNumQueries(3), CaptureQueriesContext(connection) as ctx:
                resposta = gerar_csv_livros(request)
            self.assertEqual(len(list(csv.reader(StringIO(resposta.content.decode())))) - 1, total)
            self.assertFalse(any('JOIN' in q['sql'] for q in ctx))
            if os.getenv('CSV_REPORT') == '1':
                print(f'CSV: {total} livros, {len(ctx)} consultas')
                for q in ctx:
                    print(q['sql'])

    def test_anonimo_redirecionado(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f'{reverse("login")}?next={self.url}')

    def test_bloqueio_temporario_inclusive_staff_e_superusuario(self):
        for staff, superuser in [(False, False), (True, False), (True, True)]:
            self.usuario.is_staff = staff
            self.usuario.is_superuser = superuser
            self.usuario.save(update_fields=['is_staff', 'is_superuser'])
            with self.subTest(staff=staff, superuser=superuser):
                for metodo in ['get', 'post']:
                    resposta = getattr(self.client, metodo)(self.url, {'pode_exportar_csv': '1'})
                    self.assertEqual(resposta.status_code, 403)
                    self.assertNotIn('Content-Disposition', resposta)
                dashboard = self.client.get(reverse('dashboard'), {'pode_exportar_csv': '1'})
                self.assertFalse(dashboard.context['pode_exportar_csv'])
                self.assertNotContains(dashboard, 'Exportar CSV')

    def test_link_preparado_preserva_periodo_sem_liberar_rota(self):
        # Renderização isolada do ramo futuro; a view continua sempre bloqueada.
        request = self.request({'inicio': '2025-01-10', 'fim': '2025-02-10'})
        html = render_to_string('acervo/dashboard.html', {
            'pode_exportar_csv': True, 'por_mes': [],
        }, request=request)
        self.assertIn(self.url + '?inicio=2025-01-10&amp;fim=2025-02-10', html)
        self.assertEqual(self.client.get(self.url).status_code, 403)
