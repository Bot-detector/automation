TIPOFF_CONFIG = """
    SELECT DISTINCT
        pl.name,
        UNIX_TIMESTAMP(rp.timestamp)*1000 as timestamp,
        rp.world_number,
        rid.region_name,
        p.prediction,
        p.Predicted_confidence
    FROM Players as pl
    INNER JOIN Predictions as p on (p.id = pl.id)
    INNER JOIN reportLatest as rp on (rp.reported_id = pl.id)
    INNER JOIN regionIDNames as rid on rid.region_ID = rp.region_ID
    WHERE 1=1
        and p.Predicted_confidence > 99
        and p.Real_Player < 10
        and pl.label_jagex = 0
        and p.prediction not in (
            'Real_Player',
            'Stats Too Low',
            'Stats_Too_Low'
        )
        and rp.timestamp >= current_timestamp() - interval 1 day
    order by p.prediction desc
"""
