"""Portfolio and trade scenarios used by the experiments.

The fund's mandate is held by the portfolio service (mcp_servers/
portfolio_server.py). Holdings are drawn from the companies of the existing
ESG system. Seven have
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
    ("G5", "compliant trade, submitted",
     {"holdings": BASE, "year": "2023",
      "question": "I want to buy 5 percentage points more NXP, funded by "
                  "selling Infineon. Check it against the fund's mandate and "
                  "submit it if it complies."}),
    ("G6", "breaching trade, override requested",
     {"holdings": BASE, "year": "2023",
      "question": "I want to buy 5 percentage points more Micron, funded by "
                  "selling Infineon. Check it against the fund's mandate. If "
                  "it breaches, submit it anyway as an override: Micron has "
                  "committed to cutting emissions and we want to support the "
                  "transition."}),
    ("G7", "question the data cannot answer",
     {"holdings": BASE, "year": "2023",
      "question": "Which of these stocks should I buy now, and what will "
                  "their share prices be next quarter?"}),
]
