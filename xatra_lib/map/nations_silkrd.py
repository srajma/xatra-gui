iran = xatrahub("/lib/iran_lib")

xatra.Flag(label="VṚJISTHĀNA", value=iran.VRJISTHANA, note="Vijayendra Kumar Mathur (1969), Aitihasik Sthanavali p 870: वृजिस्थान नामक एक ऐतिहासिक स्थान का उल्लेख प्रसिद्ध चीनी यात्री युवानच्वांग ने 'फो-लि शतंगना' नाम से किया है। सम्भवत: यह वर्तमान वज़ीरस्तान (पाकिस्तान) है।")
xatra.Flag(label="VARNU", value=iran.VARNU)
xatra.Flag(label="VANAVYA", value=iran.VANAVYA)
xatra.Flag(label="APRĪTA", value=iran.APRITA, note="or Trīrāvatīka, modern Tirāh.")
xatra.Flag(label="SATTAGYDIA?", value=iran.PSEUDOSATTAGYDIA_S, classes="names-unknown")
xatra.Flag(label="KAMBOJA", value=iran.KAMBOJA)
xatra.Flag(label="KĀPIŚĀYANA", value=iran.KAPISAYANA)
xatra.Flag(label="TRYAKŚYĀYAṆA", value=iran.TRYAKSYAYANA, note = "or Dvīrāvatika, modern Dir; or Madhumant, modern Mohmand.")
xatra.Flag(
    label="AŚVAKĀYANA",
    value=iran.ASVAKAYANA,
    note="The Hastināyanas may have have been cognate with the Aśvakāyanas, or ruled the region around Puṣkalāvatī.",
)
xatra.Flag(label="AŚVĀYANA", value=iran.ASVAYANA)
xatra.Flag(label="NIGRAHĀRA", value=iran.NIGRAHARA)
xatra.Flag(label="URAŚĀ", value=iran.URASA, note="Hazara")
#     xatra.Flag(
#         label="ŚAVASA",
#         value=sr.SAVASA,
#         note="""Of these Kekaya and Savasa may be
#  located between the Jhelum and the Chenab, the first in the
#  south and the second in the north respectively, and Madra and
#  Uśīnara between the Chenab and the Ravi in the north and
#  south respectively. The divisions become clear on the map.
#  The Divyāvadāna refers to the Śvasas in Uttarāpatha with
#  headquarters at Takṣaśilā to which Aśoka was deputed by his
#  father Bindusāra as Viceroy to quell their rebellion. The name
#  Śavasa or Śvasa seems to be preserved in the modern name 
#  Chhibha comprising Punch, Rajauri and Bhimbhara. - VS Agarwala Ch II, Sec 4.""",
#     )
xatra.Flag(label="UḌḌIYĀNA", value=iran.UDDIYANA)
xatra.Flag(label="DARADA", value=ind.DARADA)
xatra.Flag(label="MARASA", value=ind.LADAKH)
xatra.Flag(label="GEDROSIA", value=iran.BALOCH)
xatra.Flag(label="KAMBOJA", value=iran.KAMBOJA)
xatra.Flag(label="MERU", value=iran.MERU)
xatra.Flag(label="ZARANJ", value=iran.ZARANJ)
xatra.Flag(label="KANDAHAR", value=iran.KANDAHAR)
xatra.Flag(label="HERAT", value=iran.HERAT)
xatra.Flag(label="ROHITAGIRI", value=iran.ROHITAGIRI)
xatra.Flag(label="PAKTHA", value=iran.PAKTHA)
xatra.Flag(label="BAHLIKA", value=iran.BACTRIA)
xatra.Flag(label="MARGUS", value=iran.MARGIANA)
xatra.Flag(label="SOGD", value=iran.SOGDIA_PROPER)
xatra.Flag(label="PRAKAṆVA", value=iran.FERGHANA)
xatra.Flag(label="KHWAREZM", value=iran.KHWAREZM)
xatra.Flag(label="KASHGAR", value=iran.KASHGAR)
xatra.Flag(label="KHOTAN", value=iran.KHOTAN)
xatra.Flag(label="AGNI", value=iran.AGNI)
xatra.Flag(label="AKSU", value=iran.AKSU)
xatra.Flag(label="KUCHA", value=iran.KUCHA)
xatra.Flag(label="ROURAN", value=iran.ROURAN)
xatra.Flag(label="QIEMO", value=iran.QIEMO)
xatra.Flag(label="KORLA", value=iran.KORLA)
xatra.Flag(label="TURFAN", value=iran.TURFAN)
xatra.Flag(label="BHOṬA", value=sb.TIBET)
xatra.Flag(label="YYY_HIMALAYAN", classes="wild-tracts", value=ind.HIMALAYAN)
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
    Nations, not states, of the Overland Silk Road in antiquity. 
    Roughly valid in the period 800 BC to 1200, think of it as a 
    first-order approximation or a reference guide. 
    """)

