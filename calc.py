import re
import os
import sys
import math
import time
import logging
import itertools
import multiprocessing
from archgun_data import weapon_data
from mods import mod_data
from health_classes import health_type
from enemies import enemies
from contextlib import contextmanager

mode = "best build"# "best build" or "damage calc"

#debug logging                                                                        
debug_mode = 0 # 1 for debug mode, 0 for normal mode

def lazy_debug(msg_func):
    if debug_mode:
        logger.debug(msg_func())
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
#debug logging                                                                        

# ANSI color codes for colored output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

@contextmanager
def suppress_prints():
    # for debugging purposes
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout

class WeaponStats:
    def __init__(self, name, impact, puncture, slash, heat, cold, elec, tox, viral, corrosive, gas, radiation, magnetic, blast, fire_rate, cc, cd, multishot, dispo, aoe, weapon_type):
        self.name = name
        self.impact = impact
        self.puncture = puncture
        self.slash = slash
        self.heat = heat
        self.cold = cold
        self.elec = elec
        self.tox = tox
        self.viral = viral
        self.corrosive = corrosive
        self.gas = gas
        self.radiation = radiation
        self.magnetic = magnetic
        self.blast = blast
        self.fire_rate = fire_rate
        self.cc = cc
        self.cd = cd
        self.multishot = multishot
        self.dispo = dispo
        self.aoe = aoe
        self.weapon_type = weapon_type

class ModStats:
    def __init__(self, base_damage, impact, puncture, slash, heat, cold, elec, tox, viral, corrosive, gas, radiation, magnetic, blast, faction, corpus, fire_rate, cc, cd, multishot, electric_instance, cd_multiplier, eclipse, tenacious_bond, flat_cc, max_ammo, incompatible=None):
        self.base_damage = base_damage
        self.impact = impact
        self.puncture = puncture
        self.slash = slash
        self.heat = heat
        self.cold = cold
        self.elec = elec
        self.tox = tox
        self.viral = viral
        self.corrosive = corrosive
        self.gas = gas
        self.radiation = radiation
        self.magnetic = magnetic
        self.blast = blast
        self.faction = faction
        self.corpus = corpus
        self.fire_rate = fire_rate
        self.cc = cc
        self.cd = cd
        self.multishot = multishot
        self.electric_instance = electric_instance
        self.cd_multiplier = cd_multiplier
        self.eclipse = eclipse
        self.tenacious_bond = tenacious_bond
        self.incompatible = incompatible if incompatible else []
        self.flat_cc = flat_cc
        self.max_ammo = max_ammo

def parse_stat(stat):
    abbreviation_map = {
        "cc": "cc",
        "critchance": "cc",
        "cd": "cd",
        "critdamage": "cd",
        "dmg": "base_damage",
        "damage": "base_damage",
        "ms": "multishot",
        "multi": "multishot",
        "multishot": "multishot",
        "imp": "impact",
        "impact": "impact",
        "punc": "puncture",
        "puncture": "puncture",
        "slash": "slash",
        "sl": "slash",
        "heat": "heat",
        "fire": "heat",
        "cold": "cold",
        "tox": "tox",
        "toxin": "tox",
        "ele": "elec",
        "elec": "elec",
        "electric": "elec",
        "electricity": "elec",
        "fr": "fire_rate",
        "firerate": "fire_rate",
        "dtc": "corpus",
        "corp": "corpus",  
        "corpus": "corpus",
        "ammo": "max_ammo",
    }

    for abbr, key in abbreviation_map.items():
        if abbr in stat:
            try:
                value = float(stat.replace(abbr, "").replace(",", "")) / 100
                return key, value
            except ValueError:
                return None, None
    return None, None

def parse_riven_mod(riven_mod_str):
    stats = riven_mod_str.replace("riven ", "").split(" ")
    riven_stats = {
        "cc": 0,
        "cd": 0,
        "base_damage": 0,
        "multishot": 0,
        "impact": 0,
        "puncture": 0,
        "slash": 0,
        "heat": 0,
        "cold": 0,
        "elec": 0,
        "tox": 0,
        "fire_rate": 0,
        "corpus": 0,
        "max_ammo": 0,
    }

    for stat in stats:
        key, value = parse_stat(stat)
        if key:
            riven_stats[key] = value

    return riven_stats

