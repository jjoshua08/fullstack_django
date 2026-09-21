from django.test import TestCase
from django.urls import reverse

from .forms import LivroForm
from .models import Livro


class AcervoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.digital = Livro.objects.create(
            titulo='Introdução à Literatura', autor='Ana', ano=2020,
            tipo_acervo='digital', categoria='800',
        )
        cls.fisico = Livro.objects.create(
            titulo='Literatura Brasileira', autor='Bia', ano=2021,
            tipo_acervo='fisico', categoria='800', disponivel=False,
        )
        cls.historia = Livro.objects.create(
            titulo='História Geral', autor='Caio', ano=2022,
            tipo_acervo='digital', categoria='900',
        )

    def test_filtros_individuais_e_combinados(self):
        casos = [
            ({}, [self.digital, self.fisico, self.historia]),
            ({'titulo': 'LITERAT'}, [self.digital, self.fisico]),
            ({'tipo_acervo': 'digital'}, [self.digital, self.historia]),
            ({'categoria': '800'}, [self.digital, self.fisico]),
            ({'titulo': 'literat', 'tipo_acervo': 'digital', 'categoria': '800'}, [self.digital]),
            ({'tipo_acervo': 'digi'}, []),
            ({'categoria': '80'}, []),
        ]
        for filtros, esperados in casos:
            with self.subTest(filtros=filtros):
                resposta = self.client.get(reverse('lista'), filtros)
                self.assertEqual(resposta.status_code, 200)
                self.assertCountEqual(resposta.context['livros'], esperados)

    def test_preserva_filtros_e_exibe_rotulos(self):
        resposta = self.client.get(reverse('lista'), {
            'titulo': 'Literatura', 'tipo_acervo': 'fisico', 'categoria': '800',
        })
        self.assertContains(resposta, 'value="Literatura"')
        self.assertContains(resposta, 'value="fisico" selected')
        self.assertContains(resposta, 'value="800" selected')
        self.assertContains(resposta, 'Físico — 800 - Literatura')
        self.assertContains(resposta, 'Indisponível')
        self.assertNotContains(resposta, self.digital.titulo)

    def test_cadastro_com_ambos_os_campos(self):
        resposta = self.client.get(reverse('novo_livro'))
        self.assertContains(resposta, 'name="tipo_acervo"')
        self.assertContains(resposta, 'name="categoria"')
        resposta = self.client.post(reverse('novo_livro'), {
            'titulo': 'Tecnologia', 'autor': 'Dora', 'ano': 2023,
            'tipo_acervo': 'digital', 'categoria': '600',
        })
        self.assertRedirects(resposta, reverse('lista'))
        livro = Livro.objects.get(titulo='Tecnologia')
        self.assertEqual((livro.tipo_acervo, livro.categoria), ('digital', '600'))
        self.assertTrue(livro.disponivel)

    def test_choices_rejeitam_valores_invalidos(self):
        form = LivroForm(data={
            'titulo': 'Teste', 'autor': 'Ana', 'ano': 2020,
            'tipo_acervo': 'outro', 'categoria': '999',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('tipo_acervo', form.errors)
        self.assertIn('categoria', form.errors)
