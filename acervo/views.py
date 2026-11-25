import csv

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm, PeriodoForm, filtrar_periodo
from .dashboard import kpis, ranking_autores, serie_mensal, distribuicao_acervo
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


def org_atual(request):
    return request.user.perfil.organizacao


def proteger_celula_csv(valor):
    """Neutraliza fórmulas somente na saída; não altera o valor armazenado."""
    if isinstance(valor, str) and valor.startswith(('=', '+', '-', '@')):
        return "'" + valor
    return valor


def gerar_csv_livros(request):
    """Gerador interno, sem rota própria; autorização cabe à view de exportação."""
    org = org_atual(request)
    qs = filtrar_periodo(request, Livro.objects.filter(organizacao=org))
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="livros.csv"'
    w = csv.writer(resp)
    w.writerow(['Título', 'Autor', 'Ano', 'Tipo de acervo', 'Categoria',
                'Disponibilidade', 'Data de cadastro'])
    for livro in qs:
        w.writerow([
            proteger_celula_csv(livro.titulo),
            proteger_celula_csv(livro.autor),
            livro.ano,
            proteger_celula_csv(livro.get_tipo_acervo_display()),
            proteger_celula_csv(livro.get_categoria_display()),
            'Disponível' if livro.disponivel else 'Indisponível',
            livro.data_cadastro,
        ])
    return resp


@login_required
def exportar_csv(request):
    # Bloqueio temporário obrigatório: etapa 7 definirá a autorização por papel
    # antes de permitir chamar gerar_csv_livros(request). Não usar flags do Admin.
    raise PermissionDenied('Exportação indisponível até a definição dos papéis de negócio.')


@login_required
def dashboard(request):
    org = org_atual(request)
    base = Livro.objects.filter(organizacao=org)
    base = filtrar_periodo(request, base)
    por_mes_qs = serie_mensal(org, base)
    por_mes = [
        {'mes': r['mes'].strftime('%m/%Y'), 'total': r['total']}
        for r in por_mes_qs
    ]
    contexto = {
        'pode_exportar_csv': False,  # Liberação por papel somente na etapa 7.
        'form': PeriodoForm(request.GET),
        'kpis': kpis(org, base),
        'ranking': ranking_autores(org, base),
        'serie_mensal': por_mes_qs,
        'por_mes': por_mes,
        'distribuicao': distribuicao_acervo(org, base),
    }
    return render(request, 'acervo/dashboard.html', contexto)

@login_required
def lista_livros(request):
    org = org_atual(request)
    livros = Livro.objects.filter(organizacao=org)
    titulo = request.GET.get('titulo', '').strip()
    tipo_acervo = request.GET.get('tipo_acervo', '')
    categoria = request.GET.get('categoria', '')

    filtro = Q()
    if titulo:
        filtro &= Q(titulo__icontains=titulo)
    if tipo_acervo:
        filtro &= Q(tipo_acervo=tipo_acervo)
    if categoria:
        filtro &= Q(categoria=categoria)

    livros = livros.filter(filtro)

    return render(request, 'acervo/lista.html', {
        'livros': livros,
        'titulo': titulo,
        'tipo_acervo': tipo_acervo,
        'categoria': categoria,
        'tipos_acervo': Livro.TIPOS_ACERVO,
        'categorias': Livro.CATEGORIAS,
    })

@login_required
def novo_livro(request):
    org = org_atual(request)

    if request.method == 'POST':
        form = LivroForm(request.POST)

        if form.is_valid():
            livro = form.save(commit=False)
            livro.organizacao = org
            livro.save()
            form.save_m2m()

            return redirect('lista')
    else:
        form = LivroForm()

    return render(request, 'acervo/form.html', {
        'form': form
    })

@login_required
def editar_livro(request, pk):
    livro = get_object_or_404(
        Livro,
        pk=pk,
        organizacao=org_atual(request)
    )

    if request.method == 'POST':
        form = LivroForm(request.POST, instance=livro)

        if form.is_valid():
            form.save()
            return redirect('lista')
    else:
        form = LivroForm(instance=livro)

    return render(request, 'acervo/form.html', {
        'form': form
    })
