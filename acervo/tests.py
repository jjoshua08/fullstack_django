import secrets
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from core.models import Organizacao, Perfil
from .forms import LivroForm
from .models import Livro
from .dashboard import distribuicao_acervo, kpis, ranking_autores, serie_mensal


class AcervoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organizacao.objects.create(nome='Organização A de teste')
        cls.org_b = Organizacao.objects.create(nome='Organização B de teste')
        cls.usuario_a = get_user_model().objects.create_user(username='usuario_a')
        cls.usuario_b = get_user_model().objects.create_user(username='usuario_b')
        Perfil.objects.create(usuario=cls.usuario_a, organizacao=cls.org_a)
        Perfil.objects.create(usuario=cls.usuario_b, organizacao=cls.org_b)
        cls.digital = Livro.objects.create(
            titulo='Introdução à Literatura', autor='Ana', ano=2020,
            tipo_acervo='digital', categoria='800', organizacao=cls.org_a,
        )
        cls.fisico = Livro.objects.create(
            titulo='Literatura Brasileira', autor='Bia', ano=2021,
            tipo_acervo='fisico', categoria='800', disponivel=False, organizacao=cls.org_a,
        )
        cls.historia = Livro.objects.create(
            titulo='História Geral', autor='Caio', ano=2022,
            tipo_acervo='digital', categoria='900', organizacao=cls.org_a,
        )
        cls.livro_b = Livro.objects.create(
            titulo='Literatura da organização B', autor='Eva', ano=2024,
            tipo_acervo='digital', categoria='800', organizacao=cls.org_b,
        )

    def setUp(self):
        self.client.force_login(self.usuario_a)

    def dados_livro(self, **extras):
        return {
            'titulo': 'Novo livro', 'autor': 'Autor', 'ano': 2025,
            'tipo_acervo': 'digital', 'categoria': '800', **extras,
        }

    def test_filtros_individuais_e_combinados(self):
        casos = [
            ({}, [self.digital, self.fisico, self.historia]),
            ({'titulo': 'LITERAT'}, [self.digital, self.fisico]),
            ({'tipo_acervo': 'digital'}, [self.digital, self.historia]),
            ({'categoria': '800'}, [self.digital, self.fisico]),
            ({'titulo': 'literat', 'tipo_acervo': 'digital', 'categoria': '800'}, [self.digital]),
            ({'tipo_acervo': 'digi'}, []),
            ({'categoria': '80'}, []),
        ]
        for filtros, esperados in casos:
            with self.subTest(filtros=filtros):
                resposta = self.client.get(reverse('lista'), filtros)
                self.assertEqual(resposta.status_code, 200)
                self.assertCountEqual(resposta.context['livros'], esperados)

    def test_preserva_filtros_e_exibe_rotulos(self):
        resposta = self.client.get(reverse('lista'), {
            'titulo': 'Literatura', 'tipo_acervo': 'fisico', 'categoria': '800',
        })
        self.assertContains(resposta, 'value="Literatura"')
        self.assertContains(resposta, 'value="fisico" selected')
        self.assertContains(resposta, 'value="800" selected')
        self.assertContains(resposta, 'Físico — 800 - Literatura')
        self.assertContains(resposta, 'Indisponível')
        self.assertNotContains(resposta, self.digital.titulo)

    def test_cadastro_com_ambos_os_campos(self):
        resposta = self.client.get(reverse('novo_livro'))
        self.assertContains(resposta, 'name="tipo_acervo"')
        self.assertContains(resposta, 'name="categoria"')
        resposta = self.client.post(reverse('novo_livro'), {
            'titulo': 'Tecnologia', 'autor': 'Dora', 'ano': 2023,
            'tipo_acervo': 'digital', 'categoria': '600',
        })
        self.assertRedirects(resposta, reverse('lista'))
        livro = Livro.objects.get(titulo='Tecnologia')
        self.assertEqual((livro.tipo_acervo, livro.categoria), ('digital', '600'))
        self.assertTrue(livro.disponivel)
        self.assertEqual(livro.organizacao, self.org_a)

    def test_choices_rejeitam_valores_invalidos(self):
        form = LivroForm(data={
            'titulo': 'Teste', 'autor': 'Ana', 'ano': 2020,
            'tipo_acervo': 'outro', 'categoria': '999',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('tipo_acervo', form.errors)
        self.assertIn('categoria', form.errors)

    def test_listagem_isolada_para_ambos_os_usuarios(self):
        for usuario, livros in [
            (self.usuario_a, [self.digital, self.fisico, self.historia]),
            (self.usuario_b, [self.livro_b]),
        ]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse('lista'))
                self.assertEqual(resposta.status_code, 200)
                self.assertCountEqual(resposta.context['livros'], livros)

    def test_parametros_get_nao_alteram_organizacao(self):
        resposta = self.client.get(reverse('lista'), {
            'organizacao': self.org_b.pk, 'organizacao_id': self.org_b.pk,
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertCountEqual(resposta.context['livros'], [self.digital, self.fisico, self.historia])

    def test_cadastro_ignora_organizacao_enviada(self):
        self.assertNotIn('organizacao', LivroForm().fields)
        quantidade = Livro.objects.count()
        resposta = self.client.post(reverse('novo_livro'), self.dados_livro(
            organizacao=self.org_b.pk, organizacao_id=self.org_b.pk,
        ))
        self.assertRedirects(resposta, reverse('lista'))
        self.assertEqual(Livro.objects.count(), quantidade + 1)
        self.assertEqual(Livro.objects.get(titulo='Novo livro').organizacao, self.org_a)

    def test_edicao_propria_sem_transferencia_de_organizacao(self):
        url = reverse('editar_livro', args=[self.digital.pk])
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['form'].instance, self.digital)
        resposta = self.client.post(url, self.dados_livro(
            titulo='Título editado', organizacao=self.org_b.pk, organizacao_id=self.org_b.pk,
        ))
        self.assertRedirects(resposta, reverse('lista'))
        self.digital.refresh_from_db()
        self.assertEqual(self.digital.titulo, 'Título editado')
        self.assertEqual(self.digital.organizacao, self.org_a)

    def test_edicao_alheia_get_e_post_retornam_404(self):
        url = reverse('editar_livro', args=[self.livro_b.pk])
        antes = list(Livro.objects.order_by('pk').values())
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.dados_livro()).status_code, 404)
        self.assertEqual(list(Livro.objects.order_by('pk').values()), antes)

    def test_anonimos_redirecionados_sem_gravacao(self):
        cliente = Client()
        antes = list(Livro.objects.order_by('pk').values())
        for url in [reverse('lista'), reverse('novo_livro'), reverse('editar_livro', args=[self.digital.pk])]:
            for metodo in ['get', 'post']:
                with self.subTest(url=url, metodo=metodo):
                    resposta = getattr(cliente, metodo)(url, self.dados_livro() if metodo == 'post' else {})
                    self.assertRedirects(resposta, f'{reverse("login")}?next={url}')
        self.assertEqual(list(Livro.objects.order_by('pk').values()), antes)

    def test_login_comum_pelo_formulario(self):
        senha = secrets.token_urlsafe(24)
        self.usuario_a.set_password(senha)
        self.usuario_a.save(update_fields=['password'])
        cliente = Client()
        self.assertEqual(cliente.get(reverse('login')).status_code, 200)
        resposta = cliente.post(reverse('login'), {'username': self.usuario_a.username, 'password': senha}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.wsgi_request.user.pk, self.usuario_a.pk)
        self.assertCountEqual(resposta.context['livros'], [self.digital, self.fisico, self.historia])

    def test_choices_invalidos_na_view_nao_gravam(self):
        quantidade = Livro.objects.count()
        resposta = self.client.post(reverse('novo_livro'), self.dados_livro(tipo_acervo='outro', categoria='999'))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('tipo_acervo', resposta.context['form'].errors)
        self.assertIn('categoria', resposta.context['form'].errors)
        self.assertEqual(Livro.objects.count(), quantidade)

    def test_admin_global_para_superusuario_e_bloqueado_para_comum(self):
        url = reverse('admin:acervo_livro_changelist')
        self.assertRedirects(self.client.get(url), f'{reverse("admin:login")}?next={url}')
        superusuario = get_user_model().objects.create_superuser(username='admin_teste', email='')
        self.client.force_login(superusuario)
        for rota, modelo in [('admin:core_organizacao_changelist', Organizacao), ('admin:acervo_livro_changelist', Livro)]:
            resposta = self.client.get(reverse(rota))
            self.assertEqual(resposta.status_code, 200)
            self.assertCountEqual(resposta.context['cl'].queryset, modelo.objects.all())

    def test_organizacao_referenciada_protegida(self):
        with self.assertRaises(ProtectedError):
            self.org_a.delete()


