disp = xatrahub("/lib/disputed")

TERAI_HP = (
    gadm("IND.13.4")
    | gadm("IND.13.3")
    | gadm("IND.13.12")
    | gadm("IND.13.1")
    | gadm("IND.13.11")
    | gadm("IND.13.10")
)
TERAI_UK_W = gadm("IND.35.5")
TERAI_UK_ROORKEE = gadm("IND.35.7")
TERAI_UK_E = gadm("IND.35.8") | gadm("IND.35.12")
TERAI_UK = TERAI_UK_W | TERAI_UK_ROORKEE | TERAI_UK_E
TERAI_NPL_FW = gadm("NPL.3.1.4") | gadm("NPL.3.2.5")
TERAI_NPL_MW = gadm("NPL.4.1.1") | gadm("NPL.4.1.2")
TERAI_NPL_W = gadm("NPL.5.3.3") | gadm("NPL.5.3.6") | gadm("NPL.5.3.4")  # sakya
TERAI_NPL_C = (
    gadm("NPL.1.3.4")
    | gadm("NPL.1.3.1")
    | gadm("NPL.1.3.5")
    | gadm("NPL.1.2.5")
    | gadm("NPL.1.2.3")
    | gadm("NPL.1.2.1")
    | gadm("NPL.1.3.2")
)
TERAI_NPL_E = (
    gadm("NPL.2.3.4")
    | gadm("NPL.2.3.3")
    | gadm("NPL.2.1.3")
    | gadm("NPL.2.1.5")
    | gadm("NPL.2.2.2")
)
TERAI_NPL = TERAI_NPL_FW | TERAI_NPL_MW | TERAI_NPL_W | TERAI_NPL_C | TERAI_NPL_E
TERAI_BENGAL = (
    gadm("IND.36.6") | gadm("IND.36.9") | gadm("IND.36.1") | gadm("IND.36.10")
)
# BENGAL_HIM = Matcher.__false__() # keep this line in for now
TERAI = TERAI_HP | TERAI_UK | TERAI_NPL | TERAI_BENGAL
HP_HIM = (gadm("IND.13") | disp.CHINESE_CLAIMS_HP) - TERAI_HP
UK_HIM = (gadm("IND.35") | disp.CHINESE_CLAIMS_UK) - TERAI_UK
NPL_HIM = gadm("NPL") - TERAI_NPL
LADAKH = (
    gadm("Z01.14.13") | gadm("Z01.14.8") | disp.Z03 | disp.Z08
)  # Aksai Chin main part | Aksai Chin Southern bit
KASHMIR_MISC = (
    gadm("Z01.14.10")
    | gadm("Z01.14.5")
    | gadm("Z01.14.17")
    | gadm("Z01.14.18")
    | gadm("Z01.14.22")
    | gadm("Z01.14.7")
    | gadm("Z01.14.19")
    | gadm("Z01.14.9")
)
KASHMIR_PROPER = gadm("Z01.14") - (KASHMIR_MISC | LADAKH)
POJK = gadm("Z06.1")  # POK
# KASHMIR = KASHMIR_PROPER | KASHMIR_MISC | POJK

# alternate division for Kashmir:
JAMMU_IND = KASHMIR_MISC | gadm("Z01.14.16") | gadm("Z01.14.14")  # + poonch and rajouri
KASHMIR_IND = gadm("Z01.14") - (JAMMU_IND | LADAKH)
KASHMIR_POK = gadm("Z06.1.1.6") | gadm("Z06.1.1.5")
JAMMU_POK = POJK - KASHMIR_POK
JAMMU = JAMMU_IND | JAMMU_POK
KASHMIR = KASHMIR_IND | KASHMIR_POK

GLAUCUKAYANAKA = gadm("Z01.14.16") | gadm("Z01.14.18") | gadm("Z06.1.1.2")
SAVASA = JAMMU_POK | gadm("Z01.14.14") | gadm("Z01.14.16") | gadm("Z01.14.18") # reasi was a part of rajouri district when VS Agarwala wrote his book
# | gadm("Z06.1.1.7") | gadm("Z06.1.1.8") | gadm("Z06.1.1.3") | gadm("Z06.1.1.1") | gadm("Z06.1.1.4") | gadm("Z06.1.1.2")

DARADA_PROPER = gadm("Z06.6")
CHITRAL = gadm("PAK.5.6.1")
DARADA = DARADA_PROPER | CHITRAL
KHYBER_HIM = gadm("PAK.5.6") | gadm("PAK.5.4")
ASSAM_HIM = (
    gadm("IND.4.4")
    | gadm("IND.4.10")
    | gadm("IND.4.13")
    | gadm("IND.4.18")
    | gadm("IND.4.17")
    | gadm("IND.4.22")
)
LAUHITYA = gadm("IND.4") - ASSAM_HIM
NEI_HIM = (
    gadm("IND.3")
    | gadm("IND.22")
    | gadm("IND.24")
    | gadm("IND.21")
    | gadm("IND.23")
    | gadm("IND.33")
    | ASSAM_HIM
    | disp.Z07
)