def grade_riven_mod(mods_input, weapon_name):
    #https://warframe.fandom.com/wiki/Riven_Mods if i ever need more values
    mods_input = [mod.strip() for mod in mods_input.split(',')]
    riven_stats = (next((mod for mod in mods_input if "riven" in mod), None)).replace("riven ", "").strip().split(" ")
    print(f"riven: {riven_stats}")
    dispo = weapon_data.get(weapon_name).get("dispo")
    reference_values = {
        'multishot': 0.6030,
        'base_damage': 0.9990,
        'cc': 0.9990,
        'cd': 0.8010,
        'fire_rate': 0.6003,
        'elec': 1.1970,
        'heat': 1.1970,
        'cold': 1.1970,
        'tox': 1.1970,
        'corpus': 0.4500,
        'max_ammo': 0.9990,
        'impact': 0.9000,
        'slash': 0.9000,
        'puncture': 0.9000
    }
    grading = {
        'S': 9.5,
        'A+': 7.5,
        'A': 5.5,
        'A-': 3.5,
        'B+': 1.5,
        'B': -1.5,
        'B-': -3.5,
        'C+': -5.5,
        'C': -7.5,
        'C-': -9.5,
        'F': -11.0
    }
    total_positives = 0
    total_negatives = 0
    for stat in riven_stats:
        if not "rec" in stat:
            if stat.startswith('-'):
                total_negatives += 1
            else:
                total_positives += 1
        if "rec" in stat:
            if stat.startswith('-'):
                total_positives += 1
            else:
                total_negatives += 1
    if total_positives == 2:
        posmulti = 0.99
        if total_negatives == 1:
            negmulti = 0.495
            posmulti = 1.2375
    if total_positives == 3:
        negmulti = 1
        posmulti = 0.75
        if total_negatives == 1:
            negmulti = 0.75
            posmulti = 0.9375

    stat_grades = []
    for stat in riven_stats:
        key, stat_value = parse_stat(stat)
        if key and key in reference_values:
            reference_value = reference_values[key]
            stat_value = stat_value if not stat.startswith('-') else -stat_value
            #print(f"key: {key}, stat_value: {stat_value}, reference_value: {reference_value}")
            range = ((stat_value - (reference_value * dispo * (posmulti if stat_value > 0 else negmulti))) * 100) / (reference_value * dispo * (posmulti if stat_value > 0 else negmulti))
            grade_found = False
            for grade in grading:
                if 11.0 >= range >= grading[grade]:
                    stat_grades.append(grade)
                    grade_found = True
                    break
            if not grade_found:
                stat_grades.append("?")
    print(f"Stat grades: {stat_grades}")

def scan_mods(mods_input):
    if isinstance(mods_input, str):
        mods_input = [mod.strip() for mod in mods_input.split(',')]
    parsed_mods = []
    for mod in mods_input:
        if "riven" in mod:
            parsed_mods.append(parse_riven_mod(mod))
        else:
            match = re.search(r' r(\d+)$', mod)
            if match:
                name = mod[:match.start()].strip()
                rank = int(match.group(1))
                parsed_mods.append((name, rank))
            else:
                parsed_mods.append((mod, None))  # None indicates max rank
    return parsed_mods

def parse_weapon_stats(weapon_data, weapon_name):
    weapon_data = weapon_data.get(weapon_name)
    return WeaponStats(
        name=weapon_name,
        impact=weapon_data.get("impact", 0),
        puncture=weapon_data.get("puncture", 0),
        slash=weapon_data.get("slash", 0),
        heat=weapon_data.get("heat", 0),
        cold=weapon_data.get("cold", 0),
        elec=weapon_data.get("elec", 0),
        tox=weapon_data.get("tox", 0),
        viral=weapon_data.get("viral", 0),
        corrosive=weapon_data.get("corrosive", 0),
        gas=weapon_data.get("gas", 0),
        radiation=weapon_data.get("radiation", 0),
        magnetic=weapon_data.get("magnetic", 0),
        blast=weapon_data.get("blast", 0),
        fire_rate=weapon_data.get("fire rate", 0),
        cc=weapon_data.get("cc", 0),
        cd=weapon_data.get("cd", 0),
        multishot=weapon_data.get("multishot", 0),
        dispo=weapon_data.get("dispo", 0),
        aoe=weapon_data.get("aoe", 0),
        weapon_type=weapon_data.get("weapon_type", 0)
    )