class DashboardTests(TestCase):
    def setUp(self):
        self.org_a = Organizacao.objects.create(nome='Acervo A')
        self.org_b = Organizacao.objects.create(nome='Acervo B')
        self.org_vazia = Organizacao.objects.create(nome='Acervo vazio')
        # Seis autores com contagens distintas: não dependemos do desempate SQL.
        for numero, quantidade in enumerate([6, 5, 4, 3, 2, 1]):
            for indice in range(quantidade):
                livro = Livro.objects.create(
                    organizacao=self.org_a,
                    titulo=f'Livro {numero}-{indice}', autor=f'Autor {numero}',
                    ano=2020, disponivel=numero % 2 == 0,
                    tipo_acervo='fisico' if numero % 2 == 0 else 'digital',
                )
                # auto_now_add é exercitado separadamente; aqui fixamos o histórico.
                data = [date(2025, 2, 15), date(2024, 12, 31), date(2025, 1, 1)][numero % 3]
                Livro.objects.filter(pk=livro.pk).update(data_cadastro=data)
        livro_b = Livro.objects.create(
            organizacao=self.org_b, titulo='Livro externo', autor='Autor 0',
            ano=2020, disponivel=False, tipo_acervo='digital',
        )
        Livro.objects.filter(pk=livro_b.pk).update(data_cadastro=date(2023, 6, 10))

    def test_kpis_isolados_por_organizacao(self):
        self.assertEqual(kpis(self.org_a), {'total': 21, 'disponiveis': 12})
        self.assertEqual(kpis(self.org_b), {'total': 1, 'disponiveis': 0})

    def test_ranking_isolado_ordenado_e_limitado_a_cinco(self):
        self.assertEqual(list(ranking_autores(self.org_a)), [
            {'autor': f'Autor {numero}', 'total': total}
            for numero, total in enumerate([6, 5, 4, 3, 2])
        ])
        self.assertEqual(list(ranking_autores(self.org_b)), [
            {'autor': 'Autor 0', 'total': 1},
        ])

    def test_serie_mensal_isolada_e_cronologica(self):
        serie = list(serie_mensal(self.org_a))
        self.assertEqual(serie, [
            {'mes': date(2024, 12, 1), 'total': 7},
            {'mes': date(2025, 1, 1), 'total': 5},
            {'mes': date(2025, 2, 1), 'total': 9},
        ])
        self.assertEqual(sum(item['total'] for item in serie), kpis(self.org_a)['total'])
        self.assertEqual(list(serie_mensal(self.org_b)), [
            {'mes': date(2023, 6, 1), 'total': 1},
        ])

    def test_distribuicao_isolada_e_consistente_com_total(self):
        distribuicao = list(distribuicao_acervo(self.org_a))
        self.assertCountEqual(distribuicao, [
            {'tipo_acervo': 'fisico', 'total': 12},
            {'tipo_acervo': 'digital', 'total': 9},
        ])
        self.assertEqual(sum(item['total'] for item in distribuicao), kpis(self.org_a)['total'])
        self.assertEqual(list(distribuicao_acervo(self.org_b)), [
            {'tipo_acervo': 'digital', 'total': 1},
        ])

    def test_metricas_sem_livros(self):
        self.assertEqual(kpis(self.org_vazia), {'total': 0, 'disponiveis': 0})
        self.assertEqual(list(ranking_autores(self.org_vazia)), [])
        self.assertEqual(list(serie_mensal(self.org_vazia)), [])
        self.assertEqual(list(distribuicao_acervo(self.org_vazia)), [])

    def test_data_cadastro_automatica_preservada_na_edicao(self):
        inicio = date.today()
        livro = Livro.objects.create(
            organizacao=self.org_a, titulo='Novo', autor='Autora', ano=2025,
        )
        livro.refresh_from_db()
        self.assertIn(livro.data_cadastro, (inicio, date.today()))
        Livro.objects.filter(pk=livro.pk).update(data_cadastro=date(2025, 3, 12))
        livro.refresh_from_db()
        livro.titulo = 'Editado'
        livro.save()
        livro.refresh_from_db()
        self.assertEqual(livro.data_cadastro, date(2025, 3, 12))


