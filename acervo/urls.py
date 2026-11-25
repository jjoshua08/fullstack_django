from django.urls import path
from . import views
from .api import DashboardApi

urlpatterns = [
    path('api/dashboard/', DashboardApi.as_view(), name='dashboard_api'),
    path('dashboard/exportar-csv/', views.exportar_csv, name='exportar_csv'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', views.lista_livros, name='lista'),
    path('livros/novo/', views.novo_livro, name='novo_livro'),
    path('livros/<int:pk>/editar/', views.editar_livro,name='editar_livro'),
]