def combine_elements(cumulative_stats, mod_order, weapon_stats):
    single_elements = ["heat", "cold", "elec", "tox"]
    combined_elements = {
        frozenset(["heat", "cold"]): "blast",
        frozenset(["heat", "elec"]): "radiation",
        frozenset(["heat", "tox"]): "gas",
        frozenset(["cold", "elec"]): "magnetic",
        frozenset(["cold", "tox"]): "viral",
        frozenset(["elec", "tox"]): "corrosive"
    }
    
    # Identify single element mods present in the order they were added
    present_elements = [elem for elem in mod_order if elem in single_elements and cumulative_stats[elem] > 0]
    
    # Check for innate single elements in the weapon stats and add them to the end of present_elements
    for elem in single_elements:
        if getattr(weapon_stats, elem, 0) > 0:
            present_elements.append(elem)

    lazy_debug(lambda: f"Present single elements before combination: {present_elements}")
    
    combined_set = set()
    
    # Combine elements in the order they were added
    i = 0
    while i < len(present_elements) - 1:
        elem1 = present_elements[i]
        if elem1 in combined_set:
            i += 1
            continue
        j = i + 1
        while j < len(present_elements):
            elem2 = present_elements[j]
            if elem2 in combined_set:
                j += 1
                continue
            combo = frozenset([elem1, elem2])
            if combo in combined_elements:
                combined = combined_elements[combo]
                combined_value = cumulative_stats[elem1] + cumulative_stats[elem2]
                
                # Remove the single element values
                cumulative_stats[elem1] = 0
                cumulative_stats[elem2] = 0
                
                # Add the combined element value
                cumulative_stats[combined] += combined_value
                
                # Mark elements as combined
                combined_set.add(elem1)
                combined_set.add(elem2)
                
                # Remove the combined elements from the list and add the new combined element
                present_elements.pop(j)
                present_elements[i] = combined
                lazy_debug(lambda: f"Combined {combo} into {combined} with value {combined_value}")
                break
            j += 1
        else:
            i += 1
    # Handle any remaining single elements that couldn't be combined
    remaining_elements = [elem for elem in present_elements if elem not in combined_set]

    lazy_debug(lambda: f"Remaining elements (after combination): {remaining_elements}")
    
    return cumulative_stats, remaining_elements

def parse_mod_stats(mod_data, selected_mods, weapon_stats):

    cumulative_stats = {
        "base_damage": 0,
        "impact": 0,
        "puncture": 0,
        "slash": 0,
        "heat": 0,
        "cold": 0,
        "elec": 0,
        "tox": 0,
        "viral": 0,
        "corrosive": 0,
        "gas": 0,
        "radiation": 0,
        "magnetic": 0,
        "blast": 0,
        "faction": 0,
        "corpus": 0,
        "fire_rate": 0,
        "cc": 0,
        "cd": 0,
        "multishot": 0,
        "electric_instance": 0,
        "cd_multiplier": 0,
        "eclipse": 0,
        "tenacious_bond": 0,
        "flat_cc": 0,
        "max_ammo": 0,
    }
    
    mod_order = []
    
    for mod in selected_mods:
        if isinstance(mod, dict):  # Check if it's a parsed Riven mod
            for key, value in mod.items():
                cumulative_stats[key] += value
        else:
            mod, rank = mod
            if mod in mod_data:
                mod_stats = mod_data[mod]
                max_rank = mod_stats["ranks"]
                if mod == "volt shield" and rank is None:
                    rank = 0
                elif rank is None:
                    rank = max_rank
                for stat in cumulative_stats.keys():
                    if stat in mod_stats:
                        increment = mod_stats[stat] * (1 + rank)
                        cumulative_stats[stat] += increment
                        lazy_debug(lambda: f"Processing mod: {mod}, rank: {rank} || {stat}: {mod_stats[stat]} * (1 + {rank}) = {increment}, cumulative: {cumulative_stats[stat]}")
                        # volt shield cd mult will give wrong values, but that is accounted for in calculate_cd(), which always gives 2 if cd mult is true
                        if stat in ["heat", "cold", "elec", "tox"]:
                            mod_order.append(stat)
    
    # Combine single element mods into combined element mods
    cumulative_stats, remaining_elements = combine_elements(cumulative_stats, mod_order, weapon_stats)
    
    return ModStats(
        base_damage=cumulative_stats["base_damage"],
        impact=cumulative_stats["impact"],
        puncture=cumulative_stats["puncture"],
        slash=cumulative_stats["slash"],
        heat=cumulative_stats["heat"],
        cold=cumulative_stats["cold"],
        elec=cumulative_stats["elec"],
        tox=cumulative_stats["tox"],
        viral=cumulative_stats["viral"],
        corrosive=cumulative_stats["corrosive"],
        gas=cumulative_stats["gas"],
        radiation=cumulative_stats["radiation"],
        magnetic=cumulative_stats["magnetic"],
        blast=cumulative_stats["blast"],
        faction=cumulative_stats["faction"],
        corpus=cumulative_stats["corpus"],
        fire_rate=cumulative_stats["fire_rate"],
        cc=cumulative_stats["cc"],
        cd=cumulative_stats["cd"],
        multishot=cumulative_stats["multishot"],
        electric_instance=cumulative_stats["electric_instance"],
        cd_multiplier=cumulative_stats["cd_multiplier"],
        eclipse=cumulative_stats["eclipse"],
        tenacious_bond=cumulative_stats["tenacious_bond"],
        flat_cc=cumulative_stats["flat_cc"],
        max_ammo=cumulative_stats["max_ammo"],
    ), remaining_elements

