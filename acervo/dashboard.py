"""Métricas do acervo: toda consulta começa pelo escopo da organização."""

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

from .models import Livro


def livros_da_organizacao(organizacao, qs=None):
    """Recebe a organização do perfil autenticado, nunca um parâmetro do cliente."""
    if qs is None:
        qs = Livro.objects.all()
    return qs.filter(organizacao=organizacao)


def kpis(organizacao, qs=None):
    return livros_da_organizacao(organizacao, qs).aggregate(
        total=Count('id'),
        disponiveis=Count('id', filter=Q(disponivel=True)),
    )


def ranking_autores(organizacao, qs=None):
    return (
        livros_da_organizacao(organizacao, qs)
        .values('autor')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )


def serie_mensal(organizacao, qs=None):
    return (
        livros_da_organizacao(organizacao, qs)
        .annotate(mes=TruncMonth('data_cadastro'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )


def distribuicao_acervo(organizacao, qs=None):
    return (
        livros_da_organizacao(organizacao, qs)
        .values('tipo_acervo')
        .annotate(total=Count('id'))
    )
