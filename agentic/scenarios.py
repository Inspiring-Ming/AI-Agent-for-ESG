"""Portfolio scenarios used by the experiments and the analyst page.

Holdings are drawn from the companies of the existing ESG system. Seven have
both emissions and revenue, so their carbon intensity can be computed; for
others (e.g. TSMC) the system reports missing revenue.
"""

BASE = [{"company": "STMicroelectronics NV", "weight_pct": 30},
        {"company": "Infineon Technologies AG", "weight_pct": 25},
        {"company": "Micron Technology Inc", "weight_pct": 25},
        {"company": "NXP Semiconductors NV", "weight_pct": 20}]

WITH_MISSING = BASE[:3] + [{"company": "Taiwan Semiconductor Manufacturing Co Ltd",
                            "weight_pct": 20}]

SEVEN = [{"company": c, "weight_pct": w} for c, w in [
    ("STMicroelectronics NV", 20), ("Infineon Technologies AG", 15),
    ("NXP Semiconductors NV", 15), ("Microchip Technology Inc", 15),
    ("ON Semiconductor Corp", 10), ("United Microelectronics Corp", 10),
    ("Micron Technology Inc", 15)]]

DRIVERS = "What is the carbon intensity of my portfolio, and which holdings drive it?"

# Worked example (Section V): a portfolio with one holding lacking data.
WORKED_EXAMPLE = {"holdings": WITH_MISSING, "year": "2023", "question": DRIVERS}

GOALS = [
    ("G1", "carbon intensity and its drivers",
     {"holdings": BASE, "year": "2023", "question": DRIVERS}),
    ("G2", "change since an earlier year",
     {"holdings": BASE, "year": "2023", "compare_year": "2022",
      "question": "Has my portfolio's carbon intensity improved since 2022? "
                  "What changed?"}),
    ("G3", "a holding without data",
     {"holdings": WITH_MISSING, "year": "2023", "question": DRIVERS}),
    ("G4", "larger portfolio",
     {"holdings": SEVEN, "year": "2023", "question": DRIVERS}),
    ("G5", "lower-carbon reweighting",
     {"holdings": BASE, "year": "2023",
      "question": "Propose a reweighting that reduces the portfolio's carbon "
                  "intensity by at least 30%, keeping every holding at 10% "
                  "or more."}),
    ("G6", "question the data cannot answer",
     {"holdings": BASE, "year": "2023",
      "question": "Which of these stocks should I buy now, and what will "
                  "their share prices be next quarter?"}),
]
