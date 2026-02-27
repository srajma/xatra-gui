disp = xatrahub("/lib/disputed")
ind = xatrahub("/lib/indic_lib")
sb = xatrahub("/lib/sb_lib")
iran = xatrahub("/lib/iran_lib")
arab = xatrahub("/lib/arabia_lib")


# big regions
SUBCONTINENT = (
    gadm("IND")
    | gadm("PAK")
    | gadm("AFG")
    | gadm("BGD")
    | gadm("LKA")
    | gadm("NPL")
    | gadm("BTN")
) | disp.CHINESE_CLAIMS

SUBCONTINENT_PROPER = SUBCONTINENT - (
    iran.CENTRAL_ASIA | ind.INNER_KAMBOJA | ind.HIMALAYAN | ind.ANDAMAN_NICOBAR
)  | ind.TERAI | ind.URASA | ind.UDDIYANA | ind.ASVAKAYANA # | ind.DARADA

SEA_MARITIME = (
    sb.SUMATRA
    | sb.JAVA
    | sb.BORNEO
    | sb.SULAWESI
    | sb.LESSER_SUNDA
    | sb.MALUKU
    | sb.PAPUA_IDN
    | sb.MALAY_PENINSULA
    | sb.KEPULAUAN
    | sb.BANGKA
    | sb.ANDAMAN_NICOBAR
    | sb.PHILIPPINES
)
SEA_MAINLAND = (
    sb.SIAM | sb.BURMA | sb.LAOS | sb.KHMER | sb.CHAM | sb.SIAM_BURMA_INTERM | sb.KAREN | sb.TIBET_BURMA_INTERM
)
SEA = SEA_MARITIME | SEA_MAINLAND
SEA_GREATER = SEA | sb.TIBET | ind.NEI_HIM
INDOSPHERE = SUBCONTINENT | iran.CENTRAL_ASIA | iran.TARIM | sb.TIBET | SEA | ind.HIMALAYAN
JAMBUDVIPA = SUBCONTINENT_PROPER - ind.SIMHALA

MEDITERRANEAN_EAST = (
    gadm("GRC")
    | gadm("TUR")
    | gadm("CYP")
    | gadm("EGY")
    | gadm("ALB")
    | gadm("BIH")
    | gadm("HRV")
    | gadm("ITA")
    | gadm("MLT")  # not downloaded
    | gadm("MNE")
    | gadm("SVN")
    | gadm("ISR")
    | gadm("PSE")
    | gadm("LBN")
    | gadm("SDN")
) - (
    gadm("EGY.14")
    | gadm("EGY.14")
    | gadm("SDN.10")
    | gadm("SDN.8")
    | gadm("SDN.9")
    | gadm("SDN.4")
    | gadm("SDN.14")
    | gadm("SDN.5")
    | gadm("SDN.17")
    | gadm("SDN.15")
    | gadm("SDN.16")
)

MEDITERRANEAN_WEST = (
    gadm("ESP")
    | gadm("FRA.11")
    | gadm("FRA.13")
    | gadm("MCO")  # not downloaded
    | gadm("PRT")
    | gadm("AND")  # not downloaded
    | gadm("GIB")  # not downloaded
    | gadm("MAR")
    | gadm("DZA")
    | gadm("LBY")
    | gadm("TUN")
) - (
    gadm("DZA.18")
    | gadm("DZA.33")
    | gadm("DZA.20")
    | gadm("DZA.22")
    | gadm("DZA.41")
    | gadm("DZA.1")
    | gadm("DZA.17")
    | gadm("DZA.7")
    | gadm("DZA.44")
    | gadm("LBY.17")
    | gadm("LBY.3")
    | gadm("LBY.22")
    | gadm("LBY.14")
    | gadm("LBY.21")
    | gadm("LBY.18")
    | gadm("LBY.14")
    | gadm("LBY.16")
    | gadm("LBY.5")
    | gadm("LBY.9")
    | gadm("LBY.6")
)
MEDITERRANEAN = MEDITERRANEAN_EAST | MEDITERRANEAN_WEST

AFRICA_EAST_SPOTTY = gadm("SOM") | gadm("TZA") | gadm("DJI") | gadm("ERI") | gadm("MDG")

INDIAN_OCEAN = (
    SUBCONTINENT_PROPER
    | SEA
    | arab.GULF
    | AFRICA_EAST_SPOTTY
    | iran.IRANIC
    | arab.LEVANT
    | MEDITERRANEAN
)

# WORLD = (
#     INDOSPHERE
#     | INDIAN_OCEAN
#     | BUDDHIST_RUSSIA
#     | CHINA_PROPER
#     | NORTH_VIETNAM
#     | JAPAN
#     | KOREA
#     | MONGOLIA
#     | ARMENIA
#     | SOCOTRA
# )
