import os

from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('screening/<int:screening_id>/', views.screening_detail, name='screening_detail'),
    path('screening/<int:screening_id>/partial/', views.screening_partial, name='screening_partial'),
    path('book/', views.book_tickets, name='book_tickets'),
    path('download-ticket/', views.download_ticket, name='download_ticket'),
    # Админка
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/movies/', views.movie_manage, name='movie_manage'),
    path('admin/movies/add/', views.movie_add, name='movie_add'),
    path('admin/movies/edit/<int:movie_id>/', views.movie_edit, name='movie_edit'),
    path('admin/movies/delete/<int:movie_id>/', views.movie_delete, name='movie_delete'),
    path('admin/hall/', views.hall_manage, name='hall_manage'),
    path('admin/hall/add/', views.hall_add, name='hall_add'),
    path('admin/hall/edit/<int:hall_id>/', views.hall_edit, name='hall_edit'),
    path('admin/hall/delete/<int:hall_id>/', views.hall_delete, name='hall_delete'),
    path('admin/screening/', views.screening_manage, name='screening_manage'),
    path('admin/screening/add/', views.screening_add, name='screening_add'),
    path('admin/screening/edit/<int:screening_id>/', views.screening_edit, name='screening_edit'),
    path('admin/screening/delete/<int:screening_id>/', views.screening_delete, name='screening_delete'),
    path('admin/screening/calculate-price/', views.calculate_screening_price, name='calculate_screening_price'),
    # Профиль
    path('profile/', views.profile, name='profile'),
    path('download-ticket/<int:ticket_id>/', views.download_ticket_single, name='download_ticket_single'),
    path('download-ticket-group/<str:group_id>/', views.download_ticket_group, name='download_ticket_group'),
    path('ticket-group/<str:group_uuid>/refund/', views.request_group_refund, name='request_group_refund'),
    path('ticket/<int:ticket_id>/refund/', views.request_ticket_refund, name='request_ticket_refund'),
    path('ticket/<int:ticket_id>/cancel-refund/', views.cancel_refund_request, name='cancel_refund_request'),
    # Почта
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification-code/', views.resend_verification_code, name='resend_verification_code'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/code/', views.password_reset_code, name='password_reset_code'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    # Руководство пользователя
    path('about/', views.about, name='about'),
    # Менеджер панель
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/movies/', views.manager_movies, name='manager_movies'),
    path('manager/movies/add/', views.manager_movie_add, name='manager_movie_add'),
    path('manager/movies/<int:movie_id>/edit/', views.manager_movie_edit, name='manager_movie_edit'),
    path('manager/movies/<int:movie_id>/delete/', views.manager_movie_delete, name='manager_movie_delete'),
    path('manager/screenings/', views.manager_screenings, name='manager_screenings'),
    path('manager/screenings/add/', views.manager_screening_add, name='manager_screening_add'),
    path('manager/screenings/<int:screening_id>/edit/', views.manager_screening_edit, name='manager_screening_edit'),
    path('manager/screenings/<int:screening_id>/delete/', views.manager_screening_delete, name='manager_screening_delete'),
    path('manager/statistics/', views.manager_statistics, name='manager_statistics'),
    path('manager/api/countries/', views.manager_api_countries, name='manager_api_countries'),
    path('manager/api/quick-add-director/', views.manager_quick_add_director, name='manager_quick_add_director'),
    path('manager/api/quick-add-actor/', views.manager_quick_add_actor, name='manager_quick_add_actor'),
    # API для импорта фильмов
    path('manager/api/search-movie/', views.search_movie_api, name='search_movie_api'),
    path('manager/api/import-movie/', views.import_single_movie_api, name='import_single_movie_api'),
    path('manager/api/remaining-requests/', views.api_remaining_requests, name='api_remaining_requests'),
    # Управление токенами API
    path('manager/api/tokens/info/', views.api_token_info, name='api_token_info'),
    path('manager/api/tokens/add/', views.api_add_token, name='api_add_token'),
    path('manager/api/tokens/toggle/', views.api_toggle_token, name='api_toggle_token'),
    path('manager/api/tokens/delete/', views.api_delete_token, name='api_delete_token'),
    path('manager/api/tokens/set-current/', views.api_set_current_token, name='api_set_current_token'),
    # YooKassa
    path('payment/result/<uuid:group_uuid>/', views.payment_result, name='payment_result'),
    path('webhook/yookassa/', views.yookassa_webhook, name='yookassa_webhook'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static('/backups/', document_root=os.path.join(settings.BASE_DIR, 'backups'))