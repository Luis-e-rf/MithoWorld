from rest_framework import serializers


class LuchadoresSerializer(serializers.Serializer):
    luchador_1_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    luchador_2_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)


class ReferenciaCriaturaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class MetricasSerializer(serializers.Serializer):
    diferencial = serializers.JSONField()
    ventaja_elemental = serializers.JSONField()
    latencia_ms = serializers.FloatField()


class CombateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    creado_en = serializers.DateTimeField()
    luchador_1 = ReferenciaCriaturaSerializer(allow_null=True)
    luchador_2 = ReferenciaCriaturaSerializer(allow_null=True)
    ganador_predicho = ReferenciaCriaturaSerializer(allow_null=True)
    probabilidad = serializers.FloatField()
    metricas = MetricasSerializer(source='*')
