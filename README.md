# Xatra Studio GUI

## How to Start / Restart

To start the full application (backend + frontend):
```bash
./start_gui.sh
```

To start in production:
```bash
./start_gui_prod.sh
```


To restart if the page is blank or not responding:
1. Stop the current process (usually `Ctrl+C` in the terminal where you ran the script).
2. If it doesn't stop cleanly, kill any remaining processes:
   ```bash
   pkill -f uvicorn
   pkill -f vite
   ```
3. Run `./start_gui.sh` again.

Backend at `localhost:8088`, frontend at `localhost:5188` (production frontend at `localhost:4173`).

## TODO

Bugs
- [x] Base map doesn't appear by default---it appears in the Base Layer dropdown and I can select it and it appears, but the map renders with None by default even though I have a Base Layer selected which is odd
- [x] Period field has a bug: it doesn't allow commas, so I cannot actually enter a range. It also doesn't seem to allow minus signs (which is how we enter BC dates---in fact, the example shown should be something like [-320, -180] and the "format" helper should explicitly say "use negative numbers for BC years".), or for the first entry to be 0 (which should be possible since these are years). This applies to all elements.
- [x] Admin and AdminRivers elements have a bug: Error: Map.Admin() got an unexpected keyword argument 'label'.
- [x] I get an Error: object of type 'int' has no len() sometimes ... leave this issue for now, I think fixing the Period field will fix it.
- [x] Start year end year fields for the Time Slider in Global Options are broken again
  - [x] This is still broken, entering "-" leaves it blank.
- [x] Code Editor is broken (shows a blank page)
- [x] In case of any error where the map runs into "Rendering..." "Generating map..." forever, there should be something to let the user stop the generation. Sometimes even reloading the page doesn't work.
  - [x] While the feature has been implemented, it doesn't solve the underlying problem, which is that the server is itself in an error state, so no other operation runs afterward. It should stop the underlying Python process that is in error. 
  - [x] Also in general errors should always break the process, right (I might be talking nonsense, IDK)? Why does the execution not return things to normal upon these errors? 
- [x] In all the forms there should be something to ensure when the contents are cleared, it is treated exactly as it would be exactly as if it were never edited. E.g. when I enter something into the Flag Color Sequence box and then remove it, I get an error while generating the map "Error: name 'parse_color_sequence' is not defined" even though its contents are clear again.
- [x] territories don't get stored correctly if they themselves contain pre-computed territories. I.e. if I define a new Flag and build a territory for it KURU | gadm("IND.31") | polygon([[25.483,74.8389],[21.6166,70.2246],[14.1792,68.7305],[15.5807,75.6299],[16.6362,80.6836]]), it will just get stored as: india =  |  |  |  - gadm("IND.12") | polygon([[25.483,74.8389],[21.6166,70.2246],[14.1792,68.7305],[15.5807,75.6299],[16.6362,80.6836]]).
- [x] Bugs with the code editor
  - [x] Weird bug: Every time I switch away from the Code window and then back to it, another copy of each item in the autocomplete appears. So when one first clicks out and back, there are two copies of "xatra" in the autocomplete menu, and if you type `xatra.` then there are two copies of `Admin` etc.; do it again and there are three copies of each, etc.
  - [x] Code editor is weirdly smaller vertically than the space available in the boxes for them 
    - [x] Map Code editor now uses ResizeObserver to fill available height in the Code tab panel.
      - [x] Map Code is fine, but Predefined Territories code editor is still much smaller than its box.
  - [x] This tip: `Type xatra. or map. for map methods. Use Ctrl+Space for suggestions.` should not say `map.`, it should just be `Type xatra. for map methods. Use Ctrl+Space for suggestions.`
  - [x] I have vimium installed, and when I try typing in the code editor it doesn't realize I'm in insert mode. This is weird, since I haven't had this issue on other sites using Monaco. Can you figure out how to fix this? 
    - [x] The current attempted fixes, "Force focus" etc. don't work, and should be removed to avoid bloat. Instead, just put a blaring banner at the top of the code screen saying "If you are using<b>Vimium</b>, please DISABLE it on this website."
  - [x] The Territory picker is bugged out:
    - [x] When I select and unselect a territory, it becomes black rather than returning to its original color and transparency (like it correctly does for the GADM picker).
    - [x] When I pan or zoom, those blackened territories become white, making them impossible to click again.
  - [x] Flag Territories: Dragging an item *out* of a group doesn't seem to be working (moving something into a group works). Instead, moves the whole group to wherever we tried to move the item.
  - [x] Bug fixes with new Add Operation UI
    - [x] when focusing the input field (upon creating a GADM/Polygon/Territory) it sometimes goes and focuses on some other Flag's territory's input field for some reason? This needs to be fixed.
    - [x] The + - & keys only work when one of the items in the Flag Territory list or the buttons themselves are focused (and that too not child elements of those items) -- instead, it should work when *anything* in that Flag Layer element (any children recursively thereof) is focused. (3) Sometimes (e.g. after going through "Define Territory"
    - [x] clicking the add/subtract/intersection buttons with my mouse rather than keyboard) "gadm" is not immediately focused. Like it shows in blue highlight, but pressing enter doesn't select it, pressing arrow keys doesn't cycle through the options etc. (4) "Esc" should also be cycled through in all cases.
    - [X] keyboard shortcuts (both the + - & shortcuts and the g p t o arrow-keys-cycle tab keyboard shortcuts) conflict in nested groups. All keyboard shortcuts should operate only on the lowest-level element we're focused in, and similarly focus should not shift to somewhere outside that current focused group.
