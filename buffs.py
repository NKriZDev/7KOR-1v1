"""Buff configuration mapping."""

# Each buff entry can be toggled on/off and references a module that holds its value.
# Example for attack buffs: {"power_strike": {"enabled": True, "value_file": "power_strike", "value_attr": "ATTACK_DAMAGE_BONUS"}}

ATTACK_BUFFS = {
    "power_strike": {
        "enabled": False,
        "value_file": "power_strike",
        "value_attr": "ATTACK_DAMAGE_BONUS",
    },
}


def set_attack_buff_enabled(name, enabled=True):
    """Toggle an attack buff by name."""
    if name in ATTACK_BUFFS:
        ATTACK_BUFFS[name]["enabled"] = enabled
    else:
        print(f"Unknown attack buff: {name}")


def reset_buffs():
    """Disable all buffs."""
    for buff in ATTACK_BUFFS.values():
        buff["enabled"] = False
