WITH catalogo AS (
    SELECT id, NULLIF(lower(btrim(tipo_primario)), '') AS tipo
    FROM criaturas_criatura
),
lote AS (
    SELECT dataset_sha256, seed_simulacion
    FROM analytics_lotesimulacion WHERE activo
),
duelos AS (
    SELECT a.tipo AS t1, b.tipo AS t2, f.gano_primero
    FROM lote JOIN analytics_combatesimulado f USING (dataset_sha256)
    LEFT JOIN catalogo a ON a.id = f.luchador_1_id
    LEFT JOIN catalogo b ON b.id = f.luchador_2_id
),
totales AS (
    SELECT count(*) AS n_simulados,
           count(*) FILTER (WHERE t1 = t2) AS n_espejos,
           count(*) FILTER (WHERE t1 IS NULL OR t2 IS NULL) AS n_sin_clasificar
    FROM duelos
),
kpis AS (
    SELECT (SELECT count(*) FROM catalogo) AS n_catalogo,
           (SELECT count(*) FROM criaturas_combatlog) AS n_predicciones,
           l.dataset_sha256, l.seed_simulacion, t.*
    FROM totales t LEFT JOIN lote l ON TRUE
),
distribucion AS (
    SELECT tipo, count(*) AS criaturas FROM catalogo GROUP BY tipo
),
balance AS (
    SELECT p.tipo, count(*) AS participaciones,
           count(*) FILTER (WHERE p.gano) AS victorias
    FROM duelos d
    CROSS JOIN LATERAL (VALUES
        (d.t1, d.gano_primero), (d.t2, NOT d.gano_primero)
    ) AS p(tipo, gano)
    WHERE d.t1 <> d.t2
    GROUP BY p.tipo
)
SELECT k.*, d.tipo, d.criaturas,
       d.criaturas::numeric / NULLIF(k.n_catalogo, 0) AS proporcion_catalogo,
       COALESCE(b.victorias, 0) AS victorias,
       COALESCE(b.participaciones, 0) AS participaciones,
       b.victorias::numeric / NULLIF(b.participaciones, 0) AS win_rate
FROM kpis k
LEFT JOIN distribucion d ON TRUE
LEFT JOIN balance b ON b.tipo = d.tipo
ORDER BY d.tipo;