KAMBOJA = (
    gadm("AFG.24")
    | gadm("AFG.18")
    | gadm("AFG.22")
    | gadm("AFG.26")
    | gadm("AFG.17")
    | gadm("AFG.21")
    | gadm("AFG.33")
    | gadm("AFG.28")
    | gadm("AFG.20")
    | gadm("AFG.14")
    | gadm("AFG.16")
    | gadm("AFG.27")
    | gadm("AFG.5")
)
PAKTHA = gadm("AFG.25") | gadm("AFG.26") | gadm("AFG.17")
INNER_KAMBOJA = gadm("PAK.3")  # Federally Administered Tribal Areas
URASA = gadm("PAK.5.4")

HIMALAYAN = (
    HP_HIM
    | UK_HIM
    | NPL_HIM
    | gadm("BTN")
    # | BENGAL_HIM # keep this line in for now
    | NEI_HIM
    | gadm("IND.30")
    | LADAKH
    | DARADA
    | KHYBER_HIM
    | disp.CHINESE_CLAIMS
)

# gangetic
UP_CEDI = (
    gadm("IND.34.38")
    | gadm("IND.34.34")
    | gadm("IND.34.13")
    | gadm("IND.34.21")
    | gadm("IND.34.40")
    | gadm("IND.34.51")
    | gadm("IND.34.48")
)
UP_KALAKAVANA = gadm("IND.34.56") | gadm("IND.34.72")
SURASENA = gadm("IND.34.53") | gadm("IND.34.1")
KURU_PROPER = (
    gadm("IND.34.63")
    | gadm("IND.34.58")
    | gadm("IND.34.68")
    | gadm("IND.34.9")
    | gadm("IND.34.55")
    | gadm("IND.34.30")
    | gadm("IND.34.35")
    | gadm("IND.34.19")
    | gadm("IND.34.29")
    | gadm("IND.35.7")
)
KURU_KSETRA = (
    gadm("IND.12.21")
    | gadm("IND.12.11")
    | gadm("IND.12.9")
    | gadm("IND.12.8")
    | gadm("IND.12.10")
    | gadm("IND.12.16")
)
KURU_JANGALA = (
    gadm("IND.25")
    | gadm("IND.12.20")
    | gadm("IND.12.18")
    | gadm("IND.12.7")
    | gadm("IND.12.5")
    | gadm("IND.12.3")
    | gadm("IND.12.14")
    | gadm("IND.12.13")
)
KURU_KSETRA_GREATER_HARYANA = KURU_KSETRA | gadm("IND.12.15") | gadm("IND.12.1")
JANGALA_HARYANA = (
    KURU_JANGALA
    | gadm("IND.12.17")
    | gadm("IND.12.12")
    | gadm("IND.12.2")
    | gadm("IND.12.6")
    | gadm("IND.12.4")
    | gadm("IND.12.19")
)
KURU = KURU_PROPER | KURU_JANGALA | KURU_KSETRA
PANCALA_S = (
    gadm("IND.34.2")
    | gadm("IND.34.37")
    | gadm("IND.34.23")
    | gadm("IND.34.44")
    | gadm("IND.34.28")
    | gadm("IND.34.52")
    | gadm("IND.34.24")
    | gadm("IND.34.26")
    | gadm("IND.34.41")
)
PANCALA_N = (
    gadm("IND.34.17")
    | gadm("IND.34.6")
    | gadm("IND.34.64")
    | gadm("IND.34.57")
    | gadm("IND.34.62")
    | gadm("IND.34.15")
    | gadm("IND.34.18")
    | gadm("IND.34.64")
)
PANCALA = PANCALA_N | PANCALA_S
VATSA = gadm("IND.34.27") | gadm("IND.34.45") | gadm("IND.34.3")
KASI = (
    gadm("IND.34.39")
    | gadm("IND.34.66")
    | gadm("IND.34.75")
    | gadm("IND.34.20")
    | gadm("IND.5.14")
    | gadm("IND.5.29")
    | gadm("IND.5.8")
    | gadm("IND.5.7")
)
KOSALA = (
    gadm("IND.34.10")
    | gadm("IND.34.69")
    | gadm("IND.34.32")
    | gadm("IND.34.12")
    | gadm("IND.34.70")
    | gadm("IND.34.16")
    | gadm("IND.34.65")
    | gadm("IND.34.33")
    | gadm("IND.34.25")
    | gadm("IND.34.4")
    | gadm("IND.34.4")
    | gadm("IND.34.8")
    | gadm("IND.34.54")
    | gadm("IND.34.11")
    | gadm("IND.34.73")
    | gadm("IND.34.31")
)
SAKYA = TERAI_NPL_W  # | gadm("NPL.1.3.2")
JANAKPUR = TERAI_NPL_C  # - gadm("NPL.1.3.2")
MALLA = (
    gadm("IND.34.50")
    | gadm("IND.34.46")
    | gadm("IND.34.22")
    | gadm("IND.5.11")
    | gadm("IND.5.36")
    | gadm("IND.5.32")
)
VIDEHA_IN = (
    gadm("IND.5.25")
    | gadm("IND.5.27")
    | gadm("IND.5.34")
    | gadm("IND.5.35")
    | gadm("IND.5.20")
)
VIDEHA = VIDEHA_IN | JANAKPUR
LICCHAVI = (
    gadm("IND.5.22")
    | gadm("IND.5.38")
    | gadm("IND.5.9")
    | gadm("IND.5.31")
    | gadm("IND.5.5")
    | gadm("IND.5.16")
)
MAGADHA = (
    gadm("IND.5.26")
    | gadm("IND.5.13")
    | gadm("IND.5.3")
    | gadm("IND.5.2")
    | gadm("IND.5.10")
    | gadm("IND.5.23")
    | gadm("IND.5.33")
    | gadm("IND.5.24")
    | gadm("IND.5.18")
    | gadm("IND.5.12")
    | gadm("IND.5.21")
)
KOSALA_GREATER = KOSALA | VIDEHA | LICCHAVI | SAKYA | MALLA | KASI | VATSA
BIHAR_ANGA = gadm("IND.5.4") | gadm("IND.5.6")
BIHAR_NORTHEAST = gadm("IND.5") - (
    VIDEHA | LICCHAVI | MAGADHA | BIHAR_ANGA | KASI | MALLA
)
UP_NAIMISA = gadm("IND.34") - (
    KURU_PROPER
    | PANCALA_S
    | PANCALA_N
    | SURASENA
    | KOSALA
    | KASI
    | VATSA
    | MALLA
    | UP_CEDI
    | UP_KALAKAVANA
)
BIHAR_N = LICCHAVI | VIDEHA
BIHAR = MAGADHA | LICCHAVI | VIDEHA
UP_EAST = KOSALA_GREATER
UP_WEST = KURU_PROPER | PANCALA | SURASENA
UP = UP_WEST | UP_EAST | UP_NAIMISA
GANGETIC = UP | BIHAR

