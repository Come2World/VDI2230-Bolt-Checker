from __future__ import annotations

from math import log, pi

from vdi2230.domain.models import CalculationResult

from ._common import (
    ResultBuilder,
    area_circle,
    bearing_area,
)


def calculate_b2() -> CalculationResult:
    """Recalculate the printed B2 quantities from the supplied case inputs."""
    r = ResultBuilder("B2", "139–142")
    torque = 13_000_000.0
    bolt_count = 12.0
    pitch_circle = 258.0
    r.source_input("MTmax", "Maximum transmitted torque", torque, "N·mm", "B2.1; 13 kN·m")
    r.source_input("boltCount", "Number of bolts", bolt_count, "—", "B2.1")
    r.source_input("Dt", "Bolt pitch-circle diameter", pitch_circle, "mm", "B2.1, Figure B2")
    r.source_input("lk", "Clamped length", 60, "mm", "B2.1, Figure B2")
    r.source_input("hmin", "Minimum half-clamp height", 30, "mm", "B2.1; lk/2")
    r.source_input("Di", "Inner flange diameter", 178, "mm", "B2.1, Figure B2")
    r.source_input("Da", "Outer flange diameter", 338, "mm", "B2.1, Figure B2")
    fq = 2 * torque / (bolt_count * pitch_circle)
    r.add("FQmax", "Maximum tangential bolt load", fq, "N", "B2.2 R0; FQmax=2MTmax/(i·Dt)", reference=8400)
    r.source_input("d", "Nominal bolt diameter", 16, "mm", "B2.2 R0, Table A7")
    r.source_input("FMmin,R0", "Initial sizing minimum preload", 63_000, "N", "B2.2 R0, Table A7")
    r.source_input("FMmax,R0", "Initial sizing maximum preload", 100_000, "N", "B2.2 R0, Table A7")
    r.source_input("alphaA", "Tightening factor", 1.6, "—", "B2.2 R1, Table A8")
    r.source_input("muTmin", "Minimum interface friction coefficient", 0.15, "—", "B2.1, assumed material-pair value")
    fkerf = fq / (1 * 0.15)
    r.add("FKerf", "Required minimum clamp load", fkerf, "N", "B2.2 R2; FKQ=FQmax/(qF·μTmin)", reference=56_000)

    es = em = 205_000.0
    ep = 110_000.0
    d, pitch, d3, an, ad3 = 16.0, 2.0, 13.546, area_circle(16), 144.0
    l_k, l1, l_gew = 60.0, 42.0, 18.0
    for symbol, label, value, unit in (
        ("d3", "Thread minor diameter", d3, "mm"),
        ("dW", "Bolt bearing diameter", 22.5, "mm"),
        ("dh", "Clearance-hole diameter", 17.0, "mm"),
        ("dha", "Hole chamfer diameter", 17.7, "mm"),
        ("P", "Thread pitch", pitch, "mm"),
        ("l", "Bolt length", 80.0, "mm"),
        ("l1", "Bolt shank length in grip", l1, "mm"),
        ("lGew", "Thread length in grip", l_gew, "mm"),
        ("mM", "Nut height", 14.1, "mm"),
        ("AN", "Nominal shank area", 201.06, "mm²"),
        ("Ad3", "Thread minor-diameter area", ad3, "mm²"),
        ("ES", "Bolt Young's modulus", es, "N/mm²"),
        ("EM", "Nut Young's modulus", em, "N/mm²"),
        ("EP", "Clamped-part Young's modulus", ep, "N/mm²"),
    ):
        r.source_input(symbol, label, value, unit, "B2.2 R0, Tables A9/A11 and cited ISO dimensions")
    dsk = 0.5 * d / (es * an)
    d1 = l1 / (es * an)
    dgew = l_gew / (es * ad3)
    dg = 0.5 * d / (es * ad3)
    dm = 0.4 * d / (em * an)
    ds = dsk + d1 + dgew + dg + dm
    for symbol, label, value, ref in (
        ("dSK", "Bolt head compliance", dsk, 0.194e-6),
        ("d1", "Shank compliance", d1, 1.019e-6),
        ("dGew", "Thread compliance", dgew, 0.610e-6),
        ("dGM", "Thread engagement compliance", dg + dm, 0.426e-6),
        ("dS", "Total bolt compliance", ds, 2.249e-6),
    ):
        r.add(symbol, label, value, "mm/N", "B2.2 R3; equations (19)–(20)", reference=ref)

    dw, dh, da1, da2 = 22.5, 17.0, 80.0, 2 * pi * pitch_circle / bolt_count - 17.0
    dam = (da1 + da2) / 2
    beta = l_k / dw
    y = dam / dw
    tan_phi = 0.362 + 0.032 * log(beta / 2) + 0.153 * log(y)
    da_gr = dw + l_k * tan_phi
    w = 1.0
    dp = (
        2
        * log(
            ((dw + dh) * (dw + w * l_k * tan_phi - dh))
            / ((dw - dh) * (dw + w * l_k * tan_phi + dh))
        )
        / (w * ep * pi * dh * tan_phi)
    )
    r.add("DA1", "Equivalent body diameter at inner side", da1, "mm", "B2.2 R3; (Da−Di)/2", reference=80)
    r.add("DA2", "Equivalent body diameter at adjacent-hole side", da2, "mm", "B2.2 R3; 2πDt/i−dh", reference=118)
    r.add("DAm", "Mean equivalent body diameter", dam, "mm", "B2.2 R3; (DA1′+DA2′)/2", reference=99)
    r.add("betaL", "Clamped-length ratio", beta, "—", "B2.2 R3; βL=lK/dW", reference=2.67)
    r.add("y", "Equivalent body diameter ratio", y, "—", "B2.2 R3; y=DAm′/dW", reference=4.4)
    r.add("tanPhiD", "Equivalent cone angle tangent", tan_phi, "—", "B2.2 R3; equation (43)", reference=0.598)
    r.add("DAgr", "Limiting diameter", da_gr, "mm", "B2.2 R3; equation (39)", reference=58.4)
    r.add("dP", "Clamped-member compliance", dp, "mm/N", "B2.2 R3; equation (40), w=1", reference=0.781e-6)
    r.add("dSP", "Combined joint compliance", ds + dp, "mm/N", "B2.2 R3; δS+δP", reference=3.030e-6)

    fz = 11e-3
    fz_force = fz / (ds + dp)
    fmmin = fkerf + fz_force
    fmmax = 1.6 * fmmin
    for symbol, label, value in (
        ("fZ1", "Thread embedment", 3.0),
        ("fZ2", "Bearing-surface embedment", 6.0),
        ("fZ3", "Interface embedment", 2.0),
    ):
        r.source_input(symbol, label, value, "μm", "B2.2 R4, Table 5")
    r.add("fZ", "Total embedment", fz, "mm", "B2.2 R4; Table 5, 3+6+2 μm", reference=0.011)
    r.add("FZ", "Preload loss from embedment", fz_force, "N", "B2.2 R4; FZ=fZ/(δS+δP)", reference=3630)
    r.add("FMmin", "Minimum assembly preload", fmmin, "N", "B2.2 R5; FKerf+FZ", reference=59_630)
    r.add("FMmax", "Maximum assembly preload", fmmax, "N", "B2.2 R6; αA·FMmin", reference=95_408)
    r.source_input("FMzul", "Allowable preload", 118_800, "N", "B2.2 R7, Table A1")
    fkr = 118_800 / 1.6 - fz_force
    sg = fkr / 56_000
    r.add("FKRmin", "Minimum residual clamp load", fkr, "N", "B2.2 R12; FMzul/αA−FZ", reference=70_620)
    r.add("SG", "Slip safety factor", sg, "—", "B2.2 R12; FKRmin/FKQerf", reference=1.26)
    tau = fq / 201.06
    r.add("tauQmax", "Shear stress if joint slips", tau, "N/mm²", "B2.2 R12; τQmax=FQmax/AN", reference=41.8)
    r.source_input("tauB", "Bolt shear strength", 620, "N/mm²", "B2.2 R12; Table 7 ratio × Rm")
    apmin = bearing_area(22.5, 17.7)
    pressure = 118_800 / apmin
    r.add("Apmin", "Minimum bearing area", apmin, "mm²", "B2.2 R10; π/4(dW²−dha²)", reference=151.5)
    r.add("pMmax", "Assembly bearing pressure", pressure, "N/mm²", "B2.2 R10; FMzul/Apmin", reference=784)
    r.source_input("pG", "Allowable bearing pressure", 850, "N/mm²", "B2.2 R10, Table A9")
    r.source_input("MA", "Tightening torque", 302, "N·m", "B2.2 R13, Table A1")
    r.warnings.append(
        "The source obtains FKQ from its rounded 8.4 kN transverse load; calculations retain that printed rounded value for the preload requirement."
    )
    return r.result()