def sum_base_damage(weapon_stats):
    return (
        weapon_stats.impact + 
         weapon_stats.puncture + 
         weapon_stats.slash + 
         weapon_stats.heat + 
         weapon_stats.cold + 
         weapon_stats.elec + 
         weapon_stats.tox + 
         weapon_stats.viral + 
         weapon_stats.corrosive + 
         weapon_stats.gas + 
         weapon_stats.radiation + 
         weapon_stats.magnetic + 
         weapon_stats.blast
        )

def quantum(base_damage, mod_stats):
    return (base_damage * (1 + mod_stats.base_damage)) / 16

def damage_reduction(enemy_name):
    return 0.9 * math.sqrt(enemies.get(enemy_name)["armor"] / 2700)

def calculate_damage_modifiers(damage_reduction_value, enemy_name, mod_stats, enemies, health_classes):
    
    health_type = enemies.get(enemy_name)["health_type"]
    lazy_debug(lambda: f"Health Type: {health_type}")
    
    health_modifiers = health_classes.get(health_type)
    
    damage_modifiers = {}
    
    damage_types = ["impact", "puncture", "slash", "heat", "cold", "elec", "tox", "viral", "corrosive", "gas", "radiation", "magnetic", "blast"]
    
    # Calculate the damage modifier for each damage type
    for damage_type in damage_types:
        health_modifier = health_modifiers.get(damage_type, 0)
        damage_modifier = (1 + health_modifier) * (1 + mod_stats.eclipse) * (1 + mod_stats.faction + mod_stats.corpus) * (1 - damage_reduction_value)
        damage_modifiers[damage_type] = damage_modifier
    
    return damage_modifiers

def apply_mods_to_weapon_stats(base_damage, base_weapon_stats, mod_stats, quantum, remaining_elements):
    
    def calculate_new_stat(base_stat, stat_mod):
        return base_stat * (1 + stat_mod)

    def calculate_cc(base_stat, stat_mod, flat_cc):
        return (base_stat * (1 + stat_mod))+flat_cc

    def calculate_cd(base_stat, stat_mod, tenacious_bond, cd_multiplier):
        return (round((base_stat * (1 + stat_mod))*(4095/32))*(32/4095) + tenacious_bond) * (2 if cd_multiplier else 1)
        """
        --todo check tenacious bond quantization
        """

    def calculate_ips(base_stat, base_damage_mod, stat_mod, quantum):
        return round((base_stat * (1 + base_damage_mod) * (1 + stat_mod))/quantum) * quantum

    def calculate_single_element(element, base_damage, base_stat, base_damage_mod, stat_mod, quantum, remaining_elements):
        
        based_damage = round((base_damage * (1 + base_damage_mod) * stat_mod)/quantum) * quantum
        damage2 = round((base_stat * (1 + base_damage_mod))/quantum) * quantum if element in remaining_elements else 0

        total_damage = based_damage + damage2

        return total_damage

    def calculate_electric(volt_shield_electric_instance, base_damage, base_stat, base_damage_mod, stat_mod, quantum, remaining_elements):

        based_damage = round((base_damage * (1 + base_damage_mod) * (stat_mod + volt_shield_electric_instance))/quantum) * quantum
        damage2 = round((base_stat * (1 + base_damage_mod))/quantum) * quantum if "elec" in remaining_elements else 0

        total_damage = based_damage + damage2

        return total_damage

    def calculate_combined_element(element, base_damage, base_stat, base_damage_mod, stat_mod, quantum, base_stat1, base_stat2, remaining_elements):

        based_damage = round((base_damage * (1 + base_damage_mod) * stat_mod)/quantum) * quantum
        combined_element_damage = round((base_stat * (1 + base_damage_mod))/quantum) * quantum
        single_element_damage = (round((base_stat1 * (1 + base_damage_mod))/quantum) * quantum + round((base_stat2 * (1 + base_damage_mod))/quantum) * quantum) if element in remaining_elements else 0

        total_damage = based_damage + combined_element_damage + single_element_damage

        return total_damage
    
    return {
        "impact": calculate_ips(base_weapon_stats.impact, mod_stats.base_damage, mod_stats.impact, quantum),
        "puncture": calculate_ips(base_weapon_stats.puncture, mod_stats.base_damage, mod_stats.puncture, quantum),
        "slash": calculate_ips(base_weapon_stats.slash, mod_stats.base_damage, mod_stats.slash, quantum),
        "heat": calculate_single_element("heat", base_damage, base_weapon_stats.heat, mod_stats.base_damage, mod_stats.heat, quantum, remaining_elements),
        "cold": calculate_single_element("cold", base_damage, base_weapon_stats.cold, mod_stats.base_damage, mod_stats.cold, quantum, remaining_elements),
        "elec": calculate_electric(mod_stats.electric_instance, base_damage, base_weapon_stats.elec, mod_stats.base_damage, mod_stats.elec, quantum, remaining_elements),
        "tox": calculate_single_element("tox", base_damage, base_weapon_stats.tox, mod_stats.base_damage, mod_stats.tox, quantum, remaining_elements),
        "viral": calculate_combined_element("viral", base_damage, base_weapon_stats.viral, mod_stats.base_damage, mod_stats.viral, quantum, base_weapon_stats.cold, base_weapon_stats.tox, remaining_elements),
        "corrosive": calculate_combined_element("corrosive", base_damage, base_weapon_stats.corrosive, mod_stats.base_damage, mod_stats.corrosive, quantum, base_weapon_stats.elec, base_weapon_stats.tox, remaining_elements),
        "gas": calculate_combined_element("gas", base_damage, base_weapon_stats.gas, mod_stats.base_damage, mod_stats.gas, quantum, base_weapon_stats.heat, base_weapon_stats.tox, remaining_elements),
        "radiation": calculate_combined_element("radiation", base_damage, base_weapon_stats.radiation, mod_stats.base_damage, mod_stats.radiation, quantum, base_weapon_stats.heat, base_weapon_stats.elec, remaining_elements),
        "magnetic": calculate_combined_element("magnetic", base_damage, base_weapon_stats.magnetic, mod_stats.base_damage, mod_stats.magnetic, quantum, base_weapon_stats.cold, base_weapon_stats.elec, remaining_elements),
        "blast": calculate_combined_element("blast", base_damage, base_weapon_stats.blast, mod_stats.base_damage, mod_stats.blast, quantum, base_weapon_stats.heat, base_weapon_stats.cold, remaining_elements),
        "fire_rate": calculate_new_stat(base_weapon_stats.fire_rate, mod_stats.fire_rate),
        "cc": calculate_cc(base_weapon_stats.cc, mod_stats.cc, mod_stats.flat_cc),
        "cd": calculate_cd(base_weapon_stats.cd, mod_stats.cd, mod_stats.tenacious_bond, mod_stats.cd_multiplier),
        "multishot": calculate_new_stat(base_weapon_stats.multishot, mod_stats.multishot)
    }

    """
    --TODO: not implemented yet: rivens and riven ranges.
    """