- [x] Fixes for project export, code to builder conversion
  - [x] Triple-quoted mulitiline strings need better support in handling. Right now if I put something like this into the code editor:
    ```python
      xatra.Flag(
      label="ŚAVASA",
      value=SAVASA,
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
    ```
    Then switch to the Builder, the lines get concatenated into one in the note field. Which would still be fine, except that when I switch back, I see:

    ```python
    xatra.Flag(value=SAVASA, note="Of these Kekaya and Savasa may be
    located between the Jhelum and the Chenab, the first in the
    south and the second in the north respectively, and Madra and
    Uśīnara between the Chenab and the Ravi in the north and
    south respectively. The divisions become clear on the xatra.
    The Divyāvadāna refers to the Śvasas in Uttarāpatha with
    headquarters at Takṣaśilā to which Aśoka was deputed by his
    father Bindusāra as Viceroy to quell their rebellion. The name
    Śavasa or Śvasa seems to be preserved in the modern name 
    Chhibha comprising Punch, Rajauri and Bhimbhara. - VS Agarwala Ch II, Sec 4.", label="ŚAVASA")
    ```
    i.e. the triple-quoted string gets converted into a single-quoted string, causing a syntax error. In order to fix this:
    - [x] when converting from Builder to Code, multiline strings should always be triple-quoted.
    - [x] "Note" fields in the Builder should be text areas. They should start at single-line height, but the user should be able to enter more lines by pressing Enter and that should automatically increase the height of that particular text area as well. Converting from code to builder should use this for multiline strings.
  - [x] CSS conversion when converting from Code to Builder---messes up when there are multiple xatra.CSS() lines. It should just merge them into a single string when converting to Builder.
  - [x] Allow "Python" layers. Any line of code that doesn't match the existing matches should be made a "Python" block in the Builder. Allow the user to add and edit Python layers through the Builder (so it will be one more layer type after Flag, River, ... complete with its own keyboard shortcut Ctrl/Cmd+Shift+Y).
    - [x] To make this useful, it should also be possible to use Python in any text field. Every text input field should have a little icon inside it near the right edge that one can toggle to input Python code for the value of that variable instead (so it wouldn't be interpreted as a string). Code to Builder conversion should use this when needed (i.e. where it would otherwise lead to error)
  - [x] Code doesn't directly turn into project json for download (the "Save Project" one, not the "Export Map JSON" one) without converting to Builder mode first. It should.
  - [x] Can remove the "Sync from Builder" button since it automatically syncs now.
  - [x] Fix new weird bug where an Admin layer gets added every time we switch from Code to Builder
  - [x] Oh, and Code comments should also get converted to Python layers in the Builder.
  - [x] Weird issue with code in the territory library getting duplicated when switching from Code editor to Builder---however don't try to fix this now, I think it will automatically get fixed when you implement the later-detailed changes to the Code editor sections that will prevent the need to mirror code between the Territory library and the Map Code---ok nvm, you fixed it.
  - [x] Code editor: cursor jumps to the bottom of the editor when typing rapidly
    - [x] Fixed, but now it randomly jumps to the end of the line instead
- [x] Keyboard cycling through the xatra menu is messed-up. Sometimes it doesn't work at all; sometimes even when you cycle through it, pressing Enter selects "Load" instead of whatever I want to select; "Load" appears highlighted no matter what I do etc.
- [x] xatrahub imports (e.g. `indic = xatrahub("/srajma/lib/indic/alpha")`) still getting converted into "Python" layers when translating from Code to Builder when they should _only_ get converted into imports.
- [x]  After some changes I have made in this project, the Flag Territory builder in the Builder UI is unable to properly handle the "Territory" option (i.e. using pre-defined territories from imported territory libraries or custom territories). I believe this is because after my changes, the territories are no longer referred to just by their names but rather `<libraryname>.<name>`, e.g. not "KURU" but "indic.KURU" (since we have imported indic = xatrahub("/srajma/lib/indic/alpha")). Check  ../xatra.master/src/xatra/hub.py to see exactly how it works. The Territory search needs to be updated to understand this and list territories as indic.KURU etc. for imported libraries and just KURU etc. for custom territories defined in that very map. This might be a bit complicated---you need to think this through, make sure it works with the territory search/autocomplete, the Territory library visualization tab and the Territory  picker, builder to code conversion and reverse. Really make sure you understand the code and know how to do this. You can verify your work by using the browser to navigate to  http://localhost:5188/.
- [x] Why does the app consume so much CPU utilization even when the user isn't doing anything?
- [x] Why doesn't the `<i>made with <a href="https://github.com/srajma/xatra">xatra</a></i>` attribution appear in the title box? It's hardcoded in the xatra package to appear no matter what, even if the user doesn't add any `xatra.TitleBox()` layers, yet it doesn't seem to be appearing in the maps made with the GUI?
- [x] The Custom Territory library and Custom theme sections of the Code editor are bugged. The alpha version of the code (which should be latest) often does not reflect the latest version, but clicking on the latest version and coming back to it fixes it to the latest version. Go through this logic and fix it.

Basic extensions
- [x] Allow adding any feature to the map, not just flags and rivers. Every single method listed under #### Methods in the main README should have an appropriate interface for adding it:
  - [x] Flags (already exist, but allow adding any attribute, not just label, note and GADM code)
  - [x] Rivers
    - [x] Needs to allow overpass() rivers as well---let the user choose overpass or natural earth, and enter the ID. Also it should not say "NE ID / Name", only ID works (for now at least). You can use naturalearth("1159122643") (Ganga) as a sample example.
    - [x] Do not prefill the ID with the text "Ganges". Instead prefill with "1159122643" for Naturalearth and "1159233" for Overpass.
  - [x] Admin
  - [x] AdminRivers
  - [x] Path, Point, Text.
    - [x] For Point, think carefully about how to implement the icon choice UI (whatever is supported by .Icon() in the library---both the in-built icons, geometric and any custom ones).
  - [x] Dataframes will be complicated, but at least the user should be able to upload a CSV. (See README.md for the format of the pandas dataframe)
    - [x] The sample example prefilled when adding a dataframe has the GID column titled "gadm". This is wrong, it should be "GID".
    - [x] Remove the "Find in GADM" field. Even in the original package it's kind of irrelevant.
    - [x] plotting data doesn't really work for some reason, it generates the following error.
    - [x] We should not need to enter the data and year columns manually.
      - [x] Actually just remove the fields for entering data and year columns entirely, we don't need them.

  - [x] NOTE: allow adding any attribute to those objects, not just label, note and GADM code. Period is especially important. The less important attributes could be hidden under a "More..."
    - [x] "Period" should not be under a "More Options" It is optional, but should still be accessible without clicking "More Options". All the other things under "More Options" are fine there.
  - Global options---only TitleBox should be displayed prominently, the rest can be under a "More..." button and shown if expanded
    - [X] .TitleBox() (this already exists, but it should be a multiline textbox instead of a single line, it should be called "TitleBox (HTML)" instead of "Map Title", and the font for the content should be monospace)
      - [x] Thanks for fixing the other things, but change this to "TitleBox (HTML) please, not just "Title (HTML)".
    - [x] .CSS() --- the interface for this should be as follows: we have a list of classes (record all the classes used in rendering the map and use them here, and also add any custom CSS classes the user added for any element he added); each row is a pair of a dropdown (containing that list of classes) and the corresponding style for it in a text field. The user can add or delete rows, or change the class from that dropdown.
      - [x] Right now this is implemented in a weird way where the input is a text field prefilled with ".flag" and the options appear as autocomplete options. I think this is unintuitive for users---instead, make it an actual dropdown, with a "Custom..." option which if selected lets the user input any custom class/CSS selector.
    - [x] Base Layers: allow adding any number of base layers, and selecting one as default.
      - [x] Fixed. But the UI is a bit clumsy. Instead, just have the list of available base layers as checkboxes (where checking a box means it will be included in the base layer options) and include buttons next to them to make default (it should only be possible to make one default).
  - [x] FlagColorSequence, AdminColorSequence, DataColormap --- think through the interface for this carefully; users should be able to set the obvious ones easily, or create their own color sequence or map, just like in the package itself (see the README for details). [This still needs to be done better---also it should be possible to set multiple color sequences for different classes].
    - [x] Nah the FlagColorSequence interface is still totally wrong. See the colorseq.py file---basically we should always construct a linear color sequence, and the user should be able to enter the step-sizes in H,S,L and optionally a list of starting colors, and we initialize a LinearColorSequence(colors=those optional colors or None if not provided, step=Color.hsl(those values)). It should be pre-loaded with the default color sequence, LinearColorSequence(colors=None,step=Color.hsl(1.6180339887, 0.0, 0.0)) (and there doesn't need to be that cluttery explanatory note explaining that this is a default, like there is now). The user should also be able to restrict the color sequence to any particular class if need be, but the dropdown should not consist of all the classes present but only the custom classes that have been applied to Flags.
      - [x] Ok, it's better now---but it doesn't fit in the horizontal space.
      - [x] AdminColorSequence should work the same way as FlagColorSequence.
        - [x] Except one thing: the UI shouldn't allow adding multiple AdminColorSequences, and there should not be a class dropdown for it. Unlike FlagSequences, there can only be one AdminColorSequence, and it doesn't take any `class_name` parameter since it applies to all classes.
      - [x] The Datacolormap UI is also weird. Instead, there should be a dropdown to select the color map (e.g. viridis etc.), and if "LinearSegmented" is selected, it should allow the user to input a list of colors. By default "LinearSegmented" should be selected, and the colors should be yellow, orange, red.
  - [x] zoom and focus
    - [x] this should include a button to just use the current zoom and focus levels at the map is at
    - [x] there's a weird bug where I can't clear the contents of Initial focus manually because if I clear Latitude, Longitude becomes filled again (with 0) and if I clear Longitude, Latitude gets filled again. Fix that.
    - [x] Add a little clear button to the Initial View and Time slider buttons to reset their contents to emptiness.
  - [x] slider()
    - [x] It has the same bug of not allowing 0 as a year
  Wherever something is a bit complicated for the user to know how to set---e.g. color sequences and color maps, or icons for Point; there should be a little info tooltip with helpful documentation.
- [x] Exporting map JSON and HTML
- [x] Paint unselection with Alt doesn't seem to have been implemented (or doesn't work) with the Territory library, only works with GADM.


Features
- [x] Visual ways to draw Paths, picking locations for Texts and Points.
  - [x] Amazing, well done. Just one thing: show some visual cues on the map when picking points or drawing paths and polygons; i.e. actually show/preview the path or polygon being drawn.
  - [x] Also allow a user to undo the last point by pressing backspace.
    - [x] I think a previous AI agent attempted to implement this, but has failed.
      - [x] Fixed by forwarding Backspace/Escape/Space from the map iframe to the parent (focus is in iframe when user clicks map)
  - [x] Also allow a user to draw a path "freehand" by pressing spacebar (or maybe some other key---you pick whatever makes sense, like what's in line with tools like photoshop?) once, then holding and dragging. Press spacebar again to get out of freehand mode (and then you can continue clicking points normally).
    - [x] Ok, one issue: holding and dragging *also* moves the map around at the same time. Maybe instead of pressing spacebar + dragging, we should change it to holding shift and dragging, and prevent Leaflet from moving the map when shift is pressed.
      - [x] Fixed. However, Shift is actually also used for zooming in to maps, so another conflict. Can we switch to Ctrl+dragging (Cmd should also work for Mac users)?
        - [x] This works as long as I click at least one point on the map before going freehand, or if I hold down my mouse at a point then press control---but if I already have control held and then start drawing, the moving-around doesn't get cancelled---kind of like it needs the map to be in focus for the Ctrl to have the desired effect?
  - [x] Display these tips (backspace, freehand mode)
    - [x] These tips should be shown in a blaring message on the map while picker mode is on, not underneath the box like it currently is.
  - [x] One problem is that the user may forget to un-click the picker and leave it on while picking other co-ordinates. To avoid this, only one picker should be turned on at a time: clicking another picker should turn off all the other ones (and show this visually too).
  - [x] Oh, and for Path the co-ordinates should not be pre-filled with [[28.6, 77.2], [19.0, 72.8]] like they are now: it should start out blank, like polygon does.
- [x] Better Territory setting interface---right now it just lets you pick one individual GADM for a flag, rather than any complex territory. Instead, we should have a fancier system: where you can compose the territory with the | and - operations (so you have buttons "add" and "subtract" which let you define a new step of the operation); in each component you can select `gadm`, Predefined territory or `polygon`.
  - [x] `gadm` should have autocomplete search for all the gadm entities in the data based on their GIDs, names and varnames (there should be a pre-computed list---and make sure you know what these look like, e.g. the "_1"s in the GIDs are not considered by xatra, so we just give gadm("IND.31") not gadm("IND.31_1")).
    - [x] The `_1`s are a bit of a problem, because it means IND.31_1 comes *after* IND.31.1_1, IND.31.8_1 etc. which basically makes it invisible as it is under all its children. Instead you should strip the codes of their `_1`.
      - [x] No, no no---you fixed this wrong. I didn't ask you to strip `_1` from the input field if the user inputs it (please revert this), I asked you to strip it out in the list of GIDs that we search.
  - [x] Predefined territories should be a section under the Code tab, also in the form of a code field. For any existing territory in the Flags, there should be a button to add it to pre-existing territories.
  - [x] `polygon` should, in addition to just typing out co-ordinates manually, have a visual way to draw it on the map---by picking points or tracing them out if some key is held.
  - [x] Still need to implement the ability to actually *use* pre-defined territories in the territory-making (i.e. as an option in the dropdown alongside GADM and polygon).
    - [x] a previous AI agent has attempted to do this, but it doesn't really work: the pre-defined territories do not seem to contribute to the computed territories at all.
    - [x] then there should be autocomplete search for entering pre-defined territories in the pre-defined territory option
    - [x] xatra.territory_library should be imported in the Pre-defined territories code, and available in the list of pre-defined territories (for autocomplete search)
- [x] The user should be able to create AN auxillary "Picker map" for visualizing and selecting admin features and pre-defined territories. The map panel should be tabbed, so the user can create a new (or switch to THE) Picker Map tab---when they create a new Picker Map tab, they will get to set any number of countries whose admin maps (at any level) to load, or instead to create a map with .AdminRivers(), or instead to load the pre-defined territories for visualization.
  - [x] Nice, I like the implementation. However, instead of just one field for Countries and one field for Level, the user should be able to add multiple rows, one for each country and set the level for each. So e.g. I can have IND: 2: PAK: 3.
    - [x] Nice. However, the box and its contents are a bit weirdly-sized (the contents don't fit the box which causes a horizontal scrollbar to appear)
    - [x] The user should be able to search for their country (either by GID or by country name) when entering a country code--just like they can while entering GADM territories for Flags.
  - [x] Then they will be able to select gadm territories from an admin Picker map.
  - [x] that can also be extended to select multiple gadm territories at once from the admin Picker map by pressing some key, and add them as multiple `| gadm(...)` or `- gadm(...)` fields. This will need some re-thinking of how the solution is currently implemented.
    - [x] Very nice implementation. However, I want this to be implemented a bit differently, because there can actually be multiple flag layers with the same label (and this is an important aspect of the app). So instead:
      - The GADM territories have a pick button (use the little arrow icon instead of "Use Picked" text), and that sets the flag layer being selected for to this particular element and also switches the view to Reference Map.
      - The user should not be able to select this flag layer from a dropdown in the Reference Map Options box like they are now (it's too confusing), however it should lightly display the flag name and a number representing which layer with that Flag label is being selected for (e.g. 15 if the 15th instance of that Flag label in the Layers list is being selected for).
      - Clicking a territory should add it to the list of territories being multi-selected, or remove it if it is already in the list. No need for Ctrl/Cmd/Shift, since we're going to do away with the separate single selections feature anyway. Holding Ctrl and moving the mouse should select all territories it moves over (no undoing already-selected territories in this mode); holding Alt and moving the mouse should unselect all territories it moves over. There should be a little tip mentioning this in the Reference Map Options.
      - Instead of choosing +, -, & from a dropdown, let us just have three buttons for us to choose how to add these selections to our territory. Keep the Clear button as it is. These are added/subtracted/intersected to our territory based on the operation button chosen.
      - The divisions in our selection list should be visually indicated on the map.
      - River selection should also just have a pick icon and we pick a river on the Admin Rivers.
      - We can then do away with the legacy "Last picked" and "Use Picked" features.
      - In all of this, make sure these new Pick buttons have the same "exclusivity" as the existing Pick buttons (for paths, points, polygons and texts)---only one is allowed to be on at a time, clicking it turns off the previous Picker.
  - [x] And also selecting rivers
- [x] Code editor should be nice, not just a simple text editor.
  - [x] Main thing I'd like is autocomplete---like in VS Code or in online coding sites like leetcode. It should work as though xatra is actually imported. Maybe can use an actual code editor plugin or something.
- [x] Loading a previously-built map. I think the best way to do this will be to keep the state of the Builder and Code synchronized two-way and just export/import the code both ways.
  - [x] Code generation is quite buggy.
    - [x] One issue I've observed: for rivers it creates a random attribute source_type for River objects, which doesn't exist. This is not necessary, the value is already either naturalearth() or overpass()---you just need to make sure these are imported at the top.
    - [x] When a Flag has a blank value (i.e. nothing has been built in Territory) or anything else is blank, it should default be converted to None in the code, not just left empty causing a syntax error.
    - [x] Eventually we should also implement reverse-syncing the code to the builder, so might be worth thinking about how to better store the state
    - [x] Also need to make sure any changes to the pre-defined territories code will update the stored territories.
    - [x] Once we have arranged the two-way synchronization perfectly, the Builder-Code syncing should be modified to happen automatically upon switching from Builder to Code and vice versa, rather than manually clicking Sync from Builder
- [x] Better keyboard-based navigation. This will need to be implemented very carefully and thoroughly, making sure everything is easily accessible by keyboard or has convenient keyboard shortcuts---these should all be documented in the little keyboard shortcuts hint panel that appears when pressing ? or clicking the button for it.
    - [x] It should be made possible to navigate the autocomplete searches via keyboard---both in the territory GADM picker and in the Reference Map autocomplete-search for countries.
      - [x] When going down on an autocomplete search, it should scroll the autocomplete search box as necessary.
    - [x] Keyboard shortcuts for adding a new layer
    - [x] When a new layer is created, its first input field should immediately be focused.
      - [x] A previous agent attempted to do this, but it doesn't seem to be working. The input field should be focused so that the user can immediately start typing.
    - [x] Keyboard shortcut Ctrl+Space to run "Update Reference Map" if in the Reference Map tab or "Update Territory Library Map" if in the Territory Library tab
      - [x] This is a bit unreliable---Ctrl+Space stops working if I click on the map, or if I click on the checkboxes in the Territory Library options, or if I click on the input fields in the Reference Map Options.
- [x] Territory library tab (Ctrl/Cmd+5)
  - This will be a third map tab after "Map Preview" and "Reference Map", and will serve to visualize territories in the territory library.
  - Within this tab, there are multiple tabs. There is one tab for xatra.territory_library and one tab for those that the user has saved to library/entered in the Territory library code editor.
    - [x] In future, when we have multiple territory libraries (i.e. when it's a proper website where people can publish their own territory libraries), it will show 
  - Within each sub-tab, the territories in that list are plotted on the map (i.e. by wrapping them in Flags and letting their labels be their variable names).
  - [x] When the user is entering an item from Territory library while building a Territory for a Flag, he will have a little Picker button. Clicking this will take him to the Territory Library where there will be a very similar multi-selection UI as in the Reference Map tab.
  - [x] Hmm, ther seem to be too many things in the territory library to render. Instead, the territory library file should include an index at the end __TERRITORY_INDEX__ = ["TERRITORY_1_NAME", "TERRITORY_2_NAME", ...] and there should be a checklist of territories in the Territory library map---the checklist will contain all the territories in the library, but only the ones in the index will be checked by default, while extra ones can be selected and rendered by the user. If there is no __TERRITORY_INDEX__ variable in the territory library (whether xatra.territory_library, the user's custom territory library for this map, or in future any imported territory library), then it should be considered [], i.e. all the boxes should be un-checked. When the user selects a bunch of checkboxes, there should be a button to copy the list consisting of those selected territory names so that they can be used as a __TERRITORY_INDEX__.
    - [x] The Orange banner (about Shift and backspace) should not appear for territory picker.
    - [x] It shouldn't re-render the territory library map every time a checkbox is marked or unmarked---instead it should only update when the button to re-render the map is pressed
    - [x] It also shouldn't re-render the territory library map every time we navigate to the territory library tab.
    - [x] However, it _should_ render the territory library map in the background when the page is loaded (just like the reference map is loaded in the background).
    - [x] Why is there a tip saying "Default index: VRJISTHANA, VARNU, VANAVYA, APRITA, PSEUDOSATTAGYDIA_S, ..."? We don't need this, we can already see in the checklist which boxes are marked.
    - [x] The territory library checklist should have a search bar to filter and select the checkboxes based on your search term.
    - [x] The "Copy index" button should be an icon instead of text, and when it is clicked it should temporarily show a visual cue that it has been copied to clipboard.
    - [x] When it is rendering one of the maps (Map Preview, Reference Map, Territory library), why do all the other maps also need to get blurred out and blocked from interaction?
    - [x] with regard to how the Reference Map and Territory Library render in the background when we first load the page, it is a bit misleading because it just shows "No map rendered yet" with no sign of rendering going on. Instead it should show the usual blur Generating screen over those maps. Also in the Territory Library box the checklist and everything should be fully displayed before waiting for the map to load.
- [x] Flag Territories: Recursive territory construction. Right now Flag Territories can only be created as simple sequences of operations (add, subtract, intersect) of base territories, i.e. without any "brackets".
  - [x] Implement the ability to construct arbitrarly nested territories, i.e. in addition to "GADM", "Polygon" and "Territory library" the user should be able to pick "Group..." which should create an indented list similar to the root one, starting with a Base and the user can add further operations to it, etc.
  - [x] Make sure it flows properly with the code conversion (both to-and-fro)
- [x] Flag Territories: Implement the ability to enter multiple comma-separated GADMs or Territory library items in a GADM or Territory library field. These should be displayed nicely as little boxes in the text field with cross buttons to remove them, the search autocomplete should work properly (i.e. ignore existing entries in the list) and all normal editing in the field (backspace etc) should be smooth. Under the hood, the GADMs and Territories will be in a little bracket of their own, being unioned.
  - [x] This will allow a better way to use the GADM picker and the Territory picker. Instead of selecting some number of territories and choosing whether to add/subtract/intersect them in sequence from the territory---it should simply insert whatever is selected with the respective Territory picker as a comma-separated list into that field.
  - [x] Again, make sure it flows properly with the code conversion (both to-and-fro)
  - [x] Upon entering the GADM or Territory library picker, a blaring message (same design as the one for Paths/Points/Texts) should appear saying "Click regions to toggle selection. Hold `Ctrl/Cmd` and move to paint-select, hold `Alt` and move to paint-unselect."
- [x] Auto-save feature --- edits made in the alpha version of a map (which is the only version you can make edits in), whether in the Builder or the Code editor, should get periodically saved (not as a new version, just in the alpha version) (unless the entered map name conflicts with the name of one of the user's existing maps, in which case it should _not_ save it) and display a little indicator at the end of the second line (i.e. after the author username, like count and view count) that says things like "Unsaved changes" "Saving..." "All changes saved" "Save failed: map with name {map name} already exists".
  - [x] In fact, instead of "Unsaved changes" it can show an actual clickable "Save" when in that state.
  - [x] To avoid confusion, we should stop calling our current version-publishing feature "Save". Its icon should be changed from the Save icon to something that looks more like a "Publish" icon. This applies both to the version-publishing button on the main map (next to the title) and for Custom territory library and Custom theme in the Code editor.


Minor changes
- [x] "Rivers" in the add Layers panel should be "All Rivers".
- [x] "Picker Map" should be called "Reference Map" instead.
- [x] The panel for adding layers should be at the *bottom* of the layer list, so that new layers just get added on top of it (while scrolling just to compensate for the new element to ensure the panel is still in view) rather than having to scroll all the way to the bottom like it is now.
  - [x] Thank you---but can you make it automatically scroll to the very bottom of the panel after adding any new layer?
- [x] should be able to reorder the lines of the territory builder (the operations) around by dragging them (and it should also reorder them in the internal state)
- [x] when you save a territory to library, it should be case-sensitive, i.e. if you store the territory of a flag called "India" its variable name should be "India" and not "india".
- [x] We now have visual cues for drawing paths and polygons, thank you---just one thing: the *vertices* of paths and polygons should also be shown in this visual cue, with dots, so that even the first point drawn can be seen on the map before any actual line is drawn.
  - [x] Also implement this for Points and Texts. When a point has a pre-existing value for Position and you hit the "Click on map" button, it should show that little point on that map with the same sort of dot.
    - [x] Also: these visual cues should appear regardless of which map (Map Preview, Reference Map, Territory Library) we're on. Right now they appear for the former two but not the last one.
    - [x] For points and texts, the visual cue (the dot) at the point where we click should persist for a fraction of a second after we press it, so that we can still see it even though the Picker mode is instantly turned off.
- [x] The "Note" field should have monospaced font.
- [x] Everywhere we use the term "Pre-defined territory", use "Territory library" instead.
  - [x] And include a from xatra.territory_library import * line at the top, since all those territories are included in our library---and in a comment right next to it, link to https://github.com/srajma/xatra/blob/master/src/xatra/territory_library.py. Remove all the other junk comments pre-filled there by default.
- [x] In "Reference Map Options", just like there's a label "Countries" for the country field there should be a label "Admin Level" for the Admin Level field.
  - [x] Also, the levels entry field should be a dropdown with all the admin levels available for their country (these should be pre-computed and kept in an index).
- [x] The Keyboard Shortcuts panel should have a little icon to toggle it so the user can see the keyboard shortcuts list even if he doesn't already know that `?` does the job.
- [x] Clicking "Render Map" (from either Builder or Code) should set the tab (which can currently be "Map Preview" or "Reference Map") to "Map Preview".
- [x] The picker icons for picking GADMs and Rivers from the Reference Map, and for picking territories from the Territory library map, should match the nicer icon that is used for picking co-ordinates from the map for Points/Texts/Paths/Polygons.
- [x] Under the title "Flag" in a Flag layer, there should be a small note: "A <b>Flag</b> asserts the reign of a State over a Territory (perhaps for a particular period of time). Flag layers with the same State name are rendered as the same geometry."
  - [x] Oh, and change the displayed label of the "Label" input field to "State name" instead of "Label" (obviously the underlying parameter should still be "label").
- [x] In the GADM picker, when we press the Add/Subtract/Intersect buttons (to add the selections to a Flag layer's territory as operations), any blank GADM row in that Flag layer's territory (blank meaning: without a value/with the value field blank) should be deleted after the new operations are added. Similarly in the Territory library picker, when we press the Add/Subtract/Intersect buttons, any blank Territory library row in that Flag layer's territory should be automatically deleted after the new operations are added.
- [x] By default, the Reference Map should be loaded as IND-2, PAK-3, BGD-2, NPL-3, BTN-1, LKA-1, AFG-2 with Admin Rivers. The loading can happen in the background while the user can still work on things.
- [x] The countries column in the reference map should allow any GADM ID, not just country codes---since xatra.Admin() allows for it. So its search autocomplete should be exactly like that of the GADM entries in the Flag layer territory building, and there should not be any restriction on the characters (since we might want to search for these things by name). The level dropdown should still be taken from the country code part of the GADM ID (i.e. for IND.20 still take the levels list from that of IND).
- [x] When "Generating Map" is going on (for whatever generation---either the Map Preview, the Reference Map or the Territory Library), it blurs out everything in the map frame, including the Reference Map options box and the Territory library box. It should leave these boxes available for the user to interact with while the map renders.
- [x] Remove this hint: `Ctrl/Cmd+5` opens this tab. `Custom Library` uses the code from the Code tab's Territory library editor.
- [x] TitleBox should actually not be a global element, but a layer---xatra supports adding as many "TitleBox" elements as you want, e.g. with different periods. As with the other layers, the "period" field should be present.
- [x] Remove the "Hold Ctrl/Cmd + drag for freehand ⌫ Backspace to undo" tip that appears in the sidebar when you click the Picker for Paths---since it already appears on the map in a blaring orange message, which is enough. Similarly upon making the Picker changes, the right sidebar of GADM will no longer need "Tip: Click regions to toggle selection. Hold Ctrl/Cmd and move to paint-select, hold Alt and move to paint-unselect.".
- [x] Flag Territories: UI improvements for dragging items---
  - [x] Scroll sidebar when dragging beyond current view
  - [x] Right now if I'm trying to move Item 5 above Item 4 (counting from the top), Item 4's border gets highlighted blue to show it's getting "jumped" over---and when moving Item 5 below Item 6, Item 6 gets highlighted. This is confusing. Instead, a small horizontal line above Item 4 should get highlighted blue (taking care to ensure those lines between the items already exist, so it doesn't cause stuff to move up or down a pixel when it highlights blue); likewise when moving Item 5 below Item 6, a small horizontal line below Item 6 should get highlighted.
  - [x] Instead, the blue highlight on borders should be shown when moving an item into a group: the group's border should get highlighted blue.
  - [x] Now we can hide the little "Drop here to move inside this group" "Drop here to move to end of this level" hint boxes.
- [x] It should be possible to drag items around with the keyboard: Shift+Up to go up, Shift+Down to go down, Shift+Left to exit group upwards (i.e. go to the position right above the group the element is in), Shift+Right to exit group downwards. A small hint should appear below a territory when it is selected, displaying these keyboard shortcuts.
- [x] Flag Territories: Better UI for "Add Operation" 
  - [x] Instead of a single "Add Operation" link, there should be three separate links "(+) add / (-) subtract / (&) intersect".
  - [x] Upon clicking one of those buttons (or pressing +, - or & when that particular Flag item or anything therein is focused), it should turn into a prompt asking what sort of territory you want to add, e.g. if we select subtract then it expands to "(-) subtract: _**g**adm_ / **p**olygon / **t**erritory / gr**o**up / [Esc]". It immediately focuses on gadm (so it is underlined), and we can cycle to focus a different option with arrow or tab keys. Preessing Enter or clicking one of those options selects it. Pressing the respective bolded key (g, p, t or o) also selects that option. Navigating to Esc, clicking it or pressing the escape key on the keyboard escapes this selection and returns the state of the links to "(+) add / (-) subtract / (&) intersect". So e.g. if we press "o" here it would create an entry with operation "-" and territory type "group".
  - [x] Upon creating this entry, its field should immediately be focused (if GADM, Polygon or Territory) or the "Define Territory" button should be focused (if Group).
  - [x] Likewise, when clicking "Define Territory" it should lead to the "Base: _**g**adm_ / **p**olygon / **t**erritory / gr**o**up / [Esc]" state.
- [x] Don't use the word "GADM" in the Flag territory builder (users won't understand) instead use "Admin unit"
- [x] Change the button for downloading the Project JSON to a download icon (it's currently a save icon, which suggests just saving the map to the database). And remove the option to download the Map JSON ("Export Map JSON"), it will confuse the user. And maybe change the icon for Export HTML to something that looks like a map and change the hover tip to "Download Map" (rather than "Export HTML"), the user doesn't care that it's in HTML format, just that it's a nice visual map.
- [x] Add users list in the sidebar
- [x] Make the "Map description" prompt use a dialog within the website's design rather than bizarrely using a browser pop-up for the purpose. Obviously make sure it is keyboard navigable (enter, escape should perform the expected functions)
- [x] There is a default Flag layer that gets loaded when a user loads the GUI for the first time. That's fine, but initialize it with a territory that is GADM IND, rather than None.
- [x] The "Explore" page should not show the version dropdown and Open buttons. It's too complicated; the user can already open the map by clicking its name, that's enough.
- [x] When the Territory picker is active, the blaring orange banner ("Click regions to toggle selection...") should appear at the bottom of the map frame, not at the top (where it covers the sub-tabs).
- [x] The version-publishing buttons in the Custom territory library and Custom theme sections of the Code editor should show visual indications just like the version-publishing button for the map itself. Like: display you when a new version was successfully published; when "No changes" etc., actually update the version list dropdown... This whole thing is quite bugged; fix it.
- [x] In the xatra menu change "Load" to "Load JSON"; "Save" to "Save JSON", "Export" to "Export HTML".
- Forking
- [x] The Reference Map selections (which countries/GADMs, which admin levels, whether to show Admin Rivers or not) should be stored as part of the map state, kept in the database (so that is selected again, instead of the default, the next time the particular map is open) and in the savable JSON.

Keyboard navigation
- [x] Should be something to navigate the sub-tabs in the "Territory library" tab: let's say---Ctrl/Cmd+0 should focus those sub-tabs, allowing us to use arrow key or tab/shift+tab to cycle through the sub-tabs. This should be documented in the keyboard shortcuts hint panel as "`Ctrl/Cmd+0` Focus Territory library sub-tabs" (under the `Ctrl/Cmd+5` hint).
- [x] Enter to submit on Login/signup page (make sure it submits the correct form)

Design improvements
- [x] introduce a dark mode
- [x] the "Xatra Studio" title is cheesy. Replace it with just xatra (lowercase), and no icon.
- [x] allow the user to freely resize the left sidebar
- [x] Design consistency and prettiness---the main map editor has nice design; everything else (i.e. the Explore, profile and Login pages) have jarringly boring UIs.

Experiments I have to do
- [x] Make sure my existing maps work in this
- [ ] Play around as srajma/ to make sure
  - [ ] Split "indic" territory library into separate territory libraries
  - [ ] Add all the maps
- [ ] experiment with some different designs [NOT NOW]

Bugs we still have
- [x] when I publish a new version of a map, it doesn't automatically add that version to the version dropdown---same thing with publishing new versions of Custom territory libraries or themes (in the Code editor).
- [x] When I create a new map, it gets auto-saved after a few seconds even though I have not made any changes.
- [x] Any map I load immediately just shows the map for India in the Map Preview at the start until I click "Render Map". It should render the actual map on first load instead.
- [x] Not every map has a Territory library or Theme that can be imported from other maps (i.e. not even an alpha version may have been created) --- which leads to errors like "Cannot import css: /srajmabr/css/xatra_2_1 does not exist". In such case, the "Import CSS" and "Import Territories" buttons should be greyed out and not available to click.
- [x] When editing a new map, the save button no longer automatically appears (and autosave doesn't happen) when I make some changes---I need to publish a version first. This is not the intended behaviour; I should be able to save the alpha version without publishing any version.
- [x] When a map has no versions (e.g. if it's an unsaved map), the version dropdown appears empty. In this case, the version dropdown shouldn't appear at all.
- [x] Drafts don't actually seem to be getting saved for logged-out users? Like if I make some edits, then reload the map editor (or open it in a new tab), it just shows the default map without my changes
- [x] Editing the name of a map doesn't seem to do anything: it should register that as a change for saving/showing the save button/auto-saving; and when the change is saved, it should change the URL of the page (without causing a refresh) to point to the resulting new URL of the map.
- [x] Our current new map and landing page workflow causes an unnecessary proliferation of maps, because:
  - [x] every time we go to the landing page (which is the New Map page), we create a new map if there is no existing draft. While this makes sense for users who are not logged-in; for users who are logged-in and do not have a draft, it makes more sense to take them to their profile page where they can view a list of their maps (_unless_ they created a draft when logged-out, in which case it should load that draft for them on the landing page map editor).
  - [x] For users who are logged in, the "New map" button should actually prompt them for a name for their new map (in a nice little thing dropping down from the "New map" button), annoy them until they pick a name that's not taken, and create a new map (not a draft) and take us to the URL of that map directly to edit it, rather than keep us at a `new-map` URL. So logged-in users should only ever be able to create a draft when logged-out (in which case they should be taken to that draft after logging in and have the opportunity to save it if they want). So the /new-map URL should basically not exist --- for guests, the "New map" button should just take them to the login/signup page (the langing page itself should show the map editor for their draft, as usual of course)---for logged-in users, it should do what I described.
- [x] Behavior of drafts and saving is still very weird.
  - [x] For logged-in users, a red "Unsaved changes" blurb should appear as soon as there are any unsaved changes (this already appears for guests) and disappear only once the save or autosave is completed (unless there are again any unsaved changes, in which case it should stay)
  - [x] When a guest who has a draft logs in, that draft map should be loaded within their account with a red "Unsaved changes" and Save button.
  - [x] The "New map" button only seems to work from the map editor for some reason? It should work everywhere.
  - [x] The logic for the version dropdown seems to depend on the name entered in the name field rather than the actual identity of the map loaded. This is quite stupid, and must be fixed.
- [x] Actually I have a better idea for the whole drafts/landing page/saving flow: (don't do this now, I have to flesh it out)
  - Only for logged-in users, the Explore page will have a section above for the logged-in user's own maps. It will be a single-row grid, starting with an "Add New Map" entry (a nice big box the same size as all the other entries), then an "Unsaved Draft" entry _if it exists_ (again a nice big box, but the "Unsaved Draft" title should be in red), then the user's few recent maps---and then there should be a little "More >" link that takes the user to his profile page.
    - while we're changing the Explore page, you can also change the weird "box inside a box" design of the search bar.
    - [x] Oh also add the same "New Map" and "Unsaved Draft" icons on the user's own profile page (only the logged-in user's _own_ profile page, not anybody else's).
  - For logged-in users, this new /explore should be the landing page. 
      - [x] Uh, the Unsaved Draft still does not appear in the user profile page? Also both the New Map and the Unsaved Draft buttons should appear in the same grid as the user's list of maps, they don't need a separate row for themselves.
  - If a logged-in user clicks the "Unsaved Draft" entry, they should be prompted to give a name for the map (and make sure they do not give a conflicting name), then it should convert that draft into a map with that name belonging to the user and take the user to that map, deleting the Unsaved draft from the database.
  - The logged-in user should _never_ be in a situation where they are editing a draft directly. Make sure of this! Make sure they cannot access a map editor at any endpoint like /new-map (such things should just redirect them to /explore); that causes a mess.
  - When a guest user logs in, any Unsaved Draft belonging to them should be transferred to the logged-in user (so the guest user should not have an unsaved draft any more), replacing any existing Unsaved Draft belonging to that user
    - [x] Actually, this has an unintended result: if a user logs in, then doesn't save their unsaved draft, and logs out, the guest draft will get     
   reset to the default map (empty with just gadm("IND")), so when they log in again their unsaved draft will get replaced with this default map. Instead, when the guest logs in, that unsaved draft should get duplicated (so both the logged-in user and the guest have identical copies of it).
   - [x] Uh there's still a weird issue: a logged-in user editing any existing map or creating any new map seems to also overwrite the unsaved draft. This is wrong; like I said, nothing the logged-in user does should ever affect the unsaved draft. Go through things very thoroughly so this is guaranteed.
  - For the guest, the landing page should still be the map editor.
  - [x] Ok there is still a weird issue with "New Map": if a logged-in user has unsaved changes in a map he is editing and creates a new map, that new map gets loaded with the content of that unsaved map. I don't understand how such a simple thing can be so bugged, to the point that I wonder if the AI agents I'm asking to work on this simply do not understand the intended behaviour. All that New Map needs to do, is **create a new map with the standard, default initialization** with the name given by the user in response to the prompt. There is simply no reason why it should have any dependence on where it is clicked from. This bug (of initializing the content with that of the current map editor), the previous (now-resolved) issue of it not loading the relevant data when initialized from the Code editor, the previous (now-resolved) issue where it wouldn't work on any non-map-editor page, all suggest there is some totally wrong logic being used to implement it. [SEEMS TO BE FIXED FOR NOW]
    - [x] Another issue with New Map. I created a new map. It loaded with the whole editor greyed out, no user name after "by", the default author like not registered, a fork button instead of a publish button etc.---i.e. it did not perceive that I owned the map. When I reloaded the page, it redirected me to /explore, indicating that the map hadn't been created. But then after a minute, the name of the map appeared in /explore and I could access and edit it normally. What on earth? [SEEMS TO BE FIXED FOR NOW]
- [x] Anonymization is very buggy; sometimes an anonymized map reappears in the user's profile with some underscores.
- [x] The New map button doesn't seem to bother checking if the name of the map entered already exists, and allows overwriting existing maps. This is bad!
- [x] The New map prompt on the map page and on other pages seem to be slightly different? Why? E.g. the New map prompt on the other pages does not respect dark mode for some reason.
  - [x] Also the "Save map" dialog for saving an unsaved draft should respect night mode.
- [x] For some reason, the "Published v1" message doesn't appear when the first version of a map is published. It appears for versions after v1 though.
- [x] For some reason, when I click the "New map" button when I am on the code editor of another map, the resulting map does not have the default elements (the Flag with name India and territory gadm("IND"), the default base options and color sequences etc.) This is quite surprising behavior---how exactly does the New map button work? Why does it even depend on the page I am currently on?
- [x] Keyboard shortcuts (stuff like Ctrl/Cmd+<number>, Ctrl/Cmd+Enter, Ctrl/Cmd+;) don't get captured when the map frame is focused.
- [x] In many fields, setting a value for it then resetting it to None/empty etc. doesn't correctly reset it but resets to the wrong thing. One example is "Inherit Color from" in Flag territories, but there may be other examples.
- [x] Drawing Paths, Polygons, Points with the Picker has become very buggy:
  - [x] Simply clicking the picker icon sometimes randomly loads some existing points into the field. I have no idea why or how this would happen---it sometimes even happens with totally fresh new maps! In fact, sometimes the points just infinitely keep getting added! (this also makes my computer overheat)
  - [x] The previewed path/polygon on the map doesn't even properly reflect the co-ordinates in the co-ordinates field. Sometimes there will be a whole bunch of co-ordinates in the co-ordinates field, and yet only one point will show up in the preview.
  - [x] Holding Ctrl/Cmd to drag free-hand does not behave as intended in polygons. Say we already have points a, b, c and then draw freehand x1 x2 x3 x4 ... You would expect lines from c to x1, x1 to x2, x2 to x3, ... but instead the preview shows lines from c to x1, c to x2, c to x3, c to x4 etc. And when I click Render map, the polygon doesn't even render! WTF?
  - [x] Backspace does not remove the previous point.
- [x] Ok, the above bugs with drawing Paths, Polygons, Points with the Picker are fixed/much better; however there's still one issue: the moment I click the picker for a new (empty) field, the field gets populated with the last point I had selected (for any other item/layer). Instead it should be initialized with the empty list.
- [x] When running the server I get a lot of "404 error not found"s in my logs in the terminal. It doesn't actually hamper my usage of the site in any way; it's just that it might be worth knowing what's causing this and if it's something that should be fixed/handled better.

Random misc
- [x] On the new map creating editor, non logged-in user should see a red "Unsaved changes" message on the second line (i.e. below the name field etc.) as soon as they make any change worth saving, and a "Login to save/publish" link after it (this should be visible whether or not the user has made any changes).
  - [x] And when the user logs in and is returned to the map editor, make sure it correctly shows "Unsaved changes" since the map has not yet been saved.
- [x] change "three-line menu" (on the map editor) and sidebar (on the explore and profile pages) to a unified top bar.
  - [x] On the left-most of the top-bar: "xatra" (the site title); Load JSON; Save JSON; Export HTML (keep the existing icons for these)
    - [x] Oh, the Load JSON; Save JSON; Export HTML buttons should only appear on Map pages. And Load JSON in particular should not even appear when looking at other users' maps.
  - [x] Right-aligned: New map (this should stand out); Explore; Users; Night mode toggle (should be literally just a nice toggle with night/day icons, no "Night mode" text); `[username](link to profile)` if logged in; Login/Signup or Logout (depending on whether logged in or not)
  - [x] `Ctrl/Cmd+;`, which currently clicks the triple-line menu, should instead focus the top bar allowing us to cycle through it with tab or left-right arrow keys. Make sure to update the keyboard shortcuts hint panel.
- [x] Use image of map from last save as the map's thumbnail (in the Explore, User page and Import from xatrahub interfaces). For this you must figure out how to best capture an image of the rendered map.
- [x] improvements to forking and voting
  - [x] forks should show "fork of [...](link to original map)" under their page's byline (i.e. under "by <user> . likes . views")
  - [x] forking a map should automatically vote it up
  - [x] users should by default have liked their own maps, and should be unable to change this
- [x] voting
  - [x] Map vote counts are buggy---when loading a map, it shows "0 votes" (both on the map page and on the Explore and User profile pages) even though they are always supposed to start with 1 vote (from the map's author). But when I check out the published versions, the vote count updates to the correct vote count, even on the Explore and Profile pages.
  - [x] Instead of changing the color of the little triangle to show when the user has liked a map, the whole like-count box should be shaded blue (with white text) to show this. There should also be hover styling. 
- [x] For maps the user can't edit (i.e. other users' maps, and even the own users' published versions), the whole Builder/Code side panel appears greyed out. While this makes sense, the "Render Map" button should not be greyed out; it should still be clickable---even for guests!
- [x] Move the anonymize/disassociate button in the map editor to the top bar after the export button (obviously, the button should only appear on map editor pages, specifically only on the user's own maps) and change the icon to a red trash button.
- [x] The right side of the top bar looks a bit cluttered.
  - [x] Explore should not be icon-only, but should be a button with an icon followed by the text "Explore". The icon should also be changed back to the old compass icon instead of the search icon.
  - [x] The Night mode toggle and keyboard shortcuts hint button should be to the Left of "New map".
- [x] it may make sense to go from map names being unique per-user to unique globally, and change map/territory/theme slugs to not use the username (i.e. be simply `lib/mapname` rather than `lib/username/mapname`; `map/mapname` rather than `map/username/mapname`; `css/mapname` rather than `css/username/mapname`)
  - [x] This will have to be updated in the original xatra project's hub.py (I maintain it, it's in `../xatra.master`) as well as in the imports list here, etc. [NO, APPARENTLY THIS IS NOT NECESSARY]
  - [x] putting a username in between should still work for backwards-compatibility
  - [x] Since map names must now be unique globally, the default name counter cannot simply increment as `new_map_<n>`. Instead just let the default name be the ID of the map in the database (assuming such a numeric ID exists---if not, make one). The name of a map should never be allowed to entirely numeric _unless_ it happens to be that map's ID.
  - [x] In order to prevent conflicts (since map URLs will now simply be `/<mapname>`), user profile pages should now appear under `/user/<username>` rather than simply `<username>`. Non-existent URLs (like `/oogabooga4473`) currently show a fake user page---instead, you should just show the "Uncharted territories" 404 error page.
  - [x] There is the question of how to migrate existing map names. We can just migrate them all to their integer IDs for now; taking care to ensure that imports in existing maps also change along with this. Only the `srajma/.../indic` case needs to be handled specifically, rename this to `dtl` (for default territory library) and make sure that all references to it (in imports, in default imports, in the code for pre-seeding this library in the database etc.) use this new reference.
  - [x] the main reason to make this change is to let users change their usernames without breaking links/imports to their maps. For the same reason, it should not be possible to change the name of a map after publishing a version of it or of any of its territory libraries and themes (it should warn the user of this when he tries to publish v1 of either the map or a territory library/theme, asking for confirmation).
    - [x] Currently, a user can still edit the name field of a map; it just gets saved as a new map. Instead, the name field should simply be greyed out completely if there are any versions (besides alpha) of that map. Also remember: it should warn the user of this when he tries to publish v1 of either the map or a territory library/theme, asking for confirmation before doing so.
    - [x] Oh, also it seems that even editing the name of a map _without_ non-alpha versions is creating a new map instead of editing the name of the existing map. This is a bug; users **should** be able to edit the name of a map if neither the map nor its theme or territory library have any non-alpha versions.
- [x] Change the icon for likes from a heart to a simple upwards triangle (meaning "upvote"). And change the icon for "/explore" from the compass to a search icon.
- [x] Make sure the xatra top bar is everywhere: on the "Loading editor context" page, on error pages etc.
- [x] Increase the number of items in the grid on the user profile page to 6 (it seems to be 4 at the moment).
- [x] allow user to "disassociate" their maps from their usernames on their own user page, and on the map's page. This is better than allowing deletion, so that published maps/themes/territory libraries still exist and can be used; they're just not associated with that user's name. Use an icon for "Anonymous", if such an icon exists; otherwise just use a simple trash icon. It should prompt the user for confirmation before anonymizing; making it clear to him that he will **lose all ownership and editing rights** to this map (though he can fork it) and make him type in the name of the map before anonymizing it.
- [x] Make Import panel more keyboard-friendly.
  - [x] Pressing the down key from the search bar should focus the first entry in the grid of maps.
  - [x] We should be able to navigate the grid with arrow keys.
  - [x] Pressing the up key from a map in the top row of the grid should take us back to the search bar
  - [x] Oh one last thing: escape should close the import panel
- [x] Instead of having a separate "/users" page, merge it into "/explore" by using a column view and making Users (with its own search bar, like it has now) the little right column. Make sure this doesn't mess up the Import panel in maps, which may share some UI with /explore. Also update the top bar to remove the link to /users.
- [x] You know the little keyboard shortcuts panel? Move the button for that (which is currently inside the map preview for some reason) to the top-bar, next to the night mode toggle.
- [x] Re-design the Profile page to give main focus to the list of maps (and have a thumbnail-based grid view exactly like /explore); while the account settings and stuff appears as a collapsible form that is collapsed by default.
- [x] Make sure all the obvious things can be set by environment variables---admin username and password, backend and frontend ports, anonymous username, whatever makes sense---and create a .env file showing our defaults for these.
- [x] Add support for the new xatra.Music() layers that have just been implemented.
  - [x] The interface for the Music layers is wrong. Have you looked at what its fields actually are in xatra? The xatra repo is in ../xatra.master.
    - It should not ask for a path to the mp3 file, but should have a file upload UI (and it should upload from the _user_'s system, not a path on the server system, obviously).
    - It has two optional fields: Period and Timestamps. Both of these are optional fields, so should be collapsed by default in the UI.
- [ ] Parse territory libraries and themes before allowing them to be published as versions. 
  - exactly how are territory libraries and themes imported? Are they imported directly as Python code? I saw an error saying "oqow is not defined" because the territory library I was importing lib/owokwod/v2 had a random string "oqow" at the end, suggesting that territory library code is simply run as arbitrary Python code without parsing?! No, territory libraries must be stored and parsed exactly like Flag territories: i.e. every territory must be comprised from trees of operations out of admin units, polygons, and other (perhaps-imported) territories. Similarly, the "Custom theme"s should not simply be execed as code but rather parsed into xatra layers (typically xatra.CSS(), xatra.BaseOption(), xatra.FlagColorSequence(), xatra.AdminColorSequence(), xatra.DataColormap()).
- [ ] In the Code -> Builder conversion/parsing, when we convert Flag values into builder syntax, we should always try to 
when we convert unions of gadms or unions of custom territories, we should always try to parse them into lists of 

intersecting territory librarues
comma in gadm autocomplete

Development difficulties
- [x] keeping synchrony between things---this should be documented, i.e. "if you change this, then change this too"
  - See "Development / Synchrony" section below.

Proper database of maps
- [x] A database of:
  - users
  - users may save, edit their own:
    - maps (where it currently says "xatra" in the top-left of the GUI there will be the name of the map, which can be edited at any point by the user---only characters allowed are lowercase letters, numerals, underscores and dots---no spaces). It will also have a version number (which may be "alpha"), a "save" button next to it---and a "copy" button to copy the slug of the map name (e.g. `xatrahub("/username/map/mapname")`) for import.
    - territory libraries (i.e. their "saved territories") in any map. Basically they will have a version number (which may be "alpha"), a "save" button next to the Territory library section of the code editor which will create a new version of that territory library (with the same name as the map itself)---and a "copy" button to copy the slug of the library name (e.g. `xatrahub("/username/lib/libname")`) for import.
    - map themes (also just Python code, but typically comprised of xatra.CSS(), xatra.BaseOption(), xatra.FlagColorSequence(), xatra.AdminColorSequence(), xatra.DataColormap() elements). This will be another code editor in the code editor tab alongside "Territory library" and "Map code", and again have the version number, save and copy slug icons next to its title.
    Only the names of the maps, territory libraries and themes will be synced; their versions are only updated when their respective save buttons are clicked.
  - each of these will have basic integer versioning, so the user can any time choose to publish the current state of that map/library/theme as a new version number. The current state (not necessarily published as a version) is considered the "alpha" build.
- [x] Importing maps, territory libraries and themes from the database (whether their own or another user's) into their project. Importing maps will allow people to smoothly combine maps of e.g. different kingdoms or different regions of the world into one.
  - [x] server should expose an API for getting any particular map, territory library or theme on the website as /username/map/mapname/12, /username/lib/libname/3 /username/css/themename/alpha (where the last number is the version number) and a registry of such "packages"
  - [x] We'll have to modify the xatra library itself (which I also maintain---it's in ../xatra.master) to allow importing from this library via the API, i.e.
    - `xatrahub("/username/map/mapname/12")` and all the elements in that map just get included in ours
    - `xatrahub("/username/css/themename")` similarly 
    - `lib = xatrahub("/username/lib/libname/3")` then use `lib.TERRITORY_NAME` etc. as territories
    - We could either get these as exact Python code (and exec it) or as project json that is interpreted and loaded into Python, whatever makes most snse
    - `xatrahub` should also take optional arguments `filter_only` and `filter_not` which, for maps and css, allow you to supply lists to filter which elements in the imported code are used in your code, i.e. `filter_only=['Flag','River']` ensures only you only import xatra.Flag and xatra.River elements or `filter_not=['TitleBox']` ensures you do not import xatra.TitleBox elements.
    - There will have to be a XATRAHUB_URL constant (which can be read as an environment variable)---by default, it will just point to the localhost URL of the API, but in future when we publish the xatra GUI as a website we will change this to a public URL.
  - [x] In xatra gui, the user should have an interface to import maps/themes/territory libraries (should be able to search through names, descriptions, usernames of contributors) from the Builder UI, which get translated into the `xatrahub(...)` statements in the code and vice versa. The interface should also include the ability to set the `filter_not` attribute through checkboxes.
    - [x] The current `xatra.territory_library` will be published on `xatrahub` under the admin user `srajma` i.e. `/srajma/lib/indic`. In the xatra Code editor, the default import will then be `xatrahub("/srajma/lib/indic")` rather than `from xatra.territory_library import *`.
      - [x] Also in general the Code editor tab needs to be a bit more organized. Instead of duplicating content between different code boxes in that tab, we should have the following sections with _distinct_ contents:
        - Imports of all the important things in xatra, i.e.
        ```python
        import xatra
        from xatra.loaders import gadm, naturalearth, polygon, overpass
        from xatra.icon import Icon
        from xatra.colorseq import Color, ColorSequence, LinearColorSequence
        from matplotlib.colors import LinearSegmentedColormap
        ```
        (this could even be fixed and read-only, if possible)
        - xatrahub Imports (including map, theme and territory library imports)
        - Custom territory library (with its version/save/copy icons as mentioned)
        - Custom theme---this will include xatra.CSS(), xatra.BaseOption(), xatra.FlagColorSequence(), xatra.AdminColorSequence(), xatra.DataColormap() elements. (with its version/save/copy icons as mentioned)
        - Map code, i.e. _not_ including the contents of the other fields above
        - Not-for-library, i.e. code you only want to be executed in this map but not be part of the library (basically the analog of an `if __name__ = "__main__"` block).
        Finally these code editor blocks should be "stuck" to one another with just the headings (with version/save/copy icons) of each section between them, and those headings should be similarly darkly-backgrounded to fit in with the flow of the code editor boxes perfectly. You know what I mean?
    - [x] The "Territory library" tab in the GUI, currently there are just two tabs "xatra.territory_library" and "Custom Library" (which is the "Custom territory library" created in this particular map) and they are in the side box. With an arbitrary number of territory libraries imported, they should instead all be listed (alongside "Custom Library") as sub-tabs under the main "Map Preview/Referennce Map/Territory library" tabs, with the sub-tabs updating when the territory library imports are chnaged.

For eventually publishing this as a website
- [x] Move GUI to a separate repo instead of being part of the main xatra package
- [ ] Security
  - [ ] Obviously can't allow users to just run any Python code. Instead of blindly running whatever code the user enters in the Code editor, we should convert it into the "Builder" format first and then run _that_.
      - [ ] "Python" blocks and "Python" input to fields should _only_ be available to "Trusted" users. Other users should not be able to do that or even see the options; however they should be able to import maps from users who did use these blocks. Admin users are always trusted.
        - [ ] Even that code should only be run in a sandbox, not affecting anything else on the system.
    - [ ] Is the parsing of Python into Builder json, and the parsing of Builder json back into Python code, perfectly secure?
- [ ] Efficiency and scalability concerns [for now, just answer in words, don't implement anything]
  - Can this website handle, idk, approx 1000 users making maps? How can we estimate the resources etc. that will cost and the servers we will need? (I'm totally new to this, I have no idea if this makes sense).
  - Is it inefficient that for every change the user makes to the map, it has to be re-rendered from ground up by xatra? Are there better solutions? Do note that the maps can get pretty long (e.g. maps of global territorial evolution over history, etc.)
- [ ] Admin can "featured" maps, making them appear on top
- [ ] Collaborative editing/Github integration
- [ ] AI agent that makes maps for you --- only for paid users [have to think about exactly how to implement this]


---


### 5) Production platform features (sandboxing/accounts/publishing/AI)
- Sandbox:
  Use isolated worker containers (Firecracker/containers), strict CPU/memory/timeouts, blocked outbound network by default, signed artifact export only.
- Accounts + projects:
  Introduce auth (OIDC + sessions), project ownership, versioned saves, and RBAC tiers (free/paid).
- Publishing:
  Store published HTML/JSON + assets in object storage with immutable versions and moderated public links.
- AI agent:
  Add paid-tier feature gate, request quotas, audited tool execution logs, and policy-enforced prompt/tool sandboxing.

## Development / Synchrony

When changing behaviour that is shared between frontend and backend or between Builder and Code, keep these in sync:

| If you change… | Also change… |
|----------------|---------------|
| **Builder payload** (elements/options shape) | `xatra_gui/main.py` `run_rendering_task` for `task_type == 'builder'`, and any code generation in `App.jsx` `generatePythonCode`. |
| **River element** (source_type, value) | Backend: `main.py` river branch (naturalearth/overpass); Frontend: `generatePythonCode` (no `source_type` in generated code, use `naturalearth(...)` or `overpass(...)`). |
| **Point icon** (builtin / geometric / custom) | Backend: `main.py` point branch (resolve `args.icon` to `Icon`); Frontend: `LayerItem.jsx` icon UI and `generatePythonCode` (emit `Icon.builtin` / `Icon.geometric` / `Icon(...)`). |
| **Flag territory** (parts: gadm / polygon / predefined) | Backend: `main.py` Flag branch and `predefined_namespace` from `predefined_code`; Frontend: `TerritoryBuilder.jsx` and `formatTerritory` in `App.jsx`. |
| **Pre-defined territories** (variable names) | Backend: exec `predefined_code` with `territory_library` in scope; Frontend: send `predefined_code` in builder request; `TerritoryBuilder` uses parsed names + `GET /territory_library/names` for autocomplete. |
| **Draft overlay** (path/polygon/point on map) | Frontend: `postMessage({ type: 'setDraft', points, shapeType })` (use `shapeType` not `type`); Backend: `src/xatra/render.py` message handler `setDraft` uses `shapeType`. |
| **Rename in UI** (e.g. "Rivers" → "All Rivers", "Picker Map" → "Reference Map") | `Builder.jsx` (button/label), `App.jsx` (tab and panel titles). |
