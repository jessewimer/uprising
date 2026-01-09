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
    
    # URL patterns for online order(s)
    path('process-orders/', views.process_orders, name='process_orders'),
    path('reprint-packing-slip/<str:order_id>/', views.reprint_packing_slip, name='reprint_packing_slip'), 
    path('reprocess-order/<str:order_id>/', views.reprocess_order, name='reprocess_order'),
    path('record-label-prints/', views.record_label_prints, name='record_label_prints'),
]
