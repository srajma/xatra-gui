CITIES = {
    "Delhi": [28.7041, 77.1025],
    "Mumbai": [19.0760, 72.8777],
    "Kolkata": [22.5726, 88.3639],
    "Chennai": [13.0827, 80.2707],
    "Bangalore": [12.9716, 77.5946],
    "Hyderabad": [17.3850, 78.4867],
    "Pune": [18.5204, 73.8567],
    "Ahmedabad": [23.0225, 72.5714],
    "Ranchi": [23.3441, 85.3096],
    "Jaipur": [26.9124, 75.7873],
    "Surat": [21.1702, 72.8311],
    "Lucknow": [26.8467, 80.9462],
    "Kanpur": [26.4499, 80.3319],
    "Kannauj": [27.0551, 79.9133],
    "Prayagraj": [25.4358, 81.8463],
    "Nagpur": [21.1458, 79.0882],
    "Gondia": [21.4602, 80.1920],
    "Patna": [25.5941, 85.1376],
    "Indore": [22.7196, 75.8577],
    "Bhopal": [23.2599, 77.4126],
    "Ludhiana": [30.9010, 75.8573],
    "Agra": [27.1767, 78.0081],
    "Pryagraj": [25.4358, 81.8463],
    "Varanasi": [25.3176, 82.9739],
    "Ayodhya": [26.7925, 82.1942],
    "Vadodara": [22.3072, 73.1812],
    "Nashik": [20.0059, 73.7910],
    "Aurangabad": [19.8762, 75.3433],
    "Amaravati": [20.9331, 77.7519],
    "Udaipur": [24.5854, 73.7125],
    "Ajmer": [26.4499, 74.6399],
    "Amritsar": [31.6340, 74.8723],
    "Chandigarh": [30.7333, 76.7794],
    "Coimbatore": [11.0168, 76.9558],
    "Goa": [15.2993, 74.1240],
    "Mangalore": [12.9141, 74.8560],
    "Madurai": [9.9252, 78.1198],
    "Kochi": [9.9312, 76.2673],
    "Visakhapatnam": [17.6868, 83.2185],
    "Ongole": [15.9129, 80.1529],
    "Nellore": [14.4426, 79.9865],
    "Tanjore": [10.7867, 79.1378],
    "Bhubaneswar": [20.2961, 85.8245],
    "Thiruvananthapuram": [8.5241, 76.9366],
    "Vijayawada": [16.5062, 80.6480],
    "Jodhpur": [26.2389, 73.0243],
    "Raipur": [21.2514, 81.6296],
    "Kota": [25.2138, 75.8648],
    "Guwahati": [26.1445, 91.7362],
    "Jabalpur": [23.1815, 79.9864],
    "Gwalior": [26.2183, 78.1828],
    "Bikaner": [28.0229, 73.3119],
    "Kolhapur": [16.7050, 74.2433],
    "Akola": [20.7096, 77.0022],
    "Solapur": [17.6599, 75.9064],
    "Hubli": [15.3647, 75.1240],
    "Belgaum": [15.8497, 74.4977],
    "Davangere": [14.4644, 75.9218],
    "Mysore": [12.2958, 76.6394],
    "Gulbarga": [17.3850, 76.4797],
    "Shimoga": [13.9299, 75.5681],
    "Tumkur": [13.3409, 77.1010],
    "Dhanbad": [23.7957, 86.4304],
    "Muzaffarpur": [26.1209, 85.3647],
    "Darbhanga": [26.1524, 85.8971],
    "Purnia": [25.7781, 87.4700],
    "Gaya": [24.7964, 85.0070],
    "Bhagalpur": [25.2445, 86.9718],
    "Kishanganj": [26.1119, 87.9563],
    "Rae Bareli": [26.2301, 81.2409],
    "Jammu": [32.7266, 74.8570],
    "Pathankot": [32.2746, 75.6527],
    "Jalandhar": [31.3260, 75.5762],
    "Ambala": [30.3753, 76.7821],
    "Vidisha": [23.5260, 77.8210],
}


