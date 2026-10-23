#!/usr/bin/env python3
"""
Patch printing_service.py so every receipt is laid out in a fixed 203-dpi
"design space" and scaled to the real printer resolution.

Usage:
    python patch_printing.py path/to/printing_service.py

A backup is written next to the file as printing_service.py.bak.
Every replacement is counted; if anything does not match exactly the script
stops WITHOUT touching your file.
"""
import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# New helper methods, inserted into PrintingService right after __init__
# ----------------------------------------------------------------------------
HELPERS = '''
    # =========================================================================
    # PRINTER SETUP - resolution independent
    # All layout code draws in a fixed 203-dpi "design space" (80mm ~ 550 units,
    # 58mm ~ 380 units). _begin_painter() scales that space to the real printer
    # resolution, so identical coordinates give an identical physical layout on
    # any driver (180 / 203 / 300 / 600 dpi, generic drivers, etc).
    # =========================================================================
    STRICT_PRINTER_NAME = True   # False -> fall back to default printer if name not found

    @staticmethod
    def _print_log(msg: str) -> None:
        """Print + append to app_data/print_debug.log (so failing PCs can be compared)."""
        print(msg)
        try:
            log = _get_app_data_dir() / "print_debug.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists() and log.stat().st_size > 512_000:
                log.write_text("", encoding="utf-8")
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\\n")
        except Exception:
            pass

    def _setup_printer(self, printer_name=None, height_mm=2000, paper_size=None) -> QPrinter:
        """Create a QPrinter with an explicit page size. Also sets self.paper_width."""
        paper_size = paper_size or get_configured_paper_size()
        is_58 = str(paper_size).strip().lower().startswith("58")
        width_mm = 58 if is_58 else 80
        self.paper_width = 380 if is_58 else 550

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        if printer_name and printer_name != "(None)":
            info = QPrinterInfo.printerInfo(printer_name)
            if not info.isNull():
                printer.setPrinterName(printer_name)
            elif self.STRICT_PRINTER_NAME:
                raise RuntimeError(
                    f"Printer '{printer_name}' was not found. "
                    f"Check the printer name in Settings."
                )
            else:
                self._print_log(f"[PRINT] WARNING printer {printer_name!r} not found - using default")

        ok_size = printer.setPageSize(
            QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter))
        ok_margin = printer.setPageMargins(
            QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

        try:
            pa = printer.paperRect(QPrinter.Unit.Millimeter)
            pr = printer.pageRect(QPrinter.Unit.Millimeter)
            self._print_log(
                f"[PRINT] printer={printer.printerName()!r} res={printer.resolution()}dpi "
                f"paper={pa.width():.1f}x{pa.height():.1f}mm "
                f"printable={pr.width():.1f}x{pr.height():.1f}mm "
                f"setPageSize={ok_size} setMargins={ok_margin} "
                f"requested={width_mm}x{height_mm}mm"
            )
        except Exception as e:
            print(f"[PRINT] could not log printer info: {e}")
        return printer

    def _begin_painter(self, printer: QPrinter) -> QPainter:
        """Start painting and map the 203-dpi design space onto the real printer."""
        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError(
                "Could not start the print job. Is the printer online and its driver installed?")

        scale = (printer.resolution() or DESIGN_DPI) / DESIGN_DPI
        page_w = printer.pageRect(QPrinter.Unit.DevicePixel).width() / scale  # design units
        painter.scale(scale, scale)

        offset = 0.0
        fit = 1.0
        if page_w >= self.paper_width:
            offset = (page_w - self.paper_width) / 2.0     # centre in the printable width
            painter.translate(offset, 0)
        else:
            fit = page_w / self.paper_width                # shrink to fit rather than clip
            painter.scale(fit, fit)

        self._print_log(
            f"[PRINT] scale={scale:.3f} printable_width={page_w:.0f} "
            f"design_width={self.paper_width} offset={offset:.1f} fit={fit:.3f}"
        )
        return painter
'''


class PatchError(Exception):
    pass


def sub_exact(text, pattern, repl, expected, label, flags=0):
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != expected:
        raise PatchError(f"{label}: expected {expected} match(es), found {n}")
    print(f"  ok  {label} ({n})")
    return new


