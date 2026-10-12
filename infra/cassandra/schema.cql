CREATE TABLE IF NOT EXISTS ais.vessel_latest (
    mmsi              bigint PRIMARY KEY,
    event_time        timestamp,
    message_id        tinyint,
    ship_name         text,
    latitude          double,
    longitude         double,
    sog               float,
    cog               float,
    true_heading      smallint,
    rate_of_turn      smallint,
    nav_status        tinyint,
    position_accuracy boolean,
    raim              boolean,
    report_second     tinyint
);

CREATE TABLE IF NOT EXISTS ais.position_by_vessel_day (
    mmsi              bigint,
    day               date,
    event_time        timestamp,
    event_nanos       int,
    message_id        tinyint,
    ship_name         text,
    latitude          double,
    longitude         double,
    sog               float,
    cog               float,
    true_heading      smallint,
    rate_of_turn      smallint,
    nav_status        tinyint,
    position_accuracy boolean,
    raim              boolean,
    report_second     tinyint,
    PRIMARY KEY ((mmsi, day), event_time, event_nanos)
) WITH CLUSTERING ORDER BY (event_time DESC, event_nanos DESC)
  AND default_time_to_live = 259200
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_unit': 'DAYS',
      'compaction_window_size': 1
  };

CREATE TABLE IF NOT EXISTS ais.vessel_static (
    mmsi         bigint PRIMARY KEY,
    updated_at   timestamp,
    name         text,
    call_sign    text,
    imo_number   int,
    ship_type    smallint,
    dim_a        smallint,
    dim_b        smallint,
    dim_c        smallint,
    dim_d        smallint,
    max_draught  float,
    destination  text,
    eta_month    tinyint,
    eta_day      tinyint,
    eta_hour     tinyint,
    eta_minute   tinyint,
    fix_type     tinyint,
    ais_version  tinyint
);
