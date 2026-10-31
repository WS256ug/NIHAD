from django.urls import path
from . import views

app_name = 'promotions'
urlpatterns = [
    path('', views.batch_list, name='list'),
    path('new/', views.batch_create, name='create'),
    path('<int:pk>/edit/', views.batch_edit, name='edit'),
    path('<int:pk>/', views.preview, name='preview'),
]
