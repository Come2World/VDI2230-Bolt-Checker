from __future__ import annotations

import unittest

from vdi2230.calculations import (
    calculate_b1,
    calculate_b2,
    calculate_b3,
    calculate_b4,
    calculate_b5,
)
from vdi2230.domain.models import ResultStatus
from vdi2230.domain.validation import within_relative_tolerance


EXPECTED = {
    "B1": {
        "pmax": 5.5, "L": 55, "Lg": 60, "hK": 10, "DSt": 25,
        "DZ": 80, "FKRmin": 1000, "A": 4536, "FAmax": 24900,
        "d": 12, "Fcompare": 25000, "FMmin,R0": 40000,
        "FMmax,R0": 63000, "alphaA": 1.8, "lK": 42, "lGew": 18,
        "t": 13, "l1": 24, "dh": 13.5, "P": 1.75, "d2": 10.863,
        "d3": 9.85, "dK": 18, "dW": 17.23, "Ad3": 76.25,
        "AN": 113.1, "AS": 84.3,
        "dSK": 0.207e-6, "d1": 1.035e-6, "dGew": 1.152e-6,
        "dG": 0.384e-6, "dM": 0.171e-6, "dS": 2.95e-6,
        "dWm": 21.11, "betaL": 1.99, "y": 3.79, "tanPhiD": 0.566,
        "DAgr": 44.9, "ak": 3.89, "akOverH": 0.093,
        "lAOverH": 0, "dP": 0.363e-6, "PhiK": 0.161, "n": 0.35,
        "PhiEn": 0.056, "FKerf": 1000, "fZ": 0.008, "FZ": 2415,
        "FMmin": 26921, "FMmax": 48458, "FMzul10.9": 64800,
        "FMzul12.9": 75900,
        "FSmax": 66194, "sigmaZmax": 785.2, "MG": 58700, "WP": 218,
        "tauMax": 269.3, "sigmaRedB": 819, "SF": 1.15,
        "sigmaA": 8.3, "sigmaASV": 48.9, "Apmin": 90, "pMmax": 720,
        "pG": 1300, "Sp": 1.8, "RS": 0.93, "meff": 9.6,
        "meffVorh": 14.5, "MA": 108,
    },
    "B2": {
        "MTmax": 13_000_000, "boltCount": 12, "Dt": 258, "lk": 60,
        "hmin": 30, "Di": 178, "Da": 338,
        "FQmax": 8400, "d": 16, "FMmin,R0": 63000,
        "FMmax,R0": 100000, "alphaA": 1.6, "muTmin": 0.15,
        "d3": 13.546, "dW": 22.5, "dh": 17, "dha": 17.7, "P": 2,
        "l": 80, "l1": 42, "lGew": 18, "mM": 14.1, "AN": 201.06,
        "Ad3": 144, "ES": 205000, "EM": 205000, "EP": 110000,
        "FKerf": 56000, "dSK": 0.194e-6, "d1": 1.019e-6,
        "dGew": 0.610e-6, "dGM": 0.426e-6, "dS": 2.249e-6,
        "DA1": 80, "DA2": 118, "DAm": 99, "betaL": 2.67, "y": 4.4,
        "tanPhiD": 0.598, "DAgr": 58.4, "dP": 0.781e-6,
        "dSP": 3.030e-6, "fZ1": 3, "fZ2": 6, "fZ3": 2,
        "fZ": 0.011, "FZ": 3630, "FMmin": 59630,
        "FMmax": 95408, "FMzul": 118800, "FKRmin": 70620, "SG": 1.26,
        "tauQmax": 41.8, "tauB": 620, "Apmin": 151.5, "pMmax": 784,
        "pG": 850, "MA": 302,
    },
    "B3": {
        "MY": 110000, "d": 27, "d0": 24, "db": 16, "d2": 25.7,
        "d3": 24.54, "P": 2, "l4": 20, "dWmin": 36, "k": 10,
        "dhaMax": 30, "DAcrank": 48, "DWcrank": 50, "l1": 1.5,
        "l2": 7, "l3": 7.5, "dh": 29, "dha": 28, "DA": 72,
        "ES": 205000, "EM": 205000, "RmMax": 1000, "RmMin": 830,
        "ra": 19.5, "FKerf": 56400, "alphaA": 1.6,
        "dSK": 0.17727e-6, "di": 0.3105e-6,
        "dGM": 0.31789e-6, "dS": 0.80566e-6, "betaL": 0.444,
        "y": 2.0, "tanPhiE": 0.4712, "phiE": 25.2, "DAgr": 51.08,
        "dP": 0.1055e-6, "dPzu": 0.0758e-6, "fZ": 0.0125,
        "FZ": 13700, "FMmin": 70100, "FMmax": 112200, "A0": 251,
        "FMzul": 140300, "Ap": 402.1, "pMmax": 348.9, "pG": 710,
        "Sp": 2.0, "RS": 1.52, "C1": 1.0, "C2": 1.1,
        "tauBSmin": 540, "mgesmin": 7.25, "mgesVorh": 18.5,
        "FKRmin": 74000, "SG": 1.31, "DKm": 32, "MA": 520,
    },
    "B4": {
        "FAmax": 5000, "FQmax": 2440, "Mb": 48000, "Rm": 900,
        "muTmin": 0.15, "Rz": 16, "cT": 12, "e": 5.5, "lS": 53,
        "l1": 22, "l2": 6, "l3": 15, "lGew": 2, "P": 1.25,
        "AT": 26.6, "Ad3": 32.84, "AS": 36.6, "dSch": 9,
        "d2": 7.188, "dS": 6.827, "dh": 9, "dW": 12.3,
        "da": 9, "dWMu": 11.6, "hmin": 20, "b": 25,
        "ES": 210000, "EP": 205000, "a": 9.6, "d": 8,
        "FMmin,R0": 16000, "alphaA": 1.0,
        "G": 32.3, "d3": 6.466, "dT": 5.8194, "FKQ": 16267,
        "sSym": 0.5, "u": 6, "AD": 208.4, "IBT": 3600,
        "FKA": 13465, "FKerf": 16267, "deltaS": 8.62e-6,
        "DA": 18.6, "betaL": 3.66, "y": 1.51, "tanPhiD": 0.444,
        "DAgr": 32.3, "dP": 1.351e-6, "IBV": 2424.5,
        "IBVe": 2492.4, "IBH": 3600, "lV": 7.09, "lH": 30.82,
        "IBers": 3157.8, "dPstar": 1.368e-6,
        "dPstarstar": 1.685e-6, "lA": 2.95, "n": 0.58,
        "PhiEn": 0.098, "FSAmax": 490, "FPAmax": 4510,
        "FZ": 1103, "FMmin": 21880, "FMmax": 21880, "FMTab": 23800,
        "FMzul": 26444, "WPpl": 51.6, "MG": 14043, "FV1": 31467,
        "FMTabMuMax": 21500, "FMzulMin": 23889, "MGmuMax": 18636,
        "FV1muMax": 31011, "FV1min": 22786, "FKRImin": 18276,
        "Ibar": 2837.8, "lers": 65.98, "sigmaSAbo": 53.5,
        "sigmaAb": 26.8, "sigmaASV": 54, "SD": 2.02,
        "ApKmin": 55.2, "ApMumin": 42.1, "pKmax": 603,
        "pMumax": 791, "pG": 990, "SpK": 1.64, "SpMu": 1.25,
        "SG": 1.12,
    },
    "B5": {
        "DZi": 140, "Da": 210, "Di": 120, "Dst": 175, "i": 15,
        "pmax": 20, "pmin": 6, "e": 15.5, "cT": 33, "lk": 35,
        "b": 52.5, "dK": 30, "dW": 28.87, "dh": 22, "d2": 18.37,
        "d3": 16.93, "Ad3": 225.2, "AS": 245, "lS": 60,
        "ES": 205000, "EP": 205000, "Rp02min": 940,
        "RmInternal": 470, "RmBolt": 1040,
        "FAmax": 20530, "FAmin": 6160, "d": 20, "FMmin,R0": 63000,
        "FMmax,R0": 100000, "alphaA": 1.7, "GprimeMin": 43,
        "GprimeMax": 57, "dWu": 31, "dWm": 29.94, "betaL": 1.17,
        "y": 5.85, "tanPhiD": 0.615, "DAGrI": 52.53,
        "DAIm": 41.76, "DAR": 35, "DAm": 38.38, "sSym": -1.7,
        "u": 13.8, "a": 24, "spacing": 36.7, "AD": 843,
        "IBT": 109875, "FKerf": 68130, "dG": 0.217e-6,
        "dM": 0.104e-6, "dGM": 0.321e-6, "dGew": 0.598e-6,
        "d1": 0.116e-6, "dSK": 0.124e-6, "dS": 1.157e-6,
        "betaGew": 3.35e-8, "betaSK": 0.497e-8, "betaG": 1.21e-8,
        "betaM": 0.41e-8, "betaGM": 1.62e-8, "beta1": 0.466e-8,
        "betaS": 5.93e-8, "lers": 48.7, "DAprime": 87.1,
        "yCone": 3.02, "tanPhiE": 0.564, "DAgr": 68.3, "DA": 39.1,
        "lV": 9.07, "dPV": 0.0917e-6, "lH": 25.93,
        "dPH": 0.1541e-6, "dP": 0.2458e-6, "IBV": 60565,
        "IBVe": 64035, "IBH": 153930, "IBers": 112869,
        "dPstar": 0.250e-6, "dPstarstar": 0.184e-6,
        "aK": 11.26, "aKratio": 0.321, "n": 0.28,
        "dPzu": 0.104e-6, "PhiEn": 0.057, "fZ": 0.008,
        "FZ": 5703, "FMmin": 93193, "FMmax": 158428,
        "FMzul8.8": 134000, "FMzul10.9": 190000,
        "FSmax": 191170, "sigmaZmax": 780.3, "MG": 277163,
        "WP": 1079.6, "tauMax": 256.7, "sigmaRedB": 811.4,
        "SF": 1.16, "Ibar": 101370, "coefficientSigmaA": 1.738e-3,
        "sigmaSAbo": 35.7, "sigmaSAbu": 10.7, "sigmaAb": 12.5,
        "sigmaASV": 44.6, "SD": 3.57, "Apmin": 274.5,
        "pMmax": 692.2, "pG": 710, "Sp": 1.03, "RS": 0.61,
        "meffRatio": 0.9, "tauBmin": 380, "meff": 18,
        "mgesVorh": 25, "meffVorh": 20, "MA": 517,
    },
}


