# ticket/urls.py - полная версия
from django.urls import path, include
from . import views
from . import views_admin
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Публичные страницы
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('screening/<int:screening_id>/', views.screening_detail, name='screening_detail'),
    path('screening/<int:screening_id>/partial/', views.screening_partial, name='screening_partial'),
    path('book/', views.book_tickets, name='book_tickets'),
    path('download-ticket/', views.download_ticket, name='download_ticket'),
    path('about/', views.about, name='about'),

    # Профиль пользователя
    path('profile/', views.profile, name='profile'),
    path('download-ticket/<int:ticket_id>/', views.download_ticket_single, name='download_ticket_single'),
    path('download-ticket-group/<str:group_id>/', views.download_ticket_group, name='download_ticket_group'),
    path('ticket-group/<str:group_uuid>/refund/', views.request_group_refund, name='request_group_refund'),
    path('ticket/<int:ticket_id>/refund/', views.request_ticket_refund, name='request_ticket_refund'),
    path('ticket/<int:ticket_id>/cancel-refund/', views.cancel_refund_request, name='cancel_refund_request'),

    # Восстановление пароля и верификация
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification-code/', views.resend_verification_code, name='resend_verification_code'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/code/', views.password_reset_code, name='password_reset_code'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),

    # Панель менеджера
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/movies/', views.manager_movies, name='manager_movies'),
    path('manager/movies/add/', views.manager_movie_add, name='manager_movie_add'),
    path('manager/movies/<int:movie_id>/edit/', views.manager_movie_edit, name='manager_movie_edit'),
    path('manager/movies/<int:movie_id>/delete/', views.manager_movie_delete, name='manager_movie_delete'),
    path('manager/screenings/', views.manager_screenings, name='manager_screenings'),
    path('manager/screenings/add/', views.manager_screening_add, name='manager_screening_add'),
    path('manager/screenings/<int:screening_id>/edit/', views.manager_screening_edit, name='manager_screening_edit'),
    path('manager/screenings/<int:screening_id>/delete/', views.manager_screening_delete,
         name='manager_screening_delete'),
    path('manager/statistics/', views.manager_statistics, name='manager_statistics'),
    path('manager/api/countries/', views.manager_api_countries, name='manager_api_countries'),
    path('manager/api/quick-add-director/', views.manager_quick_add_director, name='manager_quick_add_director'),
    path('manager/api/quick-add-actor/', views.manager_quick_add_actor, name='manager_quick_add_actor'),
    path('manager/settings/', views.manager_settings, name='manager_settings'),

    # API для импорта фильмов
    path('manager/api/search-movie/', views.search_movie_api, name='search_movie_api'),
    path('manager/api/import-movie/', views.import_single_movie_api, name='import_single_movie_api'),
    path('manager/api/remaining-requests/', views.api_remaining_requests, name='api_remaining_requests'),
    path('manager/api/tokens/info/', views.api_token_info, name='api_token_info'),
    path('manager/api/tokens/add/', views.api_add_token, name='api_add_token'),
    path('manager/api/tokens/toggle/', views.api_toggle_token, name='api_toggle_token'),
    path('manager/api/tokens/delete/', views.api_delete_token, name='api_delete_token'),
    path('manager/api/tokens/set-current/', views.api_set_current_token, name='api_set_current_token'),

    # YooKassa
    path('payment/result/<uuid:group_uuid>/', views.payment_result, name='payment_result'),
    path('webhook/yookassa/', views.yookassa_webhook, name='yookassa_webhook'),

    # АДМИН-ПАНЕЛЬ (только для superuser)
    path('admin-panel/', include([
        path('', views_admin.admin_dashboard, name='admin_panel_dashboard'),
        path('users/', views_admin.admin_users, name='admin_panel_users'),
        path('users/<int:user_id>/edit/', views_admin.admin_user_edit, name='admin_panel_user_edit'),
        path('users/<int:user_id>/delete/', views_admin.admin_user_delete, name='admin_panel_user_delete'),
        path('users/<int:user_id>/toggle-block/', views_admin.admin_user_toggle_block,
             name='admin_panel_user_toggle_block'),
        path('roles/', views_admin.admin_roles, name='admin_panel_roles'),
        path('roles/<int:group_id>/edit/', views_admin.admin_role_edit, name='admin_panel_role_edit'),
        path('hall-types/', views_admin.admin_hall_types, name='admin_panel_hall_types'),
        path('hall-types/<int:ht_id>/edit/', views_admin.admin_hall_type_edit, name='admin_panel_hall_type_edit'),
        path('hall-types/<int:ht_id>/delete/', views_admin.admin_hall_type_delete, name='admin_panel_hall_type_delete'),
        path('age-ratings/', views_admin.admin_age_ratings, name='admin_panel_age_ratings'),
        path('age-ratings/<int:ar_id>/delete/', views_admin.admin_age_rating_delete,
             name='admin_panel_age_rating_delete'),
        path('genres/', views_admin.admin_genres, name='admin_panel_genres'),
        path('genres/<int:genre_id>/delete/', views_admin.admin_genre_delete, name='admin_panel_genre_delete'),
        path('countries/', views_admin.admin_countries, name='admin_panel_countries'),
        path('countries/<int:country_id>/delete/', views_admin.admin_country_delete, name='admin_panel_country_delete'),
        path('directors/', views_admin.admin_directors, name='admin_panel_directors'),
        path('directors/<int:director_id>/delete/', views_admin.admin_director_delete, name='admin_panel_director_delete'),
        path('actors/', views_admin.admin_actors, name='admin_panel_actors'),
        path('actors/<int:actor_id>/delete/', views_admin.admin_actor_delete, name='admin_panel_actor_delete'),
        path('logs/', views_admin.admin_logs, name='admin_panel_logs'),
        path('logs/export/', views_admin.admin_logs_export, name='admin_panel_logs_export'),
        path('ticket-statuses/', views_admin.admin_ticket_statuses, name='admin_panel_ticket_statuses'),
        path('payments/', views_admin.admin_payments, name='admin_panel_payments'),
        path('system-info/', views_admin.admin_system_info, name='admin_panel_system_info'),
        path('django-admin/', views_admin.admin_redirect_to_django, name='admin_redirect_to_django'),
        path('action-types/', views_admin.admin_action_types, name='admin_panel_action_types'),
        path('action-types/add/', views_admin.admin_action_type_add, name='admin_panel_action_type_add'),
        path('action-types/<int:at_id>/edit/', views_admin.admin_action_type_edit, name='admin_panel_action_type_edit'),
        path('action-types/<int:at_id>/delete/', views_admin.admin_action_type_delete, name='admin_panel_action_type_delete'),

        path('module-types/', views_admin.admin_module_types, name='admin_panel_module_types'),
        path('module-types/add/', views_admin.admin_module_type_add, name='admin_panel_module_type_add'),
        path('module-types/<int:mt_id>/edit/', views_admin.admin_module_type_edit, name='admin_panel_module_type_edit'),
        path('module-types/<int:mt_id>/delete/', views_admin.admin_module_type_delete, name='admin_panel_module_type_delete'),
        path('ticket-groups/', views_admin.admin_ticket_groups, name='admin_panel_ticket_groups'),
        path('ticket-groups/<uuid:group_uuid>/', views_admin.admin_ticket_group_detail, name='admin_panel_ticket_group_detail'),
        path('seats/', views_admin.admin_seats, name='admin_panel_seats'),
        path('seats/<int:seat_id>/delete/', views_admin.admin_seat_delete, name='admin_panel_seat_delete'),
        path('password-reset-requests/', views_admin.admin_password_reset_requests, name='admin_panel_password_reset_requests'),
        path('password-reset-requests/<int:pr_id>/delete/', views_admin.admin_password_reset_request_delete, name='admin_panel_password_reset_request_delete'),
        path('email-change-requests/', views_admin.admin_email_change_requests, name='admin_panel_email_change_requests'),
        path('email-change-requests/<int:ec_id>/delete/', views_admin.admin_email_change_request_delete, name='admin_panel_email_change_request_delete'),
        path('api-tokens/', views_admin.admin_api_tokens, name='admin_panel_api_tokens'),
        path('api-tokens/add/', views_admin.admin_api_token_add, name='admin_panel_api_token_add'),
        path('api-tokens/<int:token_id>/edit/', views_admin.admin_api_token_edit, name='admin_panel_api_token_edit'),
        path('api-tokens/<int:token_id>/delete/', views_admin.admin_api_token_delete, name='admin_panel_api_token_delete'),
        path('import-cache/', views_admin.admin_import_cache, name='admin_panel_import_cache'),
        path('import-cache/<int:cache_id>/delete/', views_admin.admin_import_cache_delete, name='admin_panel_import_cache_delete'),
        path('movies/', views_admin.admin_movies, name='admin_panel_movies'),
        path('movies/<int:movie_id>/edit/', views_admin.admin_movie_edit, name='admin_panel_movie_edit'),
        path('movies/<int:movie_id>/delete/', views_admin.admin_movie_delete, name='admin_panel_movie_delete'),
        path('movies/add/', views_admin.admin_movie_add, name='admin_panel_movie_add'),
        path('screenings/', views_admin.admin_screenings, name='admin_panel_screenings'),
        path('screenings/add/', views_admin.admin_screening_add, name='admin_panel_screening_add'),
        path('screenings/<int:screening_id>/edit/', views_admin.admin_screening_edit,
             name='admin_panel_screening_edit'),
        path('screenings/<int:screening_id>/delete/', views_admin.admin_screening_delete,
             name='admin_panel_screening_delete'),
        path('halls/', views_admin.admin_halls, name='admin_panel_halls'),
        path('halls/add/', views_admin.admin_hall_add, name='admin_panel_hall_add'),
        path('halls/<int:hall_id>/edit/', views_admin.admin_hall_edit, name='admin_panel_hall_edit'),
        path('halls/<int:hall_id>/delete/', views_admin.admin_hall_delete, name='admin_panel_hall_delete'),
        path('reports/', views_admin.admin_reports, name='admin_panel_reports'),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)