def calculate_inflicted_damage(damage_modifiers, modded_weapon_stats):
    inflicted_damage = {}
    for damage_type, modifier in damage_modifiers.items():
        inflicted_damage[damage_type] = modded_weapon_stats[damage_type] * modifier
    return inflicted_damage

def calculate_total_noncrit_damage(inflicted_damage):
    return sum(inflicted_damage.values())   

def calculate_worst_critical_damage(inflicted_damage, new_weapon_stats):
    crit_chance = new_weapon_stats["cc"]
    crit_damage = new_weapon_stats["cd"]
    worst_critical_damage = inflicted_damage * (1 + math.floor(crit_chance) * (crit_damage - 1))
    return worst_critical_damage

def time_to_kill(new_weapon_stats, shots_to_kill, enemy_name):
    time_to_kill = (shots_to_kill / new_weapon_stats["fire_rate"])
    if enemy_name == "profit taker leg":
        time_to_kill = ((shots_to_kill * 4) / new_weapon_stats["fire_rate"])
    return time_to_kill

def corvas_calc(enemy_name, best_damage):
    full_charge_damage = best_damage * 2
    shots_to_kill_full_charge = math.ceil((enemies.get(enemy_name)["health"]) / full_charge_damage)
    charge_needed = ((enemies.get(enemy_name)["health"] / best_damage)-1) if ((enemies.get(enemy_name)["health"] / best_damage)-1) < 1 else "Won't 1-Shot"
    if charge_needed == "Won't 1-Shot":
        print(f"{GREEN}Full charge damage: \t\t\t{full_charge_damage}{RESET}\n\nShots to kill at full charge: {shots_to_kill_full_charge}\nCharge needed to oneshot: {RED}Won't 1-Shot{RESET}\n")
    else:
        print(f"{GREEN}Full charge damage: \t\t\t{full_charge_damage}{RESET}\n\nShots to kill at full charge: {shots_to_kill_full_charge}\nCharge needed to oneshot: {(charge_needed*100):.2f}%\n")

