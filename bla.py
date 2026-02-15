import xatra
from xatra.loaders import gadm, naturalearth, polygon, overpass
from xatra.icon import Icon

from xatra.territory_library import *  # https://github.com/srajma/xatra/blob/master/src/xatra/territory_library.py



xatra.BaseOption("Esri.WorldTopoxatra", name="Esri.WorldTopoxatra", default=False)
xatra.BaseOption("OpenStreetxatra", name="OpenStreetxatra", default=False)
xatra.BaseOption("Esri.WorldImagery", name="Esri.WorldImagery", default=False)
xatra.BaseOption("OpenTopoxatra", name="OpenTopoxatra", default=False)
xatra.BaseOption("Esri.WorldPhysical", name="Esri.WorldPhysical", default=True)
xatra.zoom(4)
xatra.focus(30, 78)
xatra.CSS(""".point-label { background:None; border:None; margin-left:-21px; margin-top:24px }
.point-label:before { display:none; }
.general-label-suvarnabhumi { color: #666666;
        text-transform: uppercase;
        font-weight: bold; }
.general-label-suvarnabhumi-kataha { transform: rotate(60deg) !important; }
.general-label-suvarnabhumi-dvipantara { transform: rotate(-20deg) !important; }
.general-label-suvarnabhumi-suvarnabhumi { font-size: 18pt; }
.port-label-suvarnabhumi { color: black; line-height: 1; }
.city-label-suvarnabhumi { color: blue; line-height: 1; }
.flag-label { display: none; }
.general-label-other { color: #666666;
        text-transform: uppercase;
        font-weight: bold; }
.port-label-other { color: black; line-height: 1; }
.city-label-other { color: blue; line-height: 1; }
general-label-other-ocean { font-size: 20px; }
.general-label-other-parasika { transform: rotate(45deg) !important; }
.general-label-other-khuramala { transform: rotate(38deg) !important; }
.general-label-other-dadhimala { transform: rotate(60deg) !important; }
.general-label-other-agnimala { transform: rotate(-20deg) !important; }
.general-label-other-marukantara { transform: rotate(60deg) !important; }
.general-label-other-nilakusamala { font-size: 0.85em; line-height: 1 }
.general-label-other-nalamala { font-size: 0.85em; line-height: 1; transform: rotate(10deg) !important; }
.general-label-other-yavana-big { font-size: 18pt; }
.general-label-other-jambudvipa { font-size: 24pt;
        color: #333; }
.general-label-other-cina { font-size: 18pt; }
.general-label-other-kalayavana { font-size: 18pt; transform: rotate(45deg) !important; }
.flag-label { display: none; }""")

