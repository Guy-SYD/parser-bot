FIELD_ALIASES = {
    "LOA": [
        "loa",
        "length overall",
        "overall length",
        "loa (m/ft)",
        "loa (ft/m)",
    ],

    "BEAM": [
        "beam",
        "beam overall",
        "max beam",
        "breadth",
        "beam (m/ft)",
        "beam (ft/m)",
    ],

    "MAX_DRAFT": [
        "max draft",
        "maximum draft",
        "draft",
        "draft full load",
        "draft (full load)",
        "draft overall",
        "max draught",
        "maximum draught",
        "draught",
    ],

    "MIN_DRAFT": [
        "min draft",
        "minimum draft",
        "light draft",
        "draft light",
        "min draught",
        "minimum draught",
    ],

    "YEAR": [
        "year built",
        "built",
        "year",
        "delivery year",
        "delivery/model",
        "delivered",
    ],

    "REFIT": [
        "refit year",
        "refit",
        "last refit",
        "major refit",
    ],

    "BUILDER": [
        "builder",
        "built by",
        "shipyard",
        "manufacturer",
    ],

    "GT": [
        "gross tonnage",
        "tonnage",
        "gt",
        "gross tons",
    ],

    "STATEROOMS": [
        "staterooms",
        "cabins",
        "guest staterooms",
        "guest cabins",
    ],

    "GUESTS": [
        "guest accommodation",
        "guest capacity",
        "guest berths",
        "guests",
        # Note: "sleeps" intentionally excluded — in YATCO brochures "Sleeps: N" is
        # often the berth count (crew included), which differs from guest count.
        # If a PDF only has "Sleeps:", add it here and it will be used as a fallback.
    ],

    "CREW": [
        "crew",
        "crew accommodation",
        "crew cabins",
        "crew berths",
        "crew capacity",
    ],

    "YACHT_TYPE": [
        "type",
        "yacht type",
        "vessel type",
    ],

    "MODEL": [
        "model",
        "yacht model",
        "model name",
    ],

    "HULL_NUMBER": [
        "hull no",
        "hull no.",
        "hull number",
        "hull #",
        "official registration",
        "registration number",
    ],

    "HULL_MATERIAL": [
        "hull material",
        "construction",
    ],

    "HULL_CONFIGURATION": [
        "hull config",
        "hull configuration",
        "configuration",
        "hull type",
    ],

    "SUPERSTRUCTURE_MATERIAL": [
        "superstructure",
        "superstructure material",
    ],

    "EXTERIOR_DESIGNER": [
        "exterior designer",
        "ext designer",
        "designer exterior",
    ],

    "INTERIOR_DESIGNER": [
        "interior designer",
        "int designer",
        "designer interior",
    ],

    "NAVAL_ARCHITECT": [
        "naval architect",
        "hull designer",
        "architect",
    ],

    "MAX_SPEED": [
        "max speed",
        "maximum speed",
        "top speed",
        "speed max",
    ],

    "CRUISE_SPEED": [
        "cruise speed",
        "cruising speed",
        "speed cruising",
    ],

    "ECONOMICAL_SPEED": [
        "economical speed",
        "economic speed",
        "eco speed",
    ],

    "MAX_RANGE": [
        "max range",
        "maximum range",
        "range at max speed",
    ],

    "CRUISE_RANGE": [
        "cruise range",
        "cruising range",
        "range at cruise",
        "range at cruising speed",
    ],

    "ECONOMICAL_RANGE": [
        "economical range",
        "economic range",
        "range at economical speed",
        "range at economy speed",
    ],

    "CRUISING_CONSUMPTION": [
        "cruising consumption",
        "cruise consumption",
        "consumption at cruise",
        "fuel consumption at cruise",
    ],

    "ECONOMICAL_CONSUMPTION": [
        "economical consumption",
        "economic consumption",
        "consumption at economical speed",
        "fuel consumption at economical speed",
    ],

    "FUEL": [
        "fuel capacity",
        "fuel cap",
        "fuel",
        "fuel tank",
        "fuel tanks",
    ],

    "FRESH_WATER": [
        "water capacity",
        "fresh water",
        "freshwater",
        "fresh water capacity",
        "water tank",
        "water tanks",
    ],

    "LUBE_OIL": [
        "lube oil",
        "lub oil",
        "lubricating oil",
        "engine oil",
    ],

    "BLACK_WATER_HOLDING_TANK": [
        "black water holding tank",
        "black water",
        "blackwater",
        "sewage tank",
        "black tank",
    ],

    "GREY_WATER_HOLDING_TANK": [
        "grey water holding tank",
        "gray water holding tank",
        "grey water",
        "gray water",
        "grey tank",
        "gray tank",
    ],

    "WASTE_OIL": [
        "waste oil",
        "waste oil tank",
        "sludge tank",
    ],

    "REGISTRY_PORT": [
        "port of registry",
        "registry port",
        "registry",
        "home port",
    ],

    "IACS_SOCIETY": [
        "iacs society",
        "classification",
        "class",
        "classifications",
        "classification society",
    ],

    "FLAG": [
        "flag",
        "flag state",
        "registered flag",
    ],

    "COMMERCIAL_COMPLIANCE": [
        "commercial compliance",
        "commercially compliant",
        "commercial compliant",
        "commercial use",
        "charter compliant",
        "mca",
        "mca compliant",
        "coded",
    ],

    "IMO": [
        "imo",
        "imo number",
    ],

    "MMSI": [
        "mmsi",
        "mmsi number",
    ],
}