AVANTI = (
    gadm("IND.19.15")
    | gadm("IND.19.48")
    | gadm("IND.19.35")
    | gadm("IND.19.28")
    | gadm("IND.19.31")
    | gadm("IND.19.25")
    | gadm("IND.19.2")
    | gadm("IND.19.16")
    | gadm("IND.19.23")
)
AKARA = (
    gadm("IND.19.1")
    | gadm("IND.19.42")
    | gadm("IND.19.39")
    | gadm("IND.19.34")
    | gadm("IND.19.9")
    | gadm("IND.19.33")
    | gadm("IND.19.50")
    | gadm("IND.19.19")
    | gadm("IND.19.4")
)
DASARNA = (
    gadm("IND.19.44")
    | gadm("IND.19.43")
    | gadm("IND.19.20")
    | gadm("IND.19.14")
    | gadm("IND.19.8")
    | gadm("IND.19.29")
)
PULINDA_W = (
    gadm("IND.19.21")
    | gadm("IND.19.18")
    | gadm("IND.19.51")
    | gadm("IND.19.10")
    | gadm("IND.19.6")
)
PULINDA_E = (
    gadm("IND.19.22")
    | gadm("IND.19.7")
    | gadm("IND.19.12")
    | gadm("IND.19.30")
    | gadm("IND.19.40")
    | gadm("IND.19.27")
    | gadm("IND.19.5")
    | gadm("IND.19.17")
)
PULINDA = PULINDA_W | PULINDA_E
MP_CEDI = gadm("IND.19") - (AVANTI | AKARA | DASARNA | PULINDA_W | PULINDA_E)
CEDI = MP_CEDI | UP_CEDI

BRAHMAVARTA = gadm("IND.12") | gadm("IND.25")

MATSYA = (
    gadm("IND.29.6")
    | gadm("IND.29.2")
    | gadm("IND.29.17")
    | gadm("IND.29.12")
    | gadm("IND.29.23")
    | gadm("IND.29.13")
    | gadm("IND.29.29")
)
KUKURA = (
    gadm("IND.29.32")
    | gadm("IND.29.9")
    | gadm("IND.29.1")
    | gadm("IND.29.7")
    | gadm("IND.29.28")
    | gadm("IND.29.33")
    | gadm("IND.29.10")
    | gadm("IND.29.14")
    | gadm("IND.29.27")
    | gadm("IND.29.3")
)
# SALVA = (
#     gadm("IND.29.8")
#     | gadm("IND.29.15")
#     | gadm("IND.29.16")
#     | gadm("IND.29.11")
#     | gadm("IND.29.21")
#     | gadm("IND.29.30")
#     | gadm("IND.29.2")
#     | gadm("IND.29.17")
#     | gadm("IND.29.1")
#     | gadm("IND.29.25")
# )
# SALVA_PROPER = (
#     gadm("IND.29.16")
#     | gadm("IND.29.15")
#     | gadm("IND.29.11.5")
#     | gadm("IND.29.11.7")
#     | gadm("IND.29.11.1")
#     | gadm("IND.29.11.3")
#     | gadm("IND.29.21")
#     | gadm("IND.29.30.3")
#     | gadm("IND.29.17.8")
#     | gadm("IND.29.2")
# )
SALVA = (
    gadm("IND.29.16")
    | gadm("IND.29.15")
    | gadm("IND.29.8.3")
    | gadm("IND.29.11")
    | gadm("IND.29.21")
    | gadm("IND.29.30")
    | gadm("IND.29.17.8")
    | gadm("IND.29.17.13")
    | gadm("IND.29.2")
)
SALVA_GREATER = SALVA | gadm("IND.29.25") | gadm("IND.29.8")
KUKURA_GREATER = MATSYA | KUKURA
HADOTI = gadm("IND.29.24") | gadm("IND.29.4") | gadm("IND.29.20")
RJ_MARU = gadm("IND.29") - (MATSYA | KUKURA | HADOTI)
MP = AVANTI | AKARA | DASARNA | PULINDA | CEDI | HADOTI
RJ = gadm("IND.29")

