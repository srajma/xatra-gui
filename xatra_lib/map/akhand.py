ind = xatrahub("/lib/indic_lib")
sb = xatrahub("/lib/sb_lib")
conts = xatrahub("/lib/continents_lib")
arab = xatrahub("/lib/arabia_lib")
iran = xatrahub("/lib/iran_lib")
china = xatrahub("/lib/sinic_lib")
north = xatrahub("/lib/north_lib")

# <lib>

FUNDAMENTAL_COLONIES = conts.SEA | ind.NEI_HIM | iran.TARIM | arabia.SOCOTRA
BRIEF_COLONIES = (
    iran.BALOCH
    | iran.KANDAHAR
    | iran.ZARANJ
    | iran.AFG_MISC
    # | KAMBOJA
    # | YANA
    | iran.BACTRIA
    # | MARGIANA
    # | SOGDIA
    | iran.MERU
    | china.MONGOLIA
    | arab.MITANNI
    | arab.ARMENIA
)
FUNDAMENTAL_HB = sb.TIBET | china.JAPAN | china.KOREA | iran.SOGDIA | iran.MARGIANA
DEEP_INFLUENCE = china.CHINA_PROPER | china.MANCHURIA | north.BUDDHIST_RUSSIA | sb.NORTH_VIETNAM
EXPLORED = (conts.MEDITERRANEAN_EAST | conts.AFRICA_EAST_SPOTTY | arabia.GULF | arabia.LEVANT | iran.IRANIC) - (
    DEEP_INFLUENCE
    | FUNDAMENTAL_HB
    | BRIEF_COLONIES
    | FUNDAMENTAL_COLONIES
    | conts.SUBCONTINENT_PROPER
    | ind.DARADA
    | iran.KAMBOJA
    | iran.YANA
)

PRATIHARA_RAIDS = (
    gadm("IRN.11")
    | gadm("IRN.3")
    | gadm("IRN.15")
    | gadm("IRQ.2")
    | gadm("ARE")
    | gadm("OMN.2")
)  # | gadm("OMN.3") | gadm("OMN.11")

# </lib>

xatra.Flag(label="INDIAN CORE", value=conts.SUBCONTINENT_PROPER, classes="indian-core")
xatra.Flag(
    label="FUNDAMENTAL COLONIES",
    value=FUNDAMENTAL_COLONIES,
    classes="fundamental-colonies",
)
xatra.Flag(label="DARADA", value=ind.DARADA, classes="borderline")
xatra.Flag(label="KAMBOJA", value = ind.GREATER_KAMBOJA, classes="borderline")
xatra.Flag(label="HIMALAYAS", value=ind.YYY_HIMALAYAN - BRIEF_COLONIES - ind.DARADA - iran.GREATER_KAMBOJA - sb.TIBET, classes="borderline")
xatra.Flag(label="BRIEF COLONIES", value=BRIEF_COLONIES, classes="brief-colonies")
xatra.Flag(
    label="FUNDAMENTALLY HINDU/BUDDHIST",
    value=FUNDAMENTAL_HB,
    classes="fundamentally-hindu-buddhist",
)
xatra.Flag(label="DEEP INFLUENCE", value=DEEP_INFLUENCE, classes="deep-influence")
xatra.Flag(label="RAIDED", value=PRATIHARA_RAIDS, classes="raided")
xatra.Flag(label="EXPLORED", value=EXPLORED, classes="explored")
xatra.CSS(r"""
.indian-core {fill: #740001; color: #740001 !important;}
.fundamental-colonies {fill: #e80000; color: #e80000 !important;}
.brief-colonies {fill: #fc4e2b; color: #fc4e2b !important;}
.fundamentally-hindu-buddhist {fill: #f5820b; color: #f5820b !important;}
.deep-influence {fill: #a425d6; color: #a425d6 !important;}
.raided {fill: #936a27; color: #936a27 !important;}
.explored {fill: #698db3; color: #698db3 !important;}
.borderline {fill: #ff0000; color: #ff0000 !important;}
""")

if __name__ == "__main__":
    xatrahub("/map/rivers_gangetic")
    xatrahub("/map/rivers_peninsular")
    xatrahub("/map/rivers_saptasindhu")
    xatrahub("/map/rivers_silkrd")

    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")

    xatra.TitleBox("""
Indian interactions with the world.<br>
<b>Indian core</b>: India proper<br>
<b>Fundamentally Indian</b>: Countries whose civilizations were fundamentally an Indian endeavour.<br>
<b>Brief occupation:</b> Countries that were ruled by an Indian for a brief period of time.<br>
<b>Fundamentally Hindu/Buddhist:</b> Countries whose civilizations were fundamentally Hindu/Buddhist, but no direct Indian rule.<br>
<b>Deep Influence:</b> Countries that were significantly influenced by Indiian religion and philosophy.<br>
<b>Raided:</b> Brief raids in the 7th (by Chalukyas? Or Chach of Sindh?) and 9th centuries (by the Pratiharas).<br>
<b>Explored:</b> Countries that were visited by Indians in antiquity.<br>
""")
    
    xatra.zoom(4)
    xatra.focus(27.2156, 76.0254)