# MUMBAI - DELHI LINE
## MUMBAI-AHMEDABAD
xatra.Path(
    label="MUMBAI-DELHI",
    value=[
        CITIES["Mumbai"],
        CITIES["Surat"],
        CITIES["Vadodara"],
        CITIES["Ahmedabad"],
    ],
    classes="hsr hsr-economic hsr-mumbai-delhi",
    show_label=True,
)
## AHMEDABAD-DELHI
xatra.Path(
    label="MUMBAI-DELHI",
    value=[
        CITIES["Ahmedabad"],
        CITIES["Udaipur"],
        CITIES["Ajmer"],
        CITIES["Jaipur"],
        CITIES["Delhi"],
    ],
    classes="hsr hsr-economic hsr-mumbai-delhi",
    show_label=True,
)

# Dehati-Bachao Dehati-Padhao Line
## Jammu-Delhi
xatra.Path(
    label="NORTHERN",
    value=[
        CITIES["Jammu"],
        CITIES["Pathankot"],
        CITIES["Amritsar"],
        CITIES["Jalandhar"],
        CITIES["Ludhiana"],
        CITIES["Chandigarh"],
        CITIES["Ambala"],
        CITIES["Delhi"],
    ],
    classes="hsr hsr-social hsr-dehati",
    note="DEHATI BACHAO DEHATI PADHAO"
)
## Delhi-Patna
xatra.Path(
    label="NORTHERN",
    value=[
        CITIES["Delhi"],
        CITIES["Agra"],
        CITIES["Kannauj"],
        CITIES["Kanpur"],
        CITIES["Rae Bareli"],
        CITIES["Prayagraj"],
        CITIES["Varanasi"],
        CITIES["Patna"],
    ],
    classes="hsr hsr-social hsr-dehati",
    show_label=True,
    note="DEHATI BACHAO DEHATI PADHAO"
)
## Patna-Kolkata
xatra.Path(
    label="NORTHERN",
    value=[CITIES["Patna"], CITIES["Gaya"], CITIES["Dhanbad"], CITIES["Kolkata"]],
    classes="hsr hsr-social hsr-dehati",
    note="DEHATI BACHAO DEHATI PADHAO"
)
## Lucknow Extension
xatra.Path(
    label="NORTHERN",
    value=[CITIES["Kanpur"], CITIES["Lucknow"]],
    classes="hsr hsr-social hsr-dehati",
    note="DEHATI BACHAO DEHATI PADHAO"
)
## Ayodhya Extension
xatra.Path(
    label="NORTHERN",
    value=[CITIES["Prayagraj"], CITIES["Ayodhya"]],
    classes="hsr hsr-social hsr-dehati",
    note="DEHATI BACHAO DEHATI PADHAO"
)
## Bihar Extension
xatra.Path(
    label="NORTHERN",
    value=[
        CITIES["Patna"],
        CITIES["Muzaffarpur"],
        CITIES["Darbhanga"],
        CITIES["Purnia"],
        CITIES["Kishanganj"],
    ],
    classes="hsr hsr-social hsr-dehati",
    note="DEHATI BACHAO DEHATI PADHAO"
)

# Akaravanti Line
## Akaravanti Main Line
xatra.Path(
    label="AKARAVANTI",
    value=[
        CITIES["Vadodara"],
        CITIES["Indore"],
        CITIES["Bhopal"],
        CITIES["Vidisha"],
        CITIES["Jabalpur"],
    ],
    classes="hsr hsr-political hsr-akaravanti",
    show_label=True,
)
## Dakshinapatha Extension
xatra.Path(
    label="AKARAVANTI LINE",
    value=[CITIES["Gondia"], CITIES["Jabalpur"], CITIES["Varanasi"]],
    classes="hsr hsr-political hsr-akaravanti",
)

# Maharashtra Line
xatra.Path(
    label="MAHARASHTRA",
    value=[
        CITIES["Mumbai"],
        CITIES["Nashik"],
        CITIES["Aurangabad"],
        CITIES["Amaravati"],
        CITIES["Nagpur"],
        CITIES["Gondia"],
    ],
    classes="hsr hsr-social hsr-maharashtra",
    show_label=True,
)

# MUMBAI - BANGALORE LINE
xatra.Path(
    label="MUM-BLR",
    value=[
        CITIES["Mumbai"],
        CITIES["Pune"],
        CITIES["Kolhapur"],
        CITIES["Belgaum"],
        CITIES["Hubli"],
        CITIES["Bangalore"],
    ],
    classes="hsr hsr-political hsr-maharashtra",
    show_label=True,
)