PUNJAB = (
    gadm("IND.28") | gadm("PAK.7") | gadm("IND.6.1") | gadm("PAK.4.1") | gadm("PAK.5")
) - HIMALAYAN
GANDHARA_W_GREATER = gadm("PAK.5") - HIMALAYAN
VARNU = gadm("PAK.5.1.1") | gadm("PAK.5.1.2") | gadm("PAK.5.3.2")
VANAVYA = gadm("PAK.5.2")
APRITA = gadm("PAK.3.1.7") | gadm("PAK.3.1.3") | gadm("PAK.3.1.2")
SWAT = gadm("PAK.5.6.5")
UDDIYANA = SWAT | gadm("PAK.5.6.4")
KAPISAYANA = gadm("AFG.24")
DVIRAVATIKA_PROPER =(
    gadm("PAK.3.1.1")
    | gadm("PAK.3.1.5")
)
TRIRAVATIKA_PROPER = gadm("PAK.3.1.2")
TRYAKSYAYANA_PROPER = (
    gadm("AFG.22.13")
    | gadm("AFG.22.7")
    | gadm("AFG.22.10")
    | gadm("AFG.18.7")
    | gadm("AFG.18.12")
    | gadm("AFG.18.8")
    | gadm("AFG.18.5")
)
TRYAKSYAYANA = TRYAKSYAYANA_PROPER | DVIRAVATIKA_PROPER
DVIRAVATIKA = TRYAKSYAYANA
TRIRAVATIKA = APRITA
ASVAKAYANA = gadm("PAK.5.6.3") | gadm("PAK.5.6.2")
ASVAKAYANA_GREATER = ASVAKAYANA | gadm("PAK.5.6.1")
ASVAYANA = (
    gadm("AFG.20")
    | gadm("AFG.18")
    | gadm("AFG.22.4")
    | gadm("AFG.22.12")
    | gadm("AFG.22.9")
) - TRYAKSYAYANA

NIGRAHARA = gadm("AFG.22") - ASVAYANA - TRYAKSYAYANA

YANA = INNER_KAMBOJA | URASA | UDDIYANA | ASVAKAYANA | KAPISAYANA | ASVAYANA | NIGRAHARA | PAKTHA # | TRYAKSYAYANA | APRITA
GREATER_KAMBOJA = KAMBOJA | YANA

GANDHARA_W = GANDHARA_W_GREATER - (VANAVYA | VARNU)
GANDHARA_E = gadm("PAK.7.7.1") | gadm("PAK.7.7.4") | gadm("PAK.4.1")
PSEUDOSATTAGYDIA_S = gadm("PAK.7.2.1") | gadm("PAK.7.2.4")
PSEUDOSATTAGYDIA_N = VANAVYA | gadm("PAK.5.1") | gadm("PAK.5.3.2")
PSEUDOSATTAGYDIA = PSEUDOSATTAGYDIA_N | PSEUDOSATTAGYDIA_S
DOAB_IJ_N = (gadm("PAK.4.1") | gadm("PAK.7.7") | gadm("PAK.7.8")) - gadm("PAK.7.8.4")
DOAB_IJ_S = gadm("PAK.7.2.2") | gadm("PAK.7.2.3")
GANDHARA = GANDHARA_W | GANDHARA_E
GANDHARA_W_EXTRA = (
    gadm("PAK.3.1.5") | gadm("PAK.3.1.1") | gadm("PAK.5.6.3")
)  # himalayan-ish regions adjacent to GANDHARA_W_GREATER

VRJISTHANA = gadm("PAK.3.1.8") | gadm("PAK.3.1.6") | gadm("PAK.3.1.4")
DOAB_IJ = DOAB_IJ_N | DOAB_IJ_S
DOAB_JC = gadm("PAK.7.4.4") | gadm("PAK.7.4.1") | gadm("PAK.7.8.4")
DOAB_CR = (
    gadm("PAK.7.4.2")
    | gadm("PAK.7.4.3")
    | gadm("PAK.7.4.5")
    | gadm("PAK.7.4.6")
    | gadm("PAK.7.4.7")
    | gadm("PAK.7.4.8")
    | gadm("PAK.7.5.3")
    | gadm("PAK.7.5.6")
    | gadm("PAK.7.3.1")
    | gadm("PAK.7.3.2")
    | gadm("PAK.7.3.3")
)
DOAB_RS_N = gadm("IND.28.16") | gadm("IND.28.8") | gadm("IND.28.1") | gadm("IND.28.22")
DOAB_RS_C = (
    gadm("PAK.7.5.1") | gadm("PAK.7.5.2") | gadm("PAK.7.5.4") | gadm("PAK.7.5.5")
)
DOAB_RS_S = gadm("PAK.7.6")
DOAB_RS = DOAB_RS_N | DOAB_RS_C | DOAB_RS_S

