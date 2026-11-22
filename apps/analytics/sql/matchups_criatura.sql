WITH lote AS (
    SELECT dataset_sha256, seed_simulacion FROM analytics_lotesimulacion WHERE activo
),
duelos AS (
    SELECT f.luchador_2_id AS rival_id, CASE WHEN f.gano_primero THEN 1 ELSE 0 END AS victoria
    FROM analytics_combatesimulado f JOIN lote USING (dataset_sha256)
    WHERE f.luchador_1_id = %(criatura_id)s
    UNION ALL
    SELECT f.luchador_1_id, CASE WHEN f.gano_primero THEN 0 ELSE 1 END
    FROM analytics_combatesimulado f JOIN lote USING (dataset_sha256)
    WHERE f.luchador_2_id = %(criatura_id)s
),
resumen AS (
    SELECT COUNT(*) AS n_combates, COALESCE(SUM(victoria), 0) AS victorias,
           AVG(victoria) AS win_rate FROM duelos
),
elegibles AS (
    SELECT rival_id, COUNT(*) AS enfrentamientos, SUM(victoria) AS victorias, AVG(victoria) AS tasa
    FROM duelos WHERE rival_id IS NOT NULL
    GROUP BY rival_id HAVING COUNT(*) >= %(min_muestra)s
),
mejor AS (
    SELECT * FROM elegibles ORDER BY tasa DESC, enfrentamientos DESC, rival_id ASC LIMIT 1
),
peor AS (
    SELECT * FROM elegibles ORDER BY tasa ASC, enfrentamientos DESC, rival_id ASC LIMIT 1
)
SELECT l.seed_simulacion, r.n_combates, r.victorias, r.win_rate,
       (SELECT COUNT(*) FROM elegibles) AS n_rivales_elegibles,
       m.rival_id AS counter_id, cm.nombre AS counter_nombre,
       m.tasa AS counter_tasa, m.victorias AS counter_victorias, m.enfrentamientos AS counter_enfrentamientos,
       p.rival_id AS nemesis_id, cp.nombre AS nemesis_nombre,
       p.tasa AS nemesis_tasa, p.victorias AS nemesis_victorias, p.enfrentamientos AS nemesis_enfrentamientos
FROM resumen r
LEFT JOIN lote l ON TRUE
LEFT JOIN mejor m ON TRUE
LEFT JOIN peor p ON TRUE
LEFT JOIN criaturas_criatura cm ON cm.id = m.rival_id
LEFT JOIN criaturas_criatura cp ON cp.id = p.rival_id;
