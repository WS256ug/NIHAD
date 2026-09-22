from django.urls import path
from . import views

app_name = 'expenses'
urlpatterns = [
    path('', views.overview, name='overview'),
    path('categories/<int:pk>/activate/', views.category_status, {'active': True}, name='category_activate'),
    path('categories/<int:pk>/deactivate/', views.category_status, {'active': False}, name='category_deactivate'),
    path('<str:kind>/', views.record_list, name='list'),
    path('<str:kind>/new/', views.record_form, name='create'),
    path('<str:kind>/<int:pk>/edit/', views.record_form, name='edit'),
    path('<str:kind>/<int:pk>/reverse/', views.reverse_record, name='reverse'),
]
