"""Conferência independente das métricas, sem chamar funções de dashboard.py."""
import csv
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Perfil
from .models import Livro


class ValidacaoFinalTests(TestCase):
    def setUp(self):
        self.cenarios = []
        for nome, quantidade in [('A', 3), ('B', 5)]:
            org = Organizacao.objects.create(nome=nome)
            usuario = get_user_model().objects.create_user(username=f'final_{nome}')
            Perfil.objects.create(usuario=usuario, organizacao=org, papel='admin')
            self.cenarios.append((org, usuario, quantidade))
            for i in range(quantidade):
                livro = Livro.objects.create(
                    organizacao=org, titulo=f'{nome} {i}', autor='Ana' if i < 2 else 'Bia',
                    ano=2020, tipo_acervo='fisico' if i % 2 == 0 else 'digital',
                    disponivel=i % 2 == 0,
                )
                Livro.objects.filter(pk=livro.pk).update(data_cadastro=date(2025, 1 if i < 2 else 2, 10))

    def test_html_api_csv_conferem_com_sql_independente(self):
        for org, usuario, quantidade in self.cenarios:
            self.client.force_login(usuario)
            for parametros in [{}, {'inicio': '2025-02-01', 'fim': '2025-02-28'}]:
                with self.subTest(organizacao=org.nome, periodo=parametros):
                    condicao = 'organizacao_id = %s'
                    argumentos = [org.pk]
                    if parametros:
                        condicao += ' AND data_cadastro >= %s AND data_cadastro <= %s'
                        argumentos += [parametros['inicio'], parametros['fim']]
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT COUNT(*), COALESCE(SUM(disponivel), 0) FROM acervo_livro WHERE ' + condicao, argumentos)
                        total, disponiveis = cursor.fetchone()
                        cursor.execute('SELECT autor, COUNT(*) FROM acervo_livro WHERE ' + condicao + ' GROUP BY autor ORDER BY COUNT(*) DESC LIMIT 5', argumentos)
                        ranking = cursor.fetchall()
                        cursor.execute('SELECT tipo_acervo, COUNT(*) FROM acervo_livro WHERE ' + condicao + ' GROUP BY tipo_acervo', argumentos)
                        distribuicao = cursor.fetchall()
                        cursor.execute("SELECT substr(data_cadastro, 1, 7), COUNT(*) FROM acervo_livro WHERE " + condicao + ' GROUP BY 1 ORDER BY 1', argumentos)
                        serie = cursor.fetchall()
                    self.assertEqual(total, quantidade - 2 if parametros else quantidade)
                    html = self.client.get(reverse('dashboard'), parametros)
                    api = self.client.get(reverse('dashboard_api'), parametros).json()
                    esperado = {'total': total, 'disponiveis': disponiveis}
                    self.assertEqual(html.context['kpis'], esperado)
                    self.assertEqual(api['kpis'], esperado)
                    ranking_esperado = [{'autor': autor, 'total': n} for autor, n in ranking]
                    self.assertEqual(list(html.context['ranking']), ranking_esperado)
                    self.assertEqual(api['ranking'], ranking_esperado)
                    self.assertCountEqual(list(html.context['distribuicao']), [
                        {'tipo_acervo': tipo, 'total': n} for tipo, n in distribuicao
                    ])
                    serie_esperada = [{'mes': f'{mes[5:7]}/{mes[:4]}', 'total': n} for mes, n in serie]
                    self.assertEqual(html.context['por_mes'], serie_esperada)
                    self.assertEqual(api['por_mes'], serie_esperada)
                    resposta_csv = self.client.get(reverse('exportar_csv'), parametros)
                    self.assertEqual(resposta_csv.status_code, 200)
                    linhas = list(csv.reader(StringIO(resposta_csv.content.decode())))
                    self.assertEqual(len(linhas) - 1, total)
                    self.assertTrue(all(linha[0].startswith(org.nome + ' ') for linha in linhas[1:]))
