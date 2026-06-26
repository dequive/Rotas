# Phase 19: Route Optimization - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary
This phase introduces multi-stop waypoint sequencing optimization, OSRM/Google Maps distance matrix calculations, and route deviation alerting.

It covers:
- Optimization of waypoint sequences for a trip to minimize distance/time.
- OSRM service integration to fetch route geometries and realistic travel times.
- Cross-checking vehicle GPS positions against planned route polylines to raise deviation alerts.
</domain>

<decisions>
## Implementation Decisions

### Waypoint Optimization (OPTIM-01)
- **D-01:** Greedy/nearest-neighbor Python TSP algorithm will be used to sequence waypoints. Given the typical number of stops (< 10), an in-memory solver is sufficient and avoids external execution overhead.

### Distance Matrix & Route Geometry (OPTIM-02)
- **D-02:** Use OSRM Public Server (`router.project-osrm.org/route/v1/driving/...`) to fetch travel times, distances, and full route geometries (polylines).
- **D-03:** Provide a fallback calculation: if the OSRM request fails or times out, fall back to Haversine distance multiplied by a 1.3 road winding factor.

### Route Deviation Alerts (OPTIM-03)
- **D-04:** Planned route geometries (polylines) returned by OSRM will be saved on the `Trip` or a related `TripRoute` model.
- **D-05:** During GPS webhook processing, the vehicle's position is checked against the route polyline. If the perpendicular distance to the nearest line segment in the polyline exceeds 5km, a `route_deviation` alert is created.

### developer's Discretion
- The exact format of storing the polyline (e.g. encoded polyline string or list of coordinates) is left to the planner.
- Bounding box checks can be used as a pre-filtering step before calculating exact perpendicular segment distances to optimize performance.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` §Phase 19
- `.planning/REQUIREMENTS.md` §Route Optimization
- `backend/app/modules/trips/models.py` — Existing Trip model
- `backend/app/modules/gps/service.py` — GPS position processing pipeline
</canonical_refs>
