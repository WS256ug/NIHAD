from django.urls import path
from . import views

app_name = 'reports'
urlpatterns = [
    path('', views.report_list, name='list'),
    path('assessment/<int:pk>/generate/', views.assessment_action, {'action': 'generate'}, name='generate'),
    path('assessment/<int:pk>/correct/', views.assessment_action, {'action': 'correct'}, name='correct'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/print/', views.detail, {'output': 'print'}, name='print'),
    path('<int:pk>/pdf/', views.detail, {'output': 'pdf'}, name='pdf'),
    path('<int:pk>/comment/', views.report_action, {'action': 'comment'}, name='comment'),
    path('<int:pk>/review/', views.report_action, {'action': 'review'}, name='review'),
    path('<int:pk>/publish/', views.report_action, {'action': 'publish'}, name='publish'),
]
