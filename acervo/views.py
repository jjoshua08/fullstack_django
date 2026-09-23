from django.db.models import Q
from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm

def lista_livros(request):
    livros = Livro.objects.all()
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

def novo_livro(request):
    if request.method == 'POST':
        form = LivroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista')
    else:
        form = LivroForm()
    return render(request, 'acervo/form.html', {'form': form})
