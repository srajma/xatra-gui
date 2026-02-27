ind = xatrahub("/lib/indic_lib")
iran = xatrahub("/lib/iran_lib")

MOUNTAIN_ICON = Icon.geometric("triangle", color="#964B00", size=15)

xatra.Flag(label="PRAKAṆVA", value=iran.FERGHANA)
xatra.Flag(label="VṚKA", value=iran.HYRCANIA)
xatra.Flag(label="PĀRTHAVA", value=iran.PARTHIA)
xatra.Flag(label="PĀRŚAVA", value=iran.PERSIA, note="V.S. Agarwala Ch VII, Sec 8 p 446.")
xatra.Flag(label="DĀMANI", value=iran.DAMANI, note="V.S. Agarwala Ch VII, Sec 8 p 444.")
xatra.Flag(label="HĀRAHŪRAKA", value=iran.KANDAHAR, note="""
Its own native place is the commentary on such of its various forms iis Kāpīśāyana
and Hārahūraka: (Arth. Trans. p. 145; Text. II.25). Obviously there were two varieties
of the grape wine, the Kāpīśāyana produced in the region round Kāpīśī in north
Afghanistan, and Hārahūraka in the south in the valley of
the Harahvaiti or Arghandab.* The black raisins are still
called harahūra, and it is possible that the Kāpīśāyana or
northern variety of wine was made from green and the
Hārahūraka or Kandhar wine from black grapes.
- V.S. Agarwala Ch III Sec 6 p 117.
""")
xatra.Flag(label="SĀRAVA", value=iran.HERAT, note="""
It may be noted that Sarayu was also the name of a river in remote Rigvedic India
flowing past Herat (derived from Hari-Rud; cf. Old-Persian
Harayu from Vedic Sarayu). Darius I (516 B.C.) in his inscription mentions Haraiva,
the people of Harayū, equal to Pāṇini’s Sārava. In the Elamite version of the Behistun
inscription occurs the name Arriya (=Haraiva=Gk. Aria with its capital at Herat).
""")
xatra.Flag(label="BĀLHĪKA", value=iran.BACTRIA)
xatra.Flag(label="ANDHAKAVARTA", value=iran.ANDHAKAVARTA, note="V.S. Agarwala Ch VII Sec 7 p 435.")
xatra.Flag(label="ROHITAGIRI", value=iran.ROHITAGIRI)
xatra.Flag(label="PAKTHA", value=iran.PAKTHA)
xatra.Flag(label="DVYAKṢĀYAṆA", value=iran.AFG_MERU)
xatra.Flag(label="UḌḌIYĀNA", value=iran.UDDIYANA)
xatra.Flag(label="APRĪTA", value=iran.APRITA, note="or Trīrāvatīka, modern Tirāh. Modern Afridis.")
xatra.Flag(label="KĀPIŚĀYANA", value=iran.KAPISAYANA)
xatra.Flag(label="TRYAKŚYĀYAṆA", value=iran.TRYAKSYAYANA, note = "or Dvīrāvatika, modern Dir; or Madhumant, modern Mohmand.")
xatra.Flag(label="KAMBOJA", value=iran.KAMBOJA, note="Kamboja is usually associated with Kabul, but Pāṇini has associated it with the Meru (Pamir) mountains.")
xatra.Flag(
    label="AŚVAKĀYANA",
    value=iran.ASVAKAYANA,
    note="The Hastināyanas ruled the region around Puṣkalāvatī.",
)
xatra.Flag(label="MĀLĀVAT", value=gadm("PAK.5.6.3"), note="""VS Agarwala Ch II Sec 3 p 41: Patāñjali gives several new names of mountain-dwellers, of
which Mālāvat (II.287) is noteworthy as corresponding to 
Mallkand, the mountainous district north of Dargai, the home 
of the Dargalas in the country south of the Swat river. """)
xatra.Flag(label="AŚVĀYANA", value=iran.ASVAYANA)
xatra.Flag(label="NIGRAHĀRA", value=iran.NIGRAHARA)
xatra.Flag(
    label="DĀRADA",
    value=ind.DARADA,
    note="Inhabited by Dardic peoples such as the Piśācas.",
)
xatra.Flag(
    label="KAMBOJA?",
    value=iran.TJK_MERU,
    note="Kamboja is usually associated with Kabul, but Pāṇini has associated it with the Meru (Pamir) mountains.",
)
xatra.Flag(label="URAŚĀ", value=ind.URASA, note="Hazara")
xatra.Flag(
    label="ŚAVASA",
    value=ind.SAVASA,
    note="""Of these Kekaya and Savasa may be
located between the Jhelum and the Chenab, the first in the
south and the second in the north respectively, and Madra and
Uśīnara between the Chenab and the Ravi in the north and
south respectively. The divisions become clear on the xatra.
The Divyāvadāna refers to the Śvasas in Uttarāpatha with
headquarters at Takṣaśilā to which Aśoka was deputed by his
father Bindusāra as Viceroy to quell their rebellion. The name
Śavasa or Śvasa seems to be preserved in the modern name 
Chhibha comprising Punch, Rajauri and Bhimbhara. - VS Agarwala Ch II, Sec 4.""",
)
xatra.Flag(label="GLAUCUKAYĀNAKA", value=ind.GLAUCUKAYANAKA, note ="""
The free clan called the Glaukanikoi (identical with the Glaucukāyanakas of the
Kaśikā on Panini IV.3.99) whose country lay in the fertile and populous regions
lying in the south of Kaśmīr (the Bhimber and Rajauri districts) between the upper courses of
the Jhelum and the Chenab and the Ravi, had as many as thirty-seven cities, the smallest
of which contained not fewer than 5,000 inhabitants, while many contained upwards of
10,000. - VS Agarwala Ch II, Sec 5 p 73. The Abisares of Greek record was also located here
at the same location, which is a bit odd.
""")
xatra.Flag(label="KAŚMĪRA", value=ind.KASHMIR)
xatra.Flag(label="GANDHĀRA", value=ind.GANDHARA, note="perhaps the Hastināyanas, i.e. an elephant-expedition force, ruled here.")
xatra.Flag(label="VṚJISTHĀNA", value=iran.VRJISTHANA, note="Vijayendra Kumar Mathur (1969), Aitihasik Sthanavali p 870: वृजिस्थान नामक एक ऐतिहासिक स्थान का उल्लेख प्रसिद्ध चीनी यात्री युवानच्वांग ने 'फो-लि शतंगना' नाम से किया है। सम्भवत: यह वर्तमान वज़ीरस्तान (पाकिस्तान) है।")
xatra.Flag(label="VANAVYA", value=iran.VANAVYA)
xatra.Flag(label="VARNU", value=iran.VARNU)
xatra.Flag(label="KEKAYA", value=ind.DOAB_IJ)
xatra.Flag(
    label="SINDHU",
    value=ind.PAK_THALL,
    note=""""Sindhu as a janapada may be identified with Sind-Sāgar Doāb,
the region between the Jhelum and the Indus. Most of it is now the sandy desert
of Thal." (VS Agarwala Ch II, Sec 4.)""",
)
xatra.Flag(label="MADRA", value=ind.MADRA)
xatra.Flag(
    label="UŚĪNARA",
    value=ind.USINARA,
    note="Equivalent to Śibi/Śivi. Agalasseis of Greek accounts also dwelled somewhere here.",
)
xatra.Flag(label="MĀLAVA", value=ind.MALAVA)
xatra.Flag(label="KṢUDRAKA", value=ind.KSUDRAKA)
#     xatra.Flag(label="AMBAṢṬHA", value=gadm("PAK.7.1.2"), note="""The Abastanoi/Sambasta of Greek accounts are mentioned to the South of the
#  Mālavas, see e.g. <a href='https://www.ibiblio.org/britishraj/Jackson2/chapter04.html'>ibiblio.org/britishraj/Jackson2/chapter04.html</a>.
#  The
# """)
xatra.Flag(label="MADRA_EE", value=ind.MADRA_EE, classes="flag-grey")
xatra.Flag(label="MADRAKĀRA", value=ind.MADRAKARA)
xatra.Flag(
    label="TRIGARTA",
    value=ind.TRIGARTA,
    note="Trigarta, Audumbara, Tilakhala, Rājanya -- all ruled this region",
)
xatra.Flag(label="KUṆINDA", value=ind.KUNINDA, note="or Kulinda, or Kālakūṭa")
xatra.Flag(label="BHĀRADVAJA", value=gadm("IND.35.6"))
xatra.Flag(label="RAṄKU", value=gadm("IND.35.1"))
xatra.Flag(label="AUDUMBARA", value=ind.AUDUMBARA)
xatra.Flag(label="GABDIKA", value=ind.GABDIKA)
xatra.Flag(label="TILAKHALA", value=ind.TILAKHALA)
xatra.Flag(label="RĀJANYA", value=ind.RAJANYA)
xatra.Flag(label="KURUKṢETRA", value=ind.KURU_KSETRA_GREATER)
xatra.Flag(label="KURUJANGALA", value=ind.KURU_JANGALA)
xatra.Flag(label="YAUDHEYA", value=ind.YAUDHEYA)
xatra.Flag(
    label="PĀRASKARA",
    value=ind.YYY_MARU,
    classes="flag-grey",
    note="""Pāraskara (VI.1.157). Tliis is mentioned in the gaṇa Pāraskara-prabhṛti.
Patañjali treats it as a country (Pāraskara deśaḥ, III.96). The name corresponds 
to Thara-Pārkara (Thara being the Sindhi form of Thala meaning dry country or desert, 
as opposed to Kachchha or jāṅgala country), one of the biggest districts of Sindh which
once denoted the whole of its south-eastern part up to the coast of the Great Rann
of Kachchha or Kachchha-Iriṇa. The Ṛktantra takes the name Pāraskara as that of a mountain,
and the term Parakara for non-mountainous region, such as the Thar-Parkar district (Pāra parvate,
IV.5.1O, Suryakant's edition, p. 41). - VS Agarwala Ch II, Sec 4.""",
)
xatra.Flag(label="MATSYA", value=ind.MATSYA)
xatra.Flag(
    label="SĀLVA",
    value=ind.SALVA,
    note="""
V.S. Agarwala Ch IV, Sec 3: A confederacy of tribes including Ajamīḍha, Ajakranda, Bodha, Bhūliṅga.
V.S. Agarwala Ch II, Sec 4: Also mentioned are Sālveya (=Sālvaputra=Sālveyaka), Sālvavayava. The Kāṣikā
also describes the Udumbara, Tilakhala, Yugandhara, Śaradaṇḍa and Madrakāra as being Sālva tribes.
""",
)
xatra.Flag(label="SAUVIRA", value=ind.SINDH)
xatra.Flag(label="MASURAKARṆA", value=ind.MASURAKARNA)
xatra.Flag(label="MUCUKARṆA", value=ind.MUCUKARNA)
xatra.Flag(label="BRĀHMAṆAKA", value=ind.BRAHMANAKA)
xatra.Flag(label="INDRAVAKTRA", value=iran.INDRAVAKTRA, note="V.S. Agarwala Ch 2, Sec 5 p 65-66. Inhabited by Kitavāḥ, Pāradāḥ, Vairāmāḥ peoples.")
xatra.Flag(label="SINDHUVAKTRA", value=ind.SINDHUVAKTRA, note="V.S. Agarwala Ch 2, Sec 5 p 65-66.")
xatra.Flag(label="PĀRDĀYANA", value=iran.PARDAYANA, note="V.S. Agarwala Ch 2, Sec 5 p 65-66. Vārteyas also dwelled here (V.S. Agarwala Ch VII Sec 8 p 450).")
xatra.Flag(label="ĀRABHAṬA", value=iran.ARABHATA, note="V.S. Agarwala Ch 2, Sec 5 p 65-66.")
xatra.Flag(label="AGNI", value=ind.KUTCH, note="Kaccha. Vibhujāgni = Great Rann of Kutch; Kāṇḍāgni = Little Rann of Kutch. V.S. Agarwala Ch 2, Sec 5 p 65-66.")
xatra.Flag(label="SURĀṢṬRA", value=ind.SURASTRA, note="Dāru-kaccha.")
xatra.Flag(label="PIPPALĪKACCHA", value=ind.LATA, note="Lata")
xatra.Flag(label="ANARTA", value=ind.ANARTA)
# Glausai, Kathaioi. Phegus, Adrestians

