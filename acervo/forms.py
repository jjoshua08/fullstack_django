from datetime import date

from django import forms
from .models import Livro

class LivroForm(forms.ModelForm):
    class Meta:
        model = Livro
        fields = ['titulo', 'autor', 'ano', 'tipo_acervo', 'categoria']

    def clean_ano(self):
        ano = self.cleaned_data.get("ano")
        if ano > date.today().year:
            raise forms.ValidationError(
                "O ano de publicação não pode ser um ano futuro."
            )
        return ano
