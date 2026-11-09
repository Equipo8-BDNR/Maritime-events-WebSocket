CREATE TABLE IF NOT EXISTS ais.raw_events (
    event_day date,
    event_hour timestamp,
    shard tinyint,
    event_id timeuuid,
    received_at timestamp,
    message_type text,
    mmsi bigint,
    payload text,
    PRIMARY KEY ((event_day, event_hour, shard), event_id)
) WITH CLUSTERING ORDER BY (event_id DESC);