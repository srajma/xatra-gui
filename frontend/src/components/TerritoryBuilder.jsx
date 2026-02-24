import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Plus, Trash2, MousePointer2, GripVertical, X } from 'lucide-react';
import { API_BASE } from '../config';

const DRAG_PATH_MIME = 'application/x-xatra-territory-path';
const TERRITORY_TYPES = ['gadm', 'polygon', 'predefined', 'group'];
const PROMPT_OPTIONS = ['gadm', 'polygon', 'predefined', 'group', 'esc'];
const TYPE_SHORTCUTS = { a: 'gadm', p: 'polygon', t: 'predefined', o: 'group' };

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

const pathsEqual = (a, b) => (
  Array.isArray(a) &&
  Array.isArray(b) &&
  a.length === b.length &&
  a.every((v, i) => v === b[i])
);

const isPrefixPath = (prefix, full) => (
  Array.isArray(prefix) &&
  Array.isArray(full) &&
  prefix.length <= full.length &&
  prefix.every((v, i) => v === full[i])
);

const removeAtPath = (parts, path) => {
  if (!Array.isArray(parts) || !Array.isArray(path) || path.length === 0) return null;
  const next = [...parts];
  const [head, ...rest] = path;
  if (!Number.isInteger(head) || head < 0 || head >= next.length) return null;
  if (rest.length === 0) {
    const [removed] = next.splice(head, 1);
    return { parts: next, removed };
  }
  const target = next[head];
  if (!target || target.type !== 'group') return null;
  const nested = removeAtPath(Array.isArray(target.value) ? target.value : [], rest);
  if (!nested) return null;
  next[head] = { ...target, value: nested.parts };
  return { parts: next, removed: nested.removed };
};

const insertAtPath = (parts, parentPath, index, item) => {
  if (!Array.isArray(parts) || !Array.isArray(parentPath)) return null;
  if (parentPath.length === 0) {
    const next = [...parts];
    const safeIndex = Math.max(0, Math.min(Number.isInteger(index) ? index : next.length, next.length));
    next.splice(safeIndex, 0, item);
    return next;
  }
  const next = [...parts];
  const [head, ...rest] = parentPath;
  if (!Number.isInteger(head) || head < 0 || head >= next.length) return null;
  const target = next[head];
  if (!target || target.type !== 'group') return null;
  const nested = insertAtPath(Array.isArray(target.value) ? target.value : [], rest, index, item);
  if (!nested) return null;
  next[head] = { ...target, value: nested };
  return next;
};

const adjustPathForRemoval = (path, removedParentPath, removedIndex) => {
  if (!Array.isArray(path) || !Array.isArray(removedParentPath)) return path;
  const depth = removedParentPath.length;
  if (!isPrefixPath(removedParentPath, path)) return path;
  if (path.length <= depth) return path;
  if (path[depth] <= removedIndex) return path;
  const next = [...path];
  next[depth] -= 1;
  return next;
};

const parseDraggedPath = (e) => {
  const raw = e.dataTransfer.getData(DRAG_PATH_MIME) || e.dataTransfer.getData('text/plain');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.some((v) => !Number.isInteger(v))) return null;
    return parsed;
  } catch {
    return null;
  }
};

const isEditableTarget = (target) => {
  if (!target || !(target instanceof Element)) return false;
  if (target instanceof HTMLInputElement) {
    const t = String(target.type || '').toLowerCase();
    return !['checkbox', 'radio', 'button', 'submit', 'reset', 'color', 'range', 'file'].includes(t);
  }
  if (target instanceof HTMLTextAreaElement) return true;
  if (target.isContentEditable) return true;
  const input = target.closest('input');
  if (input instanceof HTMLInputElement) {
    const t = String(input.type || '').toLowerCase();
    return !['checkbox', 'radio', 'button', 'submit', 'reset', 'color', 'range', 'file'].includes(t);
  }
  return !!target.closest('textarea, [contenteditable="true"]');
};

const TokenInput = ({
  tokens,
  onChange,
  placeholder,
  mode,
  endpoint,
  localOptions,
  inputPath,
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
          data-territory-input-path={inputPath}
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
              if (showSuggestions && activeIndex >= 0 && activeIndex < suggestions.length) {
                e.preventDefault();
                handleSelect(suggestions[activeIndex]);
              } else if (text.trim()) {
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

const findScrollableParent = (el) => {
  let cur = el;
  while (cur && cur !== document.body) {
    const style = window.getComputedStyle(cur);
    const overflowY = style?.overflowY || '';
    if ((overflowY === 'auto' || overflowY === 'scroll') && cur.scrollHeight > cur.clientHeight) return cur;
    cur = cur.parentElement;
  }
  return null;
};

const TerritoryBuilder = ({
  value, onChange, lastMapClick, activePicker, setActivePicker, draftPoints, setDraftPoints, parentId, predefinedCode, onStartReferencePick, onStartTerritoryLibraryPick, pathPrefix = [], onMovePartByPath = null, selectedPath: selectedPathProp = null, setSelectedPath: setSelectedPathProp = null, hubImports = []
}) => {
  const builderRootRef = useRef(null);
  const lastHandledClickTsRef = useRef(null);
  const parts = normalizeParts(value);
  const [localSelectedPath, setLocalSelectedPath] = useState(null);
  const [operationPrompt, setOperationPrompt] = useState(null);
  const selectedPath = selectedPathProp || localSelectedPath;
  const setSelectedPath = setSelectedPathProp || setLocalSelectedPath;
  const promptScopeId = `${parentId}:${pathPrefix.join('.') || 'root'}`;

  const getLayerScope = () => {
    const root = builderRootRef.current;
    if (!root) return document;
    return root.closest('[data-layer-index]') || root;
  };

  const toPathId = (path) => `${parentId}:${Array.isArray(path) ? path.join('.') : ''}`;

  const matchingPickerPath = useMemo(() => {
    if (!activePicker || activePicker.context !== `territory-${parentId}`) return null;
    if (Array.isArray(activePicker.target?.partPath)) return activePicker.target.partPath;
    if (Number.isInteger(activePicker.id)) return [activePicker.id];
    return null;
  }, [activePicker, parentId]);
  const pickerStartedAt = Number(activePicker?.startedAt || 0);

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
      if (pickerStartedAt && Number(lastMapClick.ts || 0) <= pickerStartedAt) return;
      if (lastHandledClickTsRef.current === lastMapClick.ts) return;
      lastHandledClickTsRef.current = lastMapClick.ts;
      const lat = parseFloat(lastMapClick.lat.toFixed(4));
      const lng = parseFloat(lastMapClick.lng.toFixed(4));
      const point = [lat, lng];

      const part = parts[pickingIndex];
      if (part && part.type === 'polygon') {
        setDraftPoints((prev) => {
          const next = [...prev, point];
          const newParts = [...parts];
          newParts[pickingIndex] = { ...part, value: JSON.stringify(next) };
          onChange(newParts);
          return next;
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastMapClick, pickingIndex, pickerStartedAt, parts, onChange]);

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
  }, [pickingIndex, parts, setDraftPoints]);

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
    lastHandledClickTsRef.current = null;
    setActivePicker({ id: idx, type: 'polygon', context: `territory-${parentId}`, target: { partPath: nextPath }, startedAt: Date.now() });
    setDraftPoints([]);
  };

  const updatePart = (index, patch) => {
    const newParts = [...parts];
    newParts[index] = normalizePart({ ...newParts[index], ...patch });
    onChange(newParts);
  };

  const createPart = (type, op = 'union') => {
    if (type === 'group') return { op, type: 'group', value: [] };
    if (type === 'polygon') return { op, type: 'polygon', value: '' };
    if (type === 'predefined') return { op, type: 'predefined', value: '' };
    return { op, type: 'gadm', value: '' };
  };

  const focusInputSoon = (path) => {
    if (!Array.isArray(path) || path.length === 0) return;
    window.requestAnimationFrame(() => {
      const scope = getLayerScope();
      const target = scope.querySelector(`[data-territory-input-path="${toPathId(path)}"]`);
      if (target && typeof target.focus === 'function') target.focus();
    });
  };

  const focusDefineSoon = (path) => {
    if (!Array.isArray(path) || path.length === 0) return;
    window.requestAnimationFrame(() => {
      const scope = getLayerScope();
      const target = scope.querySelector(`[data-territory-define-path="${toPathId(path)}"]`);
      if (target && typeof target.focus === 'function') target.focus();
    });
  };

  const addPart = (op = 'union', type = 'gadm') => {
    const next = [...parts, createPart(type, op)];
    const newPath = [...pathPrefix, parts.length];
    onChange(next);
    setSelectedPath(newPath);
    focusPathSoon(newPath);
    if (type === 'group') focusDefineSoon(newPath);
    else focusInputSoon(newPath);
  };

  const removePart = (index) => {
    const newParts = [...parts];
    newParts.splice(index, 1);
    onChange(newParts);
  };

  const [draggedPath, setDraggedPath] = useState(null);
  const [dragInsertionIndex, setDragInsertionIndex] = useState(null);
  const [dragOverGroupInsideIndex, setDragOverGroupInsideIndex] = useState(null);

  useEffect(() => {
    const onDragEnd = () => {
      setDraggedPath(null);
      setDragInsertionIndex(null);
      setDragOverGroupInsideIndex(null);
    };
    window.addEventListener('dragend', onDragEnd);
    return () => window.removeEventListener('dragend', onDragEnd);
  }, []);

  const movePartByPathLocal = (fromPath, toParentPath, toIndex) => {
    if (!Array.isArray(fromPath) || fromPath.length === 0 || !Array.isArray(toParentPath)) return null;
    if (isPrefixPath(fromPath, toParentPath)) return null;
    const fromParentPath = fromPath.slice(0, -1);
    const fromIndex = fromPath[fromPath.length - 1];
    if (!Number.isInteger(fromIndex)) return null;

    let insertParentPath = toParentPath;
    let insertIndex = Number.isInteger(toIndex) ? toIndex : 0;
    if (pathsEqual(fromParentPath, toParentPath) && fromIndex < insertIndex) {
      insertIndex -= 1;
    }
    insertParentPath = adjustPathForRemoval(insertParentPath, fromParentPath, fromIndex);

    const removed = removeAtPath(parts, fromPath);
    if (!removed || !removed.removed) return null;
    const inserted = insertAtPath(removed.parts, insertParentPath, insertIndex, removed.removed);
    if (!inserted) return null;
    onChange(inserted);
    setActivePicker(null);
    return [...insertParentPath, insertIndex];
  };

  const movePartByPath = onMovePartByPath || movePartByPathLocal;

  const focusPathSoon = (path) => {
    if (!Array.isArray(path) || path.length === 0) return;
    window.requestAnimationFrame(() => {
      const scope = getLayerScope();
      const row = scope.querySelector(`[data-territory-path="${toPathId(path)}"]`);
      if (row && typeof row.focus === 'function') row.focus();
    });
  };

  const autoScrollForDrag = (e) => {
    const scroller = findScrollableParent(e.currentTarget);
    if (!scroller) return;
    const rect = scroller.getBoundingClientRect();
    const edge = 56;
    const y = e.clientY;
    if (y < rect.top + edge) {
      const delta = Math.max(6, ((rect.top + edge) - y) * 0.35);
      scroller.scrollTop -= delta;
    } else if (y > rect.bottom - edge) {
      const delta = Math.max(6, (y - (rect.bottom - edge)) * 0.35);
      scroller.scrollTop += delta;
    }
  };

  const clearDragTargets = () => {
    setDragInsertionIndex(null);
    setDragOverGroupInsideIndex(null);
  };

  const handleDragStart = (e, rowPath) => {
    e.stopPropagation();
    setDraggedPath(rowPath);
    e.dataTransfer.effectAllowed = 'move';
    const serialized = JSON.stringify(rowPath);
    e.dataTransfer.setData(DRAG_PATH_MIME, serialized);
    e.dataTransfer.setData('text/plain', serialized);
  };

  const handleDragOverRow = (e, index) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'move';
    autoScrollForDrag(e);
    const rect = e.currentTarget.getBoundingClientRect();
    const shouldInsertBefore = e.clientY < rect.top + rect.height / 2;
    setDragInsertionIndex(shouldInsertBefore ? index : index + 1);
    setDragOverGroupInsideIndex(null);
  };

  const handleDropOnRow = (e, index) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const shouldInsertBefore = e.clientY < rect.top + rect.height / 2;
    const toIndex = shouldInsertBefore ? index : index + 1;
    clearDragTargets();
    setDraggedPath(null);
    const fromPath = parseDraggedPath(e);
    if (!fromPath) return;
    movePartByPath(fromPath, pathPrefix, toIndex);
  };

  const handleDropInsideGroup = (e, groupPath, groupLength) => {
    e.preventDefault();
    e.stopPropagation();
    clearDragTargets();
    setDraggedPath(null);
    const fromPath = parseDraggedPath(e);
    if (!fromPath) return;
    movePartByPath(fromPath, groupPath, groupLength);
  };

  const handleDropAtEnd = (e) => {
    e.preventDefault();
    e.stopPropagation();
    clearDragTargets();
    setDraggedPath(null);
    const fromPath = parseDraggedPath(e);
    if (!fromPath) return;
    movePartByPath(fromPath, pathPrefix, parts.length);
  };

  const handleDragEnd = () => {
    setDraggedPath(null);
    clearDragTargets();
  };

  const handleRowKeyDown = (e, rowPath) => {
    if (!e.shiftKey) return;
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    e.preventDefault();
    e.stopPropagation();
    const idx = rowPath[rowPath.length - 1];
    if (!Number.isInteger(idx)) return;
    const parentPath = rowPath.slice(0, -1);
    let movedPath = null;

    if (e.key === 'ArrowUp') {
      const prev = idx > 0 ? parts[idx - 1] : null;
      if (prev?.type === 'group') {
        const groupPath = [...parentPath, idx - 1];
        const groupLength = Array.isArray(prev.value) ? prev.value.length : 0;
        movedPath = movePartByPath(rowPath, groupPath, groupLength);
      } else {
        movedPath = movePartByPath(rowPath, parentPath, Math.max(0, idx - 1));
      }
    } else if (e.key === 'ArrowDown') {
      const next = idx < parts.length - 1 ? parts[idx + 1] : null;
      if (next?.type === 'group') {
        const groupPath = [...parentPath, idx + 1];
        movedPath = movePartByPath(rowPath, groupPath, 0);
      } else {
        movedPath = movePartByPath(rowPath, parentPath, Math.min(parts.length, idx + 2));
      }
    } else if (e.key === 'ArrowLeft') {
      if (rowPath.length < 2) return;
      const grandParentPath = rowPath.slice(0, -2);
      const parentIndex = rowPath[rowPath.length - 2];
      movedPath = movePartByPath(rowPath, grandParentPath, parentIndex);
    } else if (e.key === 'ArrowRight') {
      if (rowPath.length < 2) return;
      const grandParentPath = rowPath.slice(0, -2);
      const parentIndex = rowPath[rowPath.length - 2];
      movedPath = movePartByPath(rowPath, grandParentPath, parentIndex + 1);
    }

    if (Array.isArray(movedPath)) {
      setSelectedPath(movedPath);
      focusPathSoon(movedPath);
    }
  };

  const startOperationPrompt = (mode, op = 'union') => {
    setOperationPrompt({ mode, op, focusedType: 'gadm' });
  };

  const closeOperationPrompt = () => setOperationPrompt(null);

  const cycleOperationPromptType = (direction) => {
    setOperationPrompt((prev) => {
      if (!prev) return prev;
      const current = PROMPT_OPTIONS.indexOf(prev.focusedType);
      const base = current >= 0 ? current : 0;
      const nextIndex = (base + direction + PROMPT_OPTIONS.length) % PROMPT_OPTIONS.length;
      return { ...prev, focusedType: PROMPT_OPTIONS[nextIndex] };
    });
  };

  const commitOperationPrompt = (explicitType = null) => {
    const targetType = explicitType || operationPrompt?.focusedType || 'gadm';
    if (!operationPrompt) return;
    if (targetType === 'esc') {
      closeOperationPrompt();
      return;
    }
    if (operationPrompt.mode === 'base') {
      const newPart = createPart(targetType, 'union');
      const newPath = [...pathPrefix, 0];
      onChange([newPart]);
      setSelectedPath(newPath);
      closeOperationPrompt();
      focusPathSoon(newPath);
      if (targetType === 'group') focusDefineSoon(newPath);
      else focusInputSoon(newPath);
      return;
    }
    addPart(operationPrompt.op || 'union', targetType);
    closeOperationPrompt();
  };

  const handleBuilderKeyDownCapture = (e) => {
    const targetScope = e.target instanceof Element ? e.target.closest('[data-territory-builder-scope]') : null;
    const targetScopeId = targetScope?.getAttribute('data-territory-builder-scope') || null;
    if (targetScopeId && targetScopeId !== promptScopeId) return;
    if (!targetScopeId && pathPrefix.length !== 0) return;

    if (operationPrompt) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        closeOperationPrompt();
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        commitOperationPrompt();
        return;
      }
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'Tab') {
        e.preventDefault();
        e.stopPropagation();
        cycleOperationPromptType(1);
        return;
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        cycleOperationPromptType(-1);
        return;
      }
      const shortcutType = TYPE_SHORTCUTS[String(e.key || '').toLowerCase()];
      if (shortcutType) {
        e.preventDefault();
        e.stopPropagation();
        commitOperationPrompt(shortcutType);
      }
      return;
    }
    if (isEditableTarget(e.target)) return;
    if (parts.length === 0) {
      if (String(e.key).toLowerCase() === 'd') {
        e.preventDefault();
        e.stopPropagation();
        startOperationPrompt('base');
      }
      return;
    }
    if (e.key === '+' || e.key === '=' || e.key === 'Add') {
      e.preventDefault();
      e.stopPropagation();
      startOperationPrompt('op', 'union');
      return;
    }
    if (e.key === '-' || e.key === 'Subtract') {
      e.preventDefault();
      e.stopPropagation();
      startOperationPrompt('op', 'difference');
      return;
    }
    if (e.key === '&') {
      e.preventDefault();
      e.stopPropagation();
      startOperationPrompt('op', 'intersection');
    }
  };

  useEffect(() => {
    if (!operationPrompt) return;
    window.requestAnimationFrame(() => {
      const scope = getLayerScope();
      const selector = `[data-territory-prompt-option="${promptScopeId}:${operationPrompt.focusedType || 'gadm'}"]`;
      const target = scope.querySelector(selector);
      if (target && typeof target.focus === 'function') target.focus();
    });
  }, [operationPrompt?.focusedType, operationPrompt?.mode, operationPrompt?.op, promptScopeId]);

  useEffect(() => {
    if (pathPrefix.length !== 0) return undefined;
    const onLayerKeyDown = (e) => {
      const scope = getLayerScope();
      const active = document.activeElement;
      if (!(active instanceof Element)) return;
      if (!scope.contains(active)) return;
      handleBuilderKeyDownCapture(e);
    };
    document.addEventListener('keydown', onLayerKeyDown, true);
    return () => document.removeEventListener('keydown', onLayerKeyDown, true);
  }, [pathPrefix.length, operationPrompt, parts.length]);

  const [territoryLibraryNames, setTerritoryLibraryNames] = useState([]);
  useEffect(() => {
    fetch(`${API_BASE}/territory_library/names`)
      .then(r => r.json())
      .then(setTerritoryLibraryNames)
      .catch(() => setTerritoryLibraryNames([]));
  }, []);

  // Hub library imports with kind='lib'
  const hubLibImports = useMemo(
    () => (hubImports || []).filter((imp) => imp.kind === 'lib' && imp.alias),
    [hubImports],
  );

  const [hubLibraryTerritories, setHubLibraryTerritories] = useState([]);
  useEffect(() => {
    if (!hubLibImports.length) {
      setHubLibraryTerritories([]);
      return;
    }
    Promise.all(
      hubLibImports.map(async (imp) => {
        const hub_path = imp.username
          ? `/${imp.username}/${imp.kind}/${imp.name}/${imp.selected_version || 'alpha'}`
          : `/${imp.kind}/${imp.name}/${imp.selected_version || 'alpha'}`;
        try {
          const res = await fetch(`${API_BASE}/territory_library/catalog`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ source: 'hub', hub_path }),
          });
          const data = await res.json();
          const names = Array.isArray(data.names) ? data.names : [];
          return names.map((n) => `${imp.alias}.${n}`);
        } catch {
          return [];
        }
      }),
    ).then((results) => setHubLibraryTerritories(results.flat()));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubLibImports.map((imp) => `${imp.username}:${imp.name}:${imp.selected_version || 'alpha'}:${imp.alias}`).join(',')]);

  const predefinedVariables = useMemo(() => {
    if (!predefinedCode) return [];
    // Strip comment lines so variables mentioned only in comments are not picked up
    const codeWithoutComments = predefinedCode
      .split('\n')
      .filter((line) => !/^\s*#/.test(line))
      .join('\n');
    const regex = /^(\w+)\s*=/gm;
    const matches = [];
    let match;
    // Exclude variables that are hub lib import aliases (they're namespaces, not territories)
    const hubAliases = new Set(hubLibImports.map((imp) => imp.alias).filter(Boolean));
    while ((match = regex.exec(codeWithoutComments)) !== null) {
      if (!hubAliases.has(match[1])) matches.push(match[1]);
    }
    return matches;
  }, [predefinedCode, hubLibImports]);

  const allPredefinedOptions = useMemo(() => {
    const fromCode = predefinedVariables;
    // Only show raw built-in library names if no hub lib imports override them
    const fromBuiltin = hubLibImports.length > 0
      ? []
      : territoryLibraryNames.filter((n) => !fromCode.includes(n));
    return [...fromCode, ...fromBuiltin, ...hubLibraryTerritories];
  }, [predefinedVariables, territoryLibraryNames, hubLibraryTerritories, hubLibImports]);

  if (parts.length === 0) {
    const focusedType = operationPrompt?.focusedType || 'gadm';
    return (
      <div
        ref={builderRootRef}
        data-territory-builder-scope={promptScopeId}
        onKeyDownCapture={handleBuilderKeyDownCapture}
        className="border border-dashed border-gray-300 rounded p-2 text-center bg-gray-50"
      >
        {!operationPrompt ? (
          <button
            type="button"
            data-territory-define-path={toPathId(pathPrefix)}
            onClick={() => startOperationPrompt('base')}
            className="text-xs text-blue-600 flex items-center justify-center gap-1 w-full font-medium"
            title="Define base territory (shortcut: d)"
          >
            <Plus size={12}/> Define Territory
          </button>
        ) : (
          <div className="text-xs text-gray-700 text-left">
            <div className="mb-1">
              Base:
            </div>
            <div className="flex flex-wrap gap-1">
              {PROMPT_OPTIONS.map((type) => (
                <button
                  type="button"
                  key={type}
                  onClick={() => commitOperationPrompt(type)}
                  data-territory-prompt-option={`${promptScopeId}:${type}`}
                  className={`px-1.5 py-0.5 border rounded ${focusedType === type ? 'border-blue-500 text-blue-700 bg-blue-50' : 'border-gray-300 bg-white hover:bg-gray-100'}`}
                >
                  {type === 'gadm' ? 'admin unit [a]' : type === 'polygon' ? 'polygon [p]' : type === 'predefined' ? 'territory [t]' : type === 'group' ? 'group [o]' : 'Esc'}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      ref={builderRootRef}
      data-territory-builder-scope={promptScopeId}
      className="space-y-2"
      onKeyDownCapture={handleBuilderKeyDownCapture}
    >
      {parts.map((part, idx) => {
        const rowPath = pathForIndex(idx);
        const rowPathKey = rowPath.join('.');
        const rowPathId = toPathId(rowPath);
        const isReferencePickingThisPart = !!(
          isReferencePickingThisFlag &&
          Array.isArray(activePicker?.target?.partPath) &&
          activePicker.target.partPath.join('.') === rowPathKey
        );
        const isLibraryPickingThisPart = !!(isLibraryPicking && Array.isArray(activePicker?.target?.partPath) && activePicker.target.partPath.join('.') === rowPathKey);
        const rowIndent = pathPrefix.length > 0 ? 'ml-3' : '';
        const isRowSelected = pathsEqual(selectedPath, rowPath);
        const isDropBefore = dragInsertionIndex === idx;

        if (part.type === 'group') {
          return (
            <React.Fragment key={rowPathKey}>
              <div className={`${rowIndent} h-1 rounded ${isDropBefore ? 'bg-blue-500' : 'bg-transparent'}`} />
              <div
                tabIndex={0}
                data-territory-path={rowPathId}
                onFocusCapture={() => setSelectedPath(rowPath)}
                onMouseDownCapture={() => setSelectedPath(rowPath)}
                onDragOver={(e) => handleDragOverRow(e, idx)}
                onDrop={(e) => handleDropOnRow(e, idx)}
                onKeyDown={(e) => handleRowKeyDown(e, rowPath)}
                className={`${rowIndent} bg-gray-50 p-2 rounded border transition-colors outline-none ${pathsEqual(draggedPath, rowPath) ? 'opacity-50' : ''} ${
                  dragOverGroupInsideIndex === idx ? 'border-blue-500 ring-1 ring-blue-200' : (isRowSelected ? 'border-blue-300 ring-1 ring-blue-100' : 'border-gray-200')
                }`}
              >
                <div className="flex gap-2 items-center">
                  <div
                    draggable
                    onDragStart={(e) => handleDragStart(e, rowPath)}
                    onDragEnd={handleDragEnd}
                    className="flex items-center cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 flex-shrink-0"
                    title="Drag to reorder"
                  >
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
                      if (nextType === 'group') updatePart(idx, { type: 'group', value: [] });
                      else if (nextType === 'polygon') updatePart(idx, { type: 'polygon', value: '' });
                      else updatePart(idx, { type: nextType, value: '' });
                    }}
                    className="text-xs p-1 border rounded bg-white w-24 flex-shrink-0"
                  >
                    <option value="gadm">Admin unit</option>
                    <option value="polygon">Polygon</option>
                    <option value="predefined">Territory</option>
                    <option value="group">Group...</option>
                  </select>
                  <div className="text-xs text-gray-500 font-medium">Nested Group</div>
                  <button onClick={() => removePart(idx)} className="text-red-400 hover:text-red-600 p-1 ml-auto flex-shrink-0">
                    <Trash2 size={12}/>
                  </button>
                </div>
                <div
                  className="mt-2 pl-3 border-l-2 border-gray-300 rounded-sm"
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    e.dataTransfer.dropEffect = 'move';
                    autoScrollForDrag(e);
                    setDragOverGroupInsideIndex(idx);
                    setDragInsertionIndex(null);
                  }}
                  onDragLeave={() => setDragOverGroupInsideIndex((prev) => (prev === idx ? null : prev))}
                  onDrop={(e) => handleDropInsideGroup(e, rowPath, Array.isArray(part.value) ? part.value.length : 0)}
                >
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
                    onMovePartByPath={movePartByPath}
                    selectedPath={selectedPath}
                    setSelectedPath={setSelectedPath}
                    hubImports={hubImports}
                  />
                </div>
              </div>
              {isRowSelected && (
                <div className={`${rowIndent} text-[10px] text-blue-700 mt-1 px-2`}>
                  Shift+Up/Down move • Shift+Left out above group • Shift+Right out below group {/* • + / - / & add operation */}
                </div>
              )}
            </React.Fragment>
          );
        }

        return (
          <React.Fragment key={rowPathKey}>
            <div className={`${rowIndent} h-1 rounded ${isDropBefore ? 'bg-blue-500' : 'bg-transparent'}`} />
            <div
              tabIndex={0}
              data-territory-path={rowPathId}
              onFocusCapture={() => setSelectedPath(rowPath)}
              onMouseDownCapture={() => setSelectedPath(rowPath)}
              onDragOver={(e) => handleDragOverRow(e, idx)}
              onDrop={(e) => handleDropOnRow(e, idx)}
              onKeyDown={(e) => handleRowKeyDown(e, rowPath)}
              className={`${rowIndent} flex gap-2 items-start bg-gray-50 p-2 rounded border transition-colors outline-none ${pathsEqual(draggedPath, rowPath) ? 'opacity-50' : ''} ${
                isRowSelected ? 'border-blue-300 ring-1 ring-blue-100' : 'border-gray-200'
              }`}
            >
              <div
                draggable
                onDragStart={(e) => handleDragStart(e, rowPath)}
                onDragEnd={handleDragEnd}
                className="flex items-center cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 flex-shrink-0"
                title="Drag to reorder"
              >
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
                <option value="gadm">Admin unit</option>
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
                        placeholder="Search admin units..."
                        mode="remote"
                        endpoint={`${API_BASE}/search/gadm`}
                        inputPath={rowPathId}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (isReferencePickingThisPart) {
                          setActivePicker(null);
                          return;
                        }
                        onStartReferencePick({ kind: 'gadm', flagIndex: parentId, partIndex: idx, partPath: rowPath });
                      }}
                      className={`p-1 border rounded flex-shrink-0 transition-colors ${isReferencePickingThisPart ? 'bg-blue-100 text-blue-700 border-blue-300 ring-2 ring-blue-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'}`}
                      title={isReferencePickingThisPart ? 'Cancel admin unit picking' : 'Pick admin unit from Reference Map'}
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
                        placeholder="e.g. KURU, LEVANT, AUDICYA"
                        mode="local"
                        localOptions={allPredefinedOptions}
                        inputPath={rowPathId}
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
                ) : (
                  <div className="flex gap-1 items-start">
                    <textarea
                      data-territory-input-path={rowPathId}
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
            {isRowSelected && (
              <div className={`${rowIndent} text-[10px] text-blue-700 mt-1 px-2`}>
                Shift+Up/Down move • Shift+Left out above group • Shift+Right out below group {/* • + / - / & add operation */}
              </div>
            )}
          </React.Fragment>
        );
      })}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.dataTransfer.dropEffect = 'move';
          autoScrollForDrag(e);
          setDragInsertionIndex(parts.length);
          setDragOverGroupInsideIndex(null);
        }}
        onDrop={handleDropAtEnd}
        className={`h-1 rounded ${dragInsertionIndex === parts.length ? 'bg-blue-500' : 'bg-transparent'}`}
      />

      {!operationPrompt ? (
        <div className="text-xs font-medium mt-1 flex items-center gap-1 flex-wrap">
          <button type="button" className="text-blue-600 hover:text-blue-800" onClick={() => startOperationPrompt('op', 'union')}>
            (+) add
          </button>
          <span className="text-gray-400">/</span>
          <button type="button" className="text-blue-600 hover:text-blue-800" onClick={() => startOperationPrompt('op', 'difference')}>
            (-) subtract
          </button>
          <span className="text-gray-400">/</span>
          <button type="button" className="text-blue-600 hover:text-blue-800" onClick={() => startOperationPrompt('op', 'intersection')}>
            (&) intersect
          </button>
        </div>
      ) : (
        <div className="text-xs text-gray-700 mt-1">
          <div className="mb-1">
            {operationPrompt.op === 'difference' ? '(-) subtract:' : operationPrompt.op === 'intersection' ? '(&) intersect:' : '(+) add:'}
          </div>
          <div className="flex flex-wrap gap-1">
            {PROMPT_OPTIONS.map((type) => (
              <button
                type="button"
                key={type}
                onClick={() => commitOperationPrompt(type)}
                data-territory-prompt-option={`${promptScopeId}:${type}`}
                className={`px-1.5 py-0.5 border rounded ${operationPrompt.focusedType === type ? 'border-blue-500 text-blue-700 bg-blue-50' : 'border-gray-300 bg-white hover:bg-gray-100'}`}
              >
                {type === 'gadm' ? 'admin unit [a]' : type === 'polygon' ? 'polygon [p]' : type === 'predefined' ? 'territory [t]' : type === 'group' ? 'group [o]' : 'Esc'}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TerritoryBuilder;