USINARA = gadm("PAK.7.3")
MALAVA = gadm("PAK.7.6.1") | gadm("PAK.7.6.2") | gadm("PAK.7.6.3") | gadm("PAK.7.6.6")
KSUDRAKA = gadm("PAK.7.6.4") | gadm("PAK.7.6.5")
LAVAPURA = gadm("PAK.7.5.1") | gadm("PAK.7.5.2") | gadm("PAK.7.5.4") | gadm("PAK.7.5.5")
KSUDRAKA_GREATER = KSUDRAKA | LAVAPURA
USINARA_GREATER = USINARA | MALAVA | KSUDRAKA
MADRA = DOAB_JC | DOAB_CR - USINARA_GREATER
MADRA_W = DOAB_JC - USINARA_GREATER
MADRA_E = DOAB_CR - USINARA_GREATER
MADRAKARA = gadm("IND.28.6") | gadm("IND.28.15")

BAHAWALPUR = gadm("PAK.7.1")
# TRIGARTA_PROPER = (gadm("IND.28") | gadm("IND.6.1")) - DOAB_RS_N
# TRIGARTA = gadm("IND.28") | gadm("IND.6.1") | DOAB_RS_C
TILAKHALA = gadm("IND.28.9")
RAJANYA = gadm("IND.28.10") | gadm("IND.28.11") | gadm("IND.28.21")
TRIGARTA_PJ = (
    gadm("IND.28.9") | gadm("IND.28.10") | gadm("IND.28.11") | gadm("IND.28.21")
)
TRIGARTA_HP = gadm("IND.13.4") | gadm("IND.13.12") | gadm("IND.13.1") | gadm("IND.13.3")
TRIGARTA = TRIGARTA_PJ | TRIGARTA_HP
AUDUMBARA = TRIGARTA_HP | gadm("IND.28.16")
KUNINDA = (TERAI_UK_W | TERAI_HP) - TRIGARTA_HP
GABDIKA = gadm("IND.13.2")
GABDIKA_GREATER = GABDIKA | gadm("IND.13.4")
YAKRLOMAN = gadm("IND.34.38")

MADRA_EE = LAVAPURA | DOAB_RS_N - AUDUMBARA
MADRA_GREATER = MADRA | MADRA_EE

PUADH = (
    gadm("IND.28.18")
    | gadm("IND.28.5")
    | gadm("IND.28.19")
    | gadm("IND.28.17")
    | gadm("IND.6.1")
)
JANGALA_PJ = gadm("IND.28") - (TRIGARTA_PJ | PUADH | DOAB_RS_N)
JANGALA_RJ = (
    gadm("IND.29.8") | gadm("IND.29.11") | gadm("IND.29.16") | gadm("IND.29.15")
)
KURU_KSETRA_GREATER = KURU_KSETRA_GREATER_HARYANA | PUADH
JANGALA = JANGALA_HARYANA | JANGALA_PJ | JANGALA_RJ

SUB_SUTLEJ_N = (
    gadm("IND.28.14")
    | gadm("IND.28.12")
    | gadm("IND.28.5")
    | gadm("IND.28.7")
    | gadm("IND.28.18")
) - KURU_KSETRA_GREATER
SUB_SUTLEJ_S = (
    gadm("IND.28.3")
    | gadm("IND.28.13")
    | gadm("IND.28.2")
    | gadm("IND.28.20")
    | gadm("IND.28.17")
    | gadm("IND.28.4")
    | gadm("IND.28.19")
    | gadm("IND.6")
) - KURU_KSETRA_GREATER
YAUDHEYA = (
    gadm("IND.12")
    | gadm("IND.25")
    | KURU_KSETRA_GREATER
    | SUB_SUTLEJ_S
    | MADRAKARA
    | SUB_SUTLEJ_N
)
SINDH_N = gadm("PAK.8.3.1") | gadm("PAK.8.3.2") | gadm("PAK.8.3.4")
SINDH_SW = (
    gadm("PAK.8.2.5")
    | gadm("PAK.8.5.1")
    | gadm("PAK.8.2.4")
    | gadm("PAK.8.2.1")
    | gadm("PAK.8.2.2")
    | gadm("PAK.8.2.3")
)
SINDH_SE = gadm("PAK.8.1.8") | gadm("PAK.8.1.1") | gadm("PAK.8.1.6") | gadm("PAK.8.4.2")
SINDH_W_PROPER = gadm("PAK.8.3") | gadm("PAK.8.1.2") | gadm("PAK.8.1.4")
SINDH_W = SINDH_W_PROPER | SINDH_SW
SINDH_E_PROPER = (
    gadm("PAK.8.1.3")
    | gadm("PAK.8.1.7")
    | gadm("PAK.8.4.1")
    | gadm("PAK.8.4.4")
    | gadm("PAK.8.4.3")
    | gadm("PAK.8.1.5")
    | gadm("PAK.8.6.1")
    | gadm("PAK.8.6.2")
    | gadm("PAK.8.6.3")
    | gadm("PAK.8.6.4")
    | gadm("PAK.8.6.5")
)
SINDH_E = SINDH_E_PROPER | SINDH_SE
SINDH_S = SINDH_SE | SINDH_SW
SINDH = SINDH_N | SINDH_W_PROPER | SINDH_E_PROPER | SINDH_S
MASURAKARNA = gadm("PAK.8.3")
MUCUKARNA = gadm("PAK.8.6")
BRAHMANAKA = gadm("PAK.8.4.3") | gadm("PAK.8.4.1") | gadm("PAK.8.1.3") | gadm("PAK.8.1.7") | gadm("PAK.8.1.5") 
SINDHUVAKTRA = SINDH_S - gadm("PAK.8.4.2")