def weapon_calc(weapon_name, weapon_stats, enemy_name, selected_mods, damage_reduction_value, suppress_output=False):

    def weapon_calc(weapon_name, weapon_stats, enemy_name, selected_mods, damage_reduction_value):
        base_damage = sum_base_damage(weapon_stats)

        mod_stats, remaining_elements = parse_mod_stats(mod_data, selected_mods, weapon_stats)
        print(f"\nMod stats: {mod_stats.__dict__}")

        damage_modifiers = calculate_damage_modifiers(damage_reduction_value, enemy_name, mod_stats, enemies, health_type)
        formatted_modifiers = {k: f"{v:.2f}" for k, v in damage_modifiers.items()}
        print(f"\nDamage Modifiers (truncated): {formatted_modifiers}")

        quantum_value = quantum(base_damage, mod_stats)
        print(f"\nQuantum: {quantum_value}")

        new_weapon_stats = apply_mods_to_weapon_stats(base_damage, weapon_stats, mod_stats, quantum_value, remaining_elements)
        print(f"\nModded (Quantized) Weapon Stats: {new_weapon_stats}")

        inflicted_damage = calculate_inflicted_damage(damage_modifiers, new_weapon_stats)
        print(f"\nInflicted Damage: {inflicted_damage}")

        if weapon_name == "mausolon aoe" or weapon_name == "mausolon" and enemy_name == "profit taker leg":
            non_crit = (calculate_total_noncrit_damage(inflicted_damage)) * 1.00498 # nerf for mausolon vs profit taker leg
            worst_crit_total = (calculate_worst_critical_damage(non_crit, new_weapon_stats)) * 1.00268 # nerf for mausolon vs profit taker leg
        else:
            non_crit = calculate_total_noncrit_damage(inflicted_damage)
            worst_crit_total = calculate_worst_critical_damage(non_crit, new_weapon_stats)  

        return non_crit, worst_crit_total, new_weapon_stats

    if suppress_output:
        with suppress_prints():
            non_crit, worst_crit_total, new_weapon_stats = weapon_calc(weapon_name, weapon_stats, enemy_name, selected_mods, damage_reduction_value)
    else:
        non_crit, worst_crit_total, new_weapon_stats = weapon_calc(weapon_name, weapon_stats, enemy_name, selected_mods, damage_reduction_value)

    pellet = int(worst_crit_total)
    non_crit = int(non_crit) * ((int(new_weapon_stats["multishot"])) if not "aoe" in weapon_name else 1)
    worst_crit_total = int(worst_crit_total) * ((int(new_weapon_stats["multishot"])) if not "aoe" in weapon_name else 1)

    return non_crit, worst_crit_total, pellet, new_weapon_stats

def damage_calc(weapon_name, enemy_name, selected_mods):

    weapon_stats_base = parse_weapon_stats(weapon_data, weapon_name)
    lazy_debug(lambda: f"Weapon stats: {weapon_stats_base.__dict__}")
    lazy_debug(lambda: f"Mods: {selected_mods}")

    damage_reduction_value = damage_reduction(enemy_name)
    lazy_debug(lambda: f"Damage Reduction: {damage_reduction_value} for \"{enemy_name}\"\nCalculating damage...")

    non_crit, worst_crit_total, pellet, new_weapon_stats = weapon_calc(weapon_name, weapon_stats_base, enemy_name, selected_mods, damage_reduction_value, suppress_output= not debug_mode)

    if weapon_stats_base.aoe:
        weapon_name_aoe = f"{weapon_name} aoe"
        weapon_stats_aoe = parse_weapon_stats(weapon_data, weapon_name_aoe)
        lazy_debug(lambda: f"Weapon stats AOE portion: {weapon_stats_aoe.__dict__}")
        non_crit_aoe, worst_crit_total_aoe, pellet_aoe, new_weapon_stats_aoe = weapon_calc(weapon_name_aoe, weapon_stats_aoe, enemy_name, selected_mods, damage_reduction_value, suppress_output = not debug_mode)

    if mode == "damage calc":
        print(f"\n{CYAN}Pellet Damage (integer): \t\t{int(pellet)}{RESET}")
        print(f"\n{GREEN}Worst Critical Damage (integer): \t{int(worst_crit_total)}{RESET}")
        #print(f"\n{BLUE}Total Non-Crit Damage (integer): \t{int(non_crit)}{RESET}")
        if weapon_stats_base.aoe:
            print(f"\n{GREEN}Worst Critical Damage AOE (integer): \t{int(worst_crit_total_aoe)}{RESET}")
            #print(f"\n{BLUE}Total Non-Crit Damage AOE (integer): \t{int(non_crit_aoe)}{RESET}\n")
        total_per_shot = int(worst_crit_total) + (int(worst_crit_total_aoe) if weapon_stats_base.aoe else 0)
        print(f"\n{BLUE}Total damage per shot: \t\t\t{total_per_shot}{RESET}\n")
    
    def calculate_deviation():
        calculated_damage = [int(worst_crit_total), int(worst_crit_total_aoe)]
        lazy_debug(lambda: f"Calculated damage: {calculated_damage}")

        real_damage = "77572, 13982".strip().split(',')

        real_damage = [int(i) for i in real_damage]
        lazy_debug(lambda: f"Real damage: {real_damage}")

        deviation = [100-(abs(real_damage[i] / calculated_damage[i])*100) for i in range(2)]
        formatted_deviation = [f"{d:.3f}%" for d in deviation]
        lazy_debug(lambda: f"Deviation from real: {formatted_deviation}")
    
    if mode == "damage calc" and weapon_name == "mausolon" or weapon_name == "mausolon aoe":
        if debug_mode:
            calculate_deviation()
    
    return worst_crit_total, (worst_crit_total_aoe if weapon_stats_base.aoe else 0), new_weapon_stats

