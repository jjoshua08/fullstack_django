from django.contrib.auth.models import User
from django.db import models


class Organizacao(models.Model):
    nome = models.CharField(max_length=120)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class DaOrganizacao(models.Model):
    organizacao = models.ForeignKey(
        'core.Organizacao',
        on_delete=models.PROTECT
    )

    class Meta:
        abstract = True


class Perfil(models.Model):
    papel = models.CharField(
        max_length=8,
        choices=[('admin', 'Administrador'), ('operador', 'Operador')],
        default='operador',
    )

    @property
    def eh_admin(self):
        return self.papel == 'admin'

    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE
    )

    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.PROTECT
    )
