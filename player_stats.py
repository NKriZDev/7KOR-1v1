"""Player stats loader with buff hooks."""

import importlib
from buffs import ATTACK_BUFFS


def _load_attack_bonus():
    bonus = 0.0
    for buff_name, buff_conf in ATTACK_BUFFS.items():
        if not buff_conf.get("enabled"):
            continue
        module_name = buff_conf.get("value_file")
        attr_name = buff_conf.get("value_attr", "ATTACK_DAMAGE_BONUS")
        try:
            mod = importlib.import_module(module_name)
            bonus += getattr(mod, attr_name, 0.0)
        except Exception as exc:
            print(f"Failed to load attack buff '{buff_name}': {exc}")
    return bonus


def apply_buffs(base_stats):
    """Apply enabled buffs to base stats and return new dict."""
    stats = dict(base_stats)
    attack_bonus = _load_attack_bonus()
    stats["attack_damage"] = stats.get("attack_damage", 0) * (1 + attack_bonus)
    # Other stats remain unchanged for now
    return stats
