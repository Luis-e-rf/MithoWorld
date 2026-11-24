from django.urls import path

from .views import CronicaView

urlpatterns = [path('combates/<int:pk>/cronica/', CronicaView.as_view(), name='cronica_combate')]
