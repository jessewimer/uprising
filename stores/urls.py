from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('<str:store_name>/', views.dashboard, name='dashboard'),
    path('<int:store_num>/update/', views.update_store, name='update_store'),
]
