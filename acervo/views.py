from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


def org_atual(request):
    return request.user.perfil.organizacao

@login_required
def lista_livros(request):
    org = org_atual(request)
    livros = Livro.objects.filter(organizacao=org)
    titulo = request.GET.get('titulo', '').strip()
    tipo_acervo = request.GET.get('tipo_acervo', '')
    categoria = request.GET.get('categoria', '')

    if titulo:
        livros = livros.filter(titulo__icontains=titulo)
    if tipo_acervo:
        livros = livros.filter(tipo_acervo=tipo_acervo)
    if categoria:
        livros = livros.filter(categoria=categoria)

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