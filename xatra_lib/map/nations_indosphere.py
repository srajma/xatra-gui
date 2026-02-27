xatrahub("/map/nations_india")
xatrahub("/map/nations_silkrd")
xatrahub("/map/nations_suvarnabhumi")
xatrahub("/map/rivers_gangetic")
xatrahub("/map/rivers_peninsular")
xatrahub("/map/rivers_saptasindhu")
xatrahub("/map/rivers_silkrd")

if __name__ == "__main__":
    xatra.BaseOption("Esri.WorldTopoMap", default=True)
    xatra.BaseOption("OpenStreetMap")
    xatra.BaseOption("Esri.WorldImagery")
    xatra.BaseOption("OpenTopoMap")
    xatra.BaseOption("Esri.WorldPhysical")
    xatra.TitleBox("""
    Nations, not states, of the ~Indosphere region in antiquity. 
    Roughly valid in the period 800 BC to 1200, think of it as a 
    first-order approximation or a reference guide. 
    """)