# oraculo/urls.py
from django.urls import path
from .views import PrediccionCombateView

urlpatterns = [
    path('predecir/', PrediccionCombateView.as_view(), name='predecir_combate'),
]