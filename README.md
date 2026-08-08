# 🐉 MithoWorld 2.0 — En Desarrollo Activo (rama `v2-architecture`)

![Estado](https://img.shields.io/badge/Estado-En_Desarrollo-yellow)
![Tests](https://img.shields.io/badge/Tests-pytest--django-blue)
![Arquitectura](https://img.shields.io/badge/Arquitectura-Monolito_Modular-orange)

> ⚠️ Esta rama está en desarrollo activo. Para la versión estable y en producción, ver la rama [`main`](https://github.com/Luis-e-rf/MithoWorld/tree/main).

## ¿Qué es esta rama?

Esta rama comprende la migración de un proyecto con ML predictivo (el Oráculo, que compara dos criaturas) hacia un motor de batallas RPG completo. La visión objetivo es que el sistema tenga en cuenta todos los stats de las criaturas, use esos combates para alimentar predicciones más precisas, permita consultar KPIs a través de dashboards publicados en Power BI, e integre IA para narrar las batallas y responder consultas sobre la base de datos.

Es la evolución natural del proyecto: de predecir qué criatura es mejor que otra (el Oráculo actual) a que efectivamente combatan, y usar esos resultados reales para alimentar modelos predictivos más precisos.

*(Esta sección describe el objetivo de la migración, no el estado actual — ver abajo qué está implementado hoy.)*

## Estado actual

- El plan de migración completo está documentado en [`ARCHITECTURE_MIGRATION.md`](./ARCHITECTURE_MIGRATION.md): contexto, estado actual de los servicios, arquitectura destino, y el paso a paso de ejecución.
- Se implementó testing automatizado para las apps `criaturas` y `oraculo`, que permitió detectar y corregir bugs reales de idempotencia.
- Se corrigió documentación técnica que no reflejaba el comportamiento real del sistema.

## Qué cambió respecto a v1

- **Pruebas automatizadas** que detectan bugs al ejecutar los scripts de creación de criaturas o del oráculo (antes no existía cobertura de tests).
- El script de carga de criaturas iniciales ahora **sincroniza los cambios** del CSV en cada ejecución, en vez de solo insertar una vez y quedar desactualizado.
- **Documentación específica y clara** de la migración, que incluye también el alcance completo del proyecto.

## Próximos pasos

Mover la app `criaturas` a `apps/game`, que comprende la creación del battle engine.

## Ver también

- Plan de migración detallado: [`ARCHITECTURE_MIGRATION.md`](./ARCHITECTURE_MIGRATION.md)
- Versión en producción: rama [`main`](https://github.com/Luis-e-rf/MithoWorld/tree/main)
