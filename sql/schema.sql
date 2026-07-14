-- ===========================================================================
-- 3.4  Dimensional model (star schema) for Inside Airbnb
-- ===========================================================================
-- Grain:
--   fact_listing   : one row per listing per snapshot (the analytical centre)
--   fact_calendar  : one row per listing per calendar day (time-grain companion)
--   fact_review    : one row per review event (review grain)
-- Dimensions are conformed across all facts and across cities.
--
-- Modelling choices:
--   * Surrogate integer keys on every dimension; natural keys kept as attributes.
--   * Neighbourhood aggregates pre-joined onto dim_neighbourhood -- a mild
--     denormalisation trading redundancy for fast slice-and-dice.
--   * dim_host is SCD Type 1 (single snapshot has no history; README notes T2 path).
--   * occupancy/revenue use Inside Airbnb's official estimates (calendar has no
--     nightly price in 2026 extracts).
-- ===========================================================================

DROP TABLE IF EXISTS fact_review;
DROP TABLE IF EXISTS fact_calendar;
DROP TABLE IF EXISTS fact_listing;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_room_type;
DROP TABLE IF EXISTS dim_property;
DROP TABLE IF EXISTS dim_neighbourhood;
DROP TABLE IF EXISTS dim_host;
DROP TABLE IF EXISTS dim_city;

-- ---------------------------------------------------------------- dimensions
CREATE TABLE dim_city (
    city_key      VARCHAR PRIMARY KEY,
    display_name  VARCHAR,
    country       VARCHAR,
    region        VARCHAR
);

CREATE TABLE dim_host (
    host_sk               BIGINT PRIMARY KEY,
    host_id               BIGINT,
    host_name             VARCHAR,
    host_since            DATE,
    host_is_superhost     BOOLEAN,
    host_identity_verified BOOLEAN,
    host_listings_count   INTEGER,
    host_tenure_years     DOUBLE
);

CREATE TABLE dim_neighbourhood (
    neighbourhood_sk   BIGINT PRIMARY KEY,
    city_key           VARCHAR,
    neighbourhood      VARCHAR,
    nb_listing_count   INTEGER,
    nb_median_price    DOUBLE,
    nb_avg_rating      DOUBLE,
    nb_density_pct     DOUBLE,
    FOREIGN KEY (city_key) REFERENCES dim_city(city_key)
);

CREATE TABLE dim_property (
    property_sk         BIGINT PRIMARY KEY,
    property_type_clean VARCHAR,
    property_family     VARCHAR
);

CREATE TABLE dim_room_type (
    room_type_sk BIGINT PRIMARY KEY,
    room_type    VARCHAR
);

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,   -- yyyymmdd
    date     DATE,
    year     INTEGER,
    quarter  INTEGER,
    month    INTEGER,
    day      INTEGER
);

-- --------------------------------------------------------------------- facts
CREATE TABLE fact_listing (
    listing_id          BIGINT,
    snapshot_date_key   INTEGER,
    city_key            VARCHAR,
    host_sk             BIGINT,
    neighbourhood_sk    BIGINT,
    property_sk         BIGINT,
    room_type_sk        BIGINT,
    -- core measures
    price                        DOUBLE,
    price_per_bedroom            DOUBLE,
    accommodates                 INTEGER,
    minimum_nights               INTEGER,
    number_of_reviews            INTEGER,
    reviews_per_month            DOUBLE,
    review_scores_rating         DOUBLE,
    availability_365             INTEGER,
    -- official Inside Airbnb performance estimates
    estimated_occupancy_l365d    INTEGER,
    estimated_revenue_l365d      DOUBLE,
    review_frequency_pm          DOUBLE,
    -- review sub-scores (for 4.5 / ML)
    review_scores_accuracy       DOUBLE,
    review_scores_cleanliness    DOUBLE,
    review_scores_checkin        DOUBLE,
    review_scores_communication  DOUBLE,
    review_scores_location       DOUBLE,
    review_scores_value          DOUBLE,
    PRIMARY KEY (listing_id, snapshot_date_key),
    FOREIGN KEY (snapshot_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (city_key)          REFERENCES dim_city(city_key),
    FOREIGN KEY (host_sk)           REFERENCES dim_host(host_sk),
    FOREIGN KEY (neighbourhood_sk)  REFERENCES dim_neighbourhood(neighbourhood_sk),
    FOREIGN KEY (property_sk)       REFERENCES dim_property(property_sk),
    FOREIGN KEY (room_type_sk)      REFERENCES dim_room_type(room_type_sk)
);

CREATE TABLE fact_calendar (
    listing_id     BIGINT,
    date_key       INTEGER,
    city_key       VARCHAR,
    available      BOOLEAN,
    minimum_nights INTEGER,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (city_key) REFERENCES dim_city(city_key)
);

CREATE TABLE fact_review (
    review_sk   BIGINT PRIMARY KEY,
    listing_id  BIGINT,
    city_key    VARCHAR,
    date_key    INTEGER,
    FOREIGN KEY (city_key) REFERENCES dim_city(city_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);
