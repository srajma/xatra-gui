xatra.Admin(gadm="IND", level=3, color_by_level=2)
xatra.Admin(gadm="PAK", level=3, color_by_level=2) # level-3 GADM divisions in Pak are more like districts, but we don't have finer data
xatra.Admin(gadm="BGD", level=3, color_by_level=2)
xatra.Admin(gadm="AFG", level=2, color_by_level=2) # level-2 is the best we have for Afghanistan
xatra.Admin(gadm="NPL", level=3, color_by_level=2) # level-3 GADM divisions in Nepal are more like districts, but level-4 is WAY too fine
xatra.Admin(gadm="BTN", level=2, color_by_level=2) # level-2 is the best we have for Bhutan, and they're like taluks anyway
xatra.Admin(gadm="LKA", level=2, color_by_level=2) # level-2 is the best we have for Lanka, and they're like taluks anyway


if __name__ == "__main__":
    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")

    xatra.TitleBox("""
    Indian districts (level-2 subdivisions).
    <br>
    <code>
    map.Admin(gadm="IND", level=2, color_by_level=1)
    map.Admin(gadm="PAK", level=3, color_by_level=1) # level-3 GADM divisions in Pak are more like districts
    map.Admin(gadm="BGD", level=2, color_by_level=1)
    map.Admin(gadm="AFG", level=2, color_by_level=1)
    map.Admin(gadm="NPL", level=3, color_by_level=1) # level-3 GADM divisions in Nepal are more like districts
    map.Admin(gadm="BTN", level=2, color_by_level=1)
    map.Admin(gadm="LKA", level=2, color_by_level=1)
    </code>
    """)
    xatra.CSS(r"""
    .river {
        stroke-width: 5;
    }
    """)
    

