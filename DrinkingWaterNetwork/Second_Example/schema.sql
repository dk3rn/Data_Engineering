-- 3NF schema for the pipe-network measurement data (SQLite / PostgreSQL compatible)
CREATE TABLE junctions (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE,      -- e.g. 'J-A'
    x_m         REAL    NOT NULL,
    y_m         REAL    NOT NULL
);

CREATE TABLE pipes (
    id               INTEGER PRIMARY KEY,
    code             TEXT    NOT NULL UNIQUE, -- e.g. 'P-01'
    material         TEXT    NOT NULL,
    diameter_mm      INTEGER NOT NULL,
    install_year     INTEGER NOT NULL,
    from_junction_id INTEGER NOT NULL REFERENCES junctions(id),
    to_junction_id   INTEGER NOT NULL REFERENCES junctions(id),
    CHECK (from_junction_id <> to_junction_id)
);

CREATE TABLE sensors (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE,      -- e.g. 'S-101'
    name        TEXT    NOT NULL,
    pipe_id     INTEGER NOT NULL REFERENCES pipes(id),
    position_m  REAL    NOT NULL              -- distance from the pipe's start junction
);

CREATE TABLE measurement_units (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT    NOT NULL UNIQUE,      -- e.g. 'bar'
    name        TEXT    NOT NULL,
    quantity    TEXT    NOT NULL              -- e.g. 'pressure'
);

CREATE TABLE sensor_unit_rel (
    sensor_id   INTEGER NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    unit_id     INTEGER NOT NULL REFERENCES measurement_units(id),
    PRIMARY KEY (sensor_id, unit_id)
);

CREATE TABLE measurements (
    id          INTEGER PRIMARY KEY,
    time        TIMESTAMP NOT NULL,
    sensor_id   INTEGER   NOT NULL,
    unit_id     INTEGER   NOT NULL,
    value       REAL      NOT NULL,
    FOREIGN KEY (sensor_id, unit_id) REFERENCES sensor_unit_rel(sensor_id, unit_id),
    UNIQUE (time, sensor_id, unit_id)
);
