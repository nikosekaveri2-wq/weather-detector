from django.contrib import admin
from django.urls import path
from weathercore import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.home, name='home'),

    path('history/', views.history, name='history'),

    path(
        'history/delete/<int:id>/',
        views.delete_history,
        name='delete_history'
    ),

    path(
        'history/update/<int:id>/',
        views.update_history,
        name='update_history'
    ),
]