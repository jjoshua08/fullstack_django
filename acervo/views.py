from django.shortcuts import render, redirect
from .models import Livro
from .forms import LivroForm

def lista_livros(request):
    livros = Livro.objects.all()
    return render(request, 'acervo/lista.html', {'livros': livros})

def novo_livro(request):
    if request.method == 'POST':
        form = LivroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista')
    else:
        form = LivroForm()
    return render(request, 'acervo/form.html', {'form': form})