def check_compatibility(mod_combination):
    incompatible = []
    mod_set = set(mod_combination)  # Convert to set for faster lookups

    for mod in mod_combination:
        if 'riven' in mod:  # Skip Riven mods
            continue
        mod_incompatible = mod_data[mod].get("incompatible")
        if mod_incompatible:
            for incompatible_mod in mod_incompatible:
                if incompatible_mod in mod_set:
                    incompatible.append((mod, incompatible_mod))
                    #print(f"Incompatible pair found: {mod} and {incompatible_mod}")
    
    return incompatible

def evaluate_combination(weapon_name, enemy_name, mod_combination):
    incompatible = check_compatibility(mod_combination)
    selected_mods = scan_mods(','.join(mod_combination))
    worst_crit_total, worst_crit_total_aoe, new_weapon_stats = damage_calc(weapon_name, enemy_name, selected_mods)

    if incompatible:
        worst_crit_total = 0
    #debug print(f"evaluated combination: {mod_combination} with damage: {worst_crit_total}")
    total_damage = worst_crit_total + worst_crit_total_aoe

    return mod_combination, worst_crit_total, worst_crit_total_aoe, new_weapon_stats

def find_best_build(weapon_name, enemy_name, max_mods, extra_mods=None):

    weapon_stats = parse_weapon_stats(weapon_data, weapon_name)
    applicable_mods = [mod for mod in mod_data if mod_data[mod].get("weapon_type") == weapon_stats.weapon_type or mod_data[mod].get("weapon_type") == weapon_name]
    
    # Split the extra mods string into a list
    if extra_mods:
        extra_mods_list = extra_mods.split(', ')
    else:
        extra_mods_list = []
    
    best_damage = float('-inf')
    best_combination = None
    total_calulated_combinations = 0
    best_ttk = float('inf')
    best_ratio = float('-inf')

    mod_combinations = []
    for num_mods in range(1, max_mods + 1):
        mod_combinations.extend(itertools.combinations(applicable_mods, num_mods))
        # function to find all possible combinations of mods

    with multiprocessing.Pool() as pool:
        results = pool.starmap(evaluate_combination, [(weapon_name, enemy_name, list(mod_combination) + extra_mods_list) for mod_combination in mod_combinations])

    for mod_combination, worst_crit_total, worst_crit_total_aoe, new_weapon_stats in results:
        if worst_crit_total == 0:
            continue
        if worst_crit_total > best_damage:
            best_damage = worst_crit_total
            best_damage_aoe = worst_crit_total_aoe
            best_new_weapon_stats = new_weapon_stats
            best_combination = mod_combination
        shots_to_kill = math.ceil((enemies.get(enemy_name)["health"]) / (int(worst_crit_total) + (int(worst_crit_total_aoe) if parse_weapon_stats(weapon_data, weapon_name).aoe else 0)))
        ttk = time_to_kill(new_weapon_stats, shots_to_kill, enemy_name)
        #if (ttk < best_ttk) or (ttk == best_ttk and (worst_crit_total + worst_crit_total_aoe) > (best_ttk_damage + best_ttk_damage_aoe)): 
        #    best_ttk = ttk
        #    best_ttk_combo = mod_combination
        #    best_ttk_damage = worst_crit_total
        #    best_ttk_damage_aoe = worst_crit_total_aoe
        #    shots_to_kill_best_ttk = shots_to_kill
        ratio = (worst_crit_total + worst_crit_total_aoe) / (ttk) # todo adjust ttk ratio
        if ratio > best_ratio:
            best_ratio = ratio
            best_ttk = ttk
            best_ttk_combo = mod_combination
            best_ttk_damage = worst_crit_total
            best_ttk_damage_aoe = worst_crit_total_aoe
            shots_to_kill_best_ttk = shots_to_kill
        #debug print(f"Evaluated combination: {mod_combination} with damage: {(worst_crit_total + worst_crit_total_aoe)} and ttk: {ttk:.2f} seconds with dmg/ttk ratio: {ratio:.2f}")
        total_calulated_combinations += 1
    print(f"\ntotal combinations evaluated: {total_calulated_combinations}")
    
    return best_combination, best_damage, best_damage_aoe, best_new_weapon_stats, best_ttk_combo, best_ttk, best_ttk_damage, best_ttk_damage_aoe, shots_to_kill_best_ttk

