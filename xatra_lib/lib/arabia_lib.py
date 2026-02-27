MITANNI_SYRIA = (
    gadm("SYR.9")
    | gadm("SYR.14")
    | gadm("SYR.8")
    | gadm("SYR.11")
    | gadm("SYR.10")
    | gadm("SYR.2")
    | gadm("SYR.3")
    | gadm("SYR.7")
    | gadm("SYR.1")
)
MITANNI_TURKEY = (
    gadm("TUR.58")
    | gadm("TUR.1")
    | gadm("TUR.42")
    | gadm("TUR.55")
    | gadm("TUR.64")
    | gadm("TUR.33")
    | gadm("TUR.48")
    | gadm("TUR.2")
    | gadm("TUR.68")
    | gadm("TUR.29")
    | gadm("TUR.26")
    | gadm("TUR.57")
    | gadm("TUR.14")
    | gadm("TUR.69")
    | gadm("TUR.71")
)
MITANNI_IRAQ = (
    gadm("IRQ.17") | gadm("IRQ.8") | gadm("IRQ.16") | gadm("IRQ.6") | gadm("IRQ.12")
)
MITANNI = MITANNI_SYRIA | MITANNI_TURKEY | MITANNI_IRAQ
SOCOTRA = gadm("YEM.12.20") | gadm("YEM.12.18")

# Levant
LEVANT = (
    gadm("LBN") | gadm("ISR") | gadm("PSE") | gadm("SYR") | gadm("JOR") | gadm("IRQ")
)
GULF = (
    gadm("ARE")
    | gadm("BHR")
    | gadm("KWT")
    | gadm("OMN")
    | gadm("QAT")
    | gadm("SAU")
    | gadm("YEM")
)


__TERRITORY_INDEX__ = [
    "MITANNI",
    "SOCOTRA"
]