BALOCH = gadm("PAK.2") | gadm("IRN.26")  # gedrosia
INDRAVAKTRA = gadm("PAK.2.2.1")
PARDAYANA = gadm("PAK.2.1.2") 
ARABHATA = gadm("PAK.2.1.7")
DAMANI = gadm("PAK.2.4.1")

AUDICYA = PUNJAB | SINDH

KUTCH = gadm("IND.11.16")
ANARTA = (
    gadm("IND.11.5")
    | gadm("IND.11.18")
    | gadm("IND.11.24")
    | gadm("IND.11.27")
    | gadm("IND.11.4")
    | gadm("IND.11.12")
)
SURASTRA = (
    gadm("IND.11.1")
    | gadm("IND.11.29")
    | gadm("IND.11.20")
    | gadm("IND.11.14")
    | gadm("IND.11.11")
    | gadm("IND.11.25")
    | gadm("IND.11.26")
    | gadm("IND.11.15")
    | gadm("IND.11.13")
    | gadm("IND.11.2")
    | gadm("IND.11.8")
    | gadm("IND.11.7")
)
LATA = (gadm("IND.11") | gadm("IND.8") | gadm("IND.9")) - (KUTCH | ANARTA | SURASTRA)
GUJARAT = KUTCH | ANARTA | SURASTRA | LATA

JHARKHAND_ANGA = (
    gadm("IND.15.22")
    | gadm("IND.15.8")
    | gadm("IND.15.16")
    | gadm("IND.15.5")
    | gadm("IND.15.3")
    | gadm("IND.15.11")
)
JHARKHAND_CHHOTA_NAGPUR = gadm("IND.15") - JHARKHAND_ANGA
WB_CHHOTA_NAGPUR = gadm("IND.36.18")
CHHOTA_NAGPUR = JHARKHAND_CHHOTA_NAGPUR | WB_CHHOTA_NAGPUR
ANGA = BIHAR_ANGA | JHARKHAND_ANGA
PUNDRA_WB = gadm("IND.36.5") | gadm("IND.36.20")
GAUDA_EB = gadm("BGD.5.5")
GAUDA_WB = gadm("IND.36.13") | gadm("IND.36.12")
GAUDA = GAUDA_EB | GAUDA_WB
RADHA = gadm("IND.36.2") | gadm("IND.36.3") | gadm("IND.36.4")
SUHMA = gadm("IND.36.16") | gadm("IND.36.17") | gadm("IND.36.7") | gadm("IND.36.8")
VANGA_WB = gadm("IND.36.11") | gadm("IND.36.14") | gadm("IND.36.15") | gadm("IND.36.19")
PUNDRA_EB = gadm("BGD.5") - GAUDA_EB
VANGA_EB = (
    gadm("BGD.4")
    | gadm("BGD.1")
    | gadm("BGD.3.2")
    | gadm("BGD.3.4")
    | gadm("BGD.3.7")
    | gadm("BGD.3.14")
    | gadm("BGD.3.15")
)
SAMATATA = gadm("BGD") - (VANGA_EB | PUNDRA_EB | GAUDA_EB)
VANGA = VANGA_WB | VANGA_EB
PUNDRA = PUNDRA_WB | PUNDRA_EB
CHATTISGARH_N = (
    gadm("IND.7.19")
    | gadm("IND.7.7")
    | gadm("IND.7.12")
    | gadm("IND.7.21")
    | gadm("IND.7.16")
    | gadm("IND.7.17")
    | gadm("IND.7.25")
    | gadm("IND.7.26")
    | gadm("IND.7.13")
    | gadm("IND.7.3")
)
CHATTISGARH_S = gadm("IND.7") - CHATTISGARH_N
KALINGA_UTKALA = (
    gadm("IND.26.13") | gadm("IND.26.6") | gadm("IND.26.17") | gadm("IND.26.3")
)
KALINGA_PROPER = (
    gadm("IND.26.7")
    | gadm("IND.26.10")
    | gadm("IND.26.11")
    | gadm("IND.26.12")
    | gadm("IND.26.19")
    | gadm("IND.26.24")
    | gadm("IND.26.26")
)
KALINGA_TELUGU = gadm("IND.2.3") | gadm("IND.2.9") | gadm("IND.2.10") | gadm("IND.2.11")
KALINGA = KALINGA_PROPER | KALINGA_TELUGU | KALINGA_UTKALA
UTKALA_PROPER = gadm("IND.26.22") | gadm("IND.26.18") | gadm("IND.26.9")
UTKALA_INNER = (
    gadm("IND.26.1")
    | gadm("IND.26.8")
    | gadm("IND.26.14")
    | gadm("IND.26.28")
    | gadm("IND.26.30")
)
UTKALA = UTKALA_PROPER | KALINGA_UTKALA
KALINGA_GREATER = KALINGA | UTKALA
ODRA = gadm("IND.26") - (KALINGA_PROPER | UTKALA)
GREAT_FOREST_PROPER = ODRA | CHATTISGARH_S
GREAT_FOREST_NORTH = CHATTISGARH_N | UTKALA_PROPER | CHHOTA_NAGPUR
GREAT_FOREST = GREAT_FOREST_NORTH | GREAT_FOREST_PROPER
GREAT_FOREST_GREATER = GREAT_FOREST | UP_KALAKAVANA
BENGAL = ANGA | BIHAR_NORTHEAST | RADHA | SUHMA | GAUDA | PUNDRA | VANGA | SAMATATA

