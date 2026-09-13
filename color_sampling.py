from functools import lru_cache

import numpy as np


@lru_cache(maxsize=128)
def _segment_bounds(length, count, gap):
    step = max(1, length - 2 * gap) / count
    # Keep Python's original rounding and slice semantics, including empty zones.
    bounds = [
        slice(gap + int(i * step), gap + int((i + 1) * step)).indices(length)[:2]
        for i in range(count)
    ]
    starts, ends = np.array(bounds, dtype=np.intp).T
    return starts, np.maximum(starts, ends)


def sample_segments(zone, count, axis, gap=0):
    """Exact RGB8 segment averages; axis is the dimension being collapsed."""
    if count <= 0:
        return []
    starts, ends = _segment_bounds(zone.shape[1 - axis], count, gap)
    if zone.dtype != np.uint8:
        # Preserve NumPy's accumulation rules for callers supplying other types.
        segments = (zone[:, a:b] if axis == 0 else zone[a:b, :]
                    for a, b in zip(starts, ends))
        return [np.mean(s, axis=(0, 1)) if s.size else np.zeros(zone.shape[2])
                for s in segments]
    sums = zone.sum(axis=axis, dtype=np.int64)
    prefix = np.vstack((np.zeros((1, zone.shape[2]), dtype=np.int64),
                        np.cumsum(sums, axis=0)))
    sizes = (ends - starts) * zone.shape[axis]
    colors = np.zeros((count, zone.shape[2]), dtype=np.float64)
    np.divide(prefix[ends] - prefix[starts], sizes[:, None],
              out=colors, where=sizes[:, None] > 0)
    return list(colors)
