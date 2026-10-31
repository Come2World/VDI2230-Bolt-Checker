from __future__ import annotations

from math import log, pi, sqrt, tan

from vdi2230.domain.models import CalculationResult

from ._common import ResultBuilder, area_circle, bearing_area


def calculate_b3() -> CalculationResult:
    """Recalculate the printed B3 quantities for the special hollow bolt."""
    r = ResultBuilder("B3", "143–148")
    torque = 110_000.0
    r.source_input("MY", "Transmitted torque", torque, "N·mm", "B3.1; 110 N·m")
    for symbol, label, value, unit in (
        ("d", "Nominal thread diameter", 27, "mm"),
        ("d0", "Hollow shank outside diameter", 24, "mm"),
        ("db", "Hollow bore diameter", 16, "mm"),
        ("d2", "Thread pitch diameter", 25.7, "mm"),
        ("d3", "Thread minor diameter", 24.54, "mm"),
        ("P", "Thread pitch", 2, "mm"),
        ("l4", "Threaded engagement length", 20, "mm"),
        ("dWmin", "Minimum head bearing diameter", 36, "mm"),
        ("k", "Bolt head height", 10, "mm"),
        ("dhaMax", "Maximum crankshaft counterbore diameter", 30, "mm"),
        ("DAcrank", "Crankshaft support diameter", 48, "mm"),
        ("DWcrank", "Crankshaft washer diameter", 50, "mm"),
        ("l1", "Clamped component thickness 1", 1.5, "mm"),
        ("l2", "Clamped component thickness 2", 7, "mm"),
        ("l3", "Clamped component thickness 3", 7.5, "mm"),
        ("dh", "Clearance-hole diameter", 29, "mm"),
        ("dha", "Maximum interface hole diameter", 28, "mm"),
        ("DA", "Flywheel hub outside diameter", 72, "mm"),
        ("ES", "Bolt Young's modulus", 205_000, "N/mm²"),
        ("EM", "Clamped-member Young's modulus", 205_000, "N/mm²"),
        ("RmMax", "Maximum material tensile strength", 1000, "N/mm²"),
        ("RmMin", "Minimum bolt tensile strength", 830, "N/mm²"),
    ):
        r.source_input(symbol, label, value, unit, "B3.1/B3.2, Table B1 and cited material data")
    ra = (48 + 30) / 4
    fkerf = torque / (1 * ra * 0.10)
    r.add("ra", "Effective friction radius", ra, "mm", "B3.2 R2; ra=(DA+Dhamax)/4", reference=19.5)
    r.add("FKerf", "Required minimum clamp load", fkerf, "N", "B3.2 R2; FKQ=MY/(qM·ra·μTmin)", reference=56_400)
    r.source_input("alphaA", "Tightening factor", 1.6, "—", "B3.2 R1, Table A8")

    d, d0, db, d2, d3 = 27.0, 24.0, 16.0, 25.7, 24.54
    es = em = 205_000.0
    an = area_circle(d)
    abore = area_circle(db)
    ad0 = area_circle(d0) - abore
    ad3_hollow = area_circle(d3) - abore
    l_k = 16.0
    delta_sk = 0.5 * d / (es * (area_circle(d) - abore))
    delta_i = 16.0 / (es * ad0)
    delta_g = 0.5 * d / (es * ad3_hollow)
    delta_m = 0.33 * d / (em * an)
    delta_gm = delta_g + delta_m
    delta_s = delta_sk + delta_i + delta_gm
    for symbol, label, value, ref in (
        ("dSK", "Hollow bolt head compliance", delta_sk, 0.17727e-6),
        ("di", "Hollow shank compliance", delta_i, 0.3105e-6),
        ("dG", "Thread-side engagement compliance", delta_g, None),
        ("dM", "Clamped-member-side engagement compliance", delta_m, None),
        ("dGM", "Combined engagement compliance", delta_gm, 0.31789e-6),
        ("dS", "Total bolt compliance", delta_s, 0.80566e-6),
    ):
        r.add(symbol, label, value, "mm/N", "B3.2 R3; equations (19)–(20), hollow section", reference=ref)
    r.add("d3hollow", "Net thread tensile area", ad3_hollow, "mm²", "B3.2 R3; π/4(d3²−db²)", reference=None)

    dw, da, dh = 36.0, 48.0, 29.0
    beta = l_k / dw
    y = 72.0 / dw
    tan_phi = 0.348 + 0.013 * log(beta) + 0.193 * log(y)
    r.add("betaL", "Clamped-length ratio", beta, "—", "B3.2 R3; βL=lK/dW", reference=0.444)
    r.add("y", "Equivalent body diameter ratio", y, "—", "B3.2 R3; y=DA′/dW", reference=2.0)
    r.add("tanPhiE", "Equivalent cone angle tangent", tan_phi, "—", "B3.2 R3; equation (42)", reference=0.4712)
    r.add("phiE", "Equivalent cone angle", __import__("math").degrees(__import__("math").atan(tan_phi)), "degrees", "B3.2 R3; φE=atan(tanφE)", reference=25.2)
    w = 2.0
    da_gr = dw + w * l_k * tan_phi
    r.add("DAgr", "Limiting diameter", da_gr, "mm", "B3.2 R3; equation (29)", reference=51.08)
    dp = (
        (
            2 / (w * dh * tan_phi)
            * log(((dw + dh) * (da - dh)) / ((dw - dh) * (da + dh)))
            + 4 / (da**2 - dh**2) * (l_k - (da - dw) / (w * tan_phi))
        )
        / (205_000 * pi)
    )
    r.add("dP", "Clamped-member compliance", dp, "mm/N", "B3.2 R3; equation (41), cone and cylinder", reference=0.1055e-6)
    r.add("dPzu", "Additional support compliance", delta_m, "mm/N", "B3.2 R3; δPzu=(w−1)·δM, w=2", reference=0.0758e-6)

    fz = (3 + 4.5 + 2 * 2.5) * 1e-3
    fz_force = fz / (delta_s + dp)
    fmmin = fkerf + fz_force
    fmmax = 1.6 * fmmin
    r.add("fZ", "Total embedment", fz, "mm", "B3.2 R4; Table 5, 3+4.5+2×2.5 μm", reference=0.0125)
    r.add("FZ", "Preload loss from embedment", fz_force, "N", "B3.2 R4; FZ=fZ/(δS+δP)", reference=13_700)
    r.add("FMmin", "Minimum assembly preload", fmmin, "N", "B3.2 R5; FKerf+FZ", reference=70_100)
    r.add("FMmax", "Maximum assembly preload", fmmax, "N", "B3.2 R6; αA·FMmin", reference=112_200)

    rp02, v, mug = 660.0, 0.9, 0.12
    a0 = area_circle(d0) - area_circle(db)
    wppl = pi / 12 * (d0**3 - db**3)
    torsion_factor = 1.5 * d2 * (d0**2 - db**2) / (d0**3 - db**3) * (
        2 / (pi * d2) + 1.155 * mug
    )
    fmzul = a0 * (v * rp02) / sqrt(1 + 3 * torsion_factor**2)
    r.add("A0", "Net shank area", a0, "mm²", "B3.2 R7; A0=π/4(d0²−db²)", reference=251)
    r.add("WPpl", "Plastic polar section modulus", wppl, "mm³", "B3.2 R7; WPpl=π/12(d0³−db³)", reference=None)
    r.add("FMzul", "Allowable preload of hollow bolt", fmzul, "N", "B3.2 R7; rearranged equation (140)", reference=140_300)
    ap = bearing_area(36, 28)
    pm = fmzul / ap
    r.add("Ap", "Head bearing area", ap, "mm²", "B3.2 R10; AP=π/4(dWmin²−dhamax²)", reference=402.1)
    r.add("pMmax", "Assembly bearing pressure", pm, "N/mm²", "B3.2 R10; pMmax=FMzul/AP", reference=348.9)
    r.source_input("pG", "Allowable bearing pressure for E295", 710, "N/mm²", "B3.2 R10, Table A9")
    r.add("Sp", "Bearing-pressure safety factor", 710 / pm, "—", "B3.2 R10; Sp=pG/pMmax", reference=2.0)

    rs = (
        27
        * (2 / 2 + (27 - 25.7) * tan(pi / 6))
        / (24.83 * (2 / 2 + (25.7 - 24.83) * tan(pi / 6)))
        * (1000 / 830)
    )
    c1 = 3.8 * 50 / 27 - (50 / 27) ** 2 - 2.61
    c2 = (
        5.594
        - 13.682 * rs
        + 14.107 * rs**2
        - 6.057 * rs**3
        + 0.9353 * rs**4
    )
    tau_bs = 0.65 * 830
    mges = (
        fmzul
        * 2
        / (
            c1
            * c2
            * tau_bs
            * (2 / 2 + (25.493 - 25.21) * tan(pi / 6))
            * pi
            * 26.682
        )
        + 1.2 * 2
    )
    r.add("RS", "Thread strength ratio", rs, "—", "B3.2 R11; equation (199)", reference=1.52)
    r.add("C1", "Thread engagement coefficient C1", c1, "—", "B3.2 R11; equation (200)", reference=1.0)
    r.add("C2", "Thread engagement coefficient C2", c2, "—", "B3.2 R11; equation (210)", reference=1.1)
    r.add("tauBSmin", "Minimum thread shear strength", tau_bs, "N/mm²", "B3.2 R11; Table 7 ratio×Rm,min", reference=540)
    r.add("mgesmin", "Minimum required thread engagement", mges, "mm", "B3.2 R11; equation (212)", reference=7.25)
    r.add("mgesVorh", "Available thread contact length", 20 - 1.5, "mm", "B3.2 R11; l4−chamfer", reference=18.5)
    fkr = fmzul / 1.6 - fz_force
    r.add("FKRmin", "Minimum residual clamp load", fkr, "N", "B3.2 R12; FMzul/αA−FZ", reference=74_000)
    r.add("SG", "Slip safety factor", fkr / fkerf, "—", "B3.2 R12; FKRmin/FKerf", reference=1.31)
    dkm = (36 + 28) / 2
    ma = (fmzul / 1000) * (
        0.16 * 2 + 0.58 * 25.7 * 0.12 + dkm / 2 * 0.10
    )
    r.add("DKm", "Mean head bearing diameter", dkm, "mm", "B3.2 R13; (dWmin+dhamax)/2", reference=32)
    r.add("MA", "Tightening torque", ma, "N·m", "B3.2 R13; table A1 torque equation", reference=520)
    r.warnings.append(
        "B3 is a special hollow bolt. Its geometry, material strengths, friction values, and engagement dimensions are reference inputs rather than standard-catalog selections."
    )
    return r.result()
