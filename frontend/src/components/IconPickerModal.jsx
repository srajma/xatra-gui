import React, { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import { API_BASE } from '../config';

const GEOMETRIC_SHAPES = ['circle', 'square', 'triangle', 'diamond', 'cross', 'plus', 'star', 'hexagon', 'pentagon', 'octagon'];

function normalizeIcon(icon) {
  if (!icon) return null;
  if (typeof icon === 'string') return { type: 'builtin', name: icon };
  if (typeof icon !== 'object') return null;
  if (icon.type) return { ...icon };
  if (icon.shape) return { type: 'geometric', ...icon };
  if (icon.icon_url || icon.iconUrl) return { type: 'url', ...icon, icon_url: icon.icon_url || icon.iconUrl };
  if (icon.name) return { type: 'builtin', ...icon };
  return null;
}

function NumberPairInput({ label, value, onChange, placeholder = 'x,y' }) {
  const text = Array.isArray(value) && value.length === 2 ? `${value[0]}, ${value[1]}` : '';
  return (
    <div>
      <label className="block text-[11px] text-gray-500 mb-1">{label}</label>
      <input
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
        className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono focus:border-blue-500 outline-none"
      />
    </div>
  );
}

function IconPreview({ icon }) {
  const normalized = normalizeIcon(icon);
  if (!normalized) {
    return <div className="w-9 h-9 rounded border border-gray-200 bg-white" />;
  }
  const type = normalized.type;
  if (type === 'geometric') {
    const size = Number(normalized.size || 24);
    const color = normalized.color || '#3388ff';
    const borderColor = normalized.border_color || 'transparent';
    const borderWidth = Number(normalized.border_width || 0);
    const common = {
      width: `${Math.min(28, size)}px`,
      height: `${Math.min(28, size)}px`,
      background: color,
      border: `${borderWidth}px solid ${borderColor}`,
    };
    const shape = normalized.shape || 'circle';
    let style = { ...common, borderRadius: 999 };
    if (shape === 'square') style = { ...common, borderRadius: 4 };
    if (shape === 'triangle') style = { width: 0, height: 0, borderLeft: '12px solid transparent', borderRight: '12px solid transparent', borderBottom: `24px solid ${color}`, background: 'transparent' };
    if (shape === 'diamond') style = { ...common, transform: 'rotate(45deg)', borderRadius: 2 };
    if (shape === 'cross' || shape === 'plus') style = { ...common, clipPath: 'polygon(35% 0%,65% 0%,65% 35%,100% 35%,100% 65%,65% 65%,65% 100%,35% 100%,35% 65%,0% 65%,0% 35%,35% 35%)' };
    if (shape === 'star') style = { ...common, clipPath: 'polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)' };
    return <div className="w-9 h-9 flex items-center justify-center"><div style={style} /></div>;
  }
  let src = '';
  if (type === 'builtin') {
    src = '';
  } else if (type === 'bootstrap') {
    const base = (normalized.base_url && String(normalized.base_url).trim()) || `https://cdn.jsdelivr.net/npm/bootstrap-icons@${normalized.version || '1.11.3'}/icons`;
    src = `${base.replace(/\/$/, '')}/${normalized.name || ''}.svg`;
  } else if (type === 'url') {
    src = normalized.icon_url || normalized.iconUrl || '';
  }
  if (!src && type === 'builtin') {
    const name = String(normalized.name || '').toLowerCase();
    const color = name.includes('red') ? '#d14343' : name.includes('green') ? '#2f9d57' : '#3b82f6';
    return (
      <div className="w-9 h-9 rounded border border-gray-200 bg-white flex items-center justify-center overflow-hidden">
        <div style={{ width: 14, height: 14, borderRadius: 999, background: color }} />
      </div>
    );
  }
  return (
    <div className="w-9 h-9 rounded border border-gray-200 bg-white flex items-center justify-center overflow-hidden">
      {src ? <img src={src} alt="icon preview" className="max-w-[26px] max-h-[26px] object-contain" /> : null}
    </div>
  );
}

export default function IconPickerModal({ open, onClose, iconValue, onChange, builtinIcons = [] }) {
  const initial = useMemo(() => normalizeIcon(iconValue) || { type: 'builtin', name: builtinIcons[0] || 'marker-icon.png' }, [iconValue, builtinIcons]);
  const [draft, setDraft] = useState(initial);
  const [tab, setTab] = useState(initial.type || 'builtin');
  const [search, setSearch] = useState('');
  const [bootstrapIcons, setBootstrapIcons] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const next = normalizeIcon(iconValue) || { type: 'builtin', name: builtinIcons[0] || 'marker-icon.png' };
    setDraft(next);
    setTab(next.type || 'builtin');
  }, [open, iconValue, builtinIcons]);

  useEffect(() => {
    if (!open || tab !== 'bootstrap') return;
    const version = draft?.version || '1.11.3';
    const query = search.trim();
    setLoading(true);
    fetch(`${API_BASE}/icons/bootstrap?q=${encodeURIComponent(query)}&offset=0&limit=80&version=${encodeURIComponent(version)}`)
      .then((r) => r.json())
      .then((res) => {
        setBootstrapIcons(Array.isArray(res?.items) ? res.items : []);
        setOffset((Array.isArray(res?.items) ? res.items.length : 0));
        setHasMore(Boolean(res?.has_more));
      })
      .catch(() => {
        setBootstrapIcons([]);
        setOffset(0);
        setHasMore(false);
      })
      .finally(() => setLoading(false));
  }, [open, tab, search, draft?.version]);

  const loadMoreBootstrap = () => {
    if (loading || !hasMore) return;
    const version = draft?.version || '1.11.3';
    const query = search.trim();
    setLoading(true);
    fetch(`${API_BASE}/icons/bootstrap?q=${encodeURIComponent(query)}&offset=${offset}&limit=80&version=${encodeURIComponent(version)}`)
      .then((r) => r.json())
      .then((res) => {
        const next = Array.isArray(res?.items) ? res.items : [];
        setBootstrapIcons((prev) => [...prev, ...next]);
        setOffset((prev) => prev + next.length);
        setHasMore(Boolean(res?.has_more));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  if (!open) return null;

  const chooseType = (type) => {
    setTab(type);
    if (type === 'builtin') setDraft({ type, name: builtinIcons[0] || 'marker-icon.png' });
    if (type === 'bootstrap') setDraft({ type, name: 'geo-alt-fill', version: '1.11.3', base_url: '', icon_size: [24, 24] });
    if (type === 'geometric') setDraft({ type, shape: 'circle', color: '#3388ff', size: 24, border_width: 0 });
    if (type === 'url') setDraft({ type, icon_url: '', icon_size: [24, 24], icon_anchor: [12, 12], popup_anchor: [0, -12] });
    if (type === 'none') setDraft(null);
  };

  const setDraftField = (key, val) => setDraft((prev) => ({ ...(prev || {}), [key]: val }));

  const apply = () => {
    onChange(draft);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[1000] bg-black/35 backdrop-blur-[1px] flex items-center justify-center p-4">
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-sky-50 to-indigo-50">
          <div>
            <div className="text-sm font-semibold text-gray-900">Icon Picker</div>
            <div className="text-xs text-gray-500">Browse Leaflet markers, Bootstrap icons, geometric shapes, or custom URLs.</div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/70 text-gray-600"><X size={16} /></button>
        </div>

        <div className="px-5 pt-4 pb-3 border-b border-gray-100 flex flex-wrap gap-2">
          {['none', 'builtin', 'bootstrap', 'geometric', 'url'].map((t) => (
            <button
              key={t}
              onClick={() => chooseType(t)}
              className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${tab === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300'}`}
            >
              {t === 'none' ? 'Default' : t === 'builtin' ? 'Leaflet Built-ins' : t === 'bootstrap' ? 'Bootstrap' : t === 'geometric' ? 'Geometric' : 'Custom URL'}
            </button>
          ))}
        </div>

        <div className="p-5 grid grid-cols-1 lg:grid-cols-[1.2fr,1fr] gap-5 max-h-[70vh] overflow-auto">
          <div className="space-y-4">
            {tab === 'builtin' && (
              <div>
                <label className="block text-xs text-gray-500 mb-2">Leaflet marker icons</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {builtinIcons.map((name) => (
                    <button
                      key={name}
                      onClick={() => setDraft({ type: 'builtin', name })}
                      className={`p-2 rounded-lg border text-left text-xs transition ${draft?.name === name ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                    >
                      <div className="flex items-center gap-2">
                        <IconPreview icon={{ type: 'builtin', name }} />
                        <span className="truncate">{name}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {tab === 'bootstrap' && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search size={14} className="absolute left-2 top-2 text-gray-400" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search icons: geo, bank, shield..."
                      className="w-full pl-7 pr-2 py-1.5 border border-gray-200 rounded text-xs focus:border-blue-500 outline-none"
                    />
                  </div>
                  <input
                    value={draft?.version || '1.11.3'}
                    onChange={(e) => setDraftField('version', e.target.value)}
                    placeholder="1.11.3"
                    className="w-24 px-2 py-1.5 border border-gray-200 rounded text-xs font-mono"
                    title="Bootstrap Icons version"
                  />
                </div>
                <input
                  value={draft?.name || ''}
                  onChange={(e) => setDraftField('name', e.target.value)}
                  placeholder="Icon name (e.g. geo-alt-fill)"
                  className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono focus:border-blue-500 outline-none"
                />
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {bootstrapIcons.map((name) => {
                    const icon = { type: 'bootstrap', name, version: draft?.version || '1.11.3', base_url: draft?.base_url || '' };
                    return (
                      <button
                        key={name}
                        onClick={() => setDraft({ ...icon, icon_size: draft?.icon_size || [24, 24], icon_anchor: draft?.icon_anchor || null, popup_anchor: draft?.popup_anchor || null })}
                        className={`p-2 rounded-lg border text-left text-xs transition ${draft?.name === name ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                      >
                        <div className="flex items-center gap-2">
                          <IconPreview icon={icon} />
                          <span className="truncate">{name}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
                {!loading && bootstrapIcons.length === 0 && (
                  <div className="text-[11px] text-gray-400">No results. Try a broader search or type an icon name manually.</div>
                )}
                <div className="flex justify-center pt-1">
                  {hasMore ? (
                    <button onClick={loadMoreBootstrap} className="text-xs px-3 py-1.5 rounded border border-gray-200 hover:border-blue-300 bg-white">
                      {loading ? 'Loading...' : 'Load more'}
                    </button>
                  ) : (
                    <span className="text-[11px] text-gray-400">{loading ? 'Loading...' : 'No more results'}</span>
                  )}
                </div>
              </div>
            )}

            {tab === 'geometric' && (
              <div>
                <label className="block text-xs text-gray-500 mb-2">Shape</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {GEOMETRIC_SHAPES.map((shape) => {
                    const icon = {
                      type: 'geometric',
                      shape,
                      color: draft?.color || '#3388ff',
                      size: Number(draft?.size || 24),
                      border_color: draft?.border_color,
                      border_width: Number(draft?.border_width || 0),
                    };
                    return (
                      <button
                        key={shape}
                        onClick={() => setDraft({ ...(draft || { type: 'geometric' }), ...icon })}
                        className={`p-2 rounded-lg border text-left text-xs transition ${draft?.shape === shape ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                      >
                        <div className="flex items-center gap-2">
                          <IconPreview icon={icon} />
                          <span className="truncate">{shape}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {tab === 'url' && (
              <div className="space-y-2">
                <label className="block text-xs text-gray-500">Image URL or data URI</label>
                <input
                  value={draft?.icon_url || ''}
                  onChange={(e) => setDraft({ ...(draft || { type: 'url' }), icon_url: e.target.value })}
                  placeholder="https://.../icon.svg"
                  className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono"
                />
                <input
                  value={draft?.shadow_url || ''}
                  onChange={(e) => setDraft({ ...(draft || { type: 'url' }), shadow_url: e.target.value })}
                  placeholder="Optional shadow URL"
                  className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono"
                />
              </div>
            )}
          </div>

          <div className="space-y-3 border border-gray-100 rounded-xl p-3 bg-gray-50/60">
            <div className="flex items-center gap-2">
              <IconPreview icon={draft} />
              <div>
                <div className="text-xs font-semibold text-gray-800">Current selection</div>
                <div className="text-[11px] text-gray-500 break-all">{draft?.type ? `${draft.type}${draft.name ? `: ${draft.name}` : ''}` : 'Default Leaflet marker'}</div>
              </div>
            </div>

            {tab === 'bootstrap' && (
              <>
                <label className="block text-[11px] text-gray-500 mb-1">Base URL override (optional)</label>
                <input
                  value={draft?.base_url || ''}
                  onChange={(e) => setDraftField('base_url', e.target.value)}
                  placeholder="/static/bootstrap-icons or https://.../icons"
                  className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono"
                />
                <div className="text-[10px] text-gray-400">Use this for self-hosted icons.</div>
              </>
            )}

            {tab === 'geometric' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Color</label>
                  <input value={draft?.color || '#3388ff'} onChange={(e) => setDraftField('color', e.target.value)} className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono" />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Size</label>
                  <input type="number" min={8} max={128} value={Number(draft?.size || 24)} onChange={(e) => setDraftField('size', Number(e.target.value || 24))} className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs" />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Border color</label>
                  <input value={draft?.border_color || ''} onChange={(e) => setDraftField('border_color', e.target.value)} className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs font-mono" />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Border width</label>
                  <input type="number" min={0} max={16} value={Number(draft?.border_width || 0)} onChange={(e) => setDraftField('border_width', Number(e.target.value || 0))} className="w-full px-2 py-1.5 border border-gray-200 rounded text-xs" />
                </div>
              </div>
            )}

            {tab !== 'none' && (
              <div className="grid grid-cols-1 gap-2">
                <NumberPairInput label="Icon size [w, h] (optional)" value={draft?.icon_size || null} onChange={(v) => setDraftField('icon_size', v)} />
                <NumberPairInput label="Icon anchor [x, y] (optional)" value={draft?.icon_anchor || null} onChange={(v) => setDraftField('icon_anchor', v)} />
                <NumberPairInput label="Popup anchor [x, y] (optional)" value={draft?.popup_anchor || null} onChange={(v) => setDraftField('popup_anchor', v)} />
              </div>
            )}
          </div>
        </div>

        <div className="px-5 py-3 border-t border-gray-100 bg-white flex items-center justify-between">
          <div className="text-[11px] text-gray-500">Large libraries are loaded in pages for speed.</div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-3 py-1.5 rounded border border-gray-200 text-xs hover:bg-gray-50">Cancel</button>
            <button onClick={apply} className="px-3 py-1.5 rounded bg-blue-600 text-white text-xs hover:bg-blue-700">Apply Icon</button>
          </div>
        </div>
      </div>
    </div>
  );
}
