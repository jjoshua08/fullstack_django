from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import Perfil


def papel_requerido(papel):
    def decorar(view):
        @wraps(view)
        def verificar(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            try:
                perfil = request.user.perfil
            except Perfil.DoesNotExist:
                raise PermissionDenied('Usuário sem perfil.')
            if perfil.papel != papel:
                raise PermissionDenied('Papel sem autorização.')
            return view(request, *args, **kwargs)
        return verificar
    return decorar