# MUMBAI - HYDERABAD LINE
xatra.Path(
    label="MUM-HYD",
    value=[
        CITIES["Pune"],
        CITIES["Solapur"],
        CITIES["Gulbarga"],
        CITIES["Hyderabad"],
    ],
    classes="hsr hsr-economic hs-optional hsr-mumhyd",
    show_label=True,
)

# BANGALORE - HYDERABAD LINE
xatra.Path(
    label="BLR-HYD",
    value=[CITIES["Bangalore"], CITIES["Hyderabad"]],
    classes="hsr hsr-economic hs-optional hsr-blrhyd",
    show_label=True,
)

# MOOLNIVASI LINE
xatra.Path(
    label="MOOLNIVASI",
    value=[
        CITIES["Gondia"],
        CITIES["Raipur"],
        CITIES["Ranchi"],
        CITIES["Dhanbad"],
    ],
    classes="hsr hsr-political hsr-optional hsr-moolnivasi",
    show_label=True,
)

# EAST COAST LINE
## Main line
xatra.Path(
    label="EAST COAST",
    value=[
        CITIES["Kolkata"],
        CITIES["Bhubaneswar"],
        CITIES["Visakhapatnam"],
        CITIES["Vijayawada"],
        CITIES["Ongole"],
        CITIES["Nellore"],
        CITIES["Chennai"],
    ],
    classes="hsr hsr-political hsr-ec",
    show_label=True,
)
## Hyderabad Extension
xatra.Path(
    label="EAST COAST",
    value=[CITIES["Vijayawada"], CITIES["Hyderabad"]],
    classes="hsr hsr-political hsr-ec",
)

# West Coast Line
xatra.Path(
    label="WEST COAST",
    value=[
        CITIES["Mumbai"],
        CITIES["Goa"],
        CITIES["Mangalore"],
    ],
    classes="hsr hsr-economic hsr-optional hsr-wc",
    show_label=True,
)

# BANGALORE - MANGALORE LINE
xatra.Path(
    label="BLR-MGL",
    value=[CITIES["Bangalore"], CITIES["Mysore"], CITIES["Mangalore"]],
    classes="hsr hsr-economic hsr-optional hsr-blrmgl",
)

# KERALA LINE
xatra.Path(
    label="KERALA",
    value=[
        CITIES["Mangalore"],
        CITIES["Kochi"],
        CITIES["Thiruvananthapuram"],
    ],
    classes="hsr hsr-economic hsr-optional hsr-kerala",
)

# BANGALORE - CHENNAI LINE
xatra.Path(
    label="BLR-CHN",
    value=[CITIES["Bangalore"], CITIES["Chennai"]],
    classes="hsr hsr-economic hsr-optional hsr-blrchn",
)

# TAMIL LINE
xatra.Path(
    label="TAMIL",
    value=[
        CITIES["Chennai"],
        CITIES["Tanjore"],
        CITIES["Madurai"],
        CITIES["Thiruvananthapuram"],
    ],
    classes="hsr hsr-economic hsr-optional hsr-tamil",
)

# BANGALORE - KERALA LINE
xatra.Path(
    label="BLR-KER",
    value=[CITIES["Bangalore"], CITIES["Coimbatore"], CITIES["Kochi"]],
    classes="hsr hsr-economic hsr-optional hsr-blrker",
)

# HYDERABAD-NAGPUR LINE
xatra.Path(
    label="HYD-NGP",
    value=[CITIES["Hyderabad"], CITIES["Nagpur"]],
    classes="hsr hsr-economic hsr-optional hsr-mumhyd",
)

xatra.CSS(r"""
.hsr-economic {stroke: blue; color: blue}
.hsr-political {stroke: red; color: red}
.hsr-social {stroke: green; color: green}
.hsr-optional {stroke-dasharray: 5,5; opacity: 0.4}
""")


if __name__ == "__main__":
    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")

    xatra.TitleBox(f"""
        <p><b>High-speed rail network to BVILD</b></p>
        <p><span style='color: blue; font-weight: bold'>Blue:</span> Economic lines</p>
        <p><span style='color: green; font-weight: bold'>Green:</span> Social lines</p>
        <p><span style='color: red; font-weight: bold'>Red: </span> Political lines<br></p>
        <p>Thick lines are the bare minimum. Dashed lines are still very desirable.</p>
        <p><b>Hover over each line</b> to see its name and purpose.</p>
    """)
    xatra.show(out_json="../maps/hsr.json", out_html="../maps/hsr.html")
