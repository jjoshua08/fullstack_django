from django.contrib import admin
from .models import Livro

@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'organizacao')
    list_filter = ('organizacao',)

# Register your models here.