xatra.Point(label="Takṣaśilā", position=[33.7519137, 72.7970137])
xatra.Point(label="Aṭaka", position=[33.7738058, 72.3291857])
xatra.Point(
    label="Puṣkalāvatī",
    position=[34.1682553, 71.7066247],
    note="The Hastināyanas may have ruled this region; or they may have been cognate with the Aśvakāyanas.",
)
xatra.Point(label="Śalātura", position=[34.0484722, 72.3630084])
xatra.Point(label="Kapiśi", position=[34.9446078, 69.2316018])
xatra.Point(label="Bamiyan", position=[34.8128, 67.7801507])
xatra.Point(label="Varaṇā", position=[34.8338387, 72.8750666], note="Aornos")
xatra.Point(label="Maśakāvatī", position=[34.6468965, 72.0200283], note="Massaga")
xatra.Point(label="Dvārka", position=[38.1856541, 70.6029253])
xatra.Point(label="Mauñjāyana", position=[36.0197222, 70.771314])
xatra.Point(label="Apakara", position=[31.6257828, 71.0385037])
xatra.Point(label="Śākala", position=[32.4833721, 74.4599975], note='V.S. Agarwala Ch II, Sec 5 p 72 locates Śāṅgala and the Kaṭhas to be in Jhang district in Uśīnara, and distinct from Śākala; but this seems to no longer be the view.')
xatra.Point(label="Cakravāla", position=[32.9306578, 72.7654423])
xatra.Point(label="Śibipura", position=[30.8331294, 72.0653991])
xatra.Point(label="Barbara", position=[24.7538782, 67.5180803])
xatra.Point(label="Pāṭanaprastha", position=[32.2703182, 75.6312559])
xatra.Point(label="Campa", position=[32.5473465, 76.1106229])
xatra.Point(label="Gabḍikā", position=[32.4428475, 76.513443])
xatra.Point(label="Paṭaccara", position=[28.3247889,76.77218], note="VS Agarwala Ch II, Sec 4 p 62")
xatra.Point(label="Kuluṭa", position=[31.9545839, 77.0906928])
xatra.Point(label="Udbhāṇḍa", position=[33.8968548,72.2461023], note="""On this route lay the town called Udbhāṇḍa (Ohind) as the
destination where the merchandise was unloaded for transhipment across the Indus. - V.S. Agarwala Ch IV, Sec 6 p 245.""")
xatra.Point(label="Maṇḍāmatī", position=[31.7094582, 76.9201538])
xatra.Point(label="Phalakapura", position=[31.0143239, 75.7758086])
xatra.Point(label="Sunetra", position=[30.8840679,75.7991748])
xatra.Point(label="Yugandhara", position=[30.1585396, 77.2786509])
xatra.Point(label="Kurukṣetra", position=[29.96928, 76.8613021])
xatra.Point(label="Śairīśaka", position=[29.5369779, 74.9892074])
xatra.Point(label="Kapisthala", position=[29.7918366, 76.3296551])
xatra.Point(label="Aiśukāri", position=[29.1561658, 75.6731383])
xatra.Point(label="Rohītakā", position=[28.8894463, 76.460445])
xatra.Point(label="Roṇī", position=[29.7446626,75.195733])
xatra.Point(label="Hṛḍgolīya", position=[34.3521939,70.4856822])
xatra.Point(label="Andhakavarta", position=[36.95098,65.0863755])
xatra.Point(label="Naḍvala", position=[25.3762851,73.4335213])
xatra.Point(label="Aśani", position=[34.0821216,70.6623351], note="""
e.g, Asani (Parśvādi group, V.3.117) perhaps, Shinwāris with their parent-stock of the Kārshbuns, to be identified 
with Kārśāpaṇas in the same gaṇa. - V.S. Agarwala CH VII Sec 7 p 438.
""")
xatra.Point(label="Bālhīka", position=[36.7571227,66.8740582])
xatra.Point(label="Rohitagiri", position=[33.9434, 66.2476], icon=MOUNTAIN_ICON, note="Roha is an old name for Afghanistan. See V.S. Agarwala Ch VII, Sec 7, p 435.")
xatra.Point(label="Añjanāgiri", position=[30.4999991,70.156367], icon=MOUNTAIN_ICON, note="or Trikakut, or Suleiman mountains. See V.S. Agarwala Ch II, Sec 3 p 39.")
xatra.Point(label="Salt Range", position=[32.3289,72.2186], icon=MOUNTAIN_ICON)
xatra.Point(label="Kiṃśulkāgiri", position=[27.8099,64.4678], icon=MOUNTAIN_ICON, note = "Or Hiṅgulā in Prakrit.")
xatra.Point(label="Vidura", position=[32.4032679,74.7789954], icon=MOUNTAIN_ICON, note="""VS Agarwala Ch II, Sec 3 p 39:
Pāṇini mentions some particular hills: (1) Tri-kakut 
(V.4.147) so-called from its three peaks, a name first used in
the Atharvaveda as the source of a salve (añjana), which may
he identified with the Sulaiman mountain, famous as the source
of antimony all over the Punjab and Sind (probably same as
Sauvirāñjana; cf. Vedic Index I.329; (2) Vidura (IV.3.84)
as the source of the precious stone called vaidūrya (cat’s eye/lapis lazuli),
which according to Patanjali was quarried at Vālavaya and
treated by the lapidaries in Vidura, probably Bidar (cf. Pargiter,
Mārk. p. 365, for Vaidurya as Satpura); (3) Kiṃśulakā-giri
(VI.3.117), to which the Gaṇapāṭha adds five more names, viz.,
Śālvakāgiri, Añjanāgiri, Bhañjanāgiri, Lohitāgiri, Kukkuṭāgiri, 

These six names seem to be taken from some Bhuvankosha list, giving in order the ranges on the western frontiers from Afghanistan to Baluchistan.
""")
xatra.Point(label="Śālvakāgiri", position=[25.9999992,66.1397003], icon=MOUNTAIN_ICON, note = "See V.S. Agarwala Ch II, Sec 3 p 39-40.")
xatra.Point(label="Bhañjanāgiri", position=[34.6336391,67.8086473], icon=MOUNTAIN_ICON, note="See V.S. Agarwala Ch II, Sec 3 p 39-40. Koh-i-Baba.")
xatra.Point(label="Kukkuṭagiri", position=[34.0345,64.7754], icon=MOUNTAIN_ICON, note="See V.S. Agarwala Ch II, Sec 3 p 39-40.")
xatra.Point(label="Dāmani", position=[29.5105547,64.2410892], icon =MOUNTAIN_ICON, note="Chagai hills.")
xatra.Point(label="Anusamudradvīpa", position=[20.7246,70.9161])
xatra.Point(
    label="Bahugarta",
    position=[22.6647,72.4933],
    note="Sabarmati river valley. V.S. Agarwala Ch II, śec 5 p 66."
)
xatra.Point(
    label="Cakragarta",
    position=[22.0834769,69.2641703]
)
xatra.Point(label="Haṃsamārga", position=[36.3103036,74.6081449])
# xatra.Point(label="Ajamīḍha, Ajakranda?", position=[26.0963, 74.9048], note="")
xatra.Point(
    label="Mṛttikāvatī",
    position=[26.65, 74.0307251],
    note="V.S. Agarwala Ch IV, Sec 3. Mṛttikāvatī is a Sālva capital; it might be Merta, though this is outside Sālva territory proper as identified (the region from North Bikaner to Alwar).",
)
xatra.Point(label="Śārkara", position=[27.7176044, 68.7924545])
xatra.Point(label="Rauruka", position=[27.6728038, 68.8718273])
xatra.Point(
    label="Brāhmaṇaka",
    position=[25.8801594, 68.7673041],
    note="""
It is mentioned in Paniru's sūtra V. 2.71. Patañjali definitely calls it a janapada (Brāhmaṇako
nama janapadaḥ II.298). The significance of its name is brought out by the Kāśikā, which describes
it as the land of Brahmins who were āyudhajīvins or followers of military art.
(yatrāyudhajīvino Brāhmaṇāḥ santi), Their military traditions continued up to the time of Alexander
whose invasion they resisted with patriotic heroism (Plutarch, Alex., 59) . The Greeks call them
Brachmanoi and locate them in middle Sind (Arrian, VI.I6), of which the capital is still called
Brahmanabad (Cunningham, Ancient Geog., p. 310). It may be noted that even Rajasekhara (9th century A. D.)
names Brāhmaṇavaha ('abode of Brāhmaṇas') as one of the janapadas of the west. The Muslim geographers called
Bahmanwā after this old tradition. - VS Agarwala Ch II, Sec 4.""",
)

