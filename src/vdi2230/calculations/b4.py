from __future__ import annotations

from math import log, pi, sqrt

from vdi2230.domain.models import CalculationResult

from ._common import ResultBuilder, area_circle, bearing_area


def calculate_b4() -> CalculationResult:
    """Recalculate the printed B4 eccentric joint quantities."""
    r = ResultBuilder("B4", "149–157")
    fa, fq, mb = 5000.0, 2440.0, 48_000.0
    c_t, e = 12.0, 5.5
    r.source_input("FAmax", "Maximum axial working load", fa, "N", "B4.1")
    r.source_input("FQmax", "Maximum transverse working load", fq, "N", "B4.1")
    r.source_input("Mb", "Interface bending moment", mb, "N·mm", "B4.1; 48 N·m")
    for symbol, label, value, unit in (
        ("Rm", "Clamped-part tensile strength", 900, "N/mm²"),
        ("muTmin", "Minimum interface friction coefficient", 0.15, "—"),
        ("Rz", "Surface roughness", 16, "μm"),
        ("cT", "Interface width", 12, "mm"),
        ("e", "Opening-side eccentricity", 5.5, "mm"),
        ("lS", "Bolt length", 53, "mm"),
        ("l1", "Waisted segment length 1", 22, "mm"),
        ("l2", "Head-shank segment length", 6, "mm"),
        ("l3", "Waisted segment length 2", 15, "mm"),
        ("lGew", "Thread length in grip", 2, "mm"),
        ("P", "Thread pitch", 1.25, "mm"),
        ("AT", "Waisted-shank tensile area", 26.6, "mm²"),
        ("Ad3", "Thread minor-diameter area", 32.84, "mm²"),
        ("AS", "Tensile stress area", 36.6, "mm²"),
        ("dSch", "Shoulder diameter", 9, "mm"),
        ("d2", "Thread pitch diameter", 7.188, "mm"),
        ("dS", "Equivalent stress diameter", 6.827, "mm"),
        ("dh", "Clearance-hole diameter", 9, "mm"),
        ("dW", "Bolt bearing diameter", 12.3, "mm"),
        ("da", "Maximum hole/chamfer diameter", 9, "mm"),
        ("dWMu", "Nut bearing diameter", 11.6, "mm"),
        ("hmin", "Minimum clamped-part height", 20, "mm"),
        ("b", "Interface beam width", 25, "mm"),
        ("ES", "Bolt Young's modulus", 210_000, "N/mm²"),
        ("EP", "Clamped-part Young's modulus", 205_000, "N/mm²"),
    ):
        r.source_input(symbol, label, value, unit, "B4.1/B4.2, Figure B6 and cited material data")
    a = mb / fa
    r.add("a", "Eccentricity of applied axial load", a, "mm", "B4.1; a=Mb/FAmax", reference=9.6)
    r.source_input("d", "Nominal bolt diameter", 8, "mm", "B4.2 R0, Table A7")
    r.source_input("FMmin,R0", "Initial sizing minimum preload", 16_000, "N", "B4.2 R0, Table A7 / Appendix B1")
    r.source_input("alphaA", "Tightening factor", 1.0, "—", "B4.2 R1, Table A8")
    r.add("G", "Effective-range dimension", 12.3 + 20, "mm", "B4.2 R0; G=dW+hmin", reference=32.3)
    r.source_input("d3", "Thread minor diameter", 6.466, "mm", "B4.2 R0, Figure B6")
    r.source_input("dT", "Waisted shank diameter", 0.9 * 6.466, "mm", "B4.2 R0; dT=0.9d3")

    f_kq = fq / (1 * 0.15)
    s_sym = c_t / 2 - e
    u = e + s_sym
    ad = 272.0 - area_circle(9.0)
    ibt = 25.0 * c_t**3 / 12
    f_ka = fa * (a * u * ad - s_sym * u * ad) / (ibt + s_sym * u * ad)
    fkerf = max(f_kq, f_ka)
    r.add("FKQ", "Clamp load for transverse friction", f_kq, "N", "B4.2 R2; FKQ=FQmax/(qF·μT)", reference=16_267)
    r.add("sSym", "Symmetry shift of compression body", s_sym, "mm", "B4.2 R2; equation (66)", reference=0.5)
    r.add("u", "Moment arm to compression edge", u, "mm", "B4.2 R2; u=e+ssym", reference=6)
    r.add("AD", "Effective contact area excluding hole", ad, "mm²", "B4.2 R2; AD=Ag−πdh²/4", reference=208.4)
    r.add("IBT", "Interface area moment", ibt, "mm⁴", "B4.2 R2; IBT=b·cT³/12", reference=3600)
    r.add("FKA", "Clamp load to prevent opening", f_ka, "N", "B4.2 R2; equation (R2/3)", reference=13_465)
    r.add("FKerf", "Required minimum clamp load", fkerf, "N", "B4.2 R2; max(FKQ, FKP+FKA)", reference=16_267)

    d, d2, d3, dT, dsch, dW, dh = (
        8.0,
        7.188,
        6.466,
        0.9 * 6.466,
        9.0,
        12.3,
        9.0,
    )
    es, ep = 210_000.0, 205_000.0
    an = area_circle(d)
    at = 26.6
    l1, l2, l3, lgew, lk = 22.0, 6.0, 15.0, 2.0, 45.0
    ds = 4 / (pi * es) * (
        0.5 * d / d**2
        + l1 / dT**2
        + l2 / dsch**2
        + l3 / dT**2
        + (lgew + 0.5 * d) / d3**2
        + 0.4 * d / d**2
    )
    r.add("deltaS", "Bolt axial compliance", ds, "mm/N", "B4.2 R3; equation (19), waisted bolt", reference=8.62e-6)

    ag = 272.0
    da = sqrt(ag * 4 / pi)
    beta = lk / dW
    y = da / dW
    tan_phi = 0.362 + 0.032 * log(beta / 2) + 0.153 * log(y)
    da_gr = dW + lk * tan_phi
    w = 1.0
    dp = (
        (
            2 / (w * dh * tan_phi)
            * log(((dW + dh) * (da - dh)) / ((dW - dh) * (da + dh)))
            + 4 / (da**2 - dh**2)
            * (lk - (da - dW) / (w * tan_phi))
        )
        / (ep * pi)
    )
    r.add("DA", "Equivalent interface diameter", da, "mm", "B4.2 R3; DA=√(Ag·4/π)", reference=18.6)
    r.add("betaL", "Clamped-length ratio", beta, "—", "B4.2 R3; βL=lK/dW", reference=3.66)
    r.add("y", "Equivalent body diameter ratio", y, "—", "B4.2 R3; y=DA′/dW", reference=1.51)
    r.add("tanPhiD", "Equivalent cone angle tangent", tan_phi, "—", "B4.2 R3; equation (43)", reference=0.444)
    r.add("DAgr", "Limiting diameter", da_gr, "mm", "B4.2 R3; equation (39)", reference=32.3)
    r.add("dP", "Centered clamped-member compliance", dp, "mm/N", "B4.2 R3; equation (41)", reference=1.351e-6)

    ibv = 0.147 * (da - dW) * dW**3 * da**3 / (da**3 - dW**3)
    ibve = ibv + s_sym**2 * pi / 4 * da**2
    ibh = 25 * c_t**3 / 12
    lv = (da - dW) / (2 * tan_phi)
    lh = lk - 2 * lv
    ibers = lk / (2 * lv / ibve + lh / ibh)
    dp_star = dp + s_sym**2 * lk / (ep * ibers)
    dp_starstar = dp + a * s_sym * lk / (ep * ibers)
    r.add("IBV", "Equivalent cone area moment", ibv, "mm⁴", "B4.2 R3; equation (62), cone component", reference=2424.5)
    r.add("IBVe", "Eccentric equivalent cone area moment", ibve, "mm⁴", "B4.2 R3; IBV+ssym²·πDA²/4", reference=2492.4)
    r.add("IBH", "Equivalent sleeve area moment", ibh, "mm⁴", "B4.2 R3; b·cT³/12", reference=3600)
    r.add("lV", "Equivalent cone length", lv, "mm", "B4.2 R3; (DA−dW)/(2tanφD)", reference=7.09)
    r.add("lH", "Equivalent sleeve length", lh, "mm", "B4.2 R3; lK−2lV", reference=30.82)
    r.add("IBers", "Combined area moment", ibers, "mm⁴", "B4.2 R3; series combination of cone and sleeve", reference=3157.8)
    r.add("dPstar", "Eccentric clamp compliance δP*", dp_star, "mm/N", "B4.2 R3; δP+ssym²·lK/(EP·IBers)", reference=1.368e-6)
    r.add("dPstarstar", "Eccentric load compliance δP**", dp_starstar, "mm/N", "B4.2 R3; δP+a·ssym·lK/(EP·IBers)", reference=1.685e-6)

    la = a - s_sym - dW / 2
    r.add("lA", "Load-introduction arm", la, "mm", "B4.2 R3; lA=a−ssym−dW/2", reference=2.95)
    n = 0.58
    r.source_input("n", "Load-introduction factor", n, "—", "B4.2 R3, Table 2 / Figure 22 interpolation")
    phi = n * dp_starstar / (ds + dp_star)
    fsa = phi * fa
    fpa = (1 - phi) * fa
    r.add("PhiEn", "Load factor", phi, "—", "B4.2 R3; n·δP**/(δS+δP*)", reference=0.098)
    r.add("FSAmax", "Additional bolt load", fsa, "N", "B4.2 R3; FSAmax=Φen·FAmax", reference=490)
    r.add("FPAmax", "Load on clamped members", fpa, "N", "B4.2 R3; FPAmax=(1−Φen)·FAmax", reference=4510)
    fz = 11e-3 / (ds + dp)
    fmmin = fkerf + fpa + fz
    fmmax = fmmin
    r.add("FZ", "Preload loss from embedment", fz, "N", "B4.2 R4; FZ=fZ/(δS+δP)", reference=1103)
    r.add("FMmin", "Minimum assembly preload", fmmin, "N", "B4.2 R5; FKerf+FPAmax+FZ", reference=21_880)
    r.add("FMmax", "Maximum assembly preload", fmmax, "N", "B4.2 R6; αA·FMmin", reference=21_880)
    r.source_input("FMTab", "Allowable preload from Table A2", 23_800, "N", "B4.2 R7, Table A2, property class 12.9")
    fmzul = 23_800 / 0.9
    r.add("FMzul", "Allowable preload after yield-point factor", fmzul, "N", "B4.2 R7; FMzul=FMTab/v", reference=26_444)
    wppl = pi / 12 * dT**3
    mg = fmzul * d2 / 2 * (1.25 / (pi * d2) + 1.155 * 0.08)
    fv1 = at * sqrt((1100 * 1.15) ** 2 - 3 * (0.5 * mg / wppl) ** 2) - fsa - fz
    r.add("WPpl", "Plastic polar section modulus", wppl, "mm³", "B4.2 R8; WPpl=πdT³/12", reference=51.6)
    r.add("MG", "Thread tightening torsion moment", mg, "N·mm", "B4.2 R8; bolt tightening moment", reference=14_043)
    r.add("FV1", "Residual preload after working load", fv1, "N", "B4.2 R8; equation (163)", reference=31_467)
    r.source_input("FMTabMuMax", "Allowable preload at maximum thread friction", 21_500, "N", "B4.2 R8; Table A2, μGmax=0.14")
    fmzul_min = 21_500 / 0.9
    mg_max = fmzul_min * d2 / 2 * (1.25 / (pi * d2) + 1.155 * 0.14)
    fv1_mu = at * sqrt((1100 * 1.15) ** 2 - 3 * (0.5 * mg_max / wppl) ** 2) - fsa - fz
    fv1_min = min(fv1_mu, fmzul_min - fz)
    fkri = fv1_min - fpa
    r.add("FMzulMin", "Allowable preload at maximum thread friction", fmzul_min, "N", "B4.2 R8; FMTab/v", reference=23_889)
    r.add("MGmuMax", "Thread torsion at maximum friction", mg_max, "N·mm", "B4.2 R8; thread-torsion equation", reference=18_636)
    r.add("FV1muMax", "Residual preload at maximum friction", fv1_mu, "N", "B4.2 R8; equation (163)", reference=31_011)
    r.add("FV1min", "Minimum residual bolt preload", fv1_min, "N", "B4.2 R8; min(FV1, FMzul,min−FZ)", reference=22_786)
    r.add("FKRImin", "Minimum residual clamp load", fkri, "N", "B4.2 R8; FV1min−FPAmax", reference=18_276)

    ibar = ibers - pi / 64 * dh**4
    lers = d3**4 * (
        0.5 * d / d**4
        + l1 / dT**4
        + l2 / dsch**4
        + l3 / dT**4
        + lgew / d3**4
        + 0.4 * d / d**4
        + 0.5 * d / d3**4
    )
    sigma_sabo = (
        1
        + (1 / phi - s_sym / a)
        * lk
        / lers
        * es
        / ep
        * pi
        * a
        * ((d2 + d3) / 2) ** 3
        / (8 * ibar)
    ) * phi * fa / 36.6
    sigma_ab = sigma_sabo / 2
    sigma_asv = 0.85 * (150 / d + 45)
    r.add("Ibar", "Net equivalent bending area moment", ibar, "mm⁴", "B4.2 R9; IBers−πdh⁴/64", reference=2837.8)
    r.add("lers", "Equivalent bolt bending length", lers, "mm", "B4.2 R9; equation (34)", reference=65.98)
    r.add(
        "sigmaSAbo",
        "Maximum bolt alternating stress",
        sigma_sabo,
        "N/mm²",
        "B4.2 R9; equation (R9/5-1)",
        reference=53.5,
    )
    r.add(
        "sigmaAb",
        "Alternating stress amplitude",
        sigma_ab,
        "N/mm²",
        "B4.2 R9; (σSAbo−σSAbu)/2",
        reference=26.8,
    )
    r.add("sigmaASV", "Fatigue limit", sigma_asv, "N/mm²", "B4.2 R9; equation (R9/5-1)", reference=54)
    r.add(
        "SD",
        "Fatigue safety factor",
        sigma_asv / sigma_ab,
        "—",
        "B4.2 R9; σASV/σab",
        reference=2.02,
    )

    apk = bearing_area(12.3, 9)
    apmu = bearing_area(11.6, 9)
    pk = 23_800 * 1.4 / apk
    pmu = 23_800 * 1.4 / apmu
    r.add("ApKmin", "Bolt-head bearing area", apk, "mm²", "B4.2 R10; π/4(dW²−da²)", reference=55.2)
    r.add("ApMumin", "Nut bearing area", apmu, "mm²", "B4.2 R10; π/4(dWMu²−da²)", reference=42.1)
    r.add("pKmax", "Bolt-head bearing pressure", pk, "N/mm²", "B4.2 R10; FMTab·1.4/ApKmin", reference=603)
    r.add("pMumax", "Nut bearing pressure", pmu, "N/mm²", "B4.2 R10; FMTab·1.4/ApMumin", reference=791)
    r.source_input("pG", "Allowable bearing pressure for Cq45", 990, "N/mm²", "B4.2 R10; Table A9 extrapolated to Rm=900 MPa")
    r.add("SpK", "Bolt-head bearing safety factor", 990 / pk, "—", "B4.2 R10; pG/pKmax", reference=1.64)
    r.add("SpMu", "Nut bearing safety factor", 990 / pmu, "—", "B4.2 R10; pG/pMumax", reference=1.25)
    r.add("SG", "Slip safety factor", fkri / fkerf, "—", "B4.2 R12; FKRImin/FKQerf", reference=1.12)
    r.warnings.append(
        "B4 uses source-specific geometry and chart/table selections; the 3% comparisons are to the printed reference values, not independent material certification."
    )
    return r.result()
