"""TEST FIXTURE — synthetische vector-PDF voor unit-tests van de Vector Drawing Reader.

DIT IS GEEN ECHTE BOUWTEKENING en geen echt gebouw. De maten, aantallen en posities zijn verzonnen om de reader te kunnen
testen. Resultaten hiervan mogen NOOIT als real-world resultaat of accuracy worden gerapporteerd.
"""

PAGE_W, PAGE_H = 1190.55, 841.89  # A3 liggend, PDF-punten
WIN_W, WIN_H = 34.016, 42.52  # 1,20 x 1,50 m bij 1:100 (1 pt = 0,35278 mm papier = 35,278 mm werkelijk)


def _stream(*, title="VOORGEVEL AANZICHT", scale_label=True, dim_lines=True, extra_scale_label=None):
    c = []

    def text(x, y, s, size=10):
        c.append(f"BT /F1 {size} Tf {x} {y} Td ({s}) Tj ET")

    def rect(x, y, w, h):
        c.append(f"{x} {y} {w} {h} re S")

    def line(x0, y0, x1, y1):
        c.append(f"{x0} {y0} m {x1} {y1} l S")

    text(50, 800, title, 14)
    if scale_label:
        text(50, 782, "schaal 1:100")
    if extra_scale_label:
        text(300, 782, extra_scale_label)
    text(50, 766, "TEST FIXTURE - SYNTHETISCH - GEEN ECHT GEBOUW", 8)
    rect(100, 150, 800, 500)  # gevelvlak
    for x in (200, 400, 600):  # 6 identieke ramen met middenstijl
        for y in (250, 450):
            rect(x, y, WIN_W, WIN_H)
            line(x + WIN_W / 2, y, x + WIN_W / 2, y + WIN_H)
    rect(700, 450, 70, 20)  # eenmalige, ongelabelde rechthoek: GEEN candidate
    rect(300, 150, 40, 85)  # deur met expliciet label
    text(345, 190, "deur", 8)
    rect(950, 300, 60, 60)  # buiten het gevelvlak: GEEN candidate
    if dim_lines:
        line(200, 235, 200 + WIN_W, 235)  # maatlijn breedte 1200 mm
        text(203, 238, "1200", 7)
        line(190, 250, 190, 250 + WIN_H)  # maatlijn hoogte 1500 mm
        text(176, 268, "1500", 7)
    return "\n".join(c)


def build_pdf(**kw):
    content = _stream(**kw).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".encode(),
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    here = Path(__file__).parent
    (here / "TEST_FIXTURE_synthetic_facade_v1.pdf").write_bytes(build_pdf())
    print("geschreven")
