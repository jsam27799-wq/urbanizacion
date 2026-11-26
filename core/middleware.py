# Módulo: Aplica reglas transversales durante el procesamiento de solicitudes y respuestas.
from django.contrib.auth import logout
from django.shortcuts import redirect


# Agrupa la lógica y responsabilidades de active guardia middleware.
class ActiveGuardiaMiddleware:
    # Conserva la siguiente etapa del middleware para continuar el ciclo normal de la solicitud.
    def __init__(self, get_response):
        self.get_response = get_response

    # Cierra sesiones inactivas antes de delegar la solicitud al siguiente middleware.
    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_staff and not user.is_superuser and not user.is_active:
            logout(request)
            return redirect('login')
        return self.get_response(request)
