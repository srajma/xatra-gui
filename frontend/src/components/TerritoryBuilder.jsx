import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Plus, Trash2, MousePointer2, GripVertical, X } from 'lucide-react';

const toList = (raw) => {
  if (Array.isArray(raw)) return raw.map((x) => String(x || '').trim()).filter(Boolean);
  if (raw == null) return [];
  return String(raw)
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
};

const toStored = (values) => {
  const list = values.map((x) => String(x || '').trim()).filter(Boolean);
  if (list.length <= 1) return list[0] || '';
  return list;
};

const normalizePart = (part) => {
  const op = part?.op || 'union';
  const type = part?.type || 'gadm';
  if (type === 'group') {
    const nested = Array.isArray(part?.value)
      ? part.value.map((p) => normalizePart(p)).filter(Boolean)
      : [];
    return { op, type, value: nested };
  }
  if (type === 'polygon') {
    return { op, type, value: part?.value || '' };
  }
  if (type === 'gadm' || type === 'predefined') {
    const vals = toList(part?.value);
    return { op, type, value: vals.length <= 1 ? (vals[0] || '') : vals };
  }
  return { op, type: 'gadm', value: '' };
};

const normalizeParts = (value) => {
  if (Array.isArray(value)) {
    if (value.length > 0 && typeof value[0] === 'object' && value[0] !== null) {
      return value.map((p) => normalizePart(p)).filter(Boolean);
    }
    return value.map((v) => ({ op: 'union', type: 'gadm', value: v }));
  }
  if (typeof value === 'string' && value) {
    return [{ op: 'union', type: 'gadm', value }];
  }
  return [];
};

const TokenInput = ({
  tokens,
  onChange,
  placeholder,
  mode,
  endpoint,
  localOptions,
}) => {
  const [text, setText] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timerRef = useRef(null);
  const wrapperRef = useRef(null);

  useEffect(() => {
    const onClick = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const tokenSet = useMemo(() => new Set(tokens.map((x) => String(x))), [tokens]);

  const loadSuggestions = async (query) => {
    const q = String(query || '').trim();
    if (!q) {
      setSuggestions([]);
      setActiveIndex(-1);
      return;
    }
    if (mode === 'local') {
      const filtered = (localOptions || [])
        .filter((item) => item.toLowerCase().includes(q.toLowerCase()))
        .filter((item) => !tokenSet.has(item))
        .slice(0, 20)
        .map((name) => ({ value: name, label: name }));
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setActiveIndex(filtered.length > 0 ? 0 : -1);
      return;
    }
    if (q.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      setActiveIndex(-1);
      return;
    }
    try {
      const res = await fetch(`${endpoint}?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      const filtered = (Array.isArray(data) ? data : [])
        .map((item) => ({
          value: item.gid || item.country_code || item.country || '',
          label: item.gid || item.country_code || item.country || '',
          meta: item.name || item.country || '',
        }))
        .filter((item) => item.value)
        .filter((item) => !tokenSet.has(item.value));
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setActiveIndex(filtered.length > 0 ? 0 : -1);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const addToken = (raw) => {
    const v = String(raw || '').trim();
    if (!v || tokenSet.has(v)) return;
    onChange([...tokens, v]);
  };

  const commitTextToken = () => {
    if (!text.trim()) return;
    addToken(text.trim());
    setText('');
    setSuggestions([]);
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  const handleInputChange = (val) => {
    setText(val);
    if (val.includes(',')) {
      const pieces = val.split(',');
      const committed = pieces.slice(0, -1).map((x) => x.trim()).filter(Boolean);
      if (committed.length) {
        onChange([
          ...tokens,
          ...committed.filter((x) => !tokenSet.has(x)),
        ]);
      }
      const tail = pieces[pieces.length - 1] || '';
      setText(tail);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => loadSuggestions(tail), 180);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => loadSuggestions(val), 180);
  };

  const handleSelect = (item) => {
    addToken(item.value);
    setText('');
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  return (
    <div className="relative" ref={wrapperRef}>
      <div className="w-full text-xs p-1 border rounded bg-white min-h-[30px] flex flex-wrap gap-1 items-center">
        {tokens.map((token) => (
          <span key={token} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-700 font-mono">
            {token}
            <button
              type="button"
              className="text-blue-700 hover:text-blue-900"
              onClick={() => onChange(tokens.filter((x) => x !== token))}
              title="Remove"
            >
              <X size={10} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={text}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
          onKeyDown={(e) => {
            if (e.key === 'Backspace' && !text && tokens.length > 0) {
              e.preventDefault();
              onChange(tokens.slice(0, -1));
              return;
            }
            if (e.key === 'Enter') {
              if (showSuggestions && activeIndex >= 0 && activeIndex < suggestions.length) {
                e.preventDefault();
                handleSelect(suggestions[activeIndex]);
              } else {
                e.preventDefault();
                commitTextToken();
              }
              return;
            }
            if (e.key === ',' || e.key === 'Tab') {
              if (text.trim()) {
                e.preventDefault();
                commitTextToken();
              }
              return;
            }
            if (e.key === 'ArrowDown' && showSuggestions && suggestions.length) {
              e.preventDefault();
              setActiveIndex((prev) => (prev + 1) % suggestions.length);
              return;
            }
            if (e.key === 'ArrowUp' && showSuggestions && suggestions.length) {
              e.preventDefault();
              setActiveIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
              return;
            }
            if (e.key === 'Escape') {
              setShowSuggestions(false);
              setActiveIndex(-1);
            }
          }}
          placeholder={tokens.length ? '' : placeholder}
          className="flex-1 min-w-[90px] outline-none bg-transparent"
        />
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <div className="xatra-autocomplete-menu absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map((item, idx) => (
            <div
              key={`${item.value}-${idx}`}
              onClick={() => handleSelect(item)}
              onMouseEnter={() => setActiveIndex(idx)}
              className={`xatra-autocomplete-item px-3 py-2 cursor-pointer text-xs border-b border-gray-50 last:border-none ${
                idx === activeIndex ? 'bg-blue-50 xatra-autocomplete-item-active' : 'hover:bg-gray-100'
              }`}
            >
              <div className="font-semibold">{item.label}</div>
              {item.meta ? <div className="xatra-autocomplete-meta text-gray-500 text-[10px]">{item.meta}</div> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const TerritoryBuilder = ({
  value, onChange, lastMapClick, activePicker, setActivePicker, draftPoints, setDraftPoints, parentId, predefinedCode, onStartReferencePick, onStartTerritoryLibraryPick, pathPrefix = []
}) => {
  const parts = normalizeParts(value);

  const matchingPickerPath = useMemo(() => {
    if (!activePicker || activePicker.context !== `territory-${parentId}`) return null;
    if (Array.isArray(activePicker.target?.partPath)) return activePicker.target.partPath;
    if (Number.isInteger(activePicker.id)) return [activePicker.id];
    return null;
  }, [activePicker, parentId]);

  const pickingIndex = useMemo(() => {
    if (!matchingPickerPath || matchingPickerPath.length !== pathPrefix.length + 1) return -1;
    for (let i = 0; i < pathPrefix.length; i += 1) {
      if (matchingPickerPath[i] !== pathPrefix[i]) return -1;
    }
    return matchingPickerPath[pathPrefix.length];
  }, [matchingPickerPath, pathPrefix]);

  const isReferencePickingThisFlag = !!(activePicker && activePicker.context === 'reference-gadm' && activePicker.target?.flagIndex === parentId);
  const isLibraryPicking = !!(activePicker && activePicker.context === 'territory-library' && activePicker.target?.flagIndex === parentId);

  useEffect(() => {
    if (pickingIndex >= 0 && lastMapClick) {
      const lat = parseFloat(lastMapClick.lat.toFixed(4));
      const lng = parseFloat(lastMapClick.lng.toFixed(4));
      const point = [lat, lng];

      const part = parts[pickingIndex];
      if (part && part.type === 'polygon') {
        const newPoints = [...draftPoints, point];
        setDraftPoints(newPoints);

        const newParts = [...parts];
        newParts[pickingIndex] = { ...part, value: JSON.stringify(newPoints) };
        onChange(newParts);
      }
    }
  }, [lastMapClick]);

  useEffect(() => {
    if (pickingIndex >= 0) {
      const part = parts[pickingIndex];
      if (part && part.type === 'polygon') {
        try {
          const current = JSON.parse(part.value || '[]');
          setDraftPoints(Array.isArray(current) ? current : []);
        } catch {
          setDraftPoints([]);
        }
      }
    }
  }, [pickingIndex]);

  const pathForIndex = (idx) => [...pathPrefix, idx];

  const togglePolygonPicking = (idx) => {
    const nextPath = pathForIndex(idx);
    const activePath = matchingPickerPath || [];
    const same = activePath.length === nextPath.length && activePath.every((v, i) => v === nextPath[i]);
    if (same) {
      setActivePicker(null);
      setDraftPoints([]);
      return;
    }
    setActivePicker({ id: idx, type: 'polygon', context: `territory-${parentId}`, target: { partPath: nextPath } });
    setDraftPoints([]);
  };

  const updatePart = (index, patch) => {
    const newParts = [...parts];
    newParts[index] = normalizePart({ ...newParts[index], ...patch });
    onChange(newParts);
  };

  const addPart = () => {
    onChange([...parts, { op: 'union', type: 'gadm', value: '' }]);
  };

  const removePart = (index) => {
    const newParts = [...parts];
    newParts.splice(index, 1);
    onChange(newParts);
  };

  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const movePart = (fromIndex, toIndex) => {
    if (fromIndex === toIndex) return;
    const newParts = [...parts];
    const [removed] = newParts.splice(fromIndex, 1);
    newParts.splice(toIndex, 0, removed);
    onChange(newParts);
    setActivePicker(null);
  };

  const handleDragStart = (e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };
  const handleDragOver = (e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  };
  const handleDragLeave = () => setDragOverIndex(null);
  const handleDrop = (e, toIndex) => {
    e.preventDefault();
    setDragOverIndex(null);
    setDraggedIndex(null);
    const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
    if (Number.isNaN(fromIndex)) return;
    movePart(fromIndex, toIndex);
  };
  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleRowKeyDown = (e, index) => {
    if (!e.altKey) return;
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      movePart(index, Math.max(0, index - 1));
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      movePart(index, Math.min(parts.length - 1, index + 1));
    }
  };

  const [territoryLibraryNames, setTerritoryLibraryNames] = useState([]);
  useEffect(() => {
    fetch('http://localhost:8088/territory_library/names')
      .then(r => r.json())
      .then(setTerritoryLibraryNames)
      .catch(() => setTerritoryLibraryNames([]));
  }, []);

  const predefinedVariables = useMemo(() => {
    if (!predefinedCode) return [];
    const regex = /^(\w+)\s*=/gm;
    const matches = [];
    let match;
    while ((match = regex.exec(predefinedCode)) !== null) {
      matches.push(match[1]);
    }
    return matches;
  }, [predefinedCode]);

  const allPredefinedOptions = useMemo(() => {
    const fromCode = predefinedVariables;
    const fromLib = territoryLibraryNames.filter((n) => !fromCode.includes(n));
    return [...fromCode, ...fromLib];
  }, [predefinedVariables, territoryLibraryNames]);

  if (parts.length === 0) {
    return (
      <div className="border border-dashed border-gray-300 rounded p-2 text-center bg-gray-50">
        <button onClick={addPart} className="text-xs text-blue-600 flex items-center justify-center gap-1 w-full font-medium">
          <Plus size={12}/> Define Territory
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {parts.map((part, idx) => {
        const rowPath = pathForIndex(idx);
        const isLibraryPickingThisPart = !!(isLibraryPicking && Array.isArray(activePicker?.target?.partPath) && activePicker.target.partPath.join('.') === rowPath.join('.'));

        return (
          <div
            key={idx}
            draggable
            tabIndex={0}
            onDragStart={(e) => handleDragStart(e, idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, idx)}
            onDragEnd={handleDragEnd}
            onKeyDown={(e) => handleRowKeyDown(e, idx)}
            className={`flex gap-2 items-start bg-gray-50 p-2 rounded border transition-colors ${draggedIndex === idx ? 'opacity-50' : ''} ${dragOverIndex === idx ? 'border-blue-400 ring-1 ring-blue-200' : 'border-gray-200'}`}
          >
            <div className="flex items-center cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 flex-shrink-0" title="Drag to reorder">
              <GripVertical size={14}/>
            </div>
            {idx > 0 ? (
              <select
                value={part.op}
                onChange={(e) => updatePart(idx, { op: e.target.value })}
                className="text-xs p-1 border rounded bg-white w-16 flex-shrink-0"
              >
                <option value="union">∪ (+)</option>
                <option value="difference">∖ (-)</option>
                <option value="intersection">∩ (&)</option>
              </select>
            ) : (
              <div className="w-16 text-xs p-1 text-center font-bold text-gray-500 bg-gray-100 rounded flex-shrink-0 border border-gray-200">Base</div>
            )}

            <select
              value={part.type}
              onChange={(e) => {
                const nextType = e.target.value;
                if (nextType === 'group') {
                  updatePart(idx, { type: 'group', value: [] });
                } else if (nextType === 'polygon') {
                  updatePart(idx, { type: 'polygon', value: '' });
                } else {
                  updatePart(idx, { type: nextType, value: '' });
                }
              }}
              className="text-xs p-1 border rounded bg-white w-24 flex-shrink-0"
            >
              <option value="gadm">GADM</option>
              <option value="polygon">Polygon</option>
              <option value="predefined">Territory</option>
              <option value="group">Group...</option>
            </select>

            <div className="flex-1 min-w-0">
              {part.type === 'gadm' ? (
                <div className="flex gap-1 items-start">
                  <div className="flex-1 min-w-0">
                    <TokenInput
                      tokens={toList(part.value)}
                      onChange={(vals) => updatePart(idx, { value: toStored(vals) })}
                      placeholder="Search GADM..."
                      mode="remote"
                      endpoint="http://localhost:8088/search/gadm"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (isReferencePickingThisFlag) {
                        setActivePicker(null);
                        return;
                      }
                      onStartReferencePick({ kind: 'gadm', flagIndex: parentId, partIndex: idx, partPath: rowPath });
                    }}
                    className={`p-1 border rounded flex-shrink-0 transition-colors ${isReferencePickingThisFlag ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                    title={isReferencePickingThisFlag ? 'Cancel GADM picking' : 'Pick GADM from Reference Map'}
                  >
                    <MousePointer2 size={12}/>
                  </button>
                </div>
              ) : part.type === 'predefined' ? (
                <div className="flex gap-1 items-start">
                  <div className="flex-1 min-w-0">
                    <TokenInput
                      tokens={toList(part.value)}
                      onChange={(vals) => updatePart(idx, { value: toStored(vals) })}
                      placeholder="e.g. maurya, NORTH_INDIA"
                      mode="local"
                      localOptions={allPredefinedOptions}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (isLibraryPickingThisPart) {
                        setActivePicker(null);
                        return;
                      }
                      onStartTerritoryLibraryPick({ kind: 'territory', flagIndex: parentId, partIndex: idx, partPath: rowPath });
                    }}
                    className={`p-1 border rounded flex-shrink-0 transition-colors ${isLibraryPickingThisPart ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                    title={isLibraryPickingThisPart ? 'Cancel territory library picking' : 'Pick from Territory Library map'}
                  >
                    <MousePointer2 size={12}/>
                  </button>
                </div>
              ) : part.type === 'group' ? (
                <div className="border border-gray-200 rounded bg-white p-2">
                  <TerritoryBuilder
                    value={Array.isArray(part.value) ? part.value : []}
                    onChange={(next) => updatePart(idx, { value: next })}
                    lastMapClick={lastMapClick}
                    activePicker={activePicker}
                    setActivePicker={setActivePicker}
                    draftPoints={draftPoints}
                    setDraftPoints={setDraftPoints}
                    parentId={parentId}
                    predefinedCode={predefinedCode}
                    onStartReferencePick={onStartReferencePick}
                    onStartTerritoryLibraryPick={onStartTerritoryLibraryPick}
                    pathPrefix={rowPath}
                  />
                </div>
              ) : (
                <div className="flex gap-1 items-start">
                  <textarea
                    value={part.value || ''}
                    onChange={(e) => updatePart(idx, { value: e.target.value })}
                    className="w-full text-xs p-1 border rounded font-mono h-8 resize-none bg-white"
                    placeholder="[[lat,lon],...]"
                  />
                  <button
                    onClick={() => togglePolygonPicking(idx)}
                    className={`p-1 border rounded flex-shrink-0 transition-colors ${pickingIndex === idx ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-white text-gray-600 hover:bg-gray-100 border-gray-300'}`}
                    title={pickingIndex === idx ? 'Click on map to append points (Backspace to undo, Esc to stop)' : 'Draw polygon on map'}
                  >
                    <MousePointer2 size={12}/>
                  </button>
                </div>
              )}
            </div>

            <button onClick={() => removePart(idx)} className="text-red-400 hover:text-red-600 p-1 flex-shrink-0">
              <Trash2 size={12}/>
            </button>
          </div>
        );
      })}

      <button onClick={addPart} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-medium mt-1">
        <Plus size={12}/> Add Operation
      </button>
    </div>
  );
};

export default TerritoryBuilder;
