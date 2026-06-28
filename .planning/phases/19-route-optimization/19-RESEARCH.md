---
phase: 19
plan: RESEARCH
subsystem: route-optimization
tags: [tsp, routing, gps, deviation, backend]
researched: 2026-06-27
---

# Phase 19: Route Optimization — Research

## ## RESEARCH COMPLETE

---

## 1. Current State of Codebase

### Trips & Stops
- **Trip Model (`backend/app/modules/trips/models.py`)**: Stores `origin`, `destination`, `origin_location` (JSON), and `destination_location` (JSON). It does *not* store route geometry or polyline data.
- **TripStop Model (`backend/app/modules/trips/models.py`)**: Stores intermediate stops with a `location` (JSON) containing latitude and longitude. There is currently no `sequence_number` column.
- **KnownRoute Model (`backend/app/modules/trips/models.py`)**: Used for pre-defined route distances and fuel estimates. It does *not* contain latitude/longitude coordinates for its origin or destination, which causes an existing bug in `get_trip_eta()` where it attempts to access non-existent properties `route.destination_lat` and `route.destination_lon`.

### GPS Ingestion & Webhook
- **GpsPosition / VehicleLastPosition (`backend/app/modules/gps/models.py`)**: Stores coordinate points (`lat`, `lon`) for vehicles.
- **Ingestion Pipeline (`backend/app/modules/gps/service.py`)**: Receives GPS webhook positions, validates HMAC, inserts them into `GpsPosition`, and upserts `VehicleLastPosition`. There is currently no route deviation logic here.

---

## 2. Technical Approach & Key Decisions

### Waypoint Sequence Optimization (OPTIM-01)
- **Algorithm**: Since the typical number of stops per trip is small ($N < 10$), an in-memory, greedy nearest-neighbor solver for the Traveling Salesperson Problem (TSP) is sufficient.
- **Algorithm Logic**:
  1. Let the start point be $P_{start}$ (from `trip.origin_location`).
  2. Let the end point be $P_{end}$ (from `trip.destination_location`).
  3. Let the set of remaining unvisited stops be $S_{unvisited}$ (from the active trip stops).
  4. Initialize the path with $P_{start}$.
  5. While $S_{unvisited}$ is not empty:
     - Find the stop $s \in S_{unvisited}$ that minimizes the Haversine distance from the current end of the path.
     - Add $s$ to the path, set the current point to $s$, and remove $s$ from $S_{unvisited}$.
  6. Append $P_{end}$ to the path.
  7. Update the `sequence_number` of `TripStop` records to reflect this optimized ordering.

### Distance Matrix & Route Geometry (OPTIM-02)
- **OSRM API Request**: Use the public OSRM Route service:
  `http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2};...;{lonN},{latN}?overview=full&geometries=geojson`
  - Parameters:
    - `overview=full`: Returns the complete route geometry.
    - `geometries=geojson`: Returns coordinates as an array of `[longitude, latitude]` points, which is easier to parse and query directly in Python without external decoding libraries.
- **Fallback Winding Factor**: If OSRM is unreachable or times out, calculate the Haversine distance between sequential waypoints and multiply the sum by $1.3$.
- **Database Storage**: Save the list of coordinates on the `Trip` model as a JSON array (`[[lat1, lon1], [lat2, lon2], ...]`) in a new `route_geometry` column, and store the encoded polyline string in `route_polyline`.

### Route Deviation Alerts (OPTIM-03)
- **Distance Calculation**: For each new GPS point $P = (lat_P, lon_P)$ ingested, find the minimum perpendicular distance to any segment $AB$ of the planned route geometry.
- **Flat-Earth Projection Formula**:
  Since standard projection libraries (like `shapely`) require binary dependencies, use a local flat-Earth projection which is highly performant and accurate for local distances:
  $$\Delta x = (\Delta lon) \times 111.32 \times \cos(lat_{avg})$$
  $$\Delta y = (\Delta lat) \times 111.32$$
  Calculate the perpendicular distance from $P$ to segment $AB$ in this projected local 2D space.
- **Trigger**: If the minimum distance exceeds $5$ km, create a `route_deviation` alert in the `Alert` model under `alerts` module. Use `request_reference` to prevent duplicate alerts for the same deviation occurrence on a trip.

---

## 3. Database Changes & Migration

1. **`trips` Table**:
   - `route_geometry`: JSON column to store `[[lat1, lon1], [lat2, lon2], ...]` coordinates.
   - `route_polyline`: Text column to store the encoded polyline.
   - `route_distance_km`: Numeric(10, 2) to store the total planned distance.
   - `route_duration_seconds`: Integer to store the total estimated travel time.
2. **`trip_stops` Table**:
   - `sequence_number`: Integer column to store the optimized sequence index.
3. **`known_routes` Table**:
   - `destination_lat`: Numeric(9, 6) column.
   - `destination_lon`: Numeric(9, 6) column.
   - (Fixes the existing ETA lookup bug in `gps/service.py`).

---

## 4. Validation Architecture

To comply with the Nyquist Validation framework, the following test cases must be added:
- **`test_optimize_waypoints_greedy`**: Asserts correct greedy sequencing of stops.
- **`test_osrm_integration_success`**: Verifies calling OSRM API mock and extracting geometry/distance/duration.
- **`test_osrm_fallback_haversine`**: Verifies falling back to Haversine * 1.3 on API timeout/failure.
- **`test_perpendicular_distance_calculation`**: Asserts correctness of point-to-line-segment distance calculation.
- **`test_gps_ingestion_creates_deviation_alert`**: Verifies a vehicle going >5km off-route creates a `route_deviation` alert.
- **`test_gps_ingestion_no_deviation_no_alert`**: Verifies a vehicle within <5km of route does not trigger any alert.

---

## 5. Verification Plan

### Automated Tests
- Run `pytest backend/tests/test_route_optimization.py` (New test suite).
- Run `pytest backend/tests/test_gps_tracking.py` (Verify ETA bugfix and webhook ingestion side-effects).

### Manual Verification
- Deploy to local/staging, simulate a trip with multiple stops, run the route optimization trigger, and verify the mapped route in the control tower UI.
