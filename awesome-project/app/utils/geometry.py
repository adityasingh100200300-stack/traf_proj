import math
from typing import Tuple, List

def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Computes great-circle distance between two GPS coordinates (lat, lon) in meters.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371000.0  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c

def calculate_bearing(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calculates compass bearing in degrees (0 to 360) from coord1 to coord2.
    """
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    return (initial_bearing + 360.0) % 360.0

def bearing_to_phase_group(bearing: float) -> str:
    """
    Translates a compass heading into a dominant intersection phase group.
    """
    # 315° to 45° (North) or 135° to 225° (South) -> north_south
    if (315.0 <= bearing or bearing <= 45.0) or (135.0 <= bearing <= 225.0):
        return "north_south"
    else:
        return "east_west"

def is_point_near_segment(
    point: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float],
    threshold_meters: float = 150.0
) -> bool:
    """
    Checks if a geographic point lies within a buffer distance of a line segment.
    """
    d_start = haversine_distance(point, seg_start)
    d_end = haversine_distance(point, seg_end)
    d_seg = haversine_distance(seg_start, seg_end)

    if d_seg == 0.0:
        return d_start <= threshold_meters

    # If point is close to either endpoint
    if min(d_start, d_end) <= threshold_meters:
        return True

    # Check triangle inequality buffer
    return (d_start + d_end) <= (d_seg + (threshold_meters * 0.5))