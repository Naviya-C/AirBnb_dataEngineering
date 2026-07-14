-- ===========================================================================
-- 3.4  Analytical queries against the star schema
-- ===========================================================================

-- Q1. Median price and listing count by city + room type -------------------
SELECT c.display_name AS city,
       rt.room_type,
       count(*)                              AS listings,
       round(median(f.price), 2)             AS median_price,
       round(avg(f.review_scores_rating), 2) AS avg_rating
FROM fact_listing f
JOIN dim_city c       ON c.city_key = f.city_key
JOIN dim_room_type rt ON rt.room_type_sk = f.room_type_sk
GROUP BY 1, 2
ORDER BY 1, listings DESC;

-- Q2. Top neighbourhoods by OFFICIAL estimated revenue ---------------------
--     (Inside Airbnb's estimated_revenue_l365d, summed per neighbourhood)
SELECT c.display_name AS city,
       n.neighbourhood,
       n.nb_listing_count                            AS listings,
       round(n.nb_median_price, 2)                   AS median_price,
       round(sum(f.estimated_revenue_l365d), 2)      AS est_total_revenue,
       round(avg(f.estimated_occupancy_l365d), 1)    AS avg_occupied_nights
FROM fact_listing f
JOIN dim_neighbourhood n ON n.neighbourhood_sk = f.neighbourhood_sk
JOIN dim_city c          ON c.city_key = f.city_key
WHERE f.estimated_revenue_l365d IS NOT NULL
GROUP BY 1, 2, 3, 4
ORDER BY est_total_revenue DESC
LIMIT 10;

-- Q3. Superhost price premium ----------------------------------------------
SELECT c.display_name AS city,
       h.host_is_superhost,
       count(*)                    AS listings,
       round(median(f.price), 2)   AS median_price
FROM fact_listing f
JOIN dim_host h ON h.host_sk = f.host_sk
JOIN dim_city c ON c.city_key = f.city_key
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q4. Price distribution by property family --------------------------------
SELECT p.property_family,
       count(*)                               AS listings,
       round(quantile_cont(f.price, 0.25), 2) AS p25,
       round(median(f.price), 2)              AS p50,
       round(quantile_cont(f.price, 0.75), 2) AS p75
FROM fact_listing f
JOIN dim_property p ON p.property_sk = f.property_sk
GROUP BY 1
ORDER BY listings DESC;

-- Q5. Host tenure vs review activity ---------------------------------------
SELECT CASE WHEN h.host_tenure_years < 3 THEN '0-3y'
            WHEN h.host_tenure_years < 6 THEN '3-6y'
            WHEN h.host_tenure_years < 10 THEN '6-10y'
            ELSE '10y+' END                    AS tenure_bucket,
       count(*)                                AS listings,
       round(avg(f.number_of_reviews), 1)      AS avg_reviews,
       round(avg(f.reviews_per_month), 2)      AS avg_reviews_pm
FROM fact_listing f
JOIN dim_host h ON h.host_sk = f.host_sk
WHERE h.host_tenure_years IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- Q6. Time-grain: monthly availability from fact_calendar ------------------
--     (calendar has no nightly price in 2026 extracts -> availability only)
SELECT c.display_name AS city,
       d.year, d.month,
       count(*)                                                    AS listing_days,
       round(avg(CASE WHEN cal.available THEN 1.0 ELSE 0.0 END), 3) AS avail_rate
FROM fact_calendar cal
JOIN dim_date d ON d.date_key = cal.date_key
JOIN dim_city c ON c.city_key = cal.city_key
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;

-- Q7. Review sub-score profile by city (uses new sub-score measures) -------
SELECT c.display_name AS city,
       round(avg(f.review_scores_cleanliness), 3)   AS cleanliness,
       round(avg(f.review_scores_location), 3)      AS location,
       round(avg(f.review_scores_communication), 3) AS communication,
       round(avg(f.review_scores_value), 3)         AS value
FROM fact_listing f
JOIN dim_city c ON c.city_key = f.city_key
GROUP BY 1
ORDER BY 1;
