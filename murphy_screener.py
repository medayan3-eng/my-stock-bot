"""
Murphy Screener — core engine
==============================
A stock SCREENER (not an auto-trader) built on the principles from
John Murphy's "Technical Analysis of the Financial Markets" and
"Intermarket Analysis", combined with sector relative strength and
candlestick confirmation (Nison).

The engine scores each stock 0-100 and explains, in plain English, why
it scored the way it did. It never places trades — you take it from
here.

REQUIREMENTS (run locally, not in a sandboxed/offline environment):
    pip install yfinance pandas numpy

CLI USAGE:
    python murphy_screener.py                     # scans the bundled S&P 500 list
    python murphy_screener.py AAPL MSFT NVDA       # scans just these tickers
    python murphy_screener.py --file mylist.txt    # one ticker per line
    python murphy_screener.py --top 30             # show only top 30 by score
"""

import os
import sys
import argparse
import datetime as dt
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Missing dependency. Run:  pip install yfinance pandas numpy")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

LOOKBACK_DAYS = 400          # trading days of history to pull (covers 52w + 200MA warmup)
VOLUME_SPIKE_MULT = 2.0      # today's volume vs 20d avg volume to count as "unusual"
NEAR_MA50_PCT = 0.03         # "hugging the 50MA" = within 3%
BREAKOUT_LOOKBACK = 20       # bars used to define "recent swing low" for stop-loss

