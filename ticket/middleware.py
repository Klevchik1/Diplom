from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class ManagerAccessMiddleware:
    """
    Middleware для проверки доступа к панели менеджера
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Проверяем только URL'ы, начинающиеся с /manager/
        if request.path.startswith('/manager/'):
            if not request.user.is_authenticated:
                messages.error(request, 'Для доступа к панели менеджера необходимо войти в систему.')
                return redirect(f"{reverse('login')}?next={request.path}")

            # Проверяем, является ли пользователь менеджером (член группы Manager) или staff
            if not (request.user.is_staff or request.user.groups.filter(name='Manager').exists()):
                messages.error(request, 'У вас нет прав для доступа к панели менеджера.')
                logger.warning(f"Unauthorized access attempt to manager panel by user {request.user.email}")
                return redirect('home')

        return None