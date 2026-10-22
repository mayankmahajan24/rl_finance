"""Which SEC line item is each series' KPI.

A series lists variants in priority order; for each filing and period the first variant whose
components are all present is used. A variant sums its components (each a list of acceptable
(concept, dims) selectors for one company). Variants cover tagging changes, e.g. PassengerRevenue
before ASC 606 vs the Passenger member of contract revenue after.
"""

P606 = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SRT_PAX = "srt:ProductOrServiceAxis=us-gaap:PassengerMember"


def one(cik, *selectors):
    return [{"cik": cik, "selectors": list(selectors)}]


SERIES = [
    {"id": "UAL", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["UAL"], "variants": [
        one(100517, ("us-gaap:PassengerRevenue", "")),
        one(100517, (P606, "us-gaap:ProductOrServiceAxis=ual:PassengerMember"))]},
    {"id": "DAL", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["DAL"], "variants": [
        one(27904, ("us-gaap:PassengerRevenue", "")),
        one(27904, (P606, SRT_PAX))]},
    {"id": "AAL", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["AAL"], "variants": [
        one(6201, ("us-gaap:PassengerRevenue", "")),
        one(6201, (P606, SRT_PAX)),
        [{"cik": 6201, "selectors": [("us-gaap:PassengerRevenueMainline", "")]},
         {"cik": 6201, "selectors": [("us-gaap:PassengerRevenueRegional", "")]}]]},
    {"id": "LUV", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["LUV"], "variants": [
        one(92380, ("us-gaap:PassengerRevenue", "")),
        one(92380, (P606, SRT_PAX))]},
    {"id": "ALK", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["ALK"], "variants": [
        one(766421, ("us-gaap:PassengerRevenue", "")),
        one(766421, ("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", SRT_PAX),
            (P606, "us-gaap:ContractWithCustomerSalesChannelAxis=alk:PassengerRevenueMember"))]},
    {"id": "JBLU", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["JBLU"], "variants": [
        one(1158463, ("us-gaap:PassengerRevenue", "")),
        one(1158463, (P606, SRT_PAX))]},
    {"id": "SAVE", "kpi": "Passenger revenue (fare + non-ticket)", "calendar": "calendar", "sensors": ["SAVE"], "variants": [
        # Before ASC 606 Spirit reported fares (PassengerRevenue) and non-ticket revenue separately
        [{"cik": 1498710, "selectors": [("us-gaap:PassengerRevenue", "")]},
         {"cik": 1498710, "selectors": [("us-gaap:OtherSalesRevenueNet", "")]}],
        one(1498710, (P606, "srt:ProductOrServiceAxis=save:ProductsAndServicesPassengerMember"),
            (P606, "us-gaap:ProductOrServiceAxis=save:ProductsAndServicesPassengerMember"))]},
    {"id": "HA", "kpi": "Passenger revenue", "calendar": "calendar", "sensors": ["HA"], "variants": [
        one(1172222, ("us-gaap:PassengerRevenue", "")),
        one(1172222, (P606, SRT_PAX), (P606, "us-gaap:ProductOrServiceAxis=us-gaap:PassengerMember"))]},
    {"id": "ALGT", "kpi": "Scheduled service revenue", "calendar": "calendar", "sensors": ["ALGT"], "variants": [
        one(1362468, ("us-gaap:PassengerRevenue", "us-gaap:ProductOrServiceAxis=algt:ScheduledServiceRevenueMember"),
            (P606, "us-gaap:ProductOrServiceAxis=algt:ScheduledServiceRevenueMember")),
        # Until 2018 PassengerRevenue was scheduled service alone; under ASC 606 it adds air-related ancillaries
        one(1362468, ("us-gaap:PassengerRevenue", "", "2018-03-31"))]},
    {"id": "KSS", "kpi": "Net sales", "calendar": "fiscal_jan", "sensors": ["KSS"], "variants": [
        one(885639, ("us-gaap:SalesRevenueNet", ""),
            ("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "srt:ProductOrServiceAxis=us-gaap:ProductMember"))]},
    {"id": "M", "kpi": "Net sales", "calendar": "fiscal_jan", "sensors": ["M_M", "M_BL"], "variants": [
        one(794367, ("us-gaap:SalesRevenueNet", ""), (P606, ""))]},
    {"id": "JWN_FP", "kpi": "Full-price net sales", "calendar": "fiscal_jan", "sensors": ["JWN_JWN"], "variants": [
        one(72333, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:FullPriceMember"),
            ("*:NetSalesRevenue", "us-gaap:StatementBusinessSegmentsAxis=jwn:FullPriceMember")),
        # before the 2018 full-price/off-price split: Nordstrom stores + nordstrom.com
        one(72333, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:NordstromMember"))]},
    {"id": "JWN_OP", "kpi": "Off-price net sales", "calendar": "fiscal_jan", "sensors": ["JWN_RACK"], "variants": [
        one(72333, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:OffPriceMember"),
            ("*:NetSalesRevenue", "us-gaap:StatementBusinessSegmentsAxis=jwn:OffPriceMember")),
        # before the split: Rack stores + Nordstromrack.com/HauteLook
        [{"cik": 72333, "selectors": [("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:NordstromRackMember")]},
         {"cik": 72333, "selectors": [("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:Nordstromrack.comandHauteLookMember")]}]]},
    {"id": "ROST", "kpi": "Total sales", "calendar": "fiscal_jan", "sensors": ["ROST_ROST", "ROST_DD"], "variants": [
        one(745732, ("us-gaap:SalesRevenueNet", ""), (P606, ""))]},
    {"id": "TJX_MARMAXX", "kpi": "Marmaxx segment net sales", "calendar": "fiscal_jan", "sensors": ["TJX_TJMAXX"], "variants": [
        one(109198, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=tjx:MarmaxxMember"),
            ("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "us-gaap:StatementBusinessSegmentsAxis=tjx:MarmaxxMember"),
            ("us-gaap:Revenues", "us-gaap:StatementBusinessSegmentsAxis=tjx:MarmaxxMember"))]},
    # Retail operations segment: consolidated net sales also include the CDI construction business,
    # which no card panel sees (changed 2026-10-18 at the user's request; fit 0.64 vs 0.61)
    {"id": "DDS", "kpi": "Retail operations net sales", "calendar": "fiscal_jan", "sensors": ["DDS"], "variants": [
        one(28917, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=dds:RetailOperationsMember"))]},
    # From fiscal 2018 JCPenney tags net sales as Revenues; RevenueFromContract... adds credit income
    {"id": "JCP", "kpi": "Total net sales", "calendar": "fiscal_jan", "sensors": ["JCP"], "variants": [
        one(1166126, ("us-gaap:SalesRevenueNet", ""), ("us-gaap:Revenues", ""))]},
]
