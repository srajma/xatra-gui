import React, { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import { API_BASE } from '../config';

const GEOMETRIC_SHAPES = ['circle', 'square', 'triangle', 'diamond', 'cross', 'plus', 'star', 'hexagon', 'pentagon', 'octagon'];
const DEFAULT_BOOTSTRAP_VERSION = '1.11.3';

function normalizeIcon(icon, builtinIcons) {
  const fallback = { type: 'builtin', name: builtinIcons[0] || 'marker-icon.png' };
  if (!icon) return fallback;
  if (typeof icon === 'string') return { type: 'builtin', name: icon };
  if (typeof icon !== 'object') return fallback;

  const t = String(icon.type || '').toLowerCase();
  if (t === 'geometric' || icon.shape) {
    return {
      type: 'geometric',
      shape: icon.shape || 'circle',
      color: icon.color || '#3388ff',
      border_color: icon.border_color || '',
      border_width: Number(icon.border_width || 0),
      icon_size: icon.icon_size || null,
      icon_anchor: icon.icon_anchor || null,
    };
  }
  if (t === 'bootstrap') {
    return {
      type: 'bootstrap',
      name: icon.name || 'geo-alt-fill',
      version: icon.version || DEFAULT_BOOTSTRAP_VERSION,
      icon_size: icon.icon_size || null,
      icon_anchor: icon.icon_anchor || null,
    };
  }
  if (t === 'builtin' || icon.name) {
    return {
      type: 'builtin',
      name: icon.name || builtinIcons[0] || 'marker-icon.png',
      icon_size: icon.icon_size || null,
      icon_anchor: icon.icon_anchor || null,
    };
  }

  // URL/custom icons are intentionally not supported in website picker
  return fallback;
}

function NumberPairInput({ label, value, onChange, disabled = false, placeholder = 'x,y' }) {
  const text = Array.isArray(value) && value.length === 2 ? `${value[0]}, ${value[1]}` : '';
  return (
    <div>
      <label className={`block text-[11px] mb-1 ${disabled ? 'text-gray-400' : 'text-gray-500'}`}>{label}</label>
      <input
        disabled={disabled}
        value={text}
        onChange={(e) => {
          const raw = e.target.value.trim();
          if (!raw) {
            onChange(null);
            return;
          }
          const parts = raw.split(',').map((x) => x.trim());
          if (parts.length !== 2) return;
          const a = Number(parts[0]);
          const b = Number(parts[1]);
          if (Number.isNaN(a) || Number.isNaN(b)) return;
          onChange([a, b]);
        }}
        placeholder={placeholder}
        className={`w-full px-2 py-1.5 border rounded text-xs font-mono outline-none ${disabled ? 'border-gray-100 bg-gray-100 text-gray-400' : 'border-gray-200 focus:border-blue-500'}`}
      />
    </div>
  );
}

function IconPreview({ icon }) {
  if (!icon) return <div className="w-9 h-9 rounded border border-gray-200 bg-white" />;
  if (icon.type === 'geometric') {
    const size = 20;
    const color = icon.color || '#3388ff';
    const borderColor = icon.border_color || 'transparent';
    const borderWidth = Number(icon.border_width || 0);
    const shape = icon.shape || 'circle';
    const common = {
      width: `${size}px`,
      height: `${size}px`,
      background: color,
      border: `${borderWidth}px solid ${borderColor}`,
    };
    let style = { ...common, borderRadius: 999 };
    if (shape === 'square') style = { ...common, borderRadius: 4 };
    if (shape === 'triangle') style = { width: 0, height: 0, borderLeft: '10px solid transparent', borderRight: '10px solid transparent', borderBottom: `20px solid ${color}`, background: 'transparent' };
    if (shape === 'diamond') style = { ...common, transform: 'rotate(45deg)', borderRadius: 2 };
    if (shape === 'plus') style = { ...common, clipPath: 'polygon(35% 0%,65% 0%,65% 35%,100% 35%,100% 65%,65% 65%,65% 100%,35% 100%,35% 65%,0% 65%,0% 35%,35% 35%)' };
    if (shape === 'cross') style = { ...common, clipPath: 'polygon(17% 0%,50% 33%,83% 0%,100% 17%,67% 50%,100% 83%,83% 100%,50% 67%,17% 100%,0% 83%,33% 50%,0% 17%)' };
    if (shape === 'star') style = { ...common, clipPath: 'polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)' };
    if (shape === 'hexagon') style = { ...common, clipPath: 'polygon(25% 5%,75% 5%,95% 50%,75% 95%,25% 95%,5% 50%)' };
    if (shape === 'pentagon') style = { ...common, clipPath: 'polygon(50% 4%,95% 38%,78% 95%,22% 95%,5% 38%)' };
    if (shape === 'octagon') style = { ...common, clipPath: 'polygon(30% 4%,70% 4%,96% 30%,96% 70%,70% 96%,30% 96%,4% 70%,4% 30%)' };
    return <div className="w-9 h-9 flex items-center justify-center"><div style={style} /></div>;
  }

  if (icon.type === 'builtin') {
    const src = `${API_BASE}/icons/file/${encodeURIComponent(icon.name || 'marker-icon.png')}`;
    return (
      <div className="w-9 h-9 rounded border border-gray-200 bg-white flex items-center justify-center overflow-hidden">
        <img src={src} alt="leaflet marker preview" className="max-w-[24px] max-h-[24px] object-contain" />
      </div>
    );
  }

  const version = icon.version || DEFAULT_BOOTSTRAP_VERSION;
  const src = `https://cdn.jsdelivr.net/npm/bootstrap-icons@${version}/icons/${icon.name || 'geo-alt-fill'}.svg`;
  return (
    <div className="w-9 h-9 rounded border border-gray-200 bg-white flex items-center justify-center overflow-hidden">
      <img src={src} alt="icon preview" className="max-w-[24px] max-h-[24px] object-contain" />
    </div>
  );
}

function defaultForCurrentType(draft, builtinIcons) {
  if (!draft) return { type: 'builtin', name: builtinIcons[0] || 'marker-icon.png' };
  if (draft.type === 'geometric') {
    return {
      type: 'geometric',
      shape: draft.shape || 'circle',
      color: '#3388ff',
      border_color: '',
      border_width: 0,
      icon_size: null,
      icon_anchor: null,
    };
  }
  if (draft.type === 'bootstrap') {
    return {
      type: 'bootstrap',
      name: draft.name || 'geo-alt-fill',
      version: DEFAULT_BOOTSTRAP_VERSION,
      icon_size: null,
      icon_anchor: null,
    };
  }
  return {
    type: 'builtin',
    name: draft.name || builtinIcons[0] || 'marker-icon.png',
    icon_size: null,
    icon_anchor: null,
  };
}

export default function IconPickerModal({ open, onClose, iconValue, onChange, builtinIcons = [] }) {
  const initial = useMemo(() => normalizeIcon(iconValue, builtinIcons), [iconValue, builtinIcons]);
  const [draft, setDraft] = useState(initial);
  const [search, setSearch] = useState('');
  const [bootstrapIcons, setBootstrapIcons] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDraft(normalizeIcon(iconValue, builtinIcons));
  }, [open, iconValue, builtinIcons]);

  useEffect(() => {
    if (!open) return;
    const query = search.trim();
    setLoading(true);
    fetch(`${API_BASE}/icons/bootstrap?q=${encodeURIComponent(query)}&offset=0&limit=80&version=${DEFAULT_BOOTSTRAP_VERSION}`)
      .then((r) => r.json())
      .then((res) => {
        const items = Array.isArray(res?.items) ? res.items : [];
        setBootstrapIcons(items);
        setOffset(items.length);
        setHasMore(Boolean(res?.has_more));
      })
      .catch(() => {
        setBootstrapIcons([]);
        setOffset(0);
        setHasMore(false);
      })
      .finally(() => setLoading(false));
  }, [open, search]);

  const loadMore = () => {
    if (loading || !hasMore) return;
    const query = search.trim();
    setLoading(true);
    fetch(`${API_BASE}/icons/bootstrap?q=${encodeURIComponent(query)}&offset=${offset}&limit=80&version=${DEFAULT_BOOTSTRAP_VERSION}`)
      .then((r) => r.json())
      .then((res) => {
        const items = Array.isArray(res?.items) ? res.items : [];
        setBootstrapIcons((prev) => [...prev, ...items]);
        setOffset((prev) => prev + items.length);
        setHasMore(Boolean(res?.has_more));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  if (!open) return null;

  const query = search.trim().toLowerCase();
  const geometricItems = GEOMETRIC_SHAPES.filter((s) => !query || s.includes(query)).map((shape) => ({ type: 'geometric', key: `g:${shape}`, label: shape, shape }));
  const builtinItems = builtinIcons.filter((name) => !query || String(name).toLowerCase().includes(query)).map((name) => ({ type: 'builtin', key: `b:${name}`, label: name, name }));
  const bootstrapItems = bootstrapIcons.map((name) => ({ type: 'bootstrap', key: `bs:${name}`, label: name, name }));
  const listItems = [...geometricItems, ...builtinItems, ...bootstrapItems];

  const isGeometric = draft?.type === 'geometric';

  const pick = (item) => {
    if (item.type === 'geometric') {
      setDraft((prev) => ({
        type: 'geometric',
        shape: item.shape,
        color: prev?.type === 'geometric' ? (prev.color || '#3388ff') : '#3388ff',
        border_color: prev?.type === 'geometric' ? (prev.border_color || '') : '',
        border_width: prev?.type === 'geometric' ? Number(prev.border_width || 0) : 0,
        icon_size: prev?.icon_size || null,
        icon_anchor: prev?.icon_anchor || null,
      }));
      return;
    }
    if (item.type === 'builtin') {
      setDraft((prev) => ({ type: 'builtin', name: item.name, icon_size: prev?.icon_size || null, icon_anchor: prev?.icon_anchor || null }));
      return;
    }
    setDraft((prev) => ({ type: 'bootstrap', name: item.name, version: DEFAULT_BOOTSTRAP_VERSION, icon_size: prev?.icon_size || null, icon_anchor: prev?.icon_anchor || null }));
  };

  const apply = () => {
    onChange(draft || null);
    onClose();
  };

  const currentLabel = draft?.type === 'geometric'
    ? `Geometric: ${draft.shape || 'circle'}`
    : draft?.type === 'bootstrap'
      ? `Bootstrap: ${draft.name || ''}`
      : `Leaflet built-in: ${draft?.name || ''}`;

  return (
    <div className="fixed inset-0 z-[1000] bg-black/35 backdrop-blur-[1px] flex items-center justify-center p-4">
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-sky-50 to-indigo-50">
          <div>
            <div className="text-sm font-semibold text-gray-900">Icon Picker</div>
            <div className="text-xs text-gray-500">Unified browser for geometric shapes, Leaflet markers, and Bootstrap icons.</div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/70 text-gray-600"><X size={16} /></button>
        </div>

        <div className="p-5 grid grid-cols-1 lg:grid-cols-[1fr,1.2fr] gap-5 max-h-[70vh] overflow-auto">
          <div className="space-y-3 border border-gray-100 rounded-xl p-3 bg-gray-50/60">
            <div className="flex items-center gap-2">
              <IconPreview icon={draft} />
              <div>
                <div className="text-xs font-semibold text-gray-800">Current selection</div>
                <div className="text-[11px] text-gray-500">{currentLabel}</div>
              </div>
            </div>

            <NumberPairInput label="Icon size [w, h]" value={draft?.icon_size || null} onChange={(v) => setDraft((prev) => ({ ...(prev || {}), icon_size: v }))} />
            <NumberPairInput label="Icon anchor [x, y]" value={draft?.icon_anchor || null} onChange={(v) => setDraft((prev) => ({ ...(prev || {}), icon_anchor: v }))} />

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={`block text-[11px] mb-1 ${isGeometric ? 'text-gray-500' : 'text-gray-400'}`}>Color</label>
                <input
                  disabled={!isGeometric}
                  value={draft?.color || '#3388ff'}
                  onChange={(e) => setDraft((prev) => ({ ...(prev || {}), color: e.target.value }))}
                  className={`w-full px-2 py-1.5 border rounded text-xs font-mono ${isGeometric ? 'border-gray-200 focus:border-blue-500 outline-none' : 'border-gray-100 bg-gray-100 text-gray-400'}`}
                />
              </div>
              <div>
                <label className={`block text-[11px] mb-1 ${isGeometric ? 'text-gray-500' : 'text-gray-400'}`}>Border color</label>
                <input
                  disabled={!isGeometric}
                  value={draft?.border_color || ''}
                  onChange={(e) => setDraft((prev) => ({ ...(prev || {}), border_color: e.target.value }))}
                  className={`w-full px-2 py-1.5 border rounded text-xs font-mono ${isGeometric ? 'border-gray-200 focus:border-blue-500 outline-none' : 'border-gray-100 bg-gray-100 text-gray-400'}`}
                />
              </div>
              <div>
                <label className={`block text-[11px] mb-1 ${isGeometric ? 'text-gray-500' : 'text-gray-400'}`}>Border width</label>
                <input
                  type="number"
                  min={0}
                  max={16}
                  disabled={!isGeometric}
                  value={Number(draft?.border_width || 0)}
                  onChange={(e) => setDraft((prev) => ({ ...(prev || {}), border_width: Number(e.target.value || 0) }))}
                  className={`w-full px-2 py-1.5 border rounded text-xs ${isGeometric ? 'border-gray-200 focus:border-blue-500 outline-none' : 'border-gray-100 bg-gray-100 text-gray-400'}`}
                />
              </div>
            </div>

            <button
              onClick={() => setDraft(defaultForCurrentType(draft, builtinIcons))}
              className="w-full px-3 py-1.5 rounded border border-gray-200 text-xs text-gray-700 hover:bg-gray-50"
            >
              Reset to Default
            </button>
          </div>

          <div className="space-y-3">
            <div className="relative">
              <Search size={14} className="absolute left-2 top-2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search all icons: marker, geo, shield, star..."
                className="w-full pl-7 pr-2 py-1.5 border border-gray-200 rounded text-xs focus:border-blue-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[48vh] overflow-auto pr-1">
              {listItems.map((item) => {
                const isSelected = (draft?.type === item.type) && (
                  (item.type === 'geometric' && draft?.shape === item.shape) ||
                  ((item.type === 'builtin' || item.type === 'bootstrap') && draft?.name === item.name)
                );
                const preview = item.type === 'geometric'
                  ? { type: 'geometric', shape: item.shape, color: draft?.color || '#3388ff', border_color: draft?.border_color || '', border_width: Number(draft?.border_width || 0) }
                  : item.type === 'builtin'
                    ? { type: 'builtin', name: item.name }
                    : { type: 'bootstrap', name: item.name, version: DEFAULT_BOOTSTRAP_VERSION };
                return (
                  <button
                    key={item.key}
                    onClick={() => pick(item)}
                    className={`p-2 rounded-lg border text-left text-xs transition ${isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                  >
                    <div className="flex items-center gap-2">
                      <IconPreview icon={preview} />
                      <div className="min-w-0">
                        <div className="truncate">{item.label}</div>
                        <div className="text-[10px] text-gray-400 uppercase">{item.type}</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {!loading && listItems.length === 0 && (
              <div className="text-[11px] text-gray-400">No icons found.</div>
            )}

            <div className="flex justify-center">
              {hasMore ? (
                <button onClick={loadMore} className="text-xs px-3 py-1.5 rounded border border-gray-200 hover:border-blue-300 bg-white">
                  {loading ? 'Loading...' : 'Load more Bootstrap icons'}
                </button>
              ) : (
                <span className="text-[11px] text-gray-400">{loading ? 'Loading...' : 'All available results loaded'}</span>
              )}
            </div>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-gray-100 bg-white flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 rounded border border-gray-200 text-xs hover:bg-gray-50">Cancel</button>
          <button onClick={apply} className="px-3 py-1.5 rounded bg-blue-600 text-white text-xs hover:bg-blue-700">Apply Icon</button>
        </div>
      </div>
    </div>
  );
}
