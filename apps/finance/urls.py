from django.urls import path
from . import views

app_name = 'finance'
urlpatterns = [
    path('', views.overview, name='overview'),
    path('structures/', views.structure_list, name='structures'),
    path('structures/new/', views.structure_form, name='structure_create'),
    path('structures/<int:pk>/edit/', views.structure_form, name='structure_edit'),
    path('structures/<int:pk>/activate/', views.structure_status, {'active': True}, name='structure_activate'),
    path('structures/<int:pk>/deactivate/', views.structure_status, {'active': False}, name='structure_deactivate'),
    path('charges/new/', views.charge_form, name='charge_create'),
    path('charges/<int:pk>/pay/', views.payment_form, name='payment_create'),
    path('charges/<int:pk>/cancel/', views.reverse_record, {'kind': 'charge'}, name='charge_cancel'),
    path('students/<int:pk>/', views.statement, name='statement'),
    path('students/<int:pk>/pdf/', views.statement, {'output': 'pdf'}, name='statement_pdf'),
    path('payments/', views.payment_list, name='payments'),
    path('payments/<int:pk>/', views.receipt, name='receipt'),
    path('payments/<int:pk>/pdf/', views.receipt, {'output': 'pdf'}, name='receipt_pdf'),
    path('payments/<int:pk>/print/', views.receipt, {'output': 'print'}, name='receipt_print'),
    path('payments/<int:pk>/reverse/', views.reverse_record, {'kind': 'payment'}, name='payment_reverse'),
]
