# criaturas/serializers.py
from rest_framework import serializers
from .models import Criatura

# Serializador para el modelo Criatura
# Este serializador se encarga de convertir las instancias del modelo Criatura
# en formato JSON y viceversa, facilitando la API REST
class CriaturaSerializer(serializers.ModelSerializer):
    """
    Serializador que maneja la conversión de objetos Criatura a JSON y viceversa.
    Hereda de ModelSerializer para aprovechar la generación automática de campos
    basada en el modelo Criatura.
    """
    
    class Meta:
        # Especifica el modelo que este serializador va a manejar
        model = Criatura
        
        # '__all__' indica que se deben incluir todos los campos del modelo
        # en la serialización. Esto incluirá automáticamente todos los campos
        # definidos en el modelo Criatura
        fields = '__all__'