WITH base AS (
    SELECT id, tipo_primario, ataque, defensa, velocidad, salud,
           CAST(ataque AS bigint) + defensa + velocidad + salud AS score_total
    FROM criaturas_criatura
),
ventanas AS (
    SELECT base.*,
           COUNT(*) OVER () AS n_catalogo,
           RANK() OVER (ORDER BY score_total DESC) AS puesto_global,
           PERCENT_RANK() OVER (ORDER BY score_total ASC) AS percentil_global,
           COUNT(*) OVER elemento AS n_elemento,
           AVG(ataque) OVER elemento AS media_ataque,
           AVG(defensa) OVER elemento AS media_defensa,
           AVG(velocidad) OVER elemento AS media_velocidad,
           AVG(salud) OVER elemento AS media_salud
    FROM base
    WINDOW elemento AS (PARTITION BY tipo_primario)
)
SELECT ventanas.*,
       ataque - media_ataque AS delta_ataque,
       defensa - media_defensa AS delta_defensa,
       velocidad - media_velocidad AS delta_velocidad,
       salud - media_salud AS delta_salud
FROM ventanas
WHERE id = %s;
