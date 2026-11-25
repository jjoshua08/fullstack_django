from django.contrib import admin
from .models import Organizacao, Perfil

admin.site.register(Organizacao)
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    # Atribuir papéis exige a permissão administrativa de alteração de Perfil.
    fields = ('usuario', 'organizacao', 'papel')

# Register your models here.
