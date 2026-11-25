import csv
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Perfil
from .models import Livro


class DashboardPapeisTests(TestCase):
    def setUp(self):
        self.usuarios = {}
        for nome in ['A', 'B']:
            org = Organizacao.objects.create(nome=nome)
            for papel in ['admin', 'operador']:
                u = get_user_model().objects.create_user(username=nome + papel)
                Perfil.objects.create(usuario=u, organizacao=org, papel=papel)
                self.usuarios[nome, papel] = u
            for mes in [1, 2]:
                livro = Livro.objects.create(organizacao=org, titulo=f'Livro {nome}', autor=f'Autor {nome}', ano=2020)
                Livro.objects.filter(pk=livro.pk).update(data_cadastro=date(2025, mes, 10))

    def test_html_api_e_csv_por_papel_e_organizacao(self):
        for (nome, papel), usuario in self.usuarios.items():
            with self.subTest(nome=nome, papel=papel):
                self.client.force_login(usuario)
                periodo = {'inicio': '2025-02-10', 'fim': '2025-02-10'}
                html = self.client.get(reverse('dashboard'), periodo)
                api = self.client.get(reverse('dashboard_api'), periodo).json()
                self.assertEqual(html.context['kpis']['total'], 1)
                self.assertEqual(api['kpis'], html.context['kpis'])
                self.assertEqual(api['ranking'], [{'autor': f'Autor {nome}', 'total': 1}])
                self.assertEqual(sum(r['total'] for r in html.context['distribuicao']), 1)
                resposta = self.client.get(reverse('exportar_csv'), periodo)
                if papel == 'admin':
                    self.assertTrue(html.context['mostra_series'])
                    self.assertEqual(api['por_mes'], [{'mes': '02/2025', 'total': 1}])
                    self.assertEqual(html.context['por_mes'], api['por_mes'])
                    self.assertContains(html, 'id="dados-mes"')
                    self.assertContains(html, 'Exportar CSV')
                    self.assertEqual(resposta.status_code, 200)
                    linhas = list(csv.reader(StringIO(resposta.content.decode())))
                    self.assertEqual(len(linhas), 2)
                    self.assertEqual(linhas[1][0], f'Livro {nome}')
                else:
                    self.assertFalse(html.context['mostra_series'])
                    self.assertNotIn('por_mes', html.context)
                    self.assertNotIn('serie_mensal', html.context)
                    self.assertNotIn('por_mes', api)
                    self.assertNotContains(html, 'id="dados-mes"')
                    self.assertNotContains(html, 'id="graf"')
                    self.assertNotContains(html, 'js/dashboard.js')
                    self.assertNotContains(html, 'Exportar CSV')
                    self.assertEqual(resposta.status_code, 403)

    def test_operador_nao_calcula_serie_e_consultas_constantes(self):
        u = self.usuarios['A', 'operador']
        self.client.force_login(u)
        with patch('acervo.views.serie_mensal', side_effect=AssertionError('Série proibida')):
            with self.assertNumQueries(7):
                self.client.get(reverse('dashboard'))
        with patch('acervo.api.serie_mensal', side_effect=AssertionError('Série proibida')):
            self.assertEqual(self.client.get(reverse('dashboard_api')).status_code, 200)
        org = u.perfil.organizacao
        Livro.objects.bulk_create([Livro(organizacao=org, titulo='Extra', autor='Extra', ano=2020) for _ in range(20)])
        with self.assertNumQueries(7):
            self.client.get(reverse('dashboard'))

    def test_sem_perfil_recebe_403(self):
        self.client.force_login(get_user_model().objects.create_user(username='semperfil'))
        for rota in ['dashboard', 'dashboard_api', 'exportar_csv']:
            self.assertEqual(self.client.get(reverse(rota)).status_code, 403)

    def test_operador_nao_altera_papel_por_requisicao(self):
        u = self.usuarios['A', 'operador']
        self.client.force_login(u)
        self.client.post(reverse('dashboard'), {'papel': 'admin'})
        self.assertEqual(self.client.get(reverse('exportar_csv'), {'papel': 'admin'}).status_code, 403)
        u.perfil.refresh_from_db()
        self.assertEqual(u.perfil.papel, 'operador')
        self.assertEqual(self.client.get(reverse('admin:core_perfil_change', args=[u.perfil.pk])).status_code, 302)

    def test_admin_de_organizacao_nao_ganha_acesso_ao_django_admin(self):
        self.client.force_login(self.usuarios['A', 'admin'])
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_staff_e_superusuario_operadores_sem_privilegio_de_negocio(self):
        u = self.usuarios['A', 'operador']
        for superusuario in [False, True]:
            u.is_staff = True
            u.is_superuser = superusuario
            u.save(update_fields=['is_staff', 'is_superuser'])
            self.client.force_login(u)
            html = self.client.get(reverse('dashboard'))
            self.assertNotIn('por_mes', html.context)
            self.assertNotContains(html, 'Exportar CSV')
            self.assertNotIn('por_mes', self.client.get(reverse('dashboard_api')).json())
            self.assertEqual(self.client.get(reverse('exportar_csv')).status_code, 403)