def patch(src: str) -> str:
    # 1. imports + constant --------------------------------------------------
    src = sub_exact(
        src,
        r"(from PySide6\.QtGui import QPageSize\n)",
        r"\1# pyrefly: ignore [missing-import]\nfrom PySide6.QtGui import QPageLayout\n",
        1, "import QPageLayout")

    src = sub_exact(
        src,
        r'(ORANGE[ \t]*= "#c05a00"\n)',
        r"\1\n# All layouts are drawn in a fixed 203-dpi design space and scaled to the\n"
        r"# real printer resolution (see PrintingService._begin_painter).\n"
        r"DESIGN_DPI = 203.0\n",
        1, "DESIGN_DPI constant")

    # 2. read settings from the app-data dir FIRST (not cwd-relative paths) ----
    src = sub_exact(
        src,
        r"candidate_paths = \[\n",
        'candidate_paths = [\n'
        '            os.path.join(get_app_data_dir(), "hardware_settings.json"),\n',
        1, "settings path priority")

    # 3. printer creation ------------------------------------------------------
    # 3a. dynamic-height methods (invoice, cashier slip, shift recon)
    dyn = (
        r'printer = QPrinter\(QPrinter\.HighResolution\)\n'
        r'\s*if printer_name and printer_name != "\(None\)":\n'
        r'\s*info = QPrinterInfo\.printerInfo\(printer_name\)\n'
        r'\s*if not info\.isNull\(\):\n'
        r'\s*printer\.setPrinterName\(printer_name\)\n'
        r'(?P<mid>(?:(?!QPrinter\().)*?)'
        r'if str\(paper_size\) == "58mm":\n'
        r'\s*self\.paper_width = 380\n'
        r'\s*printer\.setPageSize\(QPageSize\(QSizeF\(58, page_height\), QPageSize\.Millimeter\)\)\n'
        r'\s*else:\n'
        r'\s*self\.paper_width = 550\n'
        r'\s*printer\.setPageSize\(QPageSize\(QSizeF\(80, page_height\), QPageSize\.Millimeter\)\)\n'
        r'\s*printer\.setPageMargins\(QMarginsF\(0, 0, 0, 0\)\)\n'
        r'(?P<gap>\s*\n)'
        r'(?P<ind>[ \t]*)painter = QPainter\(printer\)'
    )

    def dyn_repl(m):
        ind = m.group("ind")
        return (
            m.group("mid").lstrip()
            + "printer = self._setup_printer(printer_name, height_mm=page_height, paper_size=paper_size)\n\n"
            + ind + "painter = self._begin_painter(printer)"
        )

    src = sub_exact(src, dyn, dyn_repl, 3, "dynamic-height printer setup", flags=re.DOTALL)

    # 3b. fixed-height methods (credit note, packaging, master KOT, KOT,
    #     payment, sales order, laybye)
    fixed = (
        r'printer = QPrinter\(QPrinter\.HighResolution\)\n'
        r'\s*if printer_name and printer_name != "\(None\)":\n'
        r'\s*info = QPrinterInfo\.printerInfo\(printer_name\)\n'
        r'\s*if not info\.isNull\(\):\n'
        r'\s*printer\.setPrinterName\(printer_name\)\n'
        r'\s*\n'
        r'\s*printer\.setPageSize\(QPageSize\(QSizeF\(\d+, (?P<h>\d+)\), QPageSize\.Millimeter\)\)\n'
        r'\s*printer\.setPageMargins\(QMarginsF\(0, 0, 0, 0\)\)\n'
        r'\s*\n'
        r'(?P<ind>[ \t]*)painter = QPainter\(printer\)'
    )
    src = sub_exact(
        src, fixed,
        lambda m: (f"printer = self._setup_printer(printer_name, height_mm={m.group('h')})\n\n"
                   f"{m.group('ind')}painter = self._begin_painter(printer)"),
        7, "fixed-height printer setup")

    for leftover in ("QPrinter(QPrinter.HighResolution)", "painter = QPainter(printer)"):
        if leftover in src:
            raise PatchError(f"leftover unpatched call: {leftover}")

    # 4. fonts: pixel sizes so metrics and drawing scale together --------------
    src = sub_exact(
        src,
        r'(?P<i>[ \t]*)font = QFont\(family or "Arial", max\(size or 10, 8\)\)',
        r'\g<i>font = QFont(family or "Arial")\n'
        r'\g<i>font.setPixelSize(round(max(size or 10, 8) * DESIGN_DPI / 72.0))',
        1, "pixel-size fonts")

    # "1pt smaller" for pixel fonts is ~3px at 203 dpi (was 1px after conversion)
    src = sub_exact(
        src,
        r"new_size = max\(base_size - 1, 8\)",
        "new_size = max(base_size - (1 if normal_font.pointSize() > 0 else 3), 8)",
        2, "small font size")

    # 5. remove the dead first copies of _create_font/_make_bold (later ones win)
    dead = (
        r'    def _create_font\(self, font_name: str, size: int, style: str\) -> QFont:'
        r'.*?return font\n\n'
        r'    def _make_bold\(self, font: QFont\) -> QFont:\n'
        r'\s*bold_font = QFont\(font\)\n'
        r'\s*bold_font\.setBold\(True\)\n'
        r'\s*return bold_font\n\n'
    )
    new, n = re.subn(dead, "", src, count=1, flags=re.DOTALL)
    if n == 1:
        src = new
        print("  ok  removed duplicate (dead) font helpers")
    else:
        print("  --  duplicate font helpers not removed (harmless, skipped)")

    # 6. insert helpers after __init__ -----------------------------------------
    src = sub_exact(
        src,
        r"(        self\.paper_width = 550\n        self\.margin = 10\n)",
        lambda m: m.group(1) + HELPERS,
        1, "insert helper methods")

    # 7. laybye: 'company' is referenced before it is assigned -> UnboundLocalError
    src = sub_exact(
        src,
        r'co\.get\("company_name", company\)',
        'co.get("company_name", "Havano POS")',
        1, "laybye UnboundLocalError fix")

    return src


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    path = Path(sys.argv[1])
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")

    if "_begin_painter" in text:
        print("Already patched - nothing to do.")
        return

    print(f"Patching {path} ...")
    try:
        out = patch(text)
    except PatchError as e:
        print(f"\nABORTED, file not modified: {e}")
        sys.exit(2)

    compile(out, str(path), "exec")  # syntax check before writing anything

    path.with_suffix(path.suffix + ".bak").write_bytes(raw)
    if crlf:
        out = out.replace("\n", "\r\n")
    path.write_bytes(out.encode("utf-8"))
    print(f"\nDone. Backup: {path.name}.bak")


if __name__ == "__main__":
    main()
