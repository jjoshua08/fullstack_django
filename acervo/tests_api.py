import json
import os
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Perfil
from .models import Livro


class DashboardApiTests(TestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(nome='API A')
        outra = Organizacao.objects.create(nome='API B')
        self.usuario = get_user_model().objects.create_user(username='api_a')
        self.usuario_b = get_user_model().objects.create_user(username='api_b')
        Perfil.objects.create(usuario=self.usuario, organizacao=self.org)
        Perfil.objects.create(usuario=self.usuario_b, organizacao=outra)
        for numero, quantidade in enumerate([6, 5, 4, 3, 2, 1]):
            for indice in range(quantidade):
                livro = Livro.objects.create(
                    organizacao=self.org, titulo=f'Livro {numero}-{indice}',
                    autor=f'Autor {numero}', ano=2020, disponivel=numero % 2 == 0,
                )
                Livro.objects.filter(pk=livro.pk).update(data_cadastro=date(2025, numero + 1, 10))
        livro = Livro.objects.create(
            organizacao=outra, titulo='Externo', autor='Autor externo', ano=2020,
        )
        Livro.objects.filter(pk=livro.pk).update(data_cadastro=date(2025, 2, 10))
        self.client.force_login(self.usuario)
        self.url = reverse('dashboard_api')

    def get_api(self, parametros=None):
        return self.client.get(self.url, parametros or {}, HTTP_ACCEPT='application/json')

    def test_acesso_autenticado_json_e_kpis(self):
        resposta = self.get_api()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/json')
        self.assertEqual(resposta.json()['kpis'], {'total': 21, 'disponiveis': 12})
        if os.getenv('API_REPORT') == '1':
            print(json.dumps(resposta.json(), ensure_ascii=False, indent=2))

    def test_anonimo_bloqueado(self):
        self.client.logout()
        resposta = self.get_api()
        # SessionAuthentication é o primeiro mecanismo padrão: anônimo recebe 403.
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn('kpis', resposta.json())

    def test_isolamento_e_parametros_nao_trocam_organizacao(self):
        self.client.force_login(self.usuario_b)
        resposta = self.get_api({'organizacao': self.org.pk, 'organizacao_id': self.org.pk})
        self.assertEqual(resposta.json(), {
            'kpis': {'total': 1, 'disponiveis': 1},
            'ranking': [{'autor': 'Autor externo', 'total': 1}],
        })

    def test_periodo_inclusivo_e_consistencia_com_html(self):
        for parametros, total, disponiveis in [
            ({}, 21, 12),
            ({'inicio': '2025-03-10'}, 10, 6),
            ({'fim': '2025-02-10'}, 11, 6),
            ({'inicio': '2025-02-10', 'fim': '2025-03-10'}, 9, 4),
        ]:
            with self.subTest(parametros=parametros):
                dados = self.get_api(parametros).json()
                html = self.client.get(reverse('dashboard'), parametros)
                self.assertEqual(dados['kpis'], {'total': total, 'disponiveis': disponiveis})
                self.assertEqual(dados['kpis'], html.context['kpis'])
                self.assertEqual(dados['ranking'], list(html.context['ranking']))

    def test_ranking_limitado_a_cinco(self):
        self.assertEqual(self.get_api().json()['ranking'], [
            {'autor': f'Autor {i}', 'total': total}
            for i, total in enumerate([6, 5, 4, 3, 2])
        ])

    def test_periodo_vazio_e_organizacao_sem_livros(self):
        vazio = {'kpis': {'total': 0, 'disponiveis': 0}, 'ranking': []}
        self.assertEqual(self.get_api({'inicio': '2030-01-01'}).json(), vazio)
        self.assertEqual(self.get_api({'inicio': '2025-06-10', 'fim': '2025-01-10'}).json(), vazio)
        Livro.objects.filter(organizacao=self.org).delete()
        self.assertEqual(self.get_api().json(), vazio)

    def test_datas_invalidas_preservam_comportamento_anterior(self):
        for parametros in [
            {'inicio': 'invalida', 'fim': '2025-01-10'},
            {'inicio': '2025-06-10', 'fim': '2025-02-30'},
        ]:
            with self.subTest(parametros=parametros):
                resposta = self.get_api(parametros)
                self.assertEqual(resposta.status_code, 200)
                html = self.client.get(reverse('dashboard'), parametros)
                self.assertEqual(resposta.json()['kpis'], {'total': 21, 'disponiveis': 12})
                self.assertEqual(resposta.json()['kpis'], html.context['kpis'])

    def test_serie_nao_exposta_e_csv_bloqueado_inclusive_para_superusuario(self):
        for privilegiado in [False, True]:
            self.usuario.is_staff = privilegiado
            self.usuario.is_superuser = privilegiado
            self.usuario.save(update_fields=['is_staff', 'is_superuser'])
            resposta = self.get_api({'mostra_series': '1', 'papel': 'admin'})
            self.assertEqual(set(resposta.json()), {'kpis', 'ranking'})
            self.assertNotIn('serie_mensal', resposta.json())
            self.assertNotIn('por_mes', resposta.json())
            self.assertEqual(self.client.get(reverse('exportar_csv')).status_code, 403)

    def test_post_nao_permitido(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