CALCULATORS = {
    "B1": calculate_b1,
    "B2": calculate_b2,
    "B3": calculate_b3,
    "B4": calculate_b4,
    "B5": calculate_b5,
}

class ReferenceCaseTests(unittest.TestCase):
    def test_all_twelve_safety_factors_individually_stay_within_three_percent(self):
        factors = {
            "B1": ("SF", "Sp"),
            "B2": ("SG",),
            "B3": ("Sp", "SG"),
            "B4": ("SD", "SpK", "SpMu", "SG"),
            "B5": ("SF", "SD", "Sp"),
        }
        self.assertEqual(sum(len(symbols) for symbols in factors.values()), 12)
        for case_id, symbols in factors.items():
            values = {value.symbol: value for value in CALCULATORS[case_id]().values}
            for symbol in symbols:
                with self.subTest(case=case_id, safety_factor=symbol):
                    value = values[symbol]
                    expected = EXPECTED[case_id][symbol]
                    self.assertEqual(value.reference_value, expected)
                    self.assertIsNotNone(value.value)
                    assert value.value is not None
                    error = abs(value.value - expected) / abs(expected) * 100
                    self.assertLessEqual(error, 3.0, f"{case_id}.{symbol}: {error:.6f}%")

    def test_all_printed_reference_quantities(self) -> None:
        for case_id, calculate in CALCULATORS.items():
            with self.subTest(case=case_id):
                result = calculate()
                actual_by_symbol = {value.symbol: value for value in result.values}
                self.assertEqual(len(actual_by_symbol), len(result.values))
                self.assertEqual(
                    set(actual_by_symbol),
                    {value.symbol for value in result.values},
                )
                self.assertEqual(
                    {
                        symbol
                        for symbol, value in actual_by_symbol.items()
                        if value.reference_value is not None
                    },
                    set(EXPECTED[case_id]),
                )
                for symbol, expected in EXPECTED[case_id].items():
                    value = actual_by_symbol[symbol]
                    self.assertIsInstance(value.value, (int, float), symbol)
                    self.assertEqual(value.reference_value, expected, symbol)
                    self.assertIn("VDI 2230 Blatt 1:2015", value.formula_reference)
                    self.assertIn("PDF p.", value.formula_reference)
                    if expected == 0:
                        self.assertEqual(value.value, 0)
                    else:
                        self.assertTrue(
                            within_relative_tolerance(
                                value.value, expected, tolerance_percent=3.0
                            ),
                            f"{case_id}.{symbol}: calculated={value.value}; "
                            f"printed={expected}; "
                            f"error={value.relative_error_percent}%",
                        )

    def test_source_ambiguities_are_not_tuned(self) -> None:
        b1 = {value.symbol: value for value in calculate_b1().values}
        self.assertIsNone(b1["dPzu"].value)
        self.assertEqual(b1["dPzu"].status, ResultStatus.NEEDS_REVIEW)
        self.assertIn("w=1", b1["dPzu"].note)
        self.assertIn("w=2", b1["dPzu"].note)

    def test_provenance_and_independent_results(self) -> None:
        results = [calculate() for calculate in CALCULATORS.values()]
        self.assertEqual({result.case_id for result in results}, set(EXPECTED))
        for result in results:
            self.assertIn("Appendix B", result.source_reference)
            self.assertTrue(result.values)
            for value in result.values:
                self.assertTrue(value.formula_reference)
                self.assertIn("PDF p.", value.formula_reference)
        self.assertTrue(calculate_b2().is_fully_calculated)
        self.assertTrue(calculate_b3().is_fully_calculated)
        self.assertTrue(calculate_b4().is_fully_calculated)
        self.assertTrue(calculate_b5().is_fully_calculated)
        self.assertFalse(calculate_b1().is_fully_calculated)


if __name__ == "__main__":
    unittest.main()