# funny thing AI came up with, not real:
# xatra.Point(
#     label="Kālakācārya",
#     position=[-0.789275, 36.428155]
# )

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
xatra.Text(label="Yāva", position=[-7.3, 110.0], classes="general-label-suvarnabhumi", note=REF_MOTI_CHANDRA_PLAIN)
xatra.Text(
    label="Karpūradvīpa/<br>Barhiṇadvīpa",
    position=[0.0, 114.0],
    classes="general-label-suvarnabhumi",
    note=REF_MOTI_CHANDRA_PLAIN
)
xatra.Text(
    label="Kaṭāha",
    position=[6.0, 100.3],
    classes="general-label-suvarnabhumi general-label-suvarnabhumi-kataha",
    note=REF_MOTI_CHANDRA_PLAIN
)
xatra.Text(
    label="Dvīpāntara",
    position=[0.0, 106.9],
    classes="general-label-suvarnabhumi general-label-suvarnabhumi-dvipantara",
    note=REF_MOTI_CHANDRA_PLAIN
)
xatra.Text(
    label="Suvarṇabhūmi",
    position=[6.053218, 107.823257],
    classes="general-label-suvarnabhumi general-label-suvarnabhumi-suvarnabhumi",
    note=REF_MOTI_CHANDRA_PLAIN
)
xatra.Point(label="Takkasilā", position=[20.70, 92.40], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Kālamukha", position=[19.71, 93.50], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Vesuṅga", position=[16.81, 96.18], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Verāpatha", position=[14.09, 98.19], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Takkola", position=[8.89, 98.27], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Tāṁbraliṅga", position=[3.80, 103.33], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 132"), classes="port-label-suvarnabhumi")
xatra.Point(label="Vaṅga", position=[-2.36, 106.15], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 133"), classes="port-label-suvarnabhumi")
xatra.Point(label="Ailavaddhana", position=[-8.50, 117.21], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 133"), classes="port-label-suvarnabhumi")
xatra.Point(label="Suvarṇakūṭa", position=[11.46, 103.08], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 133"), classes="port-label-suvarnabhumi")
xatra.Point(label="Kamalapura", position=[11.07, 103.68], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. xiv"), classes="port-label-suvarnabhumi")
xatra.Point(label="Samudrapaṭṭaṇa", position=[-0.91, 100.35], icon = PORT_ICON, show_label=True, note=REF_MOTI_CHANDRA.format("p. 141"), classes="port-label-suvarnabhumi")
xatra.Point(label=colon("Suddhamāvati/Thaton", "Telugu explorers or Tissa's son"), position=[17.33, 96.47], icon = CITY_ICON, show_label=True, note = REF_MAJUMDAR.format("p. 31"), classes="city-label-suvarnabhumi")
xatra.Point(label=colon("Saṅkissa/Tagaung", "Abhirāja"), position=[23.5, 96.0], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note = REF_MAJUMDAR.format("p. 31"))
xatra.Point(label=colon("Śrīkṣetra/Pyu", "under Saṅkissa"), position=[18.81, 95.29], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note = REF_MAJUMDAR.format("p. 31"))
xatra.Point(label=colon("Dhaññavatī/Arakanese", "under Saṅkissa"), position=[20.87, 93.06], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note = REF_MAJUMDAR.format("p. 31"))
xatra.Point(label=colon("Vyādhapura/Funan", "Kauṇḍinya I"), position=[11.00, 104.98], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note = REF_MAJUMDAR.format("p. 20"))
xatra.Point(label=colon("Kīrtinagara/Oc Eo", "under Vyādhapura"), position=[10.249203, 105.147056], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 21"))
xatra.Point(label=colon("Tien-Suen", "under Vyādhapura"), position=[9.196281, 99.329105], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 21"))
xatra.Point(label=colon("Kambuja", "Kambu Swayambhuva/Indraprastha prince"), position=[14.901246, 105.868371], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 24"))
xatra.Point(label=colon("Campa", "Śrī Māra"), position=[16.196377, 108.131374], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 25"))
xatra.Point(label=colon("Langkasuka", "Mauryan prince?"), position=[6.759206, 101.307032], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 28"))
xatra.Point(label=colon("??", "Amarāvati-style Buddhist statue found at Sempaga"), position=[-2.316840, 119.128122], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 28"))
xatra.Point(label=colon("Yava", "Hastināpura prince, Deva-varman?"), position=[-6.455765, 110.771262], icon = CITY_ICON, show_label=True, classes="city-label-suvarnabhumi", note=REF_MAJUMDAR.format("p. 33"))
xatra.Flag(value=SEA, label="SUVARṆABHŪMĪ")
xatra.Flag(value=MEDITERRANEAN, label="MEDITERRANEAN")
xatra.Flag(value=GULF, label="GULF")
xatra.Flag(value=AFRICA_EAST_SPOTTY, label="AFRICA_EAST_SPOTTY")
xatra.Flag(value=LEVANT, label="LEVANT")
xatra.Flag(value=IRANIC, label="IRANIC")
xatra.Flag(value=JAMBUDVIPA, label="JAMBUDVĪPA")
xatra.Flag(value=SIMHALA, label="SIMHALA")
xatra.Flag(value=CHINA_PROPER | NORTH_VIETNAM, label="CHINA")
xatra.Flag(value=TARIM, label="UTTARAKURU")
xatra.Flag(value=TIBET, label="BHUTA")
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
xatra.Text(position=[7.526199, 80.774671], classes="general-label-other general-label-other-simhala", label="SIṂHALA")
xatra.Text(position=[31.244868, 53.597872], classes="general-label-other general-label-other-parasika", label="Pārasīka")
xatra.Text(position=[39.36, 83.41], classes="general-label-other general-label-other-uttarakuru", label="UTTARAKURU")
xatra.Text(position=[32.55, 91.32], classes="general-label-other general-label-other-bhota", label="BHOṬA")
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
xatra.Text(position=[43.347301, 11.792144], classes="general-label-other general-label-other-romavisaya", label="Roma-Viṣaya")
xatra.Text(
    label="Valabhāmukha Sea",
    position=[35.392349, 19.468104],
    classes="general-label-other general-label-other-valabhamukha",
    note=REF_MOTI_CHANDRA.format("p. 61, 63"),
)
xatra.Text(position=[33.964831, 27.000472], classes="general-label-other general-label-other-yavana-big", label="Yavana")
xatra.Text(position=[21.407506, 78.480723], classes="general-label-other general-label-other-jambudvipa", label="Jambudvīpa")
xatra.Text(position=[30.750277, 114.330864], classes="general-label-other general-label-other-cina", label="Cīnā")
xatra.Text(position=[10.068956, 38.311893], classes="general-label-other general-label-other-kalayavana", label="Kālayavana?")
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
xatra.Admin(gadm="PAK", level=1, note="""ooga""")