xatra.Text(
    label="Ambaṣṭha",
    position=[29.2576, 71.0651],
    classes="uncertain-label uncertain-label-ambastha",
    note="""The cognate Abastanoi/Sambasta of Greek accounts are mentioned to the South of the
Mālavas, see e.g. <a href='https://www.ibiblio.org/britishraj/Jackson2/chapter04.html'>ibiblio.org/britishraj/Jackson2/chapter04.html</a>.
The Vasāti are also mentioned in the same region, see V.S. Agarwala Ch VII, Sec 8 p 453.
""",
)
xatra.Text(
    label="Śaubhreya?",
    position=[30.1404, 71.3068],
    classes="uncertain-label uncertain-label-saubreya",
    note="""V.S. Agarwala Ch VII, Sec 8 p 449. "On both banks of the river."
""",
)
xatra.Text(
    label="Śaubhreya?",
    position=[28.6906,70.0928],
    classes="uncertain-label uncertain-label-saubreya-2",
    note="""V.S. Agarwala Ch VII, Sec 8 p 449. "On both banks of the river."
""",
)
xatra.Text(
    label="Vasāti?",
    position=[29.8502, 67.9504],
    note="Ossadioi of Greek accounts. Shown here in VS Agarwala's final xatra."
)
xatra.Text(
    label="Śaudrāyaṇa?",
    position=[28.2076,69.8126],
    classes="uncertain-label uncertain-label-saudrayana",
    note="Diodorous couples the Sodrae with Massane as occupying the opposite banks of the Indus . Cunningham equates the Massane with the Mausarnaioi of Ptolemy, which name corresponds to the Masuurakarna of the Gana Patha II-4-49, IV-1-112."
)
xatra.Text(
    label="Saubhuta",
    position=[31.9055,71.9165],
    classes="uncertain-label uncertain-label-saubhuti",
    note='V.S. Agarwala Ch II, Sec 5 p 72. "Saubhuta was thus a part of Kekaya in the Salt Range."'
)
xatra.Text(
    label="Kaṭha",
    position=[32.3892,74.4324],
    classes="uncertain-label uncertain-label-katha",
    note='V.S. Agarwala Ch II, Sec 5 p 72 locates Śāṅgala and the Kaṭhas to be in Jhang district in Uśīnara, and distinct from Śākala; but this seems to no longer be the view.'
)

xatra.CSS(r"""
.uncertain-label { font-size: 12px; color: #444;}
.flag-grey { fill: #888888 !important; color: grey !important; fill-opacity: 0.25 !important; }
""")


if __name__ == "__main__":
    xatrahub("/map/rivers_saptasindhu")

    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")

    xatra.River(label="Kubha", value=overpass("1676476"), note="Kabul")
    xatra.River(label="Kāma", value=overpass("6608825"), note="Kunar")
    xatra.River(label="Vaksu (amu darya)", value=overpass("223008"), show_label=True)

    xatra.CSS(r"""
        .admin { opacity: 0.35; }
        .flag-grey { fill: #888888 !important; color: grey !important; }
    """)
    xatra.zoom(6)
    xatra.TitleBox("""
    Map of the Audicya (northern) country c. 4th century BC according to Pāṇiṇi (SS: VS Agarwala)<br><br>
    Note: Pāṇini also provides the geography of the rest of India, however that of the North-West is given with greater resolution and detail.
    """)
