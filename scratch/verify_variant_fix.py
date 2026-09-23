import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from models.product import get_product_by_part_no, get_variants_of
from PySide6.QtWidgets import QApplication

p = get_product_by_part_no("162")
print("Product 162 from DB:", p.get("name"), "is_template:", p.get("is_template"), "has_variants:", p.get("has_variants"))
vars = get_variants_of("162")
print("Variants of 162:", vars)

# Test helper matching main_window logic
def is_template_product(product: dict) -> bool:
    if not bool(product.get("is_template") or product.get("has_variants")):
        return False
    part_no = (product.get("part_no") or "").strip()
    if not part_no:
        return False
    try:
        from models.product import get_variants_of
        return bool(get_variants_of(part_no))
    except Exception:
        return False

print("is_template_product(p):", is_template_product(p))
assert is_template_product(p) == False, "Expected False because no synced variants exist!"
print("Test passed: Template without synced variants is treated as standard product.")

app = QApplication.instance() or QApplication([])
from views.dialogs.variant_picker_dialog import VariantPickerDialog
dlg = VariantPickerDialog(template=p)
assert dlg.selected_variant is None
print("VariantPickerDialog initialized cleanly.")
print("All verification checks succeeded!")
