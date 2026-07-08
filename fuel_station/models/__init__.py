# ── Phase 2: Master Data Models ─────────────────────────────────────────────
# Import order follows the dependency chain:
#   fuel.type  →  fuel.tank  →  fuel.pump  →  fuel.nozzle
from . import fuel_type
from . import fuel_tank
from . import fuel_pump
from . import fuel_nozzle

# ── Phase 3: Operations Models ───────────────────────────────────────────────
# Dependency order:
#   fuel.fleet  (standalone — referenced by fuel.sale)
#   fuel.expense (standalone — referenced by fuel.shift)
#   fuel.sale   (references: fuel.shift [forward], fuel.fleet, fuel.nozzle)
#   fuel.shift.line (references: fuel.shift [forward], fuel.nozzle)
#   fuel.shift  (references: fuel.shift.line, fuel.sale, fuel.expense)
#   fuel.purchase (references: fuel.tank)
from . import fuel_fleet
from . import fuel_expense
from . import fuel_sale
from . import fuel_shift_line
from . import fuel_shift
from . import fuel_purchase

