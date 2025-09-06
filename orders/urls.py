from rest_framework import routers
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet
from . import views

router = routers.DefaultRouter()
router.register(r'order-data', OrderViewSet, basename='order')

urlpatterns = [
    # URL patterns for store orders
    path('api/get-order-id/<str:order_number>/', views.get_order_id_by_number, name='get_order_id'),
    path('generate-pdf/<int:order_id>/', views.generate_order_pdf, name='generate_order_pdf'),
    
    # URL patterns for online order
    path('process-orders/', views.process_orders, name='process_orders'),
    path('reprint-order/', views.reprint_order, name='reprint_order'),
    # path('print-range/', views.print_range, name='print_range'),

    # Old URL patterns for outdated functionality
    # path('api/', include(router.urls)),
    # path('process-online-orders/', views.process_online_orders, name='process_online_orders'),
]
