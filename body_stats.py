"""Resolve observed upgraded mech stats into effective body dimensions.

Protocol section 10 leaves radius/height as base upgraded values in self.stats;
cube growth applies to them. Observed eye/muzzle heights already include growth.
Always pass the raw observed self object. Neither config nor observation is mutated.
"""
from __future__ import annotations


def effective_mech_stats(config, me):
    """Return a fresh merged stats dict with collision radius/height grown once."""
    base = config.get('mech', {})
    observed = me.get('stats', {})
    stats = {**base, **observed}
    scale = 1 + config.get('cubes', {}).get('size_per_cube', .05) * me.get('cubes', 0)
    stats['radius'] = stats.get('radius', 2.5) * scale
    stats['height'] = stats.get('height', 9.) * scale
    for name, fallback in (('eye_height', 8.), ('muzzle_height', 7.)):
        if name not in observed:
            stats[name] = base.get(name, fallback) * scale
    return stats
