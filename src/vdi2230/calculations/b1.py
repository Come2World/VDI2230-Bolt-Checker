from __future__ import annotations

from math import log, pi

from vdi2230.domain.models import CalculationResult

from ._common import (
    ResultBuilder,
    area_circle,
    bearing_area,
    bolt_torsion_moment,
    equivalent_stress,
    thread_strength_ratio,
)


def calculate_b1() -> CalculationResult:
    """Recalculate the printed B1 quantities from the supplied case inputs."""
    r = ResultBuilder("B1", "130–139")
    p = 5.5
    area = pi / 4 * (80**2 - 25**2)
    fa = p * area
    r.source_input("pmax", "Maximum internal pressure", p, "N/mm²", "B1.1")
    r.source_input("L", "Joint dimension L", 55, "mm", "B1.1, Figure B1")
    r.source_input("Lg", "Clamped member thickness", 60, "mm", "B1.1, Figure B1")
    r.source_input("hK", "Piston-rod recess depth", 10, "mm", "B1.1, Figure B1")
    r.source_input("DSt", "Interface support diameter", 25, "mm", "B1.1, Figure B1")
    r.source_input("DZ", "Piston diameter", 80, "mm", "B1.1, Figure B1")
    r.source_input("FKRmin", "Required residual clamp load", 1000, "N", "B1.1")
    r.add("A", "Pressure-loaded area", area, "mm²", "B1.1; A=π/4(DZ²−DSt²)", reference=4536)
    r.add("FAmax", "Maximum axial working load", fa, "N", "B1.1; FAmax=pmax·A", reference=24900)

    r.source_input("d", "Nominal bolt diameter", 12, "mm", "B1.2 R0, Table A7")
    r.source_input("Fcompare", "Sizing comparison load", 25000, "N", "B1.2 R0, Table A7")
    r.source_input("FMmin,R0", "Initial sizing minimum preload", 40000, "N", "B1.2 R0, Table A7")
    r.source_input("FMmax,R0", "Initial sizing maximum preload", 63000, "N", "B1.2 R0, Table A7")
    r.source_input("alphaA", "Tightening factor", 1.8, "—", "B1.2 R1, Table A8")
    r.source_input("t", "Counterbore depth", 13, "mm", "B1.2 R0, DIN 974")
    lk = 55 - 13
    l1 = 24
    r.add("lK", "Clamped length", lk, "mm", "B1.2 R0; lK=L−t", reference=42)
    r.source_input("l1", "Bolt shank length in grip", l1, "mm", "B1.2 R0, ISO 4762")
    r.add("lGew", "Free loaded thread length", lk - l1, "mm", "B1.2 R0; lGew=lK−l1", reference=18)
    for symbol, label, value, unit in (
        ("dh", "Medium-clearance hole diameter", 13.5, "mm"),
        ("P", "Thread pitch", 1.75, "mm"),
        ("d2", "Thread pitch diameter", 10.863, "mm"),
        ("d3", "Thread minor diameter", 9.85, "mm"),
        ("dK", "Bolt head diameter", 18, "mm"),
        ("dW", "Bolt bearing diameter", 17.23, "mm"),
        ("Ad3", "Thread minor-diameter area", 76.25, "mm²"),
        ("AN", "Nominal shank area", 113.1, "mm²"),
        ("AS", "Tensile stress area", 84.3, "mm²"),
    ):
        r.source_input(symbol, label, value, unit, "B1.2 R0, DIN EN ISO 4762 / ISO 273")

    es = 205000.0
    an = area_circle(12)
    ad3 = 76.25
    delta_sk = 0.4 * 12 / (es * an)
    delta_l1 = 24 / (es * an)
    delta_gew = 18 / (es * ad3)
    delta_g = 0.5 * 12 / (es * ad3)
    delta_m = 0.33 * 12 / (es * an)
    delta_s = delta_sk + delta_l1 + delta_gew + delta_g + delta_m
    for symbol, label, value, ref in (
        ("dSK", "Bolt head compliance", delta_sk, 0.207e-6),
        ("d1", "Shank compliance", delta_l1, 1.035e-6),
        ("dGew", "Thread compliance", delta_gew, 1.152e-6),
        ("dG", "Bolt-side thread extension compliance", delta_g, 0.384e-6),
        ("dM", "Nut-side thread extension compliance", delta_m, 0.171e-6),
        ("dS", "Total bolt compliance", delta_s, 2.95e-6),
    ):
        r.add(symbol, label, value, "mm/N", "B1.2 R3; equations (19)–(20)", reference=ref)

    dwm = (17.23 + 25) / 2
    beta = 42 / dwm
    y = 80 / dwm
    tan_phi = 0.362 + 0.032 * log(beta / 2) + 0.153 * log(y)
    da_gr = dwm + 42 * tan_phi
    # Eq. (40) for the two-cone case; the source's printed substitution has
    # an ambiguous factor in the w·lk term, so use the stated limiting diameter.
    dh = 13.5
    delta_p = (
        2
        * log(((dwm + dh) * (da_gr - dh)) / ((dwm - dh) * (da_gr + dh)))
        / (205000 * pi * dh * tan_phi)
    )
    r.add("dWm", "Mean support diameter", dwm, "mm", "B1.2 R3; dWm=(dW+DSt)/2", reference=21.11)
    r.add("betaL", "Clamped-length ratio", beta, "—", "B1.2 R3; βL=lK/dWm", reference=1.99)
    r.add("y", "Equivalent body diameter ratio", y, "—", "B1.2 R3; y=DA′/dWm", reference=3.79)
    r.add("tanPhiD", "Equivalent cone angle tangent", tan_phi, "—", "B1.2 R3; equation (43)", reference=0.566)
    r.add("DAgr", "Limiting diameter", da_gr, "mm", "B1.2 R3; equation (39)", reference=44.9)
    r.add("ak", "Support-edge distance", (25 - 17.23) / 2, "mm", "B1.2 R3; ak=(DSt−dW)/2", reference=3.89)
    r.add("akOverH", "Normalized support-edge distance", ((25 - 17.23) / 2) / 42, "—", "B1.2 R3; ak/h", reference=0.093)
    r.add("lAOverH", "Normalized load-introduction length", 0, "—", "B1.2 R3; lA/h=0", reference=0)
    r.add("dP", "Clamped-member compliance", delta_p, "mm/N", "B1.2 R3; equation (40)", reference=0.363e-6)
    phi_k = (delta_p + delta_m) / (delta_s + delta_p)
    r.add("PhiK", "Load factor at bolt head", phi_k, "—", "B1.2 R3; ΦK=(δP+δPzu)/(δS+δP), using printed δM add-on", reference=0.161)
    r.unresolved(
        "dPzu",
        "Additional compliance δPzu",
        "mm/N",
        "B1.2 R3; δPzu=(w−1)·δM",
        "The same example states w=1 for its limiting-diameter calculation but substitutes δPzu=δM, which implies w=2. The source inputs conflict; no factor was selected to force agreement.",
    )
    r.source_input("n", "Load-introduction factor", 0.35, "—", "B1.2 R3, Table 2 / Figure 22")
    phi_n = 0.35 * phi_k
    r.add("PhiEn", "Load factor", phi_n, "—", "B1.2 R3; Φen=n·ΦK", reference=0.056)

    fkerf = 1000.0
    fz = 8e-3
    fz_force = fz / (delta_s + delta_p)
    fmmin = fkerf + (1 - phi_n) * fa + fz_force
    fmmax = 1.8 * fmmin
    r.add("FKerf", "Required minimum clamp load", fkerf, "N", "B1.2 R2; specified sealing residual clamp load", reference=1000)
    r.add("fZ", "Total embedment", fz, "mm", "B1.2 R4; Table 5, 3+3+2 μm", reference=0.008)
    r.add("FZ", "Preload loss from embedment", fz_force, "N", "B1.2 R4; FZ=fZ/(δS+δP)", reference=2415)
    r.add("FMmin", "Minimum assembly preload", fmmin, "N", "B1.2 R5; FKerf+(1−Φen)FAmax+FZ", reference=26921)
    r.add("FMmax", "Maximum assembly preload", fmmax, "N", "B1.2 R6; αA·FMmin", reference=48458)
    r.source_input("FMzul10.9", "Allowable preload, property class 10.9", 64800, "N", "B1.2 R7, Table A1")
    r.source_input("FMzul12.9", "Allowable preload, property class 12.9", 75900, "N", "B1.2 R7, Table A1")
    r.add("FSmax", "Maximum bolt force", 64800 + phi_n * fa, "N", "B1.2 R8; FMzul+Φen·FAmax", reference=66194)
    sigma_z = (64800 + phi_n * fa) / 84.3
    r.add("sigmaZmax", "Maximum tensile stress", sigma_z, "N/mm²", "B1.2 R8; σzmax=FSmax/AS", reference=785.2)
    mg = bolt_torsion_moment(64800, 10.863, 1.75, 0.1)
    ds = (10.863 + 9.85) / 2
    wp = pi * ds**3 / 16
    tau = mg / wp
    sigma_red = equivalent_stress(sigma_z, tau)
    r.add("MG", "Thread tightening torsion moment", mg, "N·mm", "B1.2 R8; equation (R8/2)", reference=58700)
    r.add("WP", "Polar section modulus", wp, "mm³", "B1.2 R8; WP=πdS³/16", reference=218)
    r.add("tauMax", "Maximum torsional stress", tau, "N/mm²", "B1.2 R8; τmax=MG/WP", reference=269.3)
    r.add("sigmaRedB", "Equivalent working stress", sigma_red, "N/mm²", "B1.2 R8; equation (R8/4)", reference=819)
    r.add("SF", "Yield safety factor", 940 / sigma_red, "—", "B1.2 R8; SF=Rp0.2min/σred,B", reference=1.15)
    sigma_a = phi_n * fa / (2 * 84.3)
    sigma_asv = 0.85 * (150 / 12 + 45)
    r.add("sigmaA", "Alternating tensile stress", sigma_a, "N/mm²", "B1.2 R9; equation (R9/1)", reference=8.3)
    r.add("sigmaASV", "Fatigue limit", sigma_asv, "N/mm²", "B1.2 R9; equation (185)", reference=48.9)
    apmin = bearing_area(17.23, 13.5)
    pressure = 64800 / apmin
    r.add("Apmin", "Minimum head bearing area", apmin, "mm²", "B1.2 R10; Apmin=π/4(dW²−dh²)", reference=90)
    r.add("pMmax", "Assembly bearing pressure", pressure, "N/mm²", "B1.2 R10; pMmax=FMzul/Apmin", reference=720)
    r.source_input("pG", "Allowable bearing pressure", 1300, "N/mm²", "B1.2 R10, Table A9")
    r.add("Sp", "Bearing-pressure safety factor", 1300 / pressure, "—", "B1.2 R10; Sp=pG/pMmax", reference=1.8)
    rs = thread_strength_ratio(12, 10.863, 10.106, 1.75, 700, 1040)
    r.add("RS", "Thread strength ratio", rs, "—", "B1.2 R11; equation (199)", reference=0.93)
    r.add("meff", "Required effective engagement length", 0.8 * 12, "mm", "B1.2 R11; Figure 37, meff/d=0.8", reference=9.6)
    r.add("meffVorh", "Available effective engagement length", (60 - 42) - 2 * 1.75, "mm", "B1.2 R11; equation (208)", reference=14.5)
    r.source_input("MA", "Tightening torque", 108, "N·m", "B1.2 R13, Table A1")
    r.warnings.append(
        "Table/chart values (for example FMzul and n) are reference inputs, not recalculated material/property tables."
    )
    return r.result()
