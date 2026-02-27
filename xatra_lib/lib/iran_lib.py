ind = xatrahub("/lib/indic_lib")

# western silk road
KAMBOJA = ind.KAMBOJA
PAKTHA = ind.PAKTHA
KANDAHAR = gadm("AFG.15") | gadm("AFG.11")  # Arachosia
ZARANJ = gadm("AFG.7") | gadm("AFG.23")  # Drangiana
HERAT = gadm("AFG.12")  # Aria
AFG_MARGIANA = gadm("AFG.2") | gadm("AFG.8")
AFG_MERU = gadm("AFG.1")  # Badakhshan
AFG_BACTRIA = (
    gadm("AFG.31")
    | gadm("AFG.19")
    | gadm("AFG.3")
    | gadm("AFG.4")
    | gadm("AFG.29")
    | gadm("AFG.13")
    | gadm("AFG.30")
)
AFG_MISC = gadm("AFG") - (
    KAMBOJA | KANDAHAR | ZARANJ | HERAT | AFG_MARGIANA | AFG_BACTRIA | AFG_MERU | PAKTHA
)
INNER_KAMBOJA = ind.INNER_KAMBOJA  # Federally Administered Tribal Areas
URASA = ind.URASA
VARNU = ind.VARNU
VANAVYA = ind.VANAVYA
APRITA = ind.APRITA
SWAT = ind.SWAT
UDDIYANA = ind.UDDIYANA
KAPISAYANA = ind.KAPISAYANA
DVIRAVATIKA_PROPER = ind.DVIRAVATIKA_PROPER
TRIRAVATIKA_PROPER = ind.TRIRAVATIKA_PROPER
TRYAKSYAYANA_PROPER = ind.TRYAKSYAYANA_PROPER
TRYAKSYAYANA = ind.TRYAKSYAYANA
DVIRAVATIKA = ind.DVIRAVATIKA
TRIRAVATIKA = ind.TRIRAVATIKA
ASVAKAYANA = ind.ASVAKAYANA
ASVAKAYANA_GREATER = ind.ASVAKAYANA_GREATER
ASVAYANA = ind.ASVAYANA
NIGRAHARA = ind.NIGRAHARA
VRJISTHANA = ind.VRJISTHANA

YANA = ind.YANA
GREATER_KAMBOJA = ind.GREATER_KAMBOJA

ROHITAGIRI = AFG_MISC
KAMBOJA_EXT = KAMBOJA | AFG_MISC

# baloch areas
BALOCH = ind.BALOCH # gedrosia
INDRAVAKTRA = ind.INDRAVAKTRA
PARDAYANA = ind.PARDAYANA
ARABHATA = ind.ARABHATA
DAMANI = ind.DAMANI

TJK_BACTRIA = gadm("TJK.3") | gadm("TJK.1") | gadm("TJK.5.7")  # Khatlon province
TJK_SOGDIA_PROPER = gadm("TJK.4")
TJK_MERU = gadm("TJK.2") | (gadm("TJK.5") - TJK_BACTRIA)  # Badakhshan
UZB_BACTRIA = gadm("UZB.12")
UZB_SOGDIA_PROPER = (
    gadm("UZB.6")
    | gadm("UZB.10")
    | gadm("UZB.2")
    | gadm("UZB.9")
    | gadm("UZB.4")
    | gadm("UZB.11")
    | gadm("UZB.13")
    | gadm("UZB.14")
)  # Tashkentic ppl
UZB_KHWAREZM = gadm("UZB.5") | gadm("UZB.7")
UZB_FERGHANA = gadm("UZB") - (UZB_BACTRIA | UZB_SOGDIA_PROPER | UZB_KHWAREZM)
TKM_KHWAREZM = gadm("TKM.3") | gadm("TKM.6")
TKM_MARGIANA = gadm("TKM") - TKM_KHWAREZM
MARGIANA = TKM_MARGIANA | AFG_MARGIANA
ANDHAKAVARTA = MARGIANA - gadm("TKM")
BACTRIA = AFG_BACTRIA | TJK_BACTRIA | UZB_BACTRIA
MERU = AFG_MERU | TJK_MERU
SOGDIA_PROPER = UZB_SOGDIA_PROPER | TJK_SOGDIA_PROPER
FERGHANA = UZB_FERGHANA
SOGDIA = SOGDIA_PROPER | FERGHANA
KHWAREZM = UZB_KHWAREZM | TKM_KHWAREZM

# eastern silk road oasis states
# kashgar, khotan, rouran, kucha, agni, turfan
KASHGAR = gadm("CHN.28.9")
KHOTAN = gadm("CHN.28.10")
KUCHA = (
    gadm("CHN.28.1.5") | gadm("CHN.28.1.3") | gadm("CHN.28.1.7") | gadm("CHN.28.1.6")
)
AKSU = gadm("CHN.28.1") - KUCHA
ROURAN = gadm("CHN.28.3.7")
AGNI = gadm("CHN.28.3.8")
QIEMO = gadm("CHN.28.3.6")
KORLA = gadm("CHN.28.3.4")
TURFAN = gadm("CHN.28.14")
XINJIANG = gadm("CHN.28")
TARIM = (
    gadm("CHN.28.1")
    | gadm("CHN.28.3")
    | gadm("CHN.28.9")
    | gadm("CHN.28.10")
    | gadm("CHN.28.11")
)
DZUNGARIA = XINJIANG - TARIM

# normal iran
CENTRAL_ASIA = (
    gadm("AFG")
    | gadm("PAK.2")
    | gadm("IRN.26")
    | gadm("TJK")
    | gadm("UZB")
    | gadm("TKM")
)
CENTRAL_ASIA_GREATER = CENTRAL_ASIA | ind.INNER_KAMBOJA
IRANIC = gadm("IRN") | CENTRAL_ASIA_GREATER
IRANIC_GREATER = IRANIC | TARIM
HYRCANIA = gadm("IRN.9")
PARTHIA = gadm("IRN.25") | gadm("IRN.21") | gadm("IRN.24")  | polygon([[38.0394,57.3816],[38.1,57.7441],[38.0654,57.9749],[38.074,58.3044],[37.9875,58.5901],[37.8575,58.689],[37.7012,58.7988],[37.5794,58.8538],[37.3963,58.7549],[37.6751,57.8101],[37.9702,57.1399],[38.1173,57.1729]])
PERSIA = gadm("IRN.7")

ARMENIA = gadm("ARM")
AZER = gadm("AZE")
GEORGIA = gadm("GEO")



__TERRITORY_INDEX__ = [
    "KAMBOJA",
    "URASA",
    "VARNU",
    "VANAVYA",
    "APRITRA",
    "UDDIYANA",
    "KAPISAYANA",
    "TRYAKSYAYANA",
    "DVIRAVATIKA",
    "ASVAKAYANA",
    "VRJISTHANA",
    "ASVAYANA",
    "NIGRAHARA",
    "BALOCH",
    "INDRAVAKTRA",
    "PARDAYANA",
    "ARABHATA",
    "MERU",
    "ZARANJ",
    "KANDAHAR",
    "HERAT",
    "ROHITAGIRI",
    "PAKTHA",
    "BACTRIA",
    "MARGIANA",
    "SOGDIA_PROPER",
    "FERGHANA",
    "KHWAREZM",
    "KASHGAR",
    "KHOTAN",
    "AGNI",
    "AKSU",
    "KUCHA",
    "ROURAN",
    "QIEMO",
    "KORLA",
    "TURFAN",
    "TARIM",
    "DZUNGARIA",
    "HYRCANIA",
    "PARTHIA",
    "PERSIA",
]