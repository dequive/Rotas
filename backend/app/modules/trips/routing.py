import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in km."""
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def optimize_waypoint_sequence(
    origin_location: dict[str, float] | None,
    destination_location: dict[str, float] | None,
    stops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Optimizes the sequence of intermediate stops using a greedy nearest-neighbor TSP approach."""
    if not stops:
        return []

    # Extract start point
    start_lat = origin_location.get("lat") if origin_location else None
    start_lon = origin_location.get("lon") if origin_location else None

    # If no valid start location, preserve existing order
    if start_lat is None or start_lon is None:
        for idx, stop in enumerate(stops):
            stop["sequence_number"] = idx + 1
        return stops

    unvisited = list(stops)
    ordered_stops: list[dict[str, Any]] = []
    current_lat, current_lon = float(start_lat), float(start_lon)

    while unvisited:
        nearest_idx = 0
        min_dist = float("inf")
        for idx, stop in enumerate(unvisited):
            loc = stop.get("location") or {}
            stop_lat = loc.get("lat")
            stop_lon = loc.get("lon")
            if stop_lat is not None and stop_lon is not None:
                dist = haversine_distance_km(current_lat, current_lon, float(stop_lat), float(stop_lon))
            else:
                dist = float("inf")

            if dist < min_dist:
                min_dist = dist
                nearest_idx = idx

        next_stop = unvisited.pop(nearest_idx)
        ordered_stops.append(next_stop)
        next_loc = next_stop.get("location") or {}
        if next_loc.get("lat") is not None and next_loc.get("lon") is not None:
            current_lat, current_lon = float(next_loc["lat"]), float(next_loc["lon"])

    for idx, stop in enumerate(ordered_stops):
        stop["sequence_number"] = idx + 1

    return ordered_stops


async def fetch_osrm_route(waypoints: list[dict[str, float]]) -> dict[str, Any]:
    """Fetches route geometry, distance, and duration from OSRM demo server, with Haversine fallback."""
    if len(waypoints) < 2:
        return {
            "geometry": [],
            "polyline": "",
            "distance_km": 0.0,
            "duration_seconds": 0,
            "source": "empty",
        }

    # Waypoints format for OSRM: lon,lat;lon,lat;...
    coords_str = ";".join(f"{w['lon']},{w['lat']}" for w in waypoints)
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes:
                    route = routes[0]
                    geometry_points = route.get("geometry", {}).get("coordinates", [])
                    # OSRM returns coordinates as [lon, lat], convert to [[lat, lon], ...]
                    lat_lon_geometry = [[pt[1], pt[0]] for pt in geometry_points]
                    distance_m = route.get("distance", 0.0)
                    duration_s = route.get("duration", 0)
                    return {
                        "geometry": lat_lon_geometry,
                        "polyline": "",
                        "distance_km": round(distance_m / 1000.0, 2),
                        "duration_seconds": int(duration_s),
                        "source": "osrm",
                    }
    except Exception as exc:
        logger.warning(f"OSRM request failed: {exc}, falling back to Haversine * 1.3")

    return calculate_haversine_fallback(waypoints)


def calculate_haversine_fallback(waypoints: list[dict[str, float]]) -> dict[str, Any]:
    """Calculates route distance with Haversine distance * 1.3 winding factor."""
    total_km = 0.0
    geometry = [[w["lat"], w["lon"]] for w in waypoints]

    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        dist = haversine_distance_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        total_km += dist * 1.3

    # Estimate average speed 60 km/h for duration
    duration_s = int((total_km / 60.0) * 3600)

    return {
        "geometry": geometry,
        "polyline": "",
        "distance_km": round(total_km, 2),
        "duration_seconds": duration_s,
        "source": "haversine_fallback",
    }


def perpendicular_distance_km(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    """Calculates flat-Earth perpendicular distance from point to segment in km."""
    p_lat, p_lon = point
    a_lat, a_lon = seg_start
    b_lat, b_lon = seg_end

    avg_lat = math.radians((a_lat + b_lat + p_lat) / 3.0)

    # Flat-Earth projection to km coordinates
    def to_km(lat: float, lon: float) -> tuple[float, float]:
        x = lon * 111.32 * math.cos(avg_lat)
        y = lat * 111.32
        return x, y

    px, py = to_km(p_lat, p_lon)
    ax, ay = to_km(a_lat, a_lon)
    bx, by = to_km(b_lat, b_lon)

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    # Parameter t of nearest point on line segment
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    nearest_x = ax + t * dx
    nearest_y = ay + t * dy

    return math.hypot(px - nearest_x, py - nearest_y)


def check_route_deviation(
    gps_point: tuple[float, float],
    route_geometry: list[list[float]] | list[tuple[float, float]],
    threshold_km: float = 5.0,
) -> bool:
    """Returns True if the gps_point is further than threshold_km from any segment of route_geometry."""
    if not route_geometry or len(route_geometry) < 2:
        return False

    min_dist = float("inf")
    p = (float(gps_point[0]), float(gps_point[1]))

    for i in range(len(route_geometry) - 1):
        seg_a = (float(route_geometry[i][0]), float(route_geometry[i][1]))
        seg_b = (float(route_geometry[i + 1][0]), float(route_geometry[i + 1][1]))
        dist = perpendicular_distance_km(p, seg_a, seg_b)
        if dist < min_dist:
            min_dist = dist
            if min_dist <= threshold_km:
                return False

    return min_dist > threshold_km