def main():

    global mode 
    mode = "best build"
    #mode = "damage calc"
    global debug_mode
    debug_mode = 0
    start_time = time.time()

    weapon_name = "velocitus"
    print(f"\nWeapon: {weapon_name}")
    
    enemy_name = "profit taker leg" 

    extra_mods = "riven 97.5cc 48dtc 95.9dmg -1ammo, mech intrinsic, deathbringer, damage bless"#"riven 100cc 82dmg 44corpus -44.7ammo, eclipse, damage bless, volt shield"
    #if weapon_name == "mausolon":
    #    extra_mods += ", ammo chain"
    
    extra_mods_list = extra_mods.strip().split(', ')
    warframe_mech_mods = []
    for mod in extra_mods_list:
        if mod in mod_data:
            weapon_type = mod_data[mod].get('weapon_type', [])
            if isinstance(weapon_type, list):
                if 'warframe' in weapon_type or 'mech' in weapon_type:
                    warframe_mech_mods.append(mod)
            elif weapon_type in ['warframe', 'mech']:
                warframe_mech_mods.append(mod)

    max_mods = 8 - (len(extra_mods_list) - len(warframe_mech_mods))

    #mods_input = """riven 97.5cc 123.3elec 95.9dmg, mech intrinsic, volt shield, 
    #parallax scope, ammo chain, electrified barrel, mausolon riven,
    #polar magazine, primed dual rounds, critical focus, primed rubedo-lined barrel"""
    mods_input = ['automatic trigger', 'critical focus', 'electrified barrel', 'parallax scope', 'polar magazine', 'primed dual rounds', 'primed rubedo-lined barrel', 'riven 123.1cd 97.7fr', 'mech intrinsic', 'damage bless', 'deathbringer']

    if mode == "damage calc":
        if "riven" in mods_input:
            grade_riven_mod(mods_input, weapon_name)
        print(f"\nSelected Mods: {mods_input}")
        selected_mods = scan_mods(mods_input)
        worst_crit_total, worst_crit_total_aoe, new_weapon_stats = damage_calc(weapon_name, enemy_name, selected_mods)
        shots_to_kill = math.ceil((enemies.get(enemy_name)["health"]) / (int(worst_crit_total) + (int(worst_crit_total_aoe) if parse_weapon_stats(weapon_data, weapon_name).aoe else 0)))
        print(f"Shots to kill: {shots_to_kill}\n")
        ttk = time_to_kill(new_weapon_stats, shots_to_kill, enemy_name)
        print(f"Time to kill: {ttk:.2f} seconds\n")
        if weapon_name == "corvas":
            corvas_calc(enemy_name, worst_crit_total)
            
    elif mode == "best build":
        if "riven" in extra_mods:
            grade_riven_mod(extra_mods, weapon_name)
        best_combination, best_damage, best_damage_aoe, best_new_weapon_stats, best_ttk_combo, best_ttk, best_ttk_damage, best_ttk_damage_aoe, shots_to_kill_best_ttk = find_best_build(weapon_name, enemy_name, max_mods, extra_mods)
        shots_to_kill = math.ceil((enemies.get(enemy_name)["health"]) / (int(best_damage) + (int(best_damage_aoe) if parse_weapon_stats(weapon_data, weapon_name).aoe else 0)))
        ttk_highest_damage = time_to_kill(best_new_weapon_stats, shots_to_kill, enemy_name)
        #if ttk_highest_damage <= (best_ttk * 1.1): # added a factor of 10% to have a higher weighting for getting high damage - less shots to kill builds (to account for archgun cooldown)
        print(f"\nHighest Damage Build: {best_combination} \nwith damage: {(best_damage + best_damage_aoe)}\nShots to kill: {shots_to_kill} \nMinimum ttk all 4 legs: {ttk_highest_damage:.2f} seconds\n")
        #else:
        print(f"Best ttk combo: {best_ttk_combo} \nwith damage: {(best_ttk_damage + best_ttk_damage_aoe)}\nShots to kill: {shots_to_kill_best_ttk} \nwith ttk (all 4 legs): {best_ttk:.2f} seconds\n")
        if weapon_name == "corvas":
            corvas_calc(enemy_name, best_damage)

    print(f"Compute time: {time.time() - start_time:.10f} seconds\n")

if __name__ == "__main__":
    main()