# Embedded S&P 500 ticker -> (company name, GICS sector) map.
# Embedded directly in code (not read from an external CSV) so the sector
# lookup works reliably in any deployment environment (e.g. Streamlit Cloud)
# without depending on a file being present next to this script.
SP500_DATA = {
    "MMM": ("3M Company", "Industrials"),
    "AOS": ("A.O. Smith Corp", "Industrials"),
    "ABT": ("Abbott Laboratories", "Health Care"),
    "ABBV": ("AbbVie Inc.", "Health Care"),
    "ACN": ("Accenture plc", "Information Technology"),
    "ATVI": ("Activision Blizzard", "Information Technology"),
    "AYI": ("Acuity Brands Inc", "Industrials"),
    "ADBE": ("Adobe Systems Inc", "Information Technology"),
    "AAP": ("Advance Auto Parts", "Consumer Discretionary"),
    "AMD": ("Advanced Micro Devices Inc", "Information Technology"),
    "AES": ("AES Corp", "Utilities"),
    "AET": ("Aetna Inc", "Health Care"),
    "AMG": ("Affiliated Managers Group Inc", "Financials"),
    "AFL": ("AFLAC Inc", "Financials"),
    "A": ("Agilent Technologies Inc", "Health Care"),
    "APD": ("Air Products & Chemicals Inc", "Materials"),
    "AKAM": ("Akamai Technologies Inc", "Information Technology"),
    "ALK": ("Alaska Air Group Inc", "Industrials"),
    "ALB": ("Albemarle Corp", "Materials"),
    "ARE": ("Alexandria Real Estate Equities Inc", "Real Estate"),
    "ALXN": ("Alexion Pharmaceuticals", "Health Care"),
    "ALGN": ("Align Technology", "Health Care"),
    "ALLE": ("Allegion", "Industrials"),
    "AGN": ("Allergan, Plc", "Health Care"),
    "ADS": ("Alliance Data Systems", "Information Technology"),
    "LNT": ("Alliant Energy Corp", "Utilities"),
    "ALL": ("Allstate Corp", "Financials"),
    "GOOGL": ("Alphabet Inc Class A", "Information Technology"),
    "GOOG": ("Alphabet Inc Class C", "Information Technology"),
    "MO": ("Altria Group Inc", "Consumer Staples"),
    "AMZN": ("Amazon.com Inc", "Consumer Discretionary"),
    "AEE": ("Ameren Corp", "Utilities"),
    "AAL": ("American Airlines Group", "Industrials"),
    "AEP": ("American Electric Power", "Utilities"),
    "AXP": ("American Express Co", "Financials"),
    "AIG": ("American International Group, Inc.", "Financials"),
    "AMT": ("American Tower Corp A", "Real Estate"),
    "AWK": ("American Water Works Company Inc", "Utilities"),
    "AMP": ("Ameriprise Financial", "Financials"),
    "ABC": ("AmerisourceBergen Corp", "Health Care"),
    "AME": ("AMETEK Inc", "Industrials"),
    "AMGN": ("Amgen Inc", "Health Care"),
    "APH": ("Amphenol Corp", "Information Technology"),
    "APC": ("Anadarko Petroleum Corp", "Energy"),
    "ADI": ("Analog Devices, Inc.", "Information Technology"),
    "ANDV": ("Andeavor", "Energy"),
    "ANSS": ("ANSYS", "Information Technology"),
    "ANTM": ("Anthem Inc.", "Health Care"),
    "AON": ("Aon plc", "Financials"),
    "APA": ("Apache Corporation", "Energy"),
    "AIV": ("Apartment Investment & Management", "Real Estate"),
    "AAPL": ("Apple Inc.", "Information Technology"),
    "AMAT": ("Applied Materials Inc", "Information Technology"),
    "APTV": ("Aptiv Plc", "Consumer Discretionary"),
    "ADM": ("Archer-Daniels-Midland Co", "Consumer Staples"),
    "ARNC": ("Arconic Inc", "Industrials"),
    "AJG": ("Arthur J. Gallagher & Co.", "Financials"),
    "AIZ": ("Assurant Inc", "Financials"),
    "T": ("AT&T Inc", "Telecommunication Services"),
    "ADSK": ("Autodesk Inc", "Information Technology"),
    "ADP": ("Automatic Data Processing", "Information Technology"),
    "AZO": ("AutoZone Inc", "Consumer Discretionary"),
    "AVB": ("AvalonBay Communities, Inc.", "Real Estate"),
    "AVY": ("Avery Dennison Corp", "Materials"),
    "BHGE": ("Baker Hughes, a GE Company", "Energy"),
    "BLL": ("Ball Corp", "Materials"),
    "BAC": ("Bank of America Corp", "Financials"),
    "BAX": ("Baxter International Inc.", "Health Care"),
    "BBT": ("BB&T Corporation", "Financials"),
    "BDX": ("Becton Dickinson", "Health Care"),
    "BRK.B": ("Berkshire Hathaway", "Financials"),
    "BBY": ("Best Buy Co. Inc.", "Consumer Discretionary"),
    "BIIB": ("Biogen Inc.", "Health Care"),
    "BLK": ("BlackRock", "Financials"),
    "HRB": ("Block H&R", "Financials"),
    "BA": ("Boeing Company", "Industrials"),
    "BWA": ("BorgWarner", "Consumer Discretionary"),
    "BXP": ("Boston Properties", "Real Estate"),
    "BSX": ("Boston Scientific", "Health Care"),
    "BHF": ("Brighthouse Financial Inc", "Financials"),
    "BMY": ("Bristol-Myers Squibb", "Health Care"),
    "AVGO": ("Broadcom", "Information Technology"),
    "BF.B": ("Brown-Forman Corp.", "Consumer Staples"),
    "CHRW": ("C. H. Robinson Worldwide", "Industrials"),
    "CA": ("CA, Inc.", "Information Technology"),
    "COG": ("Cabot Oil & Gas", "Energy"),
    "CDNS": ("Cadence Design Systems", "Information Technology"),
    "CPB": ("Campbell Soup", "Consumer Staples"),
    "COF": ("Capital One Financial", "Financials"),
    "CAH": ("Cardinal Health Inc.", "Health Care"),
    "KMX": ("Carmax Inc", "Consumer Discretionary"),
    "CCL": ("Carnival Corp.", "Consumer Discretionary"),
    "CAT": ("Caterpillar Inc.", "Industrials"),
    "CBOE": ("CBOE Holdings", "Financials"),
    "CBG": ("CBRE Group", "Real Estate"),
    "CBS": ("CBS Corp.", "Consumer Discretionary"),
    "CELG": ("Celgene Corp.", "Health Care"),
    "CNC": ("Centene Corporation", "Health Care"),
    "CNP": ("CenterPoint Energy", "Utilities"),
    "CTL": ("CenturyLink Inc", "Telecommunication Services"),
    "CERN": ("Cerner", "Health Care"),
    "CF": ("CF Industries Holdings Inc", "Materials"),
    "SCHW": ("Charles Schwab Corporation", "Financials"),
    "CHTR": ("Charter Communications", "Consumer Discretionary"),
    "CHK": ("Chesapeake Energy", "Energy"),
    "CVX": ("Chevron Corp.", "Energy"),
    "CMG": ("Chipotle Mexican Grill", "Consumer Discretionary"),
    "CB": ("Chubb Limited", "Financials"),
    "CHD": ("Church & Dwight", "Consumer Staples"),
    "CI": ("CIGNA Corp.", "Health Care"),
    "XEC": ("Cimarex Energy", "Energy"),
    "CINF": ("Cincinnati Financial", "Financials"),
    "CTAS": ("Cintas Corporation", "Industrials"),
    "CSCO": ("Cisco Systems", "Information Technology"),
    "C": ("Citigroup Inc.", "Financials"),
    "CFG": ("Citizens Financial Group", "Financials"),
    "CTXS": ("Citrix Systems", "Information Technology"),
    "CME": ("CME Group Inc.", "Financials"),
    "CMS": ("CMS Energy", "Utilities"),
    "KO": ("Coca-Cola Company (The)", "Consumer Staples"),
    "CTSH": ("Cognizant Technology Solutions", "Information Technology"),
    "CL": ("Colgate-Palmolive", "Consumer Staples"),
    "CMCSA": ("Comcast Corp.", "Consumer Discretionary"),
    "CMA": ("Comerica Inc.", "Financials"),
    "CAG": ("Conagra Brands", "Consumer Staples"),
    "CXO": ("Concho Resources", "Energy"),
    "COP": ("ConocoPhillips", "Energy"),
    "ED": ("Consolidated Edison", "Utilities"),
    "STZ": ("Constellation Brands", "Consumer Staples"),
    "GLW": ("Corning Inc.", "Information Technology"),
    "COST": ("Costco Wholesale Corp.", "Consumer Staples"),
    "COTY": ("Coty, Inc", "Consumer Staples"),
    "CCI": ("Crown Castle International Corp.", "Real Estate"),
    "CSRA": ("CSRA Inc.", "Information Technology"),
    "CSX": ("CSX Corp.", "Industrials"),
    "CMI": ("Cummins Inc.", "Industrials"),
    "CVS": ("CVS Health", "Consumer Staples"),
    "DHI": ("D. R. Horton", "Consumer Discretionary"),
    "DHR": ("Danaher Corp.", "Health Care"),
    "DRI": ("Darden Restaurants", "Consumer Discretionary"),
    "DVA": ("DaVita Inc.", "Health Care"),
    "DE": ("Deere & Co.", "Industrials"),
    "DAL": ("Delta Air Lines Inc.", "Industrials"),
    "XRAY": ("Dentsply Sirona", "Health Care"),
    "DVN": ("Devon Energy Corp.", "Energy"),
    "DLR": ("Digital Realty Trust Inc", "Real Estate"),
    "DFS": ("Discover Financial Services", "Financials"),
    "DISCA": ("Discovery Communications-A", "Consumer Discretionary"),
    "DISCK": ("Discovery Communications-C", "Consumer Discretionary"),
    "DISH": ("Dish Network", "Consumer Discretionary"),
    "DG": ("Dollar General", "Consumer Discretionary"),
    "DLTR": ("Dollar Tree", "Consumer Discretionary"),
    "D": ("Dominion Energy", "Utilities"),
    "DOV": ("Dover Corp.", "Industrials"),
    "DWDP": ("DowDuPont", "Materials"),
    "DPS": ("Dr Pepper Snapple Group", "Consumer Staples"),
    "DTE": ("DTE Energy Co.", "Utilities"),
    "DUK": ("Duke Energy", "Utilities"),
    "DRE": ("Duke Realty Corp", "Real Estate"),
    "DXC": ("DXC Technology", "Information Technology"),
    "ETFC": ("E*Trade", "Financials"),
    "EMN": ("Eastman Chemical", "Materials"),
    "ETN": ("Eaton Corporation", "Industrials"),
    "EBAY": ("eBay Inc.", "Information Technology"),
    "ECL": ("Ecolab Inc.", "Materials"),
    "EIX": ("Edison Int'l", "Utilities"),
    "EW": ("Edwards Lifesciences", "Health Care"),
    "EA": ("Electronic Arts", "Information Technology"),
    "EMR": ("Emerson Electric Company", "Industrials"),
    "ETR": ("Entergy Corp.", "Utilities"),
    "EVHC": ("Envision Healthcare", "Health Care"),
    "EOG": ("EOG Resources", "Energy"),
    "EQT": ("EQT Corporation", "Energy"),
    "EFX": ("Equifax Inc.", "Industrials"),
    "EQIX": ("Equinix", "Real Estate"),
    "EQR": ("Equity Residential", "Real Estate"),
    "ESS": ("Essex Property Trust, Inc.", "Real Estate"),
    "EL": ("Estee Lauder Cos.", "Consumer Staples"),
    "RE": ("Everest Re Group Ltd.", "Financials"),
    "ES": ("Eversource Energy", "Utilities"),
    "EXC": ("Exelon Corp.", "Utilities"),
    "EXPE": ("Expedia Inc.", "Consumer Discretionary"),
    "EXPD": ("Expeditors International", "Industrials"),
    "ESRX": ("Express Scripts", "Health Care"),
    "EXR": ("Extra Space Storage", "Real Estate"),
    "XOM": ("Exxon Mobil Corp.", "Energy"),
    "FFIV": ("F5 Networks", "Information Technology"),
    "FB": ("Facebook, Inc.", "Information Technology"),
    "FAST": ("Fastenal Co", "Industrials"),
    "FRT": ("Federal Realty Investment Trust", "Real Estate"),
    "FDX": ("FedEx Corporation", "Industrials"),
    "FIS": ("Fidelity National Information Services", "Information Technology"),
    "FITB": ("Fifth Third Bancorp", "Financials"),
    "FE": ("FirstEnergy Corp", "Utilities"),
    "FISV": ("Fiserv Inc", "Information Technology"),
    "FLIR": ("FLIR Systems", "Information Technology"),
    "FLS": ("Flowserve Corporation", "Industrials"),
    "FLR": ("Fluor Corp.", "Industrials"),
    "FMC": ("FMC Corporation", "Materials"),
    "FL": ("Foot Locker Inc", "Consumer Discretionary"),
    "F": ("Ford Motor", "Consumer Discretionary"),
    "FTV": ("Fortive Corp", "Industrials"),
    "FBHS": ("Fortune Brands Home & Security", "Industrials"),
    "BEN": ("Franklin Resources", "Financials"),
    "FCX": ("Freeport-McMoRan Inc.", "Materials"),
    "GPS": ("Gap Inc.", "Consumer Discretionary"),
    "GRMN": ("Garmin Ltd.", "Consumer Discretionary"),
    "IT": ("Gartner Inc", "Information Technology"),
    "GD": ("General Dynamics", "Industrials"),
    "GE": ("General Electric", "Industrials"),
    "GGP": ("General Growth Properties Inc.", "Real Estate"),
    "GIS": ("General Mills", "Consumer Staples"),
    "GM": ("General Motors", "Consumer Discretionary"),
    "GPC": ("Genuine Parts", "Consumer Discretionary"),
    "GILD": ("Gilead Sciences", "Health Care"),
    "GPN": ("Global Payments Inc.", "Information Technology"),
    "GS": ("Goldman Sachs Group", "Financials"),
    "GT": ("Goodyear Tire & Rubber", "Consumer Discretionary"),
    "GWW": ("Grainger (W.W.) Inc.", "Industrials"),
    "HAL": ("Halliburton Co.", "Energy"),
    "HBI": ("Hanesbrands Inc", "Consumer Discretionary"),
    "HOG": ("Harley-Davidson", "Consumer Discretionary"),
    "HRS": ("Harris Corporation", "Information Technology"),
    "HIG": ("Hartford Financial Svc.Gp.", "Financials"),
    "HAS": ("Hasbro Inc.", "Consumer Discretionary"),
    "HCA": ("HCA Holdings", "Health Care"),
    "HCP": ("HCP Inc.", "Real Estate"),
    "HP": ("Helmerich & Payne", "Energy"),
    "HSIC": ("Henry Schein", "Health Care"),
    "HES": ("Hess Corporation", "Energy"),
    "HPE": ("Hewlett Packard Enterprise", "Information Technology"),
    "HLT": ("Hilton Worldwide Holdings Inc", "Consumer Discretionary"),
    "HOLX": ("Hologic", "Health Care"),
    "HD": ("Home Depot", "Consumer Discretionary"),
    "HON": ("Honeywell Int'l Inc.", "Industrials"),
    "HRL": ("Hormel Foods Corp.", "Consumer Staples"),
    "HST": ("Host Hotels & Resorts", "Real Estate"),
    "HPQ": ("HP Inc.", "Information Technology"),
    "HUM": ("Humana Inc.", "Health Care"),
    "HBAN": ("Huntington Bancshares", "Financials"),
    "HII": ("Huntington Ingalls Industries", "Industrials"),
    "IDXX": ("IDEXX Laboratories", "Health Care"),
    "INFO": ("IHS Markit Ltd.", "Industrials"),
    "ITW": ("Illinois Tool Works", "Industrials"),
    "ILMN": ("Illumina Inc", "Health Care"),
    "INCY": ("Incyte", "Health Care"),
    "IR": ("Ingersoll-Rand PLC", "Industrials"),
    "INTC": ("Intel Corp.", "Information Technology"),
    "ICE": ("Intercontinental Exchange", "Financials"),
    "IBM": ("International Business Machines", "Information Technology"),
    "IP": ("International Paper", "Materials"),
    "IPG": ("Interpublic Group", "Consumer Discretionary"),
    "IFF": ("Intl Flavors & Fragrances", "Materials"),
    "INTU": ("Intuit Inc.", "Information Technology"),
    "ISRG": ("Intuitive Surgical Inc.", "Health Care"),
    "IVZ": ("Invesco Ltd.", "Financials"),
    "IQV": ("IQVIA Holdings Inc.", "Health Care"),
    "IRM": ("Iron Mountain Incorporated", "Real Estate"),
    "JBHT": ("J. B. Hunt Transport Services", "Industrials"),
    "JEC": ("Jacobs Engineering Group", "Industrials"),
    "SJM": ("JM Smucker", "Consumer Staples"),
    "JNJ": ("Johnson & Johnson", "Health Care"),
    "JCI": ("Johnson Controls International", "Industrials"),
    "JPM": ("JPMorgan Chase & Co.", "Financials"),
    "JNPR": ("Juniper Networks", "Information Technology"),
    "KSU": ("Kansas City Southern", "Industrials"),
    "K": ("Kellogg Co.", "Consumer Staples"),
    "KEY": ("KeyCorp", "Financials"),
    "KMB": ("Kimberly-Clark", "Consumer Staples"),
    "KIM": ("Kimco Realty", "Real Estate"),
    "KMI": ("Kinder Morgan", "Energy"),
    "KLAC": ("KLA-Tencor Corp.", "Information Technology"),
    "KSS": ("Kohl's Corp.", "Consumer Discretionary"),
    "KHC": ("Kraft Heinz Co", "Consumer Staples"),
    "KR": ("Kroger Co.", "Consumer Staples"),
    "LB": ("L Brands Inc.", "Consumer Discretionary"),
    "LLL": ("L-3 Communications Holdings", "Industrials"),
    "LH": ("Laboratory Corp. of America Holding", "Health Care"),
    "LRCX": ("Lam Research", "Information Technology"),
    "LEG": ("Leggett & Platt", "Consumer Discretionary"),
    "LEN": ("Lennar Corp.", "Consumer Discretionary"),
    "LUK": ("Leucadia National Corp.", "Financials"),
    "LLY": ("Lilly (Eli) & Co.", "Health Care"),
    "LNC": ("Lincoln National", "Financials"),
    "LKQ": ("LKQ Corporation", "Consumer Discretionary"),
    "LMT": ("Lockheed Martin Corp.", "Industrials"),
    "L": ("Loews Corp.", "Financials"),
    "LOW": ("Lowe's Cos.", "Consumer Discretionary"),
    "LYB": ("LyondellBasell", "Materials"),
    "MTB": ("M&T Bank Corp.", "Financials"),
    "MAC": ("Macerich", "Real Estate"),
    "M": ("Macy's Inc.", "Consumer Discretionary"),
    "MRO": ("Marathon Oil Corp.", "Energy"),
    "MPC": ("Marathon Petroleum", "Energy"),
    "MAR": ("Marriott Int'l.", "Consumer Discretionary"),
    "MMC": ("Marsh & McLennan", "Financials"),
    "MLM": ("Martin Marietta Materials", "Materials"),
    "MAS": ("Masco Corp.", "Industrials"),
    "MA": ("Mastercard Inc.", "Information Technology"),
    "MAT": ("Mattel Inc.", "Consumer Discretionary"),
    "MKC": ("McCormick & Co.", "Consumer Staples"),
    "MCD": ("McDonald's Corp.", "Consumer Discretionary"),
    "MCK": ("McKesson Corp.", "Health Care"),
    "MDT": ("Medtronic plc", "Health Care"),
    "MRK": ("Merck & Co.", "Health Care"),
    "MET": ("MetLife Inc.", "Financials"),
    "MTD": ("Mettler Toledo", "Health Care"),
    "MGM": ("MGM Resorts International", "Consumer Discretionary"),
    "KORS": ("Michael Kors Holdings", "Consumer Discretionary"),
    "MCHP": ("Microchip Technology", "Information Technology"),
    "MU": ("Micron Technology", "Information Technology"),
    "MSFT": ("Microsoft Corp.", "Information Technology"),
    "MAA": ("Mid-America Apartments", "Real Estate"),
    "MHK": ("Mohawk Industries", "Consumer Discretionary"),
    "TAP": ("Molson Coors Brewing Company", "Consumer Staples"),
    "MDLZ": ("Mondelez International", "Consumer Staples"),
    "MON": ("Monsanto Co.", "Materials"),
    "MNST": ("Monster Beverage", "Consumer Staples"),
    "MCO": ("Moody's Corp", "Financials"),
    "MS": ("Morgan Stanley", "Financials"),
    "MSI": ("Motorola Solutions Inc.", "Information Technology"),
    "MYL": ("Mylan N.V.", "Health Care"),
    "NDAQ": ("Nasdaq, Inc.", "Financials"),
    "NOV": ("National Oilwell Varco Inc.", "Energy"),
    "NAVI": ("Navient", "Financials"),
    "NTAP": ("NetApp", "Information Technology"),
    "NFLX": ("Netflix Inc.", "Information Technology"),
    "NWL": ("Newell Brands", "Consumer Discretionary"),
    "NFX": ("Newfield Exploration Co", "Energy"),
    "NEM": ("Newmont Mining Corporation", "Materials"),
    "NWSA": ("News Corp. Class A", "Consumer Discretionary"),
    "NWS": ("News Corp. Class B", "Consumer Discretionary"),
    "NEE": ("NextEra Energy", "Utilities"),
    "NLSN": ("Nielsen Holdings", "Industrials"),
    "NKE": ("Nike", "Consumer Discretionary"),
    "NI": ("NiSource Inc.", "Utilities"),
    "NBL": ("Noble Energy Inc", "Energy"),
    "JWN": ("Nordstrom", "Consumer Discretionary"),
    "NSC": ("Norfolk Southern Corp.", "Industrials"),
    "NTRS": ("Northern Trust Corp.", "Financials"),
    "NOC": ("Northrop Grumman Corp.", "Industrials"),
    "NCLH": ("Norwegian Cruise Line", "Consumer Discretionary"),
    "NRG": ("NRG Energy", "Utilities"),
    "NUE": ("Nucor Corp.", "Materials"),
    "NVDA": ("Nvidia Corporation", "Information Technology"),
    "ORLY": ("O'Reilly Automotive", "Consumer Discretionary"),
    "OXY": ("Occidental Petroleum", "Energy"),
    "OMC": ("Omnicom Group", "Consumer Discretionary"),
    "OKE": ("ONEOK", "Energy"),
    "ORCL": ("Oracle Corp.", "Information Technology"),
    "PCAR": ("PACCAR Inc.", "Industrials"),
    "PKG": ("Packaging Corporation of America", "Materials"),
    "PH": ("Parker-Hannifin", "Industrials"),
    "PDCO": ("Patterson Companies", "Health Care"),
    "PAYX": ("Paychex Inc.", "Information Technology"),
    "PYPL": ("PayPal", "Information Technology"),
    "PNR": ("Pentair Ltd.", "Industrials"),
    "PBCT": ("People's United Financial", "Financials"),
    "PEP": ("PepsiCo Inc.", "Consumer Staples"),
    "PKI": ("PerkinElmer", "Health Care"),
    "PRGO": ("Perrigo", "Health Care"),
    "PFE": ("Pfizer Inc.", "Health Care"),
    "PCG": ("PG&E Corp.", "Utilities"),
    "PM": ("Philip Morris International", "Consumer Staples"),
    "PSX": ("Phillips 66", "Energy"),
    "PNW": ("Pinnacle West Capital", "Utilities"),
    "PXD": ("Pioneer Natural Resources", "Energy"),
    "PNC": ("PNC Financial Services", "Financials"),
    "RL": ("Polo Ralph Lauren Corp.", "Consumer Discretionary"),
    "PPG": ("PPG Industries", "Materials"),
    "PPL": ("PPL Corp.", "Utilities"),
    "PX": ("Praxair Inc.", "Materials"),
    "PCLN": ("Priceline.com Inc", "Consumer Discretionary"),
    "PFG": ("Principal Financial Group", "Financials"),
    "PG": ("Procter & Gamble", "Consumer Staples"),
    "PGR": ("Progressive Corp.", "Financials"),
    "PLD": ("Prologis", "Real Estate"),
    "PRU": ("Prudential Financial", "Financials"),
    "PEG": ("Public Serv. Enterprise Inc.", "Utilities"),
    "PSA": ("Public Storage", "Real Estate"),
    "PHM": ("Pulte Homes Inc.", "Consumer Discretionary"),
    "PVH": ("PVH Corp.", "Consumer Discretionary"),
    "QRVO": ("Qorvo", "Information Technology"),
    "QCOM": ("QUALCOMM Inc.", "Information Technology"),
    "PWR": ("Quanta Services Inc.", "Industrials"),
    "DGX": ("Quest Diagnostics", "Health Care"),
    "RRC": ("Range Resources Corp.", "Energy"),
    "RJF": ("Raymond James Financial Inc.", "Financials"),
    "RTN": ("Raytheon Co.", "Industrials"),
    "O": ("Realty Income Corporation", "Real Estate"),
    "RHT": ("Red Hat Inc.", "Information Technology"),
    "REG": ("Regency Centers Corporation", "Real Estate"),
    "REGN": ("Regeneron", "Health Care"),
    "RF": ("Regions Financial Corp.", "Financials"),
    "RSG": ("Republic Services Inc", "Industrials"),
    "RMD": ("ResMed", "Health Care"),
    "RHI": ("Robert Half International", "Industrials"),
    "ROK": ("Rockwell Automation Inc.", "Industrials"),
    "COL": ("Rockwell Collins", "Industrials"),
    "ROP": ("Roper Technologies", "Industrials"),
    "ROST": ("Ross Stores", "Consumer Discretionary"),
    "RCL": ("Royal Caribbean Cruises Ltd", "Consumer Discretionary"),
    "SPGI": ("S&P Global, Inc.", "Financials"),
    "CRM": ("Salesforce.com", "Information Technology"),
    "SBAC": ("SBA Communications", "Real Estate"),
    "SCG": ("SCANA Corp", "Utilities"),
    "SLB": ("Schlumberger Ltd.", "Energy"),
    "SNI": ("Scripps Networks Interactive Inc.", "Consumer Discretionary"),
    "STX": ("Seagate Technology", "Information Technology"),
    "SEE": ("Sealed Air", "Materials"),
    "SRE": ("Sempra Energy", "Utilities"),
    "SHW": ("Sherwin-Williams", "Materials"),
    "SIG": ("Signet Jewelers", "Consumer Discretionary"),
    "SPG": ("Simon Property Group Inc", "Real Estate"),
    "SWKS": ("Skyworks Solutions", "Information Technology"),
    "SLG": ("SL Green Realty", "Real Estate"),
    "SNA": ("Snap-On Inc.", "Consumer Discretionary"),
    "SO": ("Southern Co.", "Utilities"),
    "LUV": ("Southwest Airlines", "Industrials"),
    "SWK": ("Stanley Black & Decker", "Consumer Discretionary"),
    "SBUX": ("Starbucks Corp.", "Consumer Discretionary"),
    "STT": ("State Street Corp.", "Financials"),
    "SRCL": ("Stericycle Inc", "Industrials"),
    "SYK": ("Stryker Corp.", "Health Care"),
    "STI": ("SunTrust Banks", "Financials"),
    "SYMC": ("Symantec Corp.", "Information Technology"),
    "SYF": ("Synchrony Financial", "Financials"),
    "SNPS": ("Synopsys Inc.", "Information Technology"),
    "SYY": ("Sysco Corp.", "Consumer Staples"),
    "TROW": ("T. Rowe Price Group", "Financials"),
    "TPR": ("Tapestry, Inc.", "Consumer Discretionary"),
    "TGT": ("Target Corp.", "Consumer Discretionary"),
    "TEL": ("TE Connectivity Ltd.", "Information Technology"),
    "FTI": ("TechnipFMC", "Energy"),
    "TXN": ("Texas Instruments", "Information Technology"),
    "TXT": ("Textron Inc.", "Industrials"),
    "BK": ("The Bank of New York Mellon Corp.", "Financials"),
    "CLX": ("The Clorox Company", "Consumer Staples"),
    "COO": ("The Cooper Companies", "Health Care"),
    "HSY": ("The Hershey Company", "Consumer Staples"),
    "MOS": ("The Mosaic Company", "Materials"),
    "TRV": ("The Travelers Companies Inc.", "Financials"),
    "DIS": ("The Walt Disney Company", "Consumer Discretionary"),
    "TMO": ("Thermo Fisher Scientific", "Health Care"),
    "TIF": ("Tiffany & Co.", "Consumer Discretionary"),
    "TWX": ("Time Warner Inc.", "Consumer Discretionary"),
    "TJX": ("TJX Companies Inc.", "Consumer Discretionary"),
    "TMK": ("Torchmark Corp.", "Financials"),
    "TSS": ("Total System Services", "Information Technology"),
    "TSCO": ("Tractor Supply Company", "Consumer Discretionary"),
    "TDG": ("TransDigm Group", "Industrials"),
    "TRIP": ("TripAdvisor", "Consumer Discretionary"),
    "FOXA": ("Twenty-First Century Fox Class A", "Consumer Discretionary"),
    "FOX": ("Twenty-First Century Fox Class B", "Consumer Discretionary"),
    "TSN": ("Tyson Foods", "Consumer Staples"),
    "USB": ("U.S. Bancorp", "Financials"),
    "UDR": ("UDR Inc", "Real Estate"),
    "ULTA": ("Ulta Salon Cosmetics & Fragrance Inc", "Consumer Discretionary"),
    "UAA": ("Under Armour Class A", "Consumer Discretionary"),
    "UA": ("Under Armour Class C", "Consumer Discretionary"),
    "UNP": ("Union Pacific", "Industrials"),
    "UAL": ("United Continental Holdings", "Industrials"),
    "UNH": ("United Health Group Inc.", "Health Care"),
    "UPS": ("United Parcel Service", "Industrials"),
    "URI": ("United Rentals, Inc.", "Industrials"),
    "UTX": ("United Technologies", "Industrials"),
    "UHS": ("Universal Health Services, Inc.", "Health Care"),
    "UNM": ("Unum Group", "Financials"),
    "VFC": ("V.F. Corp.", "Consumer Discretionary"),
    "VLO": ("Valero Energy", "Energy"),
    "VAR": ("Varian Medical Systems", "Health Care"),
    "VTR": ("Ventas Inc", "Real Estate"),
    "VRSN": ("Verisign Inc.", "Information Technology"),
    "VRSK": ("Verisk Analytics", "Industrials"),
    "VZ": ("Verizon Communications", "Telecommunication Services"),
    "VRTX": ("Vertex Pharmaceuticals Inc", "Health Care"),
    "VIAB": ("Viacom Inc.", "Consumer Discretionary"),
    "V": ("Visa Inc.", "Information Technology"),
    "VNO": ("Vornado Realty Trust", "Real Estate"),
    "VMC": ("Vulcan Materials", "Materials"),
    "WMT": ("Wal-Mart Stores", "Consumer Staples"),
    "WBA": ("Walgreens Boots Alliance", "Consumer Staples"),
    "WM": ("Waste Management Inc.", "Industrials"),
    "WAT": ("Waters Corporation", "Health Care"),
    "WEC": ("Wec Energy Group Inc", "Utilities"),
    "WFC": ("Wells Fargo", "Financials"),
    "HCN": ("Welltower Inc.", "Real Estate"),
    "WDC": ("Western Digital", "Information Technology"),
    "WU": ("Western Union Co", "Information Technology"),
    "WRK": ("WestRock Company", "Materials"),
    "WY": ("Weyerhaeuser Corp.", "Real Estate"),
    "WHR": ("Whirlpool Corp.", "Consumer Discretionary"),
    "WMB": ("Williams Cos.", "Energy"),
    "WLTW": ("Willis Towers Watson", "Financials"),
    "WYN": ("Wyndham Worldwide", "Consumer Discretionary"),
    "WYNN": ("Wynn Resorts Ltd", "Consumer Discretionary"),
    "XEL": ("Xcel Energy Inc", "Utilities"),
    "XRX": ("Xerox Corp.", "Information Technology"),
    "XLNX": ("Xilinx Inc", "Information Technology"),
    "XL": ("XL Capital", "Financials"),
    "XYL": ("Xylem Inc.", "Industrials"),
    "YUM": ("Yum! Brands Inc", "Consumer Discretionary"),
    "ZBH": ("Zimmer Biomet Holdings", "Health Care"),
    "ZION": ("Zions Bancorp", "Financials"),
    "ZTS": ("Zoetis", "Health Care"),
}

# GICS sector -> representative SPDR sector ETF, used for relative-strength ranking
SECTOR_ETFS = {
    "Information Technology": "XLK",
    "Technology": "XLK",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Cyclical": "XLY",
    "Consumer Staples": "XLP",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Telecommunication Services": "XLC",
    "Communication Services": "XLC",
}

# Intermarket regime proxies (Murphy's four-market model)
INTERMARKET_TICKERS = {
    "Stocks": "SPY",
    "Bonds": "TLT",     # long-term treasuries -> proxy for interest-rate direction (inverse of yields)
    "Commodities": "DBC",
    "Dollar": "UUP",
}

BENCHMARK = "SPY"


# ---------------------------------------------------------------------------
# DATA FETCH
# ---------------------------------------------------------------------------

def fetch_history(ticker, period_days=LOOKBACK_DAYS):
    end = dt.date.today()
    start = end - dt.timedelta(days=int(period_days * 1.6))  # buffer for weekends/holidays
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 210:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    return df


def get_sp500_tickers(n=None):
    """Return S&P 500 ticker symbols from the embedded list (in the same
    order they appear in SP500_DATA). Pass n to get only the first n
    tickers (e.g. for a quick partial scan); omit n for the full list."""
    all_tickers = list(SP500_DATA.keys())
    if n is None:
        return all_tickers
    n = max(1, min(int(n), len(all_tickers)))
    return all_tickers[:n]


def get_sector(ticker):
    """Look up sector for a ticker. Prefers the embedded S&P 500 map (fast,
    free, no rate limits); falls back to a live yfinance lookup if the
    ticker isn't in that map (e.g. a non-S&P-500 symbol)."""
    if ticker in SP500_DATA:
        return SP500_DATA[ticker][1]

    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------

def sma(series, window):
    return series.rolling(window).mean()


def bollinger_bands(close, window=20, num_std=2):
    mid = sma(close, window)
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid
    return upper, mid, lower, width


def rsi(close, window=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def is_bullish_engulfing(o, h, l, c):
    # last two candles: prior red, current green, current body engulfs prior body
    prev_o, prev_c = o.iloc[-2], c.iloc[-2]
    cur_o, cur_c = o.iloc[-1], c.iloc[-1]
    return (prev_c < prev_o) and (cur_c > cur_o) and (cur_c >= prev_o) and (cur_o <= prev_c)


def is_hammer(o, h, l, c):
    cur_o, cur_c, cur_h, cur_l = o.iloc[-1], c.iloc[-1], h.iloc[-1], l.iloc[-1]
    body = abs(cur_c - cur_o)
    full_range = cur_h - cur_l
    if full_range <= 0:
        return False
    lower_shadow = min(cur_o, cur_c) - cur_l
    upper_shadow = cur_h - max(cur_o, cur_c)
    # small body near top of range, long lower shadow, little/no upper shadow
    return (lower_shadow >= 2 * body) and (upper_shadow <= 0.3 * body + 0.02 * full_range) and (body <= 0.35 * full_range)


def is_piercing_line(o, h, l, c):
    prev_o, prev_c = o.iloc[-2], c.iloc[-2]
    cur_o, cur_c = o.iloc[-1], c.iloc[-1]
    prev_mid = (prev_o + prev_c) / 2
    return (prev_c < prev_o) and (cur_c > cur_o) and (cur_o < prev_c) and (cur_c > prev_mid) and (cur_c < prev_o)


def is_morning_star(o, h, l, c):
    if len(c) < 3:
        return False
    o1, c1 = o.iloc[-3], c.iloc[-3]
    o2, c2 = o.iloc[-2], c.iloc[-2]
    o3, c3 = o.iloc[-1], c.iloc[-1]
    day1_bearish = c1 < o1
    day2_small = abs(c2 - o2) < abs(c1 - o1) * 0.5
    day3_bullish_recovery = (c3 > o3) and (c3 > (o1 + c1) / 2)
    return day1_bearish and day2_small and day3_bullish_recovery


def detect_bullish_candle(df):
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    hits = []
    try:
        if is_hammer(o, h, l, c):
            hits.append("Hammer (bullish reversal at a downtrend low)")
        if is_bullish_engulfing(o, h, l, c):
            hits.append("Bullish Engulfing pattern")
        if is_piercing_line(o, h, l, c):
            hits.append("Piercing Line pattern")
        if is_morning_star(o, h, l, c):
            hits.append("Morning Star pattern")
    except Exception:
        pass
    return hits


# ---------------------------------------------------------------------------
# INTERMARKET REGIME (Murphy's Intermarket Analysis)
# ---------------------------------------------------------------------------

def trend_direction(close, window=60):
    """Simple slope-based trend: is the N-day SMA rising or falling?"""
    ma = sma(close, window)
    if len(ma.dropna()) < 10:
        return "flat"
    recent = ma.dropna().iloc[-1]
    prior = ma.dropna().iloc[-10]
    if recent > prior * 1.01:
        return "up"
    elif recent < prior * 0.99:
        return "down"
    return "flat"


def get_intermarket_regime():
    """Classify the macro regime using bonds/stocks/commodities/dollar trends,
    per Murphy's four-market model + Pring's six-stage business cycle map."""
    trends = {}
    for name, ticker in INTERMARKET_TICKERS.items():
        df = fetch_history(ticker, period_days=250)
        if df is None:
            trends[name] = "unknown"
        else:
            trends[name] = trend_direction(df["Close"])

    bonds, stocks, commodities, dollar = (trends.get(k, "unknown") for k in
                                           ["Bonds", "Stocks", "Commodities", "Dollar"])

    # Bonds (TLT) rising == interest rates falling; bonds falling == rates rising
    if commodities == "up" and bonds == "down":
        regime = ("Early/mid inflationary regime: commodities rising, bonds falling (rates rising) — "
                   "favor commodities/energy, caution on rate-sensitive stocks")
        favored = ["Energy", "Materials", "Basic Materials"]
    elif commodities == "down" and bonds == "up":
        regime = ("Disinflationary/slowdown regime: commodities falling, bonds rising (rates falling) — "
                   "favor bonds and defensive stocks")
        favored = ["Utilities", "Consumer Staples", "Consumer Defensive", "Health Care", "Healthcare"]
    elif stocks == "up" and bonds == "up":
        regime = "Healthy early expansion: both stocks and bonds rising — constructive for growth stocks"
        favored = ["Information Technology", "Technology", "Financials", "Financial Services", "Consumer Discretionary"]
    elif stocks == "down" and commodities == "down" and bonds == "down":
        regime = "Stage 6 (everything falling) — cash is king, increased caution across all positions"
        favored = []
    else:
        regime = f"Mixed / no clear signal (stocks={stocks}, bonds={bonds}, commodities={commodities}, dollar={dollar})"
        favored = []

    return {"trends": trends, "description": regime, "favored_sectors": favored}


# ---------------------------------------------------------------------------
# SECTOR RELATIVE STRENGTH
# ---------------------------------------------------------------------------

def get_sector_leaderboard():
    """Rank each sector ETF's relative performance vs SPY over 1w/1m/3m/12m."""
    spy = fetch_history(BENCHMARK, period_days=280)
    if spy is None:
        return {}
    spy_close = spy["Close"]

    results = {}
    seen_etfs = set()
    etf_to_sector = {}
    for sector, etf in SECTOR_ETFS.items():
        etf_to_sector.setdefault(etf, sector)
        if etf in seen_etfs:
            continue
        seen_etfs.add(etf)
        df = fetch_history(etf, period_days=280)
        if df is None:
            continue
        close = df["Close"]

        def rel_perf(n):
            if len(close) <= n or len(spy_close) <= n:
                return np.nan
            stock_ret = close.iloc[-1] / close.iloc[-n] - 1
            spy_ret = spy_close.iloc[-1] / spy_close.iloc[-n] - 1
            return (stock_ret - spy_ret) * 100  # percentage points vs SPY

        results[etf] = {
            "1w": rel_perf(5),
            "1m": rel_perf(21),
            "3m": rel_perf(63),
            "12m": rel_perf(252),
        }

    # rank sectors by average of 1m + 3m relative strength (medium-term leadership)
    ranked = sorted(results.items(), key=lambda kv: np.nanmean([kv[1]["1m"], kv[1]["3m"]]), reverse=True)

    leaderboard = {}
    for rank, (etf, perf) in enumerate(ranked, start=1):
        leaderboard[etf] = {"rank": rank, "sector": etf_to_sector[etf], **perf}
    return leaderboard


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def score_stock(ticker, df, sector, sector_leaderboard, regime):
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    last_close = close.iloc[-1]
    reasons = []
    score = 0

    # --- 1. 52-week trend template (25 pts) ---------------------------------
    ma50 = sma(close, 50)
    ma200 = sma(close, 200)
    week52_high = close.rolling(252).max().iloc[-1]
    price_52w_ago = close.iloc[-252] if len(close) >= 252 else close.iloc[0]

    trend_pts = 0
    if last_close > price_52w_ago:
        trend_pts += 8
        reasons.append("Price is above where it was 52 weeks ago (positive yearly trend)")
    if last_close > ma50.iloc[-1] and last_close > ma200.iloc[-1]:
        trend_pts += 10
        reasons.append("Price is above both the 50-day and 200-day moving averages (confirmed uptrend)")
    if ma50.iloc[-1] > ma200.iloc[-1]:
        trend_pts += 4
        reasons.append("50-day MA is above the 200-day MA (golden-cross structure)")
    if last_close >= week52_high * 0.75:
        trend_pts += 3
        reasons.append("Price is within 25% of its 52-week high")
    score += min(trend_pts, 25)

    # --- 2. Near-MA50 pullback opportunity on volume (10 pts) ---------------
    near_ma50_pts = 0
    dist_from_ma50 = abs(last_close - ma50.iloc[-1]) / ma50.iloc[-1]
    avg_vol20 = vol.rolling(20).mean().iloc[-1]
    vol_today = vol.iloc[-1]
    if dist_from_ma50 <= NEAR_MA50_PCT and last_close >= ma50.iloc[-1] * 0.98:
        near_ma50_pts += 5
        reasons.append("Price is hugging the 50-day MA — a possible support zone")
        if vol_today >= avg_vol20 * 1.3:
            near_ma50_pts += 5
            reasons.append("...and that 50-MA test is accompanied by elevated volume (support defense)")
    score += near_ma50_pts

    # --- 3. Bollinger setup (10 pts) ----------------------------------------
    upper, mid, lower, width = bollinger_bands(close)
    bb_pts = 0
    width_percentile = (width.iloc[-1] <= width.rolling(120).quantile(0.2).iloc[-1])
    if width_percentile:
        bb_pts += 6
        reasons.append("Bollinger Bands are unusually narrow (squeeze) — a breakout may be brewing")
    if last_close <= lower.iloc[-1] * 1.02 and last_close > ma200.iloc[-1]:
        bb_pts += 4
        reasons.append("Price is touching the lower Bollinger Band within an overall uptrend — possible buy zone")
    score += min(bb_pts, 10)

    # --- 4. Bullish candlestick (10 pts) ------------------------------------
    candle_hits = detect_bullish_candle(df)
    if candle_hits:
        score += 10
        reasons.append("Bullish candlestick detected: " + ", ".join(candle_hits))

    # --- 5. Unusual volume day (10 pts) -------------------------------------
    vol_pts = 0
    if avg_vol20 > 0 and vol_today >= avg_vol20 * VOLUME_SPIKE_MULT:
        vol_pts += 7
        reasons.append(f"Unusual volume today ({vol_today / avg_vol20:.1f}x the 20-day average) — possible large money flow")
        day_range = high.iloc[-1] - low.iloc[-1]
        if day_range > 0 and (last_close - low.iloc[-1]) / day_range >= 0.7:
            vol_pts += 3
            reasons.append("...closed near the day's high on that unusual volume — sign of support defense / institutional buying")
    score += vol_pts

    # --- 6. RSI (10 pts) -----------------------------------------------------
    rsi_val = rsi(close).iloc[-1]
    rsi_pts = 0
    if 50 <= rsi_val <= 70:
        rsi_pts = 10
        reasons.append(f"RSI={rsi_val:.0f} — healthy bullish momentum, not overbought")
    elif 40 <= rsi_val < 50:
        rsi_pts = 5
        reasons.append(f"RSI={rsi_val:.0f} — neutral, no strong momentum confirmation yet")
    elif rsi_val > 70:
        rsi_pts = 3
        reasons.append(f"RSI={rsi_val:.0f} — overbought, watch for a short-term pullback")
    else:
        reasons.append(f"RSI={rsi_val:.0f} — weak")
    score += rsi_pts

    # --- 7. MACD (10 pts) -----------------------------------------------------
    macd_line, signal_line, hist = macd(close)
    macd_pts = 0
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_pts += 6
        reasons.append("MACD is above its signal line — positive momentum")
        if hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3]:
            macd_pts += 4
            reasons.append("MACD histogram is expanding — momentum is accelerating")
    score += macd_pts

    # --- 8. Sector leadership (10 pts) ----------------------------------------
    sector_pts = 0
    etf = SECTOR_ETFS.get(sector)
    sector_rank = None
    if etf and etf in sector_leaderboard:
        info = sector_leaderboard[etf]
        sector_rank = info["rank"]
        n_sectors = len(sector_leaderboard)
        if sector_rank <= max(1, n_sectors // 3):
            sector_pts += 10
            reasons.append(f"Sector ({sector}) is a market leader right now (rank {sector_rank}/{n_sectors})")
        elif sector_rank <= n_sectors * 2 // 3:
            sector_pts += 5
            reasons.append(f"Sector ({sector}) is performing in-line with the market (rank {sector_rank}/{n_sectors})")
        else:
            reasons.append(f"Sector ({sector}) is lagging the market (rank {sector_rank}/{n_sectors})")
    score += sector_pts

    # --- 9. Intermarket regime alignment (5 pts) -------------------------------
    macro_pts = 0
    if sector in regime.get("favored_sectors", []):
        macro_pts = 5
        reasons.append("Sector is favored under the current intermarket regime")
    score += macro_pts

    # --- Stop loss & price target -----------------------------------------
    recent_low = low.rolling(BREAKOUT_LOOKBACK).min().iloc[-1]
    stop_loss = min(recent_low, ma50.iloc[-1]) * 0.98  # small buffer below nearest support
    risk = last_close - stop_loss
    target = last_close + max(risk * 2.5, (week52_high - last_close) * 0.5)
    if week52_high > last_close:
        target = max(target, week52_high)
    reward = target - last_close
    rr_ratio = reward / risk if risk > 0 else np.nan

    return {
        "Ticker": ticker,
        "Sector": sector,
        "Score": round(score, 1),
        "Price": round(last_close, 2),
        "StopLoss": round(stop_loss, 2),
        "Target": round(target, 2),
        "R:R": round(rr_ratio, 2) if not np.isnan(rr_ratio) else None,
        "RSI": round(rsi_val, 1),
        "SectorRank": sector_rank,
        "Reasons": reasons,
    }


# ---------------------------------------------------------------------------
# MAIN SCAN (CLI)
# ---------------------------------------------------------------------------

def run_scan(tickers, top_n=None):
    print("Fetching intermarket regime (bonds/stocks/commodities/dollar)...")
    regime = get_intermarket_regime()
    print("Regime:", regime["description"])

    print("Building sector relative-strength leaderboard...")
    sector_leaderboard = get_sector_leaderboard()

    results = []
    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i}/{len(tickers)}] scanning {ticker}...", end="\r")
        try:
            df = fetch_history(ticker)
            if df is None:
                continue
            sector = get_sector(ticker)
            res = score_stock(ticker, df, sector, sector_leaderboard, regime)
            results.append(res)
        except Exception as e:
            print(f"\n  skipped {ticker}: {e}")
            continue

    print()  # newline after progress
    if not results:
        print("No results.")
        return

    df_out = pd.DataFrame(results).sort_values("Score", ascending=False)
    if top_n:
        df_out = df_out.head(top_n)

    display_cols = ["Ticker", "Score", "Sector", "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]
    print(df_out[display_cols].to_string(index=False))

    export_df = df_out.copy()
    export_df["Reasons"] = export_df["Reasons"].apply(lambda r: " | ".join(r))
    export_df.to_csv("screener_results.csv", index=False, encoding="utf-8-sig")
    print("\nSaved full results (with explanations) to screener_results.csv")

    print("\n=== Top 5 — full explanation ===")
    for _, row in df_out.head(5).iterrows():
        print(f"\n{row['Ticker']}  |  Score: {row['Score']}  |  Sector: {row['Sector']}")
        print(f"  Price: {row['Price']}  Stop-loss: {row['StopLoss']}  Target: {row['Target']}  R:R: {row['R:R']}")
        for r in row["Reasons"]:
            print(f"   - {r}")


def parse_args():
    p = argparse.ArgumentParser(description="Murphy-principles stock screener")
    p.add_argument("tickers", nargs="*", help="Ticker symbols to scan (default: bundled S&P 500 list)")
    p.add_argument("--file", help="Path to a text file with one ticker per line")
    p.add_argument("--top", type=int, default=None, help="Only show/save top N results")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.file:
        with open(args.file) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_sp500_tickers()

    run_scan(tickers, top_n=args.top)
