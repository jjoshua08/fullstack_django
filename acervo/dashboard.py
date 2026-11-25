"""Métricas do acervo: toda consulta começa pelo escopo da organização."""

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

from .models import Livro


def livros_da_organizacao(organizacao):
    """Recebe a organização do perfil autenticado, nunca um parâmetro do cliente."""
    return Livro.objects.filter(organizacao=organizacao)


def kpis(organizacao):
    return livros_da_organizacao(organizacao).aggregate(
        total=Count('id'),
        disponiveis=Count('id', filter=Q(disponivel=True)),
    )


def ranking_autores(organizacao):
    return (
        livros_da_organizacao(organizacao)
        .values('autor')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )


def serie_mensal(organizacao):
    return (
        livros_da_organizacao(organizacao)
        .annotate(mes=TruncMonth('data_cadastro'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )


def distribuicao_acervo(organizacao):
    return (
        livros_da_organizacao(organizacao)
        .values('tipo_acervo')
        .annotate(total=Count('id'))
    )
