from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_livros, name='lista'),
    path('livros/novo/', views.novo_livro, name='novo_livro'),
    path('livros/<int:pk>/editar/', views.editar_livro,name='editar_livro'),
]