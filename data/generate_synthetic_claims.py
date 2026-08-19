"""Generate a fully synthetic claim-notes dataset.

Every note in synthetic_claims.csv is produced by this script from templates
and word lists. No real claim, policyholder, or insurer data was used at any
point. The generator is committed alongside the data so that provenance is
demonstrable, and so you can regenerate, rebalance, or extend the dataset.

Labelling rules (documented in data/README.md):
  MOTOR_BI         motor incident where any person is injured, however minor
  MOTOR_PD         motor incident, vehicle/property damage only, no injury
  PROPERTY_WATER   escape of water / internal leak damage at insured property
  PROPERTY_FIRE    fire, smoke, or fire-suppression damage (origin governs)
  LIABILITY_INJURY third-party injury on or arising from insured premises

Usage:
    python data/generate_synthetic_claims.py            # writes 200 rows
    python data/generate_synthetic_claims.py --n 500    # larger set
"""

import argparse
import csv
import random
from pathlib import Path

SEED = 20260721

FIRST = ["Ms Tan", "Mr Okafor", "Mrs Petrova", "Mr Lindqvist", "Ms Reyes",
         "Mr Nakamura", "Mrs Osei", "Ms Kowalski", "Mr Brennan", "Ms Achebe"]
STREETS = ["Elm Ave", "Harbour Rd", "Mill Lane", "Station Pde", "Cedar Ct",
           "Foundry Way", "Beacon St", "Orchard Cl"]
CARS = ["hatchback", "SUV", "saloon", "estate", "van", "pickup"]
ROOMS = ["kitchen", "bathroom", "utility room", "hallway", "loft", "en-suite"]
SHOPS = ["supermarket", "cafe", "gym", "warehouse unit", "showroom", "hotel lobby"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _dt(rng):
    return f"{rng.randint(1, 28):02d} {rng.choice(MONTHS)}"


def _amt(rng, lo, hi):
    return f"${rng.randrange(lo, hi, 50):,}"


# --- template banks -----------------------------------------------------
# Each entry: (weight, callable(rng) -> note text). "Hard" templates carry
# deliberately mixed signals so the task is realistic rather than trivial;
# gold labels for hard cases follow the labelling rules above.

def motor_bi(rng):
    t = rng.random()
    p, d, c = rng.choice(FIRST), _dt(rng), rng.choice(CARS)
    if t < 0.25:
        return (f"FNOL {d}. Insd {c} rear-ended by TP at traffic lights, "
                f"{rng.choice(STREETS)}. Driver reports neck stiffness, GP visit "
                f"booked. Rear bumper and boot damage, est {_amt(rng, 1200, 4200)}. "
                f"TP insurer notified.")
    if t < 0.5:
        return (f"{d}: multi-vehicle shunt on ring road. Insd driver {p} attended "
                f"A&E with wrist pain, discharged same day. Vehicle recovered, "
                f"NSD front end. Awaiting engineer report and TP details.")
    if t < 0.7:
        return (f"Claim opened {d}. Cyclist collision at junction of "
                f"{rng.choice(STREETS)}. Cyclist sustained leg injury, ambulance "
                f"attended. Insd {c} minor wing damage. Liability under "
                f"investigation, injury reserve to be set.")
    if t < 0.85:  # hard: damage-heavy wording, injury emerges late
        return (f"FNOL {d}. Insd {c} vs bollard, front axle and radiator damage, "
                f"repair est {_amt(rng, 2400, 6200)}. Note added {_dt(rng)}: "
                f"passenger now reporting lower back pain since incident, "
                f"physio referral. Update reserve.")
    # hard: low damage, symptoms flagged
    return (f"{d}. Low-speed car park contact with TP vehicle. Cosmetic scuffs "
            f"only, {_amt(rng, 300, 900)}. TP driver mentioned headache at scene "
            f"and has since submitted whiplash claim via solicitors.")


def motor_pd(rng):
    t = rng.random()
    d, c = _dt(rng), rng.choice(CARS)
    if t < 0.3:
        return (f"FNOL {d}. Insd {c} reversed into gatepost at home address. "
                f"Rear panel dented, no injuries, no TP. Repair est "
                f"{_amt(rng, 600, 2100)}. Excess applies.")
    if t < 0.55:
        return (f"{d}: TP ran red light and struck insd nearside doors. Both "
                f"drivers exchanged details, both confirmed uninjured at scene "
                f"and on follow-up call. Doors and B-pillar, est "
                f"{_amt(rng, 1800, 5400)}. Pursuing recovery from TP insurer.")
    if t < 0.75:
        return (f"Windscreen and bonnet damage from debris on motorway, {d}. "
                f"No other vehicle involved, no injury. Glass replaced "
                f"{_amt(rng, 350, 800)}, bonnet respray quoted.")
    if t < 0.9:  # hard: dramatic wording, explicitly no injury
        return (f"{d}. Insd {c} aquaplaned and left carriageway into hedge. "
                f"Airbags deployed, vehicle likely total loss "
                f"{_amt(rng, 6000, 14000)}. Driver checked by paramedics at "
                f"scene, no injuries reported, declined hospital.")
    # hard: water word inside a motor claim
    return (f"FNOL {d}. Flood water on {rng.choice(STREETS)} ingressed insd "
            f"{c} footwells, electrics fault. No occupants at time, no injury. "
            f"Engineer to assess, est {_amt(rng, 2000, 7500)}.")


def prop_water(rng):
    t = rng.random()
    d, r = _dt(rng), rng.choice(ROOMS)
    if t < 0.3:
        return (f"{d}: escape of water from burst pipe in {r}. Ceiling below "
                f"collapsed, flooring lifted. Dehumidifiers on site, strip-out "
                f"quote {_amt(rng, 2500, 9000)}. Policyholder in situ.")
    if t < 0.55:
        return (f"FNOL {d}. Washing machine hose failed while insd away, water "
                f"tracked through {r} into hallway. Contents damage inc laminate "
                f"and skirting. Leak detection attended, mains isolated.")
    if t < 0.75:
        return (f"Slow leak from {r} pipework discovered during redecoration, "
                f"{d}. Joist damp readings high, trace and access cover "
                f"confirmed. Drying regime 2-3 wks before reinstatement.")
    if t < 0.9:  # hard: neighbour origin
        return (f"{d}. Water ingress from flat above (their {r} overflow). "
                f"Insd ceiling stained and light fitting affected. Recovery "
                f"against upstairs policy to be considered, est "
                f"{_amt(rng, 900, 3200)}.")
    # hard: fire word inside a water claim
    return (f"FNOL {d}. Pipe burst adjacent to fireplace chimney breast in "
            f"{r}; plaster and hearth surround water damaged. No fire "
            f"involved. Est {_amt(rng, 1400, 4800)}.")


def prop_fire(rng):
    t = rng.random()
    d, r = _dt(rng), rng.choice(ROOMS)
    if t < 0.3:
        return (f"{d}: pan fire in {r}, extinguished by insd before brigade "
                f"arrival. Smoke damage throughout ground floor, cabinetry "
                f"scorched. Cleaning and redecoration est "
                f"{_amt(rng, 3000, 11000)}.")
    if t < 0.55:
        return (f"FNOL {d}. Electrical fault in {r} caused localised fire. Fire "
                f"service attended, property safe. Alternative accommodation "
                f"arranged 2 wks. Loss adjuster instructed.")
    if t < 0.75:
        return (f"Garden outbuilding destroyed by fire {d}, cause TBC, possible "
                f"disposable BBQ. Fence panels and adjacent cladding heat "
                f"damaged. No injuries. Est {_amt(rng, 4000, 15000)}.")
    if t < 0.9:  # hard: suppression water damage, origin fire
        return (f"{d}. Small fire in {r} extinguished by sprinkler activation. "
                f"Fire damage limited, but water from suppression affected "
                f"stock and flooring below. Combined est "
                f"{_amt(rng, 5000, 18000)}. Treat as single fire loss.")
    # hard: smoke only
    return (f"FNOL {d}. Smoke logging from neighbouring property fire entered "
            f"insd home via open windows. No flame damage to insd risk; soot "
            f"deposits on soft furnishings, specialist clean required.")


def liab_injury(rng):
    t = rng.random()
    d, s = _dt(rng), rng.choice(SHOPS)
    p = rng.choice(FIRST)
    if t < 0.3:
        return (f"{d}: customer {p} slipped on wet floor at insd {s}, no wet "
                f"floor sign per CCTV. Ankle injury, taken to hospital. "
                f"Incident book completed, EL/PL claim expected.")
    if t < 0.55:
        return (f"FNOL {d}. Visitor tripped on raised paving at insd premises "
                f"entrance ({s}). Fractured wrist confirmed. Solicitors letter "
                f"of claim received, indemnity being reviewed.")
    if t < 0.75:
        return (f"Delivery driver struck by falling stock in insd {s} "
                f"storeroom, {d}. Shoulder injury, off work. RIDDOR "
                f"reportable. Reserve for GD and specials.")
    if t < 0.9:  # hard: property words in a liability claim
        return (f"{d}. Loose handrail at insd {s} gave way; member of public "
                f"fell on stairs, head laceration, glasses broken. Handrail "
                f"since repaired {_amt(rng, 150, 400)}. Injury claim "
                f"anticipated.")
    # hard: injury phrasing, third party on premises
    return (f"FNOL {d}. Child caught fingers in door at insd {s}; first aid "
            f"given on site, parents attended A&E as precaution. Awaiting "
            f"further contact from family.")


CATEGORIES = [
    ("MOTOR_BI", motor_bi),
    ("MOTOR_PD", motor_pd),
    ("PROPERTY_WATER", prop_water),
    ("PROPERTY_FIRE", prop_fire),
    ("LIABILITY_INJURY", liab_injury),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="total rows (default 200)")
    ap.add_argument("--out", default=str(Path(__file__).with_name("synthetic_claims.csv")))
    args = ap.parse_args()

    rng = random.Random(SEED)
    per = args.n // len(CATEGORIES)
    rows = []
    for label, fn in CATEGORIES:
        for _ in range(per):
            rows.append({"note": fn(rng), "category": label})
    rng.shuffle(rows)
    for i, row in enumerate(rows, start=1):
        row["claim_id"] = f"SYN-{i:04d}"

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "note", "category"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} synthetic claim notes to {args.out}")


if __name__ == "__main__":
    main()
