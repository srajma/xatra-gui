sb = xatrahub("/lib/sb_lib")

xatra.Flag(label="ZZZ_TIBET_BURMA_INTERM", classes="names-unknown", value=sb.TIBET_BURMA_INTERM)
xatra.Flag(label="ZZZ_YUNNAN_BURMA_INTERM", classes="names-unknown", value=sb.YUNNAN_BURMA_INTERM)
xatra.Flag(label="ZZZ_KAREN", classes="names-unknown", value=sb.KAREN)
xatra.Flag(label="ZZZ_SIAM_BURMA_INTERM", classes="names-unknown", value=sb.SIAM_BURMA_INTERM)
xatra.Flag(label="BURMA_UPPER", value=sb.BURMA_UPPER)
xatra.Flag(label="BURMA_LOWER", value=sb.BURMA_LOWER)
xatra.Flag(label="SIAM", value=sb.SIAM)
xatra.Flag(label="LAOS", value=sb.LAOS)
xatra.Flag(label="KHMER", value=sb.KHMER)
xatra.Flag(label="CHAM", value=sb.CHAM)
xatra.Flag(label="NORTH_VIETNAM", value=sb.NORTH_VIETNAM)
xatra.Flag(label="BORNEO", value=sb.BORNEO)
xatra.Flag(label="MALAY_PENINSULA", value=sb.MALAY_PENINSULA)
xatra.Flag(label="SUMATRA", value=sb.SUMATRA)
xatra.Flag(label="JAVA", value=sb.JAVA)
xatra.Flag(label="ZZZ_LESSER_SUNDA", classes="names-unknown", value=sb.LESSER_SUNDA)
xatra.Flag(label="ZZZ_MALUKU", classes="names-unknown", value=sb.MALUKU)
xatra.Flag(label="ZZZ_SULAWESI", classes="names-unknown", value=sb.SULAWESI)
xatra.Flag(label="ZZZ_KEPULAUAN", classes="names-unknown", value=sb.KEPULAUAN)
xatra.Flag(label="ZZZ_BANGKA", classes="names-unknown", value=sb.BANGKA)
xatra.Flag(label="ANDAMAN_NICOBAR", value=sb.ANDAMAN_NICOBAR)
xatra.CSS(r"""
.names-unknown {fill: #444444; color: #444444 !important;}
.wild-tracts {fill: #888888; color: #888888 !important;}
.flag-label {font-size: 10px}
.path-label {font-size: 10px}
.river-label {font-size: 10px}
"""
)

if __name__ == "__main__":
    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")

    xatra.TitleBox("""
    Nations, not states, of the Maritime Silk Road in antiquity. 
    Roughly valid in the period 800 BC to 1200, think of it as a 
    first-order approximation or a reference guide. 
    """)

