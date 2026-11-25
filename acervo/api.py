from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard import kpis, ranking_autores
from .forms import filtrar_periodo
from .models import Livro
from .views import org_atual


class DashboardApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = org_atual(request)
        base = Livro.objects.filter(organizacao=org)
        base = filtrar_periodo(request, base)
        # Séries dependem da autorização por papel, prevista para a etapa 7.
        return Response({
            'kpis': kpis(org, base),
            'ranking': list(ranking_autores(org, base)),
        })
