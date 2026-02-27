sb = xatrahub("/lib/sb_lib")
iran = xatrahub("/lib/iran_lib")

MONGOLIA = gadm("MNG") | gadm("CHN.19")
MANCHURIA = gadm("CHN.11") | gadm("CHN.17") | gadm("CHN.18")
CHINA_PROPER = gadm("CHN") - (sb.TIBET | iran.XINJIANG | MANCHURIA | MONGOLIA)
JAPAN = gadm("JPN")
KOREA = gadm("KOR") | gadm("PRK")
NORTH_VIETNAM = sb.NORTH_VIETNAM

__TERRITORY_INDEX__ = [
    "CHINA_PROPER",
    "JAPAN",
    "KOREA",
    "MONGOLIA",
    "MANCHURIA"
]