RSIKA = gadm("IND.20.13") | gadm("IND.20.9") | gadm("IND.20.21") | gadm("IND.20.22")
VIDARBHA = (
    gadm("IND.20.2")
    | gadm("IND.20.3")
    | gadm("IND.20.7")
    | gadm("IND.20.2")
    | gadm("IND.20.35")
    | gadm("IND.20.3")
    | gadm("IND.20.34")
    | gadm("IND.20.36")
    | gadm("IND.20.19")
    | gadm("IND.20.5")
    | gadm("IND.20.8")
    | gadm("IND.20.10")
    | gadm("IND.20.11")
)
NANDED_ASMAKA = (
    gadm("IND.20.20.2")
    | gadm("IND.20.20.3")
    | gadm("IND.20.20.5")
    | gadm("IND.20.20.7")
)
NANDED_MULAKA = gadm("IND.20.20") - NANDED_ASMAKA
MULAKA = (
    gadm("IND.20.4")
    | gadm("IND.20.12")
    | gadm("IND.20.14")
    | NANDED_MULAKA
    | gadm("IND.20.25")
    | gadm("IND.32.1")
)
ASMAKA = (
    gadm("IND.20.1")
    | gadm("IND.20.6")
    | gadm("IND.20.16")
    | NANDED_ASMAKA
    | gadm("IND.32.3")
    | gadm("IND.32.8")
)
APARANTA = (
    gadm("IND.20.17")
    | gadm("IND.20.18")
    | gadm("IND.20.24")
    | gadm("IND.20.27")
    | gadm("IND.20.28")
    | gadm("IND.20.33")
    | gadm("IND.20.31")
)
GREATER_PUNE = gadm("IND.20") - (RSIKA | VIDARBHA | MULAKA | ASMAKA | APARANTA)
MAHISAKA = gadm("IND.32.2") | gadm("IND.32.5") | gadm("IND.32.6") | gadm("IND.32.9")
VENGI_TG = gadm("IND.32.4") | gadm("IND.32.7") | gadm("IND.32.10")
VENGI_AP = gadm("IND.2.4") | gadm("IND.2.5") | gadm("IND.2.12")
VENGI = VENGI_TG | VENGI_AP
AP_KANCI = gadm("IND.2.2") | gadm("IND.2.7")
KUNTALA = (
    gadm("IND.16.1")
    | gadm("IND.16.5")
    | gadm("IND.16.15")
    | gadm("IND.16.21")
    | gadm("IND.16.24")
    | gadm("IND.16.6")
    | gadm("IND.16.7")
    | gadm("IND.16.13")
    | gadm("IND.16.16")
    | gadm("IND.16.30")
)
CAUVERIC = (
    gadm("IND.16.17")
    | gadm("IND.16.27")
    | gadm("IND.16.2")
    | gadm("IND.16.3")
    | gadm("IND.16.22")
    | gadm("IND.16.23")
    | gadm("IND.16.25")
    | gadm("IND.16.9")
    | gadm("IND.16.20")
    | gadm("IND.16.8")
)
TULU = gadm("IND.16.28") | gadm("IND.16.12")
KADAMBA = (
    gadm("IND.16.29")
    | gadm("IND.16.4")
    | gadm("IND.16.14")
    | gadm("IND.16.18")
    | gadm("IND.10")
)
COORG = gadm("IND.16.19")
AP_BAYALU = gadm("IND.2") - (AP_KANCI | VENGI | KALINGA)
KA_BAYALU = gadm("IND.16") - (KUNTALA | KADAMBA | CAUVERIC | TULU | COORG)
BAYALU = AP_BAYALU | KA_BAYALU
VENGI_COASTAL = gadm("IND.2.4") | gadm("IND.2.5") | gadm("IND.2.12") | gadm("IND.2.3")
KADAMBA_COASTAL = gadm("IND.10") | gadm("IND.16.29")
DECCAN = (
    PULINDA
    | VIDARBHA
    | RSIKA
    | MULAKA
    | ASMAKA
    | GREATER_PUNE
    | KUNTALA
    | KADAMBA
    | MAHISAKA
    | VENGI
    | BAYALU
    | CAUVERIC
) - (VENGI_COASTAL | gadm("IND.2.8") | KADAMBA_COASTAL)

