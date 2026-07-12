# Data Modeling – Star Schema Design

## Overview

The purpose of this stage is to transform the enriched Airbnb listing dataset (`listing_master.csv`) into a **dimensional model (Star Schema)** that is optimized for analytical queries.

Instead of storing all information in a single denormalized table, the data is separated into:

* **Fact Table** – stores measurable business metrics.
* **Dimension Tables** – store descriptive attributes about hosts, properties, locations, listings, and dates.

This design minimizes redundancy, improves query performance, and follows common data warehouse practices.

---

# Fact Table

## `fact_listing`

The fact table contains all measurable metrics that analysts aggregate using SQL functions such as:

* `SUM()`
* `AVG()`
* `COUNT()`
* `MIN()`
* `MAX()`

### Primary Key

* `listing_key`

### Foreign Keys

* `host_key`
* `property_key`
* `location_key`
* `scrape_date_key`

### Measures

#### Price

* `price`
* `price_quote_total_price`
* `price_quote_price_per_night`

#### Availability

* `availability_30`
* `availability_60`
* `availability_90`
* `availability_365`

#### Reviews

* `number_of_reviews`
* `number_of_reviews_l30d`
* `number_of_reviews_ltm`
* `number_of_reviews_ly`

#### Review Scores

* `review_scores_rating`
* `review_scores_accuracy`
* `review_scores_cleanliness`
* `review_scores_checkin`
* `review_scores_communication`
* `review_scores_location`
* `review_scores_value`

#### Occupancy & Revenue

* `estimated_occupancy_l365d`
* `estimated_revenue_l365d`
* `occupied_days`
* `total_days`
* `occupancy_rate`
* `estimated_revenue`

#### Derived Measures

* `review_frequency`
* `price_per_bedroom`

---

# Dimension Tables

## `dim_host`

Stores descriptive information about Airbnb hosts.

### Primary Key

* `host_key`

### Attributes

* `host_id`
* `host_name`
* `host_since`
* `host_location`
* `host_about`
* `host_response_time`
* `host_response_rate`
* `host_acceptance_rate`
* `host_is_superhost`
* `host_thumbnail_url`
* `host_picture_url`
* `host_neighbourhood`
* `host_listings_count`
* `host_total_listings_count`
* `host_verifications`
* `host_has_profile_pic`
* `host_identity_verified`
* `host_tenure_years`

---

## `dim_property`

Stores descriptive information about the property.

### Primary Key

* `property_key`

### Attributes

* `property_type`
* `room_type`
* `accommodates`
* `bathrooms`
* `bathrooms_text`
* `bedrooms`
* `beds`
* `amenities`
* `instant_bookable`
* `license`

---

## `dim_location`

Stores geographic information for each listing.

### Primary Key

* `location_key`

### Attributes

* `neighbourhood`
* `neighbourhood_cleansed`
* `neighbourhood_group_cleansed`
* `latitude`
* `longitude`

---

## `dim_listing`

Stores descriptive information about each listing.

### Primary Key

* `listing_key`

### Attributes

* `listing_id`
* `listing_url`
* `name`
* `description`
* `picture_url`
* `source`

---

## `dim_date`

Stores reusable calendar information.

### Primary Key

* `date_key`

### Attributes

* `full_date`
* `year`
* `quarter`
* `month`
* `week`
* `day`
* `weekday`

The fact table references this dimension using date foreign keys such as:

* `scrape_date_key`
* `first_review_date_key`
* `last_review_date_key`

---

# Primary Key and Foreign Key Relationships

| Parent Table   | Primary Key    | Child Table    | Foreign Key       |
| -------------- | -------------- | -------------- | ----------------- |
| `dim_host`     | `host_key`     | `fact_listing` | `host_key`        |
| `dim_property` | `property_key` | `fact_listing` | `property_key`    |
| `dim_location` | `location_key` | `fact_listing` | `location_key`    |
| `dim_date`     | `date_key`     | `fact_listing` | `scrape_date_key` |

---

# Star Schema

```text
                    dim_host
                  (host_key)
                       │
                       │
                       ▼
dim_property ─── fact_listing ─── dim_location
(property_key)                  (location_key)
                       │
                       │
                       ▼
                   dim_date
                  (date_key)
```

The **fact table** sits at the center of the schema and contains business measures. The surrounding **dimension tables** provide descriptive information used to filter, group, and analyze the measures.

---

# Why a Star Schema?

Compared to storing all information in one large table, the star schema offers several advantages:

* Reduces data duplication.
* Stores descriptive information only once.
* Improves analytical query performance.
* Simplifies reporting and dashboard development.
* Aligns with standard data warehouse design practices.

---

# Design Decisions

## Host Attributes

Host-related fields such as:

* `host_name`
* `host_since`
* `host_is_superhost`
* `host_response_rate`
* `host_listings_count`

are stored in **`dim_host`** because they describe the host rather than individual listing transactions.

---

## Property Attributes

Property characteristics such as:

* `property_type`
* `room_type`
* `bedrooms`
* `bathrooms`

are stored in **`dim_property`** because they describe the property.

---

## Location Attributes

Neighbourhood and geographic information is stored in **`dim_location`** to avoid repeating the same location data for every listing.

---

## Business Measures

Metrics such as:

* `price`
* `occupancy_rate`
* `estimated_revenue`
* `review_frequency`

are stored in **`fact_listing`** because they represent measurable values used for business analysis.

---

## Neighbourhood Aggregates

The enrichment stage generated:

* `neighbourhood_median_price`
* `neighbourhood_listing_count`
* `neighbourhood_average_rating`

These are derived aggregate metrics. In a production data warehouse, they are typically calculated dynamically using SQL rather than stored permanently, ensuring they always reflect the latest underlying data.

---

# Example Analytical Queries

Example questions this model can answer efficiently:

* Average listing price by neighbourhood.
* Average occupancy rate by property type.
* Total estimated revenue by city.
* Average review score by room type.
* Top hosts by estimated revenue.
* Property type distribution across neighbourhoods.
* Average price per bedroom by city.

This star schema provides a scalable foundation for analytical workloads and business intelligence reporting.
