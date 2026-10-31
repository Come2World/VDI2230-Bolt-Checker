from __future__ import annotations

from math import log, pi, sqrt, tan

from vdi2230.domain.models import CalculationResult

from ._common import (
    ResultBuilder,
    area_circle,
    bearing_area,
    bolt_torsion_moment,
    equivalent_stress,
    thread_strength_ratio,
)


def calculate_b5() -> CalculationResult:
    """Recalculate the printed B5 quantities for the eccentric cylinder cover."""
    r = ResultBuilder("B5", "158–168")
    i, d_zi, pmax, pmin = 15.0, 140.0, 20.0, 6.0
    for symbol, label, value, unit in (
        ("DZi", "Cylinder bore diameter", d_zi, "mm"),
        ("Da", "Cylinder and cover outside diameter", 210, "mm"),
        ("Di", "Cover inside diameter", 120, "mm"),
        ("Dst", "Bolt pitch-circle diameter", 175, "mm"),
        ("i", "Number of bolts", i, "—"),
        ("pmax", "Maximum internal pressure", pmax, "N/mm²"),
        ("pmin", "Minimum internal pressure", pmin, "N/mm²"),
        ("e", "Opening-side eccentricity", 15.5, "mm"),
        ("cT", "Interface width", 33, "mm"),
        ("lk", "Clamped length", 35, "mm"),
        ("b", "Bolt segment dimension", 52.5, "mm"),
        ("dK", "Bolt head diameter", 30, "mm"),
        ("dW", "Bolt bearing diameter", 28.87, "mm"),
        ("dh", "Clearance-hole diameter", 22, "mm"),
        ("d2", "Thread pitch diameter", 18.37, "mm"),
        ("d3", "Thread minor diameter", 16.93, "mm"),
        ("Ad3", "Thread minor-diameter area", 225.2, "mm²"),
        ("AS", "Tensile stress area", 245, "mm²"),
        ("lS", "Bolt length", 60, "mm"),
        ("ES", "Bolt Young's modulus", 205_000, "N/mm²"),
        ("EP", "Clamped-part Young's modulus", 205_000, "N/mm²"),
        ("Rp02min", "Minimum yield strength, class 10.9", 940, "N/mm²"),
        ("RmInternal", "Internal thread material tensile strength", 470, "N/mm²"),
        ("RmBolt", "Bolt tensile strength", 1040, "N/mm²"),
    ):
        r.source_input(symbol, label, value, unit, "B5.1/B5.2, Figures B7 and cited material data")
    fa_max = pi / (4 * i) * d_zi**2 * pmax
    fa_min = pi / (4 * i) * d_zi**2 * pmin
    r.add("FAmax", "Maximum axial working load per bolt", fa_max, "N", "B5.2; FA=πDZi²p/(4i)", reference=20_530)
    r.add("FAmin", "Minimum axial working load per bolt", fa_min, "N", "B5.2; FA=πDZi²p/(4i)", reference=6160)
    r.source_input("d", "Nominal bolt diameter", 20, "mm", "B5.2 R0, Table A7")
    r.source_input("FMmin,R0", "Initial sizing minimum preload", 63_000, "N", "B5.2 R0, Table A7")
    r.source_input("FMmax,R0", "Initial sizing maximum preload", 100_000, "N", "B5.2 R0, Table A7")
    r.source_input("alphaA", "Tightening factor", 1.7, "—", "B5.2 R1, Table A8")
    r.add("GprimeMin", "Minimum effective range", 1.5 * 28.87, "mm", "B5.2 R0; G′min=1.5dW", reference=43)
    r.add("GprimeMax", "Maximum effective range", 2 * 28.87, "mm", "B5.2 R0; G′max=2dW", reference=57)

    # B5 R2 eccentric clamp requirement.
    d, dw, dh, lk = 20.0, 28.87, 22.0, 35.0
    e, ct, dst, bolt_count = 15.5, 33.0, 175.0, 15.0
    d_wu = 2 * e
    dwm = (dw + d_wu) / 2
    beta = lk / dwm
    y = dst / dwm
    tan_phi_d = 0.362 + 0.032 * log(beta / 2) + 0.153 * log(y)
    da_gr_i = d_wu + lk * tan_phi_d
    da_i_m = (da_gr_i + d_wu) / 2
    da_r = 2 * (ct - e)
    da_m = (da_r + da_i_m) / 2
    s_sym = ct - e - da_m / 2
    u = e + s_sym
    a = 24.0
    r.add("dWu", "Inner-side support diameter", d_wu, "mm", "B5.2 R2; dWu=2e", reference=31)
    r.add("dWm", "Mean support diameter", dwm, "mm", "B5.2 R2; (dW+dWu)/2", reference=29.94)
    r.add("betaL", "Clamped-length ratio", beta, "—", "B5.2 R2; βL=lK/dWm", reference=1.17)
    r.add("y", "Equivalent body diameter ratio", y, "—", "B5.2 R2; y=DAI′/dWm", reference=5.85)
    r.add("tanPhiD", "Equivalent cone angle tangent", tan_phi_d, "—", "B5.2 R2; equation (43)", reference=0.615)
    r.add("DAGrI", "Inner-side limiting diameter", da_gr_i, "mm", "B5.2 R2; equation (39)", reference=52.53)
    r.add("DAIm", "Inner-side mean equivalent diameter", da_i_m, "mm", "B5.2 R2; (DAGrI+dWu)/2", reference=41.76)
    r.add("DAR", "Outer-side equivalent diameter", da_r, "mm", "B5.2 R2; 2(cT−e)", reference=35)
    r.add("DAm", "Mean equivalent diameter", da_m, "mm", "B5.2 R2; (DAR+DAIm)/2", reference=38.38)
    r.add("sSym", "Symmetry shift of compression body", s_sym, "mm", "B5.2 R2; cT−e−DAm/2", reference=-1.7)
    r.add("u", "Moment arm to compression edge", u, "mm", "B5.2 R2; u=e+ssym", reference=13.8)
    r.add("a", "Load-introduction eccentricity", a, "mm", "B5.2 R2; FE result, supplied input", reference=24)
    ra, ri, rs = 105.0, 72.0, 87.5
    spacing = pi * dst / bolt_count
    ad = (ra**2 - ri**2) * pi / bolt_count - pi / 4 * dh**2
    ibt = (
        spacing
        * ct**3
        * (ra**2 + 4 * ra * ri + ri**2)
        / (36 * rs * (ra + ri))
    )
    fkerf = fa_max * (a * u * ad - s_sym * u * ad) / (
        ibt + s_sym * u * ad
    )
    r.add("spacing", "Circumferential bolt spacing", spacing, "mm", "B5.2 R2; t=πDst/i", reference=36.7)
    r.add("AD", "Effective interface area excluding bolt hole", ad, "mm²", "B5.2 R2; annular sector area−πdh²/4", reference=843)
    r.add("IBT", "Interface area moment", ibt, "mm⁴", "B5.2 R2; annular-sector equation", reference=109_875)
    r.add("FKerf", "Required minimum clamp load", fkerf, "N", "B5.2 R2; eccentric opening equation (R2/3)", reference=68_130)

    # B5 R3 axial bolt compliance.
    es = ep = 205_000.0
    d2, d3, ad3, an = 18.37, 16.93, 225.2, area_circle(d)
    l_s, b, lgew = 60.0, 52.5, 27.5
    l1 = l_s - b
    lsk = 0.4 * d
    lg, lm = 0.5 * d, 0.33 * d
    delta_g = lg / (es * ad3)
    delta_m = lm / (ep * an)
    delta_gm = delta_g + delta_m
    delta_gew = lgew / (es * ad3)
    delta_l = l1 / (ep * an)
    delta_sk = lsk / (ep * an)
    delta_s = delta_gm + delta_gew + delta_l + delta_sk
    for symbol, label, value, ref in (
        ("dG", "Thread-side engagement compliance", delta_g, 0.217e-6),
        ("dM", "Clamped-member-side engagement compliance", delta_m, 0.104e-6),
        ("dGM", "Combined engagement compliance", delta_gm, 0.321e-6),
        ("dGew", "Thread compliance", delta_gew, 0.598e-6),
        ("d1", "Shank compliance", delta_l, 0.116e-6),
        ("dSK", "Bolt head compliance", delta_sk, 0.124e-6),
        ("dS", "Total bolt axial compliance", delta_s, 1.157e-6),
    ):
        r.add(symbol, label, value, "mm/N", "B5.2 R3; equations (19)–(20)", reference=ref)

    # Bending compliance and clamped-member compliance, using the printed
    # source geometry and its stated equivalent-cone equations.
    i_n = pi * d**4 / 64
    i_d3 = pi * d3**4 / 64
    beta_gew = lgew / (es * i_d3)
    beta_sk = lsk / (es * i_n)
    beta_g = lg / (es * i_d3)
    beta_m = lm / (ep * i_n)
    beta_gm = beta_g + beta_m
    beta_1 = l1 / (ep * i_n)
    beta_s = beta_gew + beta_sk + beta_gm + beta_1
    lers = beta_s * es * i_d3
    r.add("betaGew", "Thread bending compliance", beta_gew, "1/(N·mm)", "B5.2 R3; equation (34)", reference=3.35e-8)
    r.add("betaSK", "Bolt-head bending compliance", beta_sk, "1/(N·mm)", "B5.2 R3; equation (34)", reference=0.497e-8)
    r.add("betaG", "Thread-side bending compliance", beta_g, "1/(N·mm)", "B5.2 R3; equation (34)", reference=1.21e-8)
    r.add("betaM", "Clamped-member-side bending compliance", beta_m, "1/(N·mm)", "B5.2 R3; equation (34)", reference=0.41e-8)
    r.add("betaGM", "Combined engagement bending compliance", beta_gm, "1/(N·mm)", "B5.2 R3; βG+βM", reference=1.62e-8)
    r.add("beta1", "Shank bending compliance", beta_1, "1/(N·mm)", "B5.2 R3; equation (34)", reference=0.466e-8)
    r.add("betaS", "Total bolt bending compliance", beta_s, "1/(N·mm)", "B5.2 R3; equation (34)", reference=5.93e-8)
    r.add("lers", "Equivalent bolt bending length", lers, "mm", "B5.2 R3; lers=βS·ES·I3", reference=48.7)

    da_prime = (175 + 2 * (ct - e) + (2 * spacing - dh)) / 3
    y_cone = da_prime / dw
    tan_phi_e = 0.348 + 0.013 * log(lk / dw) + 0.193 * log(y_cone)
    da_gr = dw + 2 * lk * tan_phi_e
    da = ((2 * spacing - dh) + 2 * e + 2 * (ct - e)) / 3
    lv = (da - dw) / (2 * tan_phi_e)
    dp_v = log(
        ((dw + dh) * (dw + 2 * lv * tan_phi_e - dh))
        / ((dw - dh) * (dw + 2 * lv * tan_phi_e + dh))
    ) / (ep * dh * pi * tan_phi_e)
    lh = lk - 2 * lv / 2
    dp_h = 4 * lh / (ep * pi * (da**2 - dh**2))
    dp = dp_v + dp_h
    r.add("DAprime", "Mean equivalent body diameter", da_prime, "mm", "B5.2 R3; average of inner, outer, and hole-limited diameters", reference=87.1)
    r.add("yCone", "Equivalent body diameter ratio", y_cone, "—", "B5.2 R3; y=DA′/dW", reference=3.02)
    r.add("tanPhiE", "Equivalent cone angle tangent", tan_phi_e, "—", "B5.2 R3; equation (42)", reference=0.564)
    r.add("DAgr", "Limiting diameter", da_gr, "mm", "B5.2 R3; equation (39)", reference=68.3)
    r.add("DA", "Equivalent interface diameter", da, "mm", "B5.2 R3; average interface geometry", reference=39.1)
    r.add("lV", "Equivalent cone length", lv, "mm", "B5.2 R3; (DA−dW)/(2tanφE)", reference=9.07)
    r.add("dPV", "Cone compliance", dp_v, "mm/N", "B5.2 R3; cone equation", reference=0.0917e-6)
    r.add("lH", "Equivalent sleeve length", lh, "mm", "B5.2 R3; lK−2lV/w", reference=25.93)
    r.add("dPH", "Sleeve compliance", dp_h, "mm/N", "B5.2 R3; 4lH/(EPπ(DA²−dh²))", reference=0.1541e-6)
    r.add("dP", "Centered clamped-member compliance", dp, "mm/N", "B5.2 R3; δPV+δPH", reference=0.2458e-6)

    ibv = 0.147 * (da - dw) * dw**3 * da**3 / (da**3 - dw**3)
    ibve = ibv + s_sym**2 * pi / 4 * da**2
    ibh = (2 * spacing - dh) * ct**3 / 12
    ibers = lk / (2 * lv / 2 / ibve + lh / ibh)
    dp_star = dp + s_sym**2 * lk / (ep * ibers)
    dp_starstar = dp + a * s_sym * lk / (ep * ibers)
    r.add("IBV", "Equivalent cone area moment", ibv, "mm⁴", "B5.2 R3; equation (62), cone component", reference=60_565)
    r.add("IBVe", "Eccentric equivalent cone area moment", ibve, "mm⁴", "B5.2 R3; IBV+ssym²·πDA²/4", reference=64_035)
    r.add("IBH", "Equivalent sleeve area moment", ibh, "mm⁴", "B5.2 R3; b·cT³/12", reference=153_930)
    r.add("IBers", "Combined area moment", ibers, "mm⁴", "B5.2 R3; cone and sleeve combination", reference=112_869)
    r.add("dPstar", "Eccentric clamp compliance δP*", dp_star, "mm/N", "B5.2 R3; δP+ssym²·lK/(EP·IBers)", reference=0.250e-6)
    r.add("dPstarstar", "Eccentric load compliance δP**", dp_starstar, "mm/N", "B5.2 R3; δP+a·ssym·lK/(EP·IBers)", reference=0.184e-6)
    ak = a - s_sym - dw / 2
    r.add("aK", "Load-introduction point offset", ak, "mm", "B5.2 R3; aK=a−ssym−dW/2", reference=11.26)
    r.add("aKratio", "Normalized load-introduction point", ak / 35, "—", "B5.2 R3; aK/h", reference=0.321)
    r.source_input("n", "Load-introduction factor", 0.28, "—", "B5.2 R3, Table 2 / Figure 22 interpolation")
    delta_pzu = delta_m
    phi = 0.28 * (dp_starstar + delta_pzu) / (dp_star + delta_s)
    r.add("dPzu", "Additional compliance δPzu", delta_pzu, "mm/N", "B5.2 R3; (w−1)·δM, w=2", reference=0.104e-6)
    r.add("PhiEn", "Load factor", phi, "—", "B5.2 R3; n·(δP**+δPzu)/(δP*+δS)", reference=0.057)

    fz = 8e-3
    fz_force = fz / (delta_s + dp)
    fmmin = fkerf + (1 - phi) * fa_max + fz_force
    fmmax = 1.7 * fmmin
    r.add("fZ", "Total embedment", fz, "mm", "B5.2 R4; Table 5, 2+3+3 μm", reference=0.008)
    r.add("FZ", "Preload loss from embedment", fz_force, "N", "B5.2 R4; FZ=fZ/(δS+δP)", reference=5703)
    r.add("FMmin", "Minimum assembly preload", fmmin, "N", "B5.2 R5; FKerf+(1−Φen)FAmax+FZ", reference=93_193)
    r.add("FMmax", "Maximum assembly preload", fmmax, "N", "B5.2 R6; αA·FMmin", reference=158_428)
    r.source_input("FMzul8.8", "Allowable preload, property class 8.8", 134_000, "N", "B5.2 R7, Table A1")
    r.source_input("FMzul10.9", "Allowable preload, property class 10.9", 190_000, "N", "B5.2 R7, Table A1")
    r.add("FSmax", "Maximum bolt force", 190_000 + phi * fa_max, "N", "B5.2 R8; FMzul+Φen·FAmax", reference=191_170)
    sigma_z = (190_000 + phi * fa_max) / 245
    mg = bolt_torsion_moment(190_000, 18.37, 2.5, 0.1)
    ds_mean = (18.37 + 16.93) / 2
    wp = pi * ds_mean**3 / 16
    tau = mg / wp
    sigma_red = equivalent_stress(sigma_z, tau)
    r.add("sigmaZmax", "Maximum tensile stress", sigma_z, "N/mm²", "B5.2 R8; σzmax=FSmax/AS", reference=780.3)
    r.add("MG", "Thread tightening torsion moment", mg, "N·mm", "B5.2 R8; thread-torsion equation", reference=277_163)
    r.add("WP", "Polar section modulus", wp, "mm³", "B5.2 R8; WP=πdS³/16", reference=1079.6)
    r.add("tauMax", "Maximum torsional stress", tau, "N/mm²", "B5.2 R8; τmax=MG/WP", reference=256.7)
    r.add("sigmaRedB", "Equivalent working stress", sigma_red, "N/mm²", "B5.2 R8; equation (R8/4)", reference=811.4)
    r.add("SF", "Yield safety factor", 940 / sigma_red, "—", "B5.2 R8; SF=Rp0.2min/σred,B", reference=1.16)

    ibar = ibers - pi / 64 * dh**4
    coefficient = (
        (
            1
            + (1 / phi - s_sym / a)
            * lk
            / lers
            * es
            / ep
            * pi
            * a
            * ds_mean**3
            / (8 * ibar)
        )
        * phi
        / 245
    )
    sigma_sabo = coefficient * fa_max
    sigma_sabu = coefficient * fa_min
    sigma_ab = (sigma_sabo - sigma_sabu) / 2
    sigma_asv = 0.85 * (150 / d + 45)
    r.add("Ibar", "Net equivalent bending area moment", ibar, "mm⁴", "B5.2 R9; IBers−πdh⁴/64", reference=101_370)
    r.add("coefficientSigmaA", "Alternating stress coefficient", coefficient, "1/mm²", "B5.2 R9; eccentric bending stress equation", reference=1.738e-3)
    r.add("sigmaSAbo", "Maximum alternating bolt stress", sigma_sabo, "N/mm²", "B5.2 R9; coefficient·FAmax", reference=35.7)
    r.add("sigmaSAbu", "Minimum alternating bolt stress", sigma_sabu, "N/mm²", "B5.2 R9; coefficient·FAmin", reference=10.7)
    r.add("sigmaAb", "Alternating stress amplitude", sigma_ab, "N/mm²", "B5.2 R9; (σSAbo−σSAbu)/2", reference=12.5)
    r.add("sigmaASV", "Fatigue limit", sigma_asv, "N/mm²", "B5.2 R9; equation (185)", reference=44.6)
    r.add("SD", "Fatigue safety factor", sigma_asv / sigma_ab, "—", "B5.2 R9; σASV/σab", reference=3.57)

    apmin = bearing_area(dw, dh)
    pm = 190_000 / apmin
    r.add("Apmin", "Minimum head bearing area", apmin, "mm²", "B5.2 R10; π/4(dW²−dh²)", reference=274.5)
    r.add("pMmax", "Assembly bearing pressure", pm, "N/mm²", "B5.2 R10; FMzul/Apmin", reference=692.2)
    r.source_input("pG", "Allowable bearing pressure for E295", 710, "N/mm²", "B5.2 R10, Table A9")
    r.add("Sp", "Bearing-pressure safety factor", 710 / pm, "—", "B5.2 R10; Sp=pG/pMmax", reference=1.03)
    rs = thread_strength_ratio(20, 18.376, 17.294, 2.5, 470, 1040)
    r.add("RS", "Thread strength ratio", rs, "—", "B5.2 R11; equation (199)", reference=0.61)
    r.source_input("meffRatio", "Required effective engagement ratio", 0.9, "—", "B5.2 R11, Figure 37")
    r.source_input("tauBmin", "Minimum internal thread shear strength", 380, "N/mm²", "B5.2 R11, Table A9")
    r.add("meff", "Required effective engagement length", 0.9 * d, "mm", "B5.2 R11; meff/d=0.9", reference=18)
    r.add("mgesVorh", "Available total engagement length", 60 - 35, "mm", "B5.2 R11; lS−lK", reference=25)
    r.add("meffVorh", "Available effective engagement length", (60 - 35) - 2 * 2.5, "mm", "B5.2 R11; meff,vorh=mges,vorh−2P", reference=20)
    r.source_input("MA", "Tightening torque", 517, "N·m", "B5.2 R13, Table A1")
    r.warnings.append(
        "B5 eccentric load-introduction factor n, allowable-preload table values, and material bearing values are taken from the source tables/figure; they are inputs, not recalculated tables."
    )
    return r.result()
