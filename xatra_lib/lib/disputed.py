Z01 = gadm("Z01.14")
Z02 = gadm("Z02.28")
Z03 = gadm("Z03.28") | gadm("Z03.29")
Z04 = gadm("Z04.13")
Z05 = gadm("Z05.35")
Z06 = gadm("Z06.1") | gadm("Z06.6")
Z07 = gadm("Z07.3")
Z08 = gadm("Z08.29")
Z09 = gadm("Z09.35") | gadm("Z09.13")

# sorting the himalayas
CHINESE_CLAIMS_UK = Z05 | gadm("Z09.35")
CHINESE_CLAIMS_HP = gadm("Z09.13") | Z04
CHINESE_CLAIMS_LADAKH = Z03 | Z08  # Aksai Chin
CHINESE_CLAIMS_GILGIT = Z02
CHINESE_CLAIMS_AP = Z07
CHINESE_CLAIMS = (
    CHINESE_CLAIMS_UK
    | CHINESE_CLAIMS_HP
    | CHINESE_CLAIMS_AP
    | CHINESE_CLAIMS_LADAKH
    | CHINESE_CLAIMS_GILGIT
)
