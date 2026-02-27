ind = xatrahub("/lib/indic_lib")
sb = xatrahub("/lib/sb_lib")
conts = xatrahub("/lib/continents_lib")
arab = xatrahub("/lib/arabia_lib")
iran = xatrahub("/lib/iran_lib")
xatrahub("/map/sea_suvarnabhumi")

CITY_ICON = Icon.geometric("circle", color="blue", icon_size=6, icon_anchor=3)
PORT_ICON = Icon.geometric("square", color="black", icon_size=6, icon_anchor=3)
REF_MOTI_CHANDRA_PLAIN = "Ref: Moti Chandra (1977), Trade and Trade Routes in Ancient India."
REF_MOTI_CHANDRA = "Ref: Moti Chandra (1977), Trade and Trade Routes in Ancient India. {}"
REF_MAJUMDAR = "Ref: RC Majumdar (1979), Ancient Indian colonization in Southeast Asia. {}"

def colon(name, desc=None):
    if desc:
        return f"{name}<br><span style='font-size: 0.7em'>{desc}</span>"
    else:
        return name

xatra.Flag(label="SUVARṆABHŪMĪ", value=conts.SEA)
xatra.Flag(label="MEDITERRANEAN", value=conts.MEDITERRANEAN)
xatra.Flag(label="GULF", value=arabia.GULF)
xatra.Flag(label="AFRICA_EAST_SPOTTY", value=conts.AFRICA_EAST_SPOTTY)
xatra.Flag(label="LEVANT", value=arabia.LEVANT)
xatra.Flag(label="IRANIC", value=iran.IRANIC)
xatra.Flag(label="JAMBUDVĪPA", value=conts.JAMBUDVIPA)
xatra.Flag(label="SIMHALA", value=ind.SIMHALA)
xatra.Flag(label="CHINA", value=sinic.CHINA_PROPER | sb.NORTH_VIETNAM)
xatra.Flag(label="UTTARAKURU", value=iran.TARIM)
xatra.Flag(label="BHUTA", value=sb.TIBET)
xatra.Point(
    label="Dvīpa Sukhadara",
    position=[12.486956, 53.826729],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other"
)
xatra.Point(
    label="Romā",
    position=[41.887902, 12.516424],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other"
)
xatra.Point(
    label="Gaṅgana/Kāliyadvīpa",
    position=[-6.109298, 39.423733],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other",
    note=REF_MOTI_CHANDRA.format("p. 133")
)
xatra.Point(
    label="Apāragaṅgana",
    position=[-7.462715, 39.326029],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other",
    note=REF_MOTI_CHANDRA.format("p. 133")
)
xatra.Point(
    label="Alassaṇḍa/<br>Yavanapura",
    position=[31.210757, 29.919430],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other",
    note=REF_MOTI_CHANDRA.format("p. 133")
)
xatra.Point(
    label="Barbara?",
    position=[10.438412, 45.012126],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other"
)
xatra.Point(
    label="Antākhī",
    position=[36.209129, 36.178443],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other",
    note=REF_MOTI_CHANDRA.format("p. xiv")
)
xatra.Point(
    label="Bāveru",
    position=[32.519873, 44.423970],
    icon=PORT_ICON,
    show_label=True,
    classes="port-label-other"
)
# funny thing AI came up with, not real:
# xatra.Point(
#     label="Kālakācārya",
#     position=[-0.789275, 36.428155]
# )
xatra.Text(
    label="SIṂHALA",
    position=[7.526199, 80.774671],
    classes="general-label-other general-label-other-simhala"
)
xatra.Text(
    label="Pārasīka",
    position=[31.244868, 53.597872],
    classes="general-label-other general-label-other-parasika"
)
xatra.Text(
    label="UTTARAKURU",
    position=[39.36, 83.41],
    classes="general-label-other general-label-other-uttarakuru"
)
xatra.Text(
    label="BHOṬA",
    position=[32.55, 91.32],
    classes="general-label-other general-label-other-bhota"
)
xatra.Text(
    label="Khuramāla Sea/<br>Pārasavāsa Sea",
    position=[26.191326, 52.671155],
    classes="general-label-other general-label-other-khuramala",
    note=REF_MOTI_CHANDRA.format("p. 61"),
)
xatra.Text(
    label="Ratnākara Sea",
    position=[14.0, 63.5449],
    classes="general-label-other general-label-other-ocean general-label-other-ratnakara",
    note=REF_MOTI_CHANDRA.format("p. 44"),
)
xatra.Text(
    label="Mahodadhi Sea",
    position=[14.0, 89.2090],
    classes="general-label-other general-label-other-ocean general-label-other-mahodadhi",
    note=REF_MOTI_CHANDRA.format("p. 44"),
)
xatra.Text(
    label="Dadhimāla Sea",
    position=[20.083571, 38.700488],
    classes="general-label-other general-label-other-dadhimala",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(
    label="Agnimāla Sea",
    position=[12.332840, 47.519639],
    classes="general-label-other general-label-other-agnimala",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(
    label="Marukāntāra Desert",
    position=[18.953132, 35.475510],
    classes="general-label-other general-label-other-marukantara",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(
    label=colon("Nīlakuṣamāla?", "(Suez gulf)"),
    position=[28.576944, 33.147515],
    classes="general-label-other general-label-other-nilakusamala",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(
    label=colon("Nalamāla?", "(old Suez canal)"),
    position=[31.094234, 32.296720],
    classes="general-label-other general-label-other-nalamala",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(
    label="Yavana",
    position=[39.134265, 21.801574],
    classes="general-label-other general-label-other-yavana",
    note=REF_MOTI_CHANDRA.format("p. 133"),
)
xatra.Text(
    label="Parama-yavana",
    position=[38.453380, 29.463347],
    classes="general-label-other general-label-other-paramayavana",
    note=REF_MOTI_CHANDRA.format("p. 133"),
)
xatra.Text(
    label="Roma-Viṣaya",
    position=[43.347301, 11.792144],
    classes="general-label-other general-label-other-romavisaya",
)
xatra.Text(
    label="Valabhāmukha Sea",
    position=[35.392349, 19.468104],
    classes="general-label-other general-label-other-valabhamukha",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
# IT'S DOING KALAKACARYA AGAIN!!!
# xatra.Text(
#     label="Kālakācārya",
#     position=[-0.789275, 36.428155],
#     classes="general-label-other general-label-other-kalakacarya",
#     note="p. 61, 63",
# ),
xatra.Text(
    label="Yavana",
    position=[33.964831, 27.000472],
    classes="general-label-other general-label-other-yavana-big",
)
xatra.Text(
    label="Jambudvīpa",
    position=[21.407506, 78.480723],
    classes="general-label-other general-label-other-jambudvipa",
)
xatra.Text(
    label="Cīnā",
    position=[30.750277, 114.330864],
    classes="general-label-other general-label-other-cina",
)
xatra.Text(
    label="Kālayavana?",
    position=[10.068956, 38.311893],
    classes="general-label-other general-label-other-kalayavana",
)

xatra.CSS("""
    .general-label-other {
        color: #666666;
        text-transform: uppercase;
        font-weight: bold;
    }
    .port-label-other {color: black; line-height: 1;}
    .city-label-other {color: blue; line-height: 1;}
    
    general-label-other-ocean {
        font-size: 20px;
    }
    .general-label-other-parasika {
        transform: rotate(45deg) !important;
    }
    .general-label-other-khuramala {
        transform: rotate(38deg) !important;
    }
    .general-label-other-dadhimala {
        transform: rotate(60deg) !important;
    }
    .general-label-other-agnimala {
        transform: rotate(-20deg) !important;
    }
    .general-label-other-marukantara {
        transform: rotate(60deg) !important;
    }
    .general-label-other-nilakusamala {
        font-size: 0.85em; line-height: 1
    }
    .general-label-other-nalamala {
        font-size: 0.85em; line-height: 1; transform: rotate(10deg) !important;
    }
    .general-label-other-yavana-big {
        font-size: 18pt;
    }
    .general-label-other-jambudvipa {
        font-size: 24pt;
        color: #333;
    }
    .general-label-other-cina {
        font-size: 18pt;
    }
    .general-label-other-kalayavana {
        font-size: 18pt; transform: rotate(45deg) !important;
    }
    .flag-label {display: none;}
""")


if __name__ == "__main__":
    xatra.BaseOption("Esri.WorldTopoxatra")
    xatra.BaseOption("OpenStreetxatra")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoxatra")
    xatra.BaseOption("Esri.WorldPhysical", default=True)
    xatra.TitleBox(f"""
    Sea routes of India < 300 AD. Southeast Asia shows states and colonies in 1st and 2nd centuries. 
    <br><br>
    <b>Sources:</b><br>
    RC Majumdar (1979), Ancient Indian colonization in Southeast Asia. p. 20-33.<br>
    Moti Chandra (1977), Trade and Trade Routes in Ancient India. p. 132-133, xiv
    <br><br>
    {PORT_ICON.to_html()} <span style="color:black">Cities and ports mentioned in Indian literature</span><br>
    {CITY_ICON.to_html()} <span style="color:blue">Capitals of Indian(-ized) states known from local or Chinese history</span><br><br>
    """)
    xatra.zoom(4)
    xatra.focus(30.0,78.0)
