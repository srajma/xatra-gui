import React, { useState, useEffect, useRef } from 'react';
import { Trash2, ChevronDown, ChevronUp, Info, MousePointer2, Save } from 'lucide-react';
import AutocompleteInput from './AutocompleteInput';
import TerritoryBuilder from './TerritoryBuilder';
import PythonTextField from './PythonTextField';
import IconPickerModal from './IconPickerModal';
import { isPythonValue } from '../utils/pythonValue';
import { API_BASE } from '../config';

const LayerItem = ({
  element, index, elements, updateElement, updateArg, replaceElement, removeElement,
  lastMapClick, activePicker, setActivePicker, draftPoints, setDraftPoints,
  onSaveTerritory, predefinedCode, onStartReferencePick, hubImports = [], trustedUser = false, isDarkMode = false
}) => {
  const [showMore, setShowMore] = useState(false);
  const pickerTimeoutRef = useRef(null);
  const lastHandledClickTsRef = useRef(null);
  const [builtinIconsList, setBuiltinIconsList] = useState([]);
  const [musicPeriodText, setMusicPeriodText] = useState('');
  const [musicTimestampsText, setMusicTimestampsText] = useState('');
  const [iconPickerOpen, setIconPickerOpen] = useState(false);
  
  const isPicking = activePicker && activePicker.id === index && activePicker.context === 'layer';
  const isRiverReferencePicking = activePicker && activePicker.id === index && activePicker.context === 'reference-river';
  const pickerStartedAt = isPicking ? Number(activePicker?.startedAt || 0) : 0;

  const [periodText, setPeriodText] = useState(Array.isArray(element.args?.period) ? element.args.period.join(', ') : '');

  // Sync periodText when element changes (e.g. project load)
  useEffect(() => {
      setPeriodText(Array.isArray(element.args?.period) ? element.args.period.join(', ') : '');
  }, [element.args?.period]);

  useEffect(() => {
    const p = element.args?.period;
    if (Array.isArray(p) && p.length === 2) setMusicPeriodText(`${p[0]}, ${p[1]}`);
    else if (typeof p === 'string') setMusicPeriodText(p);
    else setMusicPeriodText('');
  }, [element.args?.period]);

  useEffect(() => {
    const t = element.args?.timestamps;
    if (Array.isArray(t) && t.length === 2) setMusicTimestampsText(`${t[0]}, ${t[1]}`);
    else if (typeof t === 'string') setMusicTimestampsText(t);
    else setMusicTimestampsText('');
  }, [element.args?.timestamps]);

  useEffect(() => {
    if (element.type === 'point') {
      fetch(`${API_BASE}/icons/list`)
        .then(r => r.json())
        .then(setBuiltinIconsList)
        .catch(() => setBuiltinIconsList([]));
    }
  }, [element.type]);

  useEffect(() => {
      if (isPicking && lastMapClick) {
        if (pickerStartedAt && Number(lastMapClick.ts || 0) <= pickerStartedAt) return;
        if (lastHandledClickTsRef.current === lastMapClick.ts) return;
        lastHandledClickTsRef.current = lastMapClick.ts;
        const lat = parseFloat(lastMapClick.lat.toFixed(4));
        const lng = parseFloat(lastMapClick.lng.toFixed(4));
        const point = [lat, lng];

        if (element.type === 'point' || element.type === 'text') {
            updateElement(index, 'value', JSON.stringify(point));
            setDraftPoints([point]);
            // Keep cue visible briefly so the click location is perceptible after picker turns off.
            if (pickerTimeoutRef.current) clearTimeout(pickerTimeoutRef.current);
            pickerTimeoutRef.current = window.setTimeout(() => {
              pickerTimeoutRef.current = null;
              setActivePicker(null);
              setDraftPoints([]);
            }, 240);
        } else if (element.type === 'path') {
            setDraftPoints((prev) => {
              const next = [...prev, point];
              updateElement(index, 'value', JSON.stringify(next));
              return next;
            });
        }
      }
      return () => {
        if (pickerTimeoutRef.current) clearTimeout(pickerTimeoutRef.current);
      };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastMapClick, isPicking, pickerStartedAt, element.type, index, updateElement, setActivePicker, setDraftPoints]);

  const togglePicking = () => {
      if (isPicking) {
          setActivePicker(null);
          setDraftPoints([]);
      } else {
          lastHandledClickTsRef.current = null;
          setActivePicker({ id: index, type: element.type, context: 'layer', startedAt: Date.now() });
          // For point/text, show existing position as dot when entering picker mode
          if (element.type === 'point' || element.type === 'text') {
              try {
                  const pos = typeof element.value === 'string' ? JSON.parse(element.value || '[]') : element.value;
                  if (Array.isArray(pos) && pos.length >= 2 && typeof pos[0] === 'number' && typeof pos[1] === 'number') {
                      setDraftPoints([pos]);
                      return;
                  }
              } catch {
                // ignore malformed coordinates while entering picker mode
              }
          }
          if (element.type === 'path') {
              try {
                const current = JSON.parse(element.value || '[]');
                setDraftPoints(Array.isArray(current) ? current : []);
                return;
              } catch {
                // ignore malformed coordinates while entering picker mode
              }
          }
          setDraftPoints([]);
      }
  };

  const handlePeriodChange = (val) => {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      setPeriodText('');
      updateArg(index, 'period', val);
      return;
    }
    setPeriodText(val);
    if (val === "") {
      updateArg(index, 'period', null);
      return;
    }
    
    // Support [-320, -180] or -320, -180
    let clean = val.split('[').join('').split(']').join('');
    const parts = clean.split(',').map(s => s.trim());      
    if (parts.length === 2) {
        const start = parseInt(parts[0]);
        const end = parseInt(parts[1]);
        if (!isNaN(start) && !isNaN(end)) {
            updateArg(index, 'period', [start, end]);
        }
    }
  };

  const renderSpecificFields = () => {
    switch (element.type) {
      case 'flag':
        return (
          <div className="grid grid-cols-1 gap-3 mb-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">State name</label>
              <PythonTextField allowPython={trustedUser}
                value={element.label || ''}
                onChange={(val) => updateElement(index, 'label', val)}
                data-focus-primary="true"
                inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                placeholder="Name"
              />
              <div className="mt-1 text-[10px] text-gray-500 leading-snug">
                A <b>Flag</b> asserts the reign of a State over a Territory (perhaps for a particular period of time). Flag layers with the same State name are rendered as the same geometry.
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs text-gray-500">Territory</label>
                  <button 
                    onClick={() => onSaveTerritory(element)}
                    className="text-[10px] text-blue-600 hover:text-blue-800 flex items-center gap-1 font-bold"
                    title="Save territory to Territory library"
                  >
                    <Save size={10}/> Save to Library
                  </button>
              </div>
              <TerritoryBuilder
                value={element.value}
                onChange={(val) => updateElement(index, 'value', val)}
                lastMapClick={lastMapClick}
                activePicker={activePicker}
                setActivePicker={setActivePicker}
                draftPoints={draftPoints}
                setDraftPoints={setDraftPoints}
                parentId={index}
                predefinedCode={predefinedCode}
                onStartReferencePick={onStartReferencePick}
                onStartTerritoryLibraryPick={onStartReferencePick}
                hubImports={hubImports}
              />
            </div>
          </div>
        );
      case 'river':
        return (
           <div className="space-y-3 mb-2">
            <div className="grid grid-cols-2 gap-3">
                <div>
                <label className="block text-xs text-gray-500 mb-1">Label</label>
                <PythonTextField allowPython={trustedUser}
                    value={element.label || ''}
                    onChange={(val) => updateElement(index, 'label', val)}
                    data-focus-primary="true"
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                    placeholder="River Name"
                />
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Source</label>
                    <select
                        value={element.args?.source_type || 'naturalearth'}
                        onChange={(e) => {
                             const newType = e.target.value;
                             const newValue = newType === 'overpass' ? '1159233' : '1159122643';
                             replaceElement(index, {
                                 ...element,
                                 value: newValue,
                                 args: { ...element.args, source_type: newType }
                             });
                        }}
                        className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                    >
                        <option value="naturalearth">Natural Earth</option>
                        <option value="overpass">Overpass (OSM)</option>
                    </select>
                </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">ID</label>
              <div className="flex gap-1">
                <PythonTextField allowPython={trustedUser}
                  value={element.value || ''}
                  onChange={(val) => updateElement(index, 'value', val)}
                  inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                  placeholder={element.args?.source_type === 'overpass' ? 'e.g. 1159233' : 'e.g. 1159122643'}
                />
                <button
                  type="button"
                  onClick={() => {
                    if (isRiverReferencePicking) {
                      setActivePicker(null);
                      return;
                    }
                    onStartReferencePick({ kind: 'river', layerIndex: index, label: element.label || '' });
                  }}
                  className={`p-1.5 border rounded flex-shrink-0 transition-colors ${isRiverReferencePicking ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                  title={isRiverReferencePicking ? 'Cancel river picking' : 'Pick river from Reference Map'}
                >
                  <MousePointer2 size={14} />
                </button>
              </div>
              <div className="text-[10px] text-gray-400 mt-1 flex items-center gap-1">
                  <Info size={10}/> 
                  {element.args?.source_type === 'overpass' ? 'OSM Way/Relation ID' : 'Natural Earth ID'}
              </div>
            </div>
          </div>
        );
      case 'point':
      case 'text': {
        const iconArg = element.args?.icon;
        const iconSummary = (() => {
          if (!iconArg) return 'Default Leaflet marker';
          if (isPythonValue(iconArg)) return 'Raw Python icon expression';
          if (typeof iconArg === 'string') return `Leaflet built-in: ${iconArg}`;
          if (typeof iconArg === 'object') {
            const t = String(iconArg.type || '').toLowerCase();
            if (t === 'builtin') return `Leaflet built-in: ${iconArg.name || ''}`;
            if (t === 'bootstrap') return `Bootstrap: ${iconArg.name || ''}`;
            if (t === 'geometric') return `Geometric: ${iconArg.shape || 'circle'}`;
            if (t === 'url' || iconArg.icon_url || iconArg.iconUrl) return `Custom URL icon`;
            if (iconArg.shape) return `Geometric: ${iconArg.shape}`;
          }
          return 'Custom icon';
        })();
        return (
           <div className="grid grid-cols-2 gap-3 mb-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Label</label>
                <PythonTextField allowPython={trustedUser}
                value={element.label || ''}
                onChange={(val) => updateElement(index, 'label', val)}
                data-focus-primary="true"
                inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                placeholder="Label"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Position [lat, lon]</label>
              <div className="flex gap-1">
                  <PythonTextField allowPython={trustedUser}
                    value={element.value || ''}
                    onChange={(val) => updateElement(index, 'value', val)}
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                    placeholder="[28.6, 77.2]"
                  />
                  <button 
                    onClick={togglePicking}
                    className={`p-1.5 border rounded flex-shrink-0 transition-colors ${isPicking ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                    title={isPicking ? "Click on map to pick location (Esc to cancel)" : "Pick from map"}
                  >
                    <MousePointer2 size={16}/>
                  </button>
              </div>
            </div>
            {element.type === 'point' && (
              <div className="col-span-2 space-y-2 pt-1 border-t border-gray-100">
                <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
                  Icon
                  <span title="Unified icon browser for Leaflet built-ins, Bootstrap Icons, geometric shapes, and URL icons.">
                    <Info size={12} className="text-blue-500 cursor-help"/>
                  </span>
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIconPickerOpen(true)}
                    className="px-3 py-1.5 rounded border border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100 text-xs font-medium"
                  >
                    Choose Icon
                  </button>
                  <button
                    onClick={() => updateArg(index, 'icon', null)}
                    className="px-2 py-1.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 text-xs"
                  >
                    Reset
                  </button>
                  <div className="text-xs text-gray-500 truncate">{iconSummary}</div>
                </div>
                {isPythonValue(iconArg) && (
                  <PythonTextField allowPython={trustedUser}
                    value={iconArg}
                    onChange={(val) => updateArg(index, 'icon', val)}
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-xs focus:border-blue-500 outline-none font-mono"
                    placeholder="Icon(...)"
                  />
                )}
                <IconPickerModal
                  open={iconPickerOpen}
                  onClose={() => setIconPickerOpen(false)}
                  iconValue={isPythonValue(iconArg) ? null : iconArg}
                  onChange={(val) => updateArg(index, 'icon', val)}
                  builtinIcons={builtinIconsList}
                  isDarkMode={isDarkMode}
                />
              </div>
            )}
          </div>
        );
      }
      case 'path':
         return (
           <div className="grid grid-cols-2 gap-3 mb-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Label</label>
              <PythonTextField allowPython={trustedUser}
                value={element.label || ''}
                onChange={(val) => updateElement(index, 'label', val)}
                data-focus-primary="true"
                inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                placeholder="Route Name"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Coords [[lat,lon]...]</label>
              <div className="flex gap-1 items-start">
                  <PythonTextField allowPython={trustedUser}
                    value={element.value || ''}
                    onChange={(val) => updateElement(index, 'value', val)}
                    multiline
                    rows={4}
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono h-20 resize-none"
                    placeholder="[[28.6, 77.2], [19.0, 72.8]]"
                  />
                  <button 
                    onClick={togglePicking}
                    className={`p-1.5 border rounded flex-shrink-0 transition-colors ${isPicking ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                    title={isPicking ? "Click on map to append points (Backspace to undo, Esc to stop)" : "Draw path on map"}
                  >
                    <MousePointer2 size={16}/>
                  </button>
              </div>
            </div>
          </div>
        );
      case 'dataframe':
        return (
          <div className="space-y-3 mb-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">CSV Content or File Path</label>
              <PythonTextField allowPython={trustedUser}
                value={element.value || ''}
                onChange={(val) => updateElement(index, 'value', val)}
                data-focus-primary="true"
                multiline
                rows={6}
                inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono h-24 resize-y text-xs"
                placeholder="GID,value\nIND,100"
              />
              <div className="mt-1">
                 <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                        const file = e.target.files[0];
                        if (file) {
                            const reader = new FileReader();
                            reader.onload = (ev) => {
                                updateElement(index, 'value', ev.target.result);
                            };
                            reader.readAsText(file);
                        }
                    }}
                    className="text-xs text-gray-500"
                 />
              </div>
            </div>
            <div className="text-[10px] text-gray-500 italic">
              `GID` and data/year columns are auto-detected from CSV.
            </div>
          </div>
        );
      case 'admin':
         return (
           <div className="grid grid-cols-2 gap-3 mb-2">
            <div>
               <label className="block text-xs text-gray-500 mb-1">GADM Code</label>
              <AutocompleteInput
                value={element.value || ''}
                onChange={(val) => updateElement(index, 'value', val)}
                allowPython={trustedUser}
                inputProps={{ 'data-focus-primary': 'true' }}
                className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                placeholder="e.g. IND"
              />
            </div>
             <div>
              <label className="block text-xs text-gray-500 mb-1">Level</label>
              <input
                type="number"
                value={element.args?.level || 1}
                onChange={(e) => updateArg(index, 'level', parseInt(e.target.value))}
                className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
              />
            </div>
          </div>
        );
      case 'admin_rivers':
         return (
           <div className="mb-2">
              <label className="block text-xs text-gray-500 mb-1">Sources (JSON list)</label>
              <PythonTextField allowPython={trustedUser}
                value={element.value || '["naturalearth"]'}
                onChange={(val) => updateElement(index, 'value', val)}
                data-focus-primary="true"
                inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                placeholder='["naturalearth"]'
              />
          </div>
        );
      case 'titlebox':
        return (
          <div className="mb-2">
            <label className="block text-xs text-gray-500 mb-1">TitleBox (HTML)</label>
            <PythonTextField allowPython={trustedUser}
              value={element.value || ''}
              onChange={(val) => updateElement(index, 'value', val)}
              data-focus-primary="true"
              multiline
              rows={4}
              inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono h-20 resize-y"
              placeholder="<b>My Map</b>"
            />
          </div>
        );
      case 'music':
        return (
          <div className="mb-2">
            <label className="block text-xs text-gray-500 mb-1">Audio File</label>
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept="audio/*"
                data-focus-primary="true"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const reader = new FileReader();
                  reader.onload = (ev) => {
                    updateElement(index, 'value', String(ev.target?.result || ''));
                    updateArg(index, 'filename', file.name);
                  };
                  reader.readAsDataURL(file);
                }}
                className="block w-full text-xs text-gray-600 file:mr-2 file:px-2 file:py-1 file:rounded file:border file:border-gray-200 file:bg-gray-50 file:text-gray-700 hover:file:bg-gray-100"
              />
            </div>
            <div className="mt-1 text-[10px] text-gray-500 font-mono truncate" title={element.args?.filename || ''}>
              {element.args?.filename ? `Selected: ${element.args.filename}` : 'No file selected'}
            </div>
            <details className="mt-2 rounded border border-gray-100 bg-gray-50/40 p-2">
              <summary className="cursor-pointer text-[11px] font-medium text-gray-600 select-none">Optional: Period & Timestamps</summary>
              <div className="mt-2 grid grid-cols-1 gap-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Period [start, end]</label>
                  <PythonTextField allowPython={trustedUser}
                    value={musicPeriodText}
                    onChange={(val) => {
                      if (val && typeof val === 'object' && !Array.isArray(val)) {
                        setMusicPeriodText('');
                        updateArg(index, 'period', val);
                        return;
                      }
                      const text = String(val || '').trim();
                      setMusicPeriodText(String(val || ''));
                      if (!text) {
                        updateArg(index, 'period', null);
                        return;
                      }
                      const clean = text.replace(/\[|\]/g, '');
                      const parts = clean.split(',').map((s) => s.trim());
                      if (parts.length === 2) {
                        const start = parseInt(parts[0], 10);
                        const end = parseInt(parts[1], 10);
                        if (!Number.isNaN(start) && !Number.isNaN(end)) updateArg(index, 'period', [start, end]);
                      }
                    }}
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                    placeholder="e.g. -320, -180"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Timestamps [start, end] seconds</label>
                  <PythonTextField allowPython={trustedUser}
                    value={musicTimestampsText}
                    onChange={(val) => {
                      if (val && typeof val === 'object' && !Array.isArray(val)) {
                        setMusicTimestampsText('');
                        updateArg(index, 'timestamps', val);
                        return;
                      }
                      const text = String(val || '').trim();
                      setMusicTimestampsText(String(val || ''));
                      if (!text) {
                        updateArg(index, 'timestamps', null);
                        return;
                      }
                      const clean = text.replace(/\[|\]|\(|\)/g, '');
                      const parts = clean.split(',').map((s) => s.trim());
                      if (parts.length === 2) {
                        const start = parseFloat(parts[0]);
                        const end = parseFloat(parts[1]);
                        if (!Number.isNaN(start) && !Number.isNaN(end)) updateArg(index, 'timestamps', [start, end]);
                      }
                    }}
                    inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
                    placeholder="e.g. 10, 90"
                  />
                </div>
              </div>
            </details>
          </div>
        );
      case 'python':
        return (
          <div className="mb-2">
            <label className="block text-xs text-gray-500 mb-1">Python Code</label>
            <textarea
              value={element.value || ''}
              onChange={(e) => updateElement(index, 'value', e.target.value)}
              data-focus-primary="true"
              className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono h-28 resize-y"
              placeholder="xatra.Flag(label='Custom', value=gadm('IND'))"
            />
          </div>
        );
      default:
        return null;
    }
  };

  const renderMoreOptions = () => {
    if (element.type === 'titlebox' || element.type === 'music') {
      return null;
    }
    const inheritOptions = (elements || [])
      .filter((el, idx) => idx !== index && el?.type === 'flag')
      .map((el) => String(el?.label || '').trim())
      .filter(Boolean)
      .filter((label, idx, arr) => arr.indexOf(label) === idx);

    return (
      <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-2 gap-3">
        {/* Classes */}
        <div>
           <label className="block text-xs text-gray-500 mb-1">CSS Classes</label>
           <PythonTextField allowPython={trustedUser}
            value={element.args?.classes || ''}
            onChange={(val) => updateArg(index, 'classes', val)}
            inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
            placeholder="e.g. my-style"
          />
        </div>

        {/* Type specific extra args */}
        {element.type === 'flag' && (
            <>
                 <div>
                    <label className="block text-xs text-gray-500 mb-1">Display Label</label>
                    <PythonTextField allowPython={trustedUser}
                        value={element.args?.display_label || ''}
                        onChange={(val) => updateArg(index, 'display_label', val)}
                        inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                        placeholder="Override Flag name for display"
                    />
                </div>
                 <div>
                    <label className="block text-xs text-gray-500 mb-1">Color (Hex)</label>
                    <PythonTextField allowPython={trustedUser}
                        value={element.args?.color || ''}
                        onChange={(val) => updateArg(index, 'color', val)}
                        inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                        placeholder="#ff0000"
                    />
                </div>
                 <div>
                    <label className="block text-xs text-gray-500 mb-1">Inherit Color From</label>
                    <select
                      value={element.args?.inherit || ''}
                      onChange={(e) => updateArg(index, 'inherit', e.target.value || null)}
                      className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none"
                    >
                      <option value="">None</option>
                      {inheritOptions.map((label) => (
                        <option key={label} value={label}>
                          {label}
                        </option>
                      ))}
                    </select>
                </div>
            </>
        )}
        
        {(element.type === 'river' || element.type === 'path' || element.type === 'point') && (
             <div className="flex items-center pt-4">
                <label className="flex items-center gap-2 text-xs text-gray-700 cursor-pointer select-none">
                    <input
                        type="checkbox"
                        checked={element.args?.show_label || false}
                        onChange={(e) => updateArg(index, 'show_label', e.target.checked)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    Show Label
                </label>
            </div>
        )}

         {/* Point icon is configured in the main form */}
        </div>
    );
  };

  return (
    <div data-layer-index={index} className="xatra-layer-card bg-white p-3 rounded-lg border border-gray-200 shadow-sm relative group hover:border-blue-300 transition-colors">
      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button 
          onClick={() => removeElement(index)}
          className="text-red-400 hover:text-red-600 p-1"
        >
          <Trash2 size={14} />
        </button>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-700`}>
          {element.type}
        </span>
      </div>

      {renderSpecificFields()}

      {element.type !== 'python' && element.type !== 'music' && (
        <div className="mb-2">
            <label className="block text-xs text-gray-500 mb-1">Period [start, end]</label>
            <PythonTextField allowPython={trustedUser}
              value={element.args?.period ?? periodText}
              onChange={handlePeriodChange}
              inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono"
              placeholder="e.g. -320, -180"
            />
             <div className="text-[10px] text-gray-400 mt-0.5 flex items-center gap-1">
                 <Info size={10}/> Use negative numbers for BC years (e.g. -320, -180)
             </div>
        </div>
      )}

      {element.type !== 'titlebox' && element.type !== 'python' && element.type !== 'music' && (
        <div>
          <label className="block text-xs text-gray-500 mb-1">Note (Tooltip)</label>
          <PythonTextField allowPython={trustedUser}
            value={element.args?.note || ''}
            onChange={(val) => updateArg(index, 'note', val)}
            multiline
            autoGrow
            rows={1}
            inputClassName="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:border-blue-500 outline-none font-mono resize-none overflow-hidden"
            placeholder="Optional description..."
          />
        </div>
      )}

      {element.type !== 'titlebox' && element.type !== 'python' && element.type !== 'music' && (
        <>
          <button 
            onClick={() => setShowMore(!showMore)}
            className="mt-2 text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-medium"
          >
            {showMore ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
            {showMore ? 'Less Options' : 'More Options'}
          </button>
          
          {showMore && renderMoreOptions()}
        </>
      )}
    </div>
  );
};

export default LayerItem;