# tamilakam
## conquer the pondicherries
KANNUR_PONDI = gadm("IND.17.4") | gadm("IND.27.2")  # to kerala
VILUPPURAM_PONDI = gadm("IND.31.31") | gadm("IND.27.3")  # to kanci
NAGAPPATTINAM_PONDI = gadm("IND.31.13") | gadm("IND.27.1")  # to cola
KERALA = gadm("IND.17") | KANNUR_PONDI
MALABAR = KERALA | TULU
TN_KANCI = (
    gadm("IND.31.4")
    | gadm("IND.31.29")
    | gadm("IND.31.30")
    | VILUPPURAM_PONDI
    | gadm("IND.31.2")
    | gadm("IND.31.8")
    | gadm("IND.31.23")
)
KANCI = AP_KANCI | TN_KANCI
PANDYA_PROPER = (
    gadm("IND.31.12")
    | gadm("IND.31.19")
    | gadm("IND.31.22")
    | gadm("IND.31.17")
    | gadm("IND.31.25")
    | gadm("IND.31.27")
    | gadm("IND.31.32")
)
PANDYA = PANDYA_PROPER | gadm(
    "IND.31.9"
)  # adding Kanyakumari, which is strictly Ay land
COLA = (
    gadm("IND.31.16")
    | gadm("IND.31.26")
    | gadm("IND.31.15")
    | gadm("IND.31.1")
    | gadm("IND.31.20")
    | gadm("IND.31.24")
    | NAGAPPATTINAM_PONDI
)
KONGU = gadm("IND.31") - (COLA | PANDYA | KANCI)
AY_PROPER = gadm("IND.17.12") | gadm("IND.31.9")  # Trivandrum + Kanyakumari
AY = AY_PROPER | gadm("IND.17.6") | gadm("IND.17.11")  # south kerala, later venad
EZHIMALA_PROPER = gadm("IND.17.5") | KANNUR_PONDI  # north kerala, later kolattunadu
EZHIMALA = EZHIMALA_PROPER | COORG  # Poozhinadu and Karkanadu
CERA = KERALA - (
    AY | EZHIMALA
)  # central kerala, later calicut (the zamorin one) and kochi
SIMHALA = gadm("LKA")
TAMIL_PROPER = KANCI | COLA | PANDYA | KERALA | KONGU
TAMIL = TAMIL_PROPER | TULU | COORG


NORTH_INDIA = (
    GANGETIC | BRAHMAVARTA | BENGAL | AUDICYA | RJ | MP | GUJARAT | UP_KALAKAVANA
) - PULINDA
ARYAVARTA = UP | BRAHMAVARTA
GY_DOAB = (
    KURU_PROPER
    | PANCALA_S
    | VATSA
    | gadm("IND.34.7")
    | gadm("IND.34.42")
    | gadm("IND.34.43")
)

# more deserts
PAK_THAR = gadm("PAK.8.6") | gadm("PAK.8.4")
PAK_CHOLISTAN = gadm("PAK.7.1")
PAK_THALL = gadm("PAK.7.2.2") | gadm("PAK.7.2.3")

# uncultivated (YYY) or historically unidentified (ZZZ) lands
YYY_MARU = RJ_MARU | PAK_THAR | PAK_CHOLISTAN
YYY_NAIMISA = UP_NAIMISA
YYY_KALAKAVANA = UP_KALAKAVANA
YYY_GREAT_FOREST = GREAT_FOREST
YYY_HIMALAYAN = HIMALAYAN
ZZZ_BIHAR_NORTHEAST = BIHAR_NORTHEAST
ZZZ_BAHAWALPUR = BAHAWALPUR
ZZZ_HADOTI = HADOTI
ZZZ_GREATER_PUNE = GREATER_PUNE
ZZZ_BAYALU = BAYALU





__TERRITORY_INDEX__ = [
    "VRJISTHANA",
    "VARNU",
    "VANAVYA",
    "APRITA",
    "PSEUDOSATTAGYDIA_S",
    "KAPISAYANA",
    "TRYAKSYAYANA",
    "ASVAKAYANA",
    "ASVAYANA",
    "NIGRAHARA",
    "URASA",
    "SAVASA",
    "UDDIYANA",
    "DARADA",
    "LADAKH",
    "HIMALAYAN",
    "KASHMIR",
    "JAMMU",
    "GANDHARA",
    "DOAB_IJ",
    "PAK_THALL",
    "MADRA",
    "MADRA_EE",
    "USINARA",
    "MALAVA",
    "KSUDRAKA",
    "SINDH",
    "TRIGARTA",
    "KUNINDA",
    "AUDUMBARA",
    "GABDIKA",
    "YAKRLOMAN",
    "TILAKHALA",
    "RAJANYA",
    "KUTCH",
    "SURASTRA",
    "ANARTA",
    "LATA",
    "KUKURA",
    "MATSYA",
    "BRAHMAVARTA",
    "KURU_PROPER",
    "KURU_KSETRA_GREATER",
    "JANGALA",
    "PANCALA_N",
    "PANCALA_S",
    "SURASENA",
    "VATSA",
    "KOSALA",
    "KASI",
    "MALLA",
    "VIDEHA",
    "SAKYA",
    "LICCHAVI",
    "MAGADHA",
    "TERAI",
    "AVANTI",
    "AKARA",
    "DASARNA",
    "CEDI",
    "PULINDA",
    "ANGA",
    "GAUDA",
    "RADHA",
    "SUHMA",
    "PUNDRA",
    "VANGA",
    "SAMATATA",
    "LAUHITYA",
    "UTKALA",
    "KALINGA",
    "VIDARBHA",
    "RSIKA",
    "MULAKA",
    "ASMAKA",
    "APARANTA",
    "KUNTALA",
    "KADAMBA",
    "CAUVERIC",
    "MAHISAKA",
    "VENGI",
    "TULU",
    "CERA",
    "AY",
    "EZHIMALA",
    "KANCI",
    "COLA",
    "PANDYA",
    "KONGU",
    "SIMHALA",
    "COORG",
    "GREAT_FOREST",
    "UP_KALAKAVANA",
    "RJ_MARU",
    "UP_NAIMISA",
    "BAYALU",
    "GREATER_PUNE",
    "HADOTI",
    "BIHAR_NORTHEAST",
    "BAHAWALPUR",
    "SIMHALA",
]

