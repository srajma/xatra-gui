# CITY_ICON = None
# PORT_ICON = Icon.builtin("marker-icon-red.png")
# CITY_ICON = Icon.builtin("city-nocircle.png", icon_size=(24,24), icon_anchor=(12,12))
# PORT_ICON = Icon.builtin("port.svg", icon_size=(24,24), icon_anchor=(12,12))
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

# Ports
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

# Colonies
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


xatra.CSS(r"""
    .point-label {background:None; border:None; margin-left:-21px; margin-top:24px}
    .point-label:before {display:none;}
    .general-label-suvarnabhumi {
        color: #666666;
        text-transform: uppercase;
        font-weight: bold;
    }
    .general-label-suvarnabhumi-kataha {
        transform: rotate(60deg) !important;
    }
    .general-label-suvarnabhumi-dvipantara {
        transform: rotate(-20deg) !important;
    }
    .general-label-suvarnabhumi-suvarnabhumi {
        font-size: 18pt;
    }
    .port-label-suvarnabhumi {color: black; line-height: 1;}
    .city-label-suvarnabhumi {color: blue; line-height: 1;}
    .flag-label {display: none;}
    """)

if __name__ == "__main__":
    sb = xatrahub("/map/nations_suvarnabhumi")
    
    xatra.BaseOption("Esri.WorldTopoxatra")
    xatra.BaseOption("OpenStreetxatra")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoxatra")
    xatra.BaseOption("Esri.WorldPhysical", default=True)

    xatra.TitleBox(f"""
    Earliest recorded Indian colonies and states in Southeast Asia, c. 1st and 2nd centuries. 
    <br><br>
    <b>Sources:</b><br>
    <br>
    RC Majumdar (1979), Ancient Indian colonization in Southeast Asia. p. 20-33.
    <br>
    Moti Chandra (1977), Trade and Trade Routes in Ancient India. p. 132-133, xiv
    <br><br>
    {PORT_ICON.to_html()} <span style="color:black">Cities and ports mentioned in Indian literature</span><br>
    {CITY_ICON.to_html()} <span style="color:blue">Capitals of Indian(-ized) states known from local or Chinese history</span><br><br>
    """)