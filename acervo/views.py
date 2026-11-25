from django.db.models import Q
from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm, PeriodoForm, filtrar_periodo
from .dashboard import kpis, ranking_autores, serie_mensal, distribuicao_acervo
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


def org_atual(request):
    return request.user.perfil.organizacao


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