class DataCadastroMigrationTests(TransactionTestCase):
    def test_migracao_preserva_registros_e_usa_data_da_execucao(self):
        anterior = [('acervo', '0006_alter_livro_organizacao')]
        atual = [('acervo', '0007_livro_data_cadastro')]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(anterior)
            apps = executor.loader.project_state(anterior).apps
            OrganizacaoAntiga = apps.get_model('core', 'Organizacao')
            LivroAntigo = apps.get_model('acervo', 'Livro')
            for numero in range(2):
                org = OrganizacaoAntiga.objects.create(nome=f'Legada {numero}')
                LivroAntigo.objects.create(
                    organizacao=org, titulo=f'Original {numero}', autor='Autor legado',
                    ano=1990 + numero, disponivel=bool(numero),
                    tipo_acervo='digital' if numero else 'fisico', categoria='800',
                )
            antes = list(LivroAntigo.objects.order_by('pk').values())
            inicio = date.today()
            executor = MigrationExecutor(connection)
            executor.migrate(atual)
            fim = date.today()
            LivroAtual = executor.loader.project_state(atual).apps.get_model('acervo', 'Livro')
            depois = list(LivroAtual.objects.order_by('pk').values())
            for registro in depois:
                self.assertIn(registro.pop('data_cadastro'), (inicio, fim))
            self.assertEqual(depois, antes)
        finally:
            # Devolve o esquema atual mesmo se uma asserção falhar.
            MigrationExecutor(connection).migrate(atual)
