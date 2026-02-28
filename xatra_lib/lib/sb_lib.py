disp = xatrahub("/lib/disputed")
ind = xatrahub("/lib/indic_lib")

# tibeto-burman region
TIBET_CN_TIB = gadm("CHN.29")
TIBET_CN_QIN = gadm("CHN.21")
TIBET_CN_SIC = gadm("CHN.26.5") | gadm("CHN.26.16")
TIBET_CN = TIBET_CN_TIB | TIBET_CN_QIN | TIBET_CN_SIC
TIBET_BHU = gadm("BTN")  
TIBET_NEP = (
    gadm("NPL.4.2.1")
    | gadm("NPL.4.2.2")
    | gadm("NPL.4.2.5")
    | gadm("NPL.5.1")
    | gadm("NPL.5.2")
    | gadm("NPL.1.1")
    | gadm("NPL.1.2.2")
    | gadm("NPL.1.2.4")
    | gadm("NPL.1.2.6")
    | gadm("NPL.2.3.5")
    | gadm("NPL.2.3.1")
    | gadm("NPL.2.3.2")
    | gadm("NPL.2.1.1")
    | gadm("NPL.2.1.4")
    | gadm("NPL.2.1.2")
    | gadm("NPL.2.1.6")
    | gadm("NPL.2.2.4")
    | gadm("NPL.2.2.3")
    | gadm("NPL.2.2.1")
)  # nepali-occupied tibet
TIBET_AP = disp.CHINESE_CLAIMS_AP
TIBET_LAD = ind.LADAKH  
TIBET_SIK = gadm("IND.30")  
TIBET = TIBET_CN | TIBET_BHU | TIBET_NEP | TIBET_LAD | TIBET_AP | TIBET_SIK

TIBET_BURMA_INTERM = (
    ind.NEI_HIM | gadm("MMR.3")
) - TIBET  # intermediary region from Tibet to Burma

YUNNAN_BURMA_INTERM = gadm("MMR.4")  # kachin state
KAREN = gadm("MMR.5") | gadm("MMR.6")  # karenic parts of myanmar
SIAM_BURMA_INTERM = gadm("MMR.13")  # shan state

BURMA_UPPER = gadm("MMR.12") | gadm("MMR.7") | gadm("MMR.8") | gadm("MMR.10")
BURMA_LOWER_RIVER = gadm("MMR.2") | gadm("MMR.1") | gadm("MMR.15")
BURMA_LOWER_RAKHINE = gadm("MMR.11")
BURMA_LOWER_THAICOAST = gadm("MMR.9") | gadm("MMR.14")
BURMA_LOWER = BURMA_LOWER_RIVER | BURMA_LOWER_RAKHINE | BURMA_LOWER_THAICOAST
BURMA = BURMA_UPPER | BURMA_LOWER

# southeast asia
SIAM_THA = gadm("THA")
SIAM = SIAM_THA | SIAM_BURMA_INTERM
LAOS = gadm("LAO")
KHMER = gadm("KHM")
CHAM = (
    gadm("VNM.41")
    | gadm("VNM.29")
    | gadm("VNM.46")
    | gadm("VNM.50")
    | gadm("VNM.54")
    | gadm("VNM.19")
    | gadm("VNM.47")
    | gadm("VNM.48")
    | gadm("VNM.34")
    | gadm("VNM.8")
    | gadm("VNM.21")
    | gadm("VNM.45")
    | gadm("VNM.32")
    | gadm("VNM.15")
    | gadm("VNM.43")
    | gadm("VNM.37")
    | gadm("VNM.16")
    | gadm("VNM.11")
    | gadm("VNM.7")
    | gadm("VNM.17")
    | gadm("VNM.10")
    | gadm("VNM.25")
    | gadm("VNM.9")
    | gadm("VNM.53")
    | gadm("VNM.39")
    | gadm("VNM.58")
    | gadm("VNM.6")
    | gadm("VNM.59")
    | gadm("VNM.61")
    | gadm("VNM.18")
    | gadm("VNM.51")
    | gadm("VNM.24")
    | gadm("VNM.2")
    | gadm("VNM.33")
    | gadm("VNM.12")
    | gadm("VNM.1")
    | gadm("VNM.13")
    | gadm("VNM.33")
)
NORTH_VIETNAM = gadm("VNM") - CHAM
BORNEO_MYS = gadm("MYS.13") | gadm("MYS.14") | gadm("MYS.5")  # sabah serawak
BORNEO_BRU = gadm("BRN")
BORNEO_MYS_GREATER = BORNEO_MYS | BORNEO_BRU
BORNEO_IDN = (
    gadm("IDN.35") | gadm("IDN.34") | gadm("IDN.12") | gadm("IDN.13") | gadm("IDN.14")
)  # kalimantan
BORNEO = BORNEO_MYS_GREATER | BORNEO_IDN

MALAY_PENINSULA_MYS = gadm("MYS") - BORNEO_MYS
MALAY_PENINSULA_SG = gadm("SGP")
MALAY_PENINSULA = MALAY_PENINSULA_MYS | MALAY_PENINSULA_SG
JAVA = (
    (gadm("IDN.9") | gadm("IDN.10") | gadm("IDN.11"))
    | gadm("IDN.4")
    | gadm("IDN.7")
    | gadm("IDN.33")
)
LESSER_SUNDA_IDN = gadm("IDN.2") | (gadm("IDN.20") | gadm("IDN.21"))
LESSER_SUNDA_TLS = gadm("TLS")
LESSER_SUNDA = LESSER_SUNDA_IDN | LESSER_SUNDA_TLS

MALUKU_SOUTH = gadm("IDN.19")
MALUKU_NORTH = gadm("IDN.18")
MALUKU = MALUKU_SOUTH | MALUKU_NORTH

SULAWESI = (
    (gadm("IDN.25") | gadm("IDN.26") | gadm("IDN.27") | gadm("IDN.28") | gadm("IDN.29"))
    | gadm("IDN.6")
    | gadm("IDN.29")
)
KEPULAUAN = gadm("IDN.16")  # bits of indonesia between indonesia and malaysia
BANGKA = gadm("IDN.3")  # bits of indonesia between borneo and sumatra
SUMATRA = (
    (gadm("IDN.30") | gadm("IDN.31") | gadm("IDN.32"))
    | gadm("IDN.1")
    | gadm("IDN.24")
    | gadm("IDN.8")
    | gadm("IDN.17")
    | gadm("IDN.5")
)
ANDAMAN_NICOBAR = gadm("IND.1")

PAPUA_IDN = gadm("IDN.22") | gadm("IDN.23")
PHILIPPINES = gadm("PHL")

__TERRITORY_INDEX__ = [
    "TIBET",
    "TIBET_BURMA_INTERM",
    "YUNNAN_BURMA_INTERM",
    "KAREN",
    "SIAM_BURMA_INTERM",
    "BURMA_UPPER",
    "BURMA_LOWER",
    "SIAM",
    "LAOS",
    "KHMER",
    "CHAM",
    "NORTH_VIETNAM",
    "BORNEO",
    "MALAY_PENINSULA",
    "SUMATRA",
    "JAVA",
    "LESSER_SUNDA",
    "MALUKU",
    "SULAWESI",
    "KEPULAUAN",
    "BANGKA",
    "ANDAMAN_NICOBAR",
]