from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser

from .decorators import papel_requerido
from .models import Organizacao, Perfil


class PapelTests(TestCase):
    def test_padrao_e_propriedade(self):
        u = get_user_model().objects.create_user(username='papel')
        p = Perfil.objects.create(usuario=u, organizacao=Organizacao.objects.create(nome='A'))
        self.assertEqual(p.papel, 'operador')
        self.assertFalse(p.eh_admin)
        p.papel = 'admin'
        self.assertTrue(p.eh_admin)
        u.refresh_from_db()
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_decorator_metadados_anonimo_e_sem_perfil(self):
        @papel_requerido('admin')
        def exemplo(request):
            """Descrição preservada."""
            return HttpResponse('ok')
        self.assertEqual(exemplo.__name__, 'exemplo')
        self.assertEqual(exemplo.__doc__, 'Descrição preservada.')
        r = RequestFactory().get('/restrito/')
        r.user = AnonymousUser()
        self.assertEqual(exemplo(r).status_code, 302)
        r.user = get_user_model().objects.create_user(username='sem_perfil')
        with self.assertRaises(PermissionDenied):
            exemplo(r)


class PapelMigrationTests(TransactionTestCase):
    def test_preserva_perfis_e_atribui_operador(self):
        anterior = [('core', '0002_perfil')]
        executor = MigrationExecutor(connection)
        finais = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(anterior)
            apps = executor.loader.project_state(anterior).apps
            Org = apps.get_model('core', 'Organizacao')
            User = apps.get_model('auth', 'User')
            PerfilAntigo = apps.get_model('core', 'Perfil')
            for i in range(2):
                org = Org.objects.create(nome=f'Legada {i}')
                u = User.objects.create(username=f'legado{i}', is_staff=bool(i), is_superuser=bool(i))
                PerfilAntigo.objects.create(usuario=u, organizacao=org)
            antes = list(PerfilAntigo.objects.order_by('pk').values())
            executor = MigrationExecutor(connection)
            executor.migrate(finais)
            PerfilNovo = executor.loader.project_state(finais).apps.get_model('core', 'Perfil')
            depois = list(PerfilNovo.objects.order_by('pk').values())
            for p in depois:
                self.assertEqual(p.pop('papel'), 'operador')
            self.assertEqual(antes, depois)
        finally:
            MigrationExecutor(connection).migrate(finais)
