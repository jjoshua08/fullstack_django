from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard import kpis, ranking_autores, serie_mensal
from .forms import filtrar_periodo
from .models import Livro
from .views import org_atual


class DashboardApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = org_atual(request)
        base = Livro.objects.filter(organizacao=org)
        base = filtrar_periodo(request, base)
        dados = {
            'kpis': kpis(org, base),
            'ranking': list(ranking_autores(org, base)),
        }
        if request.user.perfil.eh_admin:
            dados['por_mes'] = [
                {'mes': r['mes'].strftime('%m/%Y'), 'total': r['total']}
                for r in serie_mensal(org, base)
            ]
        return Response(dados)
