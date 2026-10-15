"""Rule-based triage. Rules are deliberately simple so a volunteer can see why a level was given."""

LEVELS = {0: "Critical", 1: "Vulnerable", 2: "General"}


def triage(e):
    """Return (priority, reasons). 0 = critical medical, 1 = vulnerable, 2 = general."""
    critical, vulnerable = [], []
    if e.get("unconscious"):
        critical.append("Unconscious")
    if e.get("injury_severity") == "critical":
        critical.append("Critical injury")
    if e.get("injury_severity") == "serious":
        critical.append("Serious injury")
    if e.get("needs_oxygen"):
        critical.append("Needs oxygen")
    age = e.get("age")
    if e.get("pregnant"):
        vulnerable.append("Pregnant")
    if age is not None and age >= 60:
        vulnerable.append("Aged 60 or over")
    if age is not None and age <= 5:
        vulnerable.append("Child aged 5 or under")
    if e.get("uses_wheelchair"):
        vulnerable.append("Uses wheelchair")
    if e.get("injury_severity") == "minor":
        vulnerable.append("Minor injury")
    if critical:
        return 0, critical + vulnerable
    if vulnerable:
        return 1, vulnerable
    return 2, []