UNIT_FIELD_ALIASES = {
    "MAX_SPEED": [
        "max speed",
        "maximum speed",
        "top speed",
        "speed max",
    ],

    "CRUISE_SPEED": [
        "cruise speed",
        "cruising speed",
        "speed cruising",
        "speed cruise",
    ],

    "ECONOMICAL_SPEED": [
        "economical speed",
        "economic speed",
        "eco speed",
        "economy speed",
    ],

    "MAX_RANGE": [
        "max range",
        "maximum range",
        "range at max speed",
        "range max",
    ],

    "CRUISE_RANGE": [
        "cruise range",
        "cruising range",
        "range at cruise",
        "range at cruising speed",
        "range cruise",
    ],

    "ECONOMICAL_RANGE": [
        "economical range",
        "economic range",
        "range at economical speed",
        "range at economy speed",
        "range economical",
    ],

    "CRUISING_CONSUMPTION": [
        "cruising consumption",
        "cruise consumption",
        "consumption at cruise",
        "consumption at cruising speed",
        "fuel consumption at cruise",
        "fuel consumption at cruising speed",
    ],

    "ECONOMICAL_CONSUMPTION": [
        "economical consumption",
        "economic consumption",
        "consumption at economical speed",
        "consumption at economy speed",
        "fuel consumption at economical speed",
        "fuel consumption at economy speed",
    ],

    "FUEL": [
        "fuel capacity",
        "fuel cap",
        "fuel",
        "fuel tank",
        "fuel tanks",
    ],

    "FRESH_WATER": [
        "fresh water capacity",
        "fresh water",
        "freshwater",
        "water capacity",
        "water cap",
        "water tank",
        "water tanks",
    ],

    "LUBE_OIL": [
        "lube oil",
        "lub oil",
        "lubricating oil",
        "engine oil",
        "lube oil capacity",
    ],

    "BLACK_WATER_HOLDING_TANK": [
        "black water holding tank",
        "black water tank",
        "black water",
        "blackwater",
        "black tank",
        "sewage tank",
    ],

    "GREY_WATER_HOLDING_TANK": [
        "grey water holding tank",
        "gray water holding tank",
        "grey water tank",
        "gray water tank",
        "grey water",
        "gray water",
        "grey tank",
        "gray tank",
    ],

    "WASTE_OIL": [
        "waste oil",
        "waste oil tank",
        "waste oil capacity",
        "sludge tank",
    ],
}

MACHINERY_FIELD_ALIASES = {
    "STABILIZER_MANUFACTURER": [
        "stabilizer manufacturer",
        "stabiliser manufacturer",
        "stabilizers",
        "stabilisers",
        "fins",
    ],
    "STABILIZER_TYPE": [
        "stabilizer type",
        "stabiliser type",
        "stabilizer system",
        "stabiliser system",
    ],
    "STABILIZER_SPEED": [
        "stabilizer speed",
        "stabiliser speed",
        "zero speed stabilizers",
        "zero speed stabilisers",
        "underway stabilizers",
        "underway stabilisers"
    ],
    "BOW_THRUSTER": [
        "bow thruster",
        "bowthruster",
    ],
    "STERN_THRUSTER": [
        "stern thruster",
        "sternthruster",
    ],
    "STEERING": [
        "steering system",
        "steering",
    ],
    "SHAFTS_PROPELLERS": [
        "shafts/propellers",
        "shafts & propellers",
        "propulsion type",
        "propulsion",
        "shafts",
        "propellers",
    ],
    "SHORE_POWER": [
        "shore power",
    ],
    "GEARBOX": [
        "gear boxes",
        "gearboxes",
        "gearbox",
        "gear box",
        "transmission",
    ],
}
