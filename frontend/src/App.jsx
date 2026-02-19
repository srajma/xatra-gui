import React, { useState, useEffect, useRef } from 'react';
import { Layers, Code, Play, Upload, Download, Image, Plus, Trash2, Keyboard, Copy, Check, Moon, Sun, Menu, Compass, User, Users, LogIn, LogOut, FilePlus2, Import, Save, Heart, GitFork } from 'lucide-react';

// Components (defined inline for simplicity first, can be split later)
import Builder from './components/Builder';
import CodeEditor from './components/CodeEditor';
import MapPreview from './components/MapPreview';
import AutocompleteInput from './components/AutocompleteInput';
import { isPythonValue, getPythonExpr } from './utils/pythonValue';

const API_BASE = 'http://localhost:8088';
const HUB_NAME_RE = /^[a-z0-9_.]+$/;
const FIXED_PY_IMPORTS = `import xatra
from xatra.loaders import gadm, naturalearth, polygon, overpass
from xatra.icon import Icon
from xatra.colorseq import Color, ColorSequence, LinearColorSequence
from matplotlib.colors import LinearSegmentedColormap`;
const IMPORTABLE_LAYER_TYPES = [
  'Flag', 'River', 'Path', 'Point', 'Text', 'Admin', 'AdminRivers', 'Dataframe',
  'TitleBox', 'CSS', 'BaseOption', 'FlagColorSequence', 'AdminColorSequence',
  'DataColormap', 'zoom', 'focus', 'slider', 'Python',
];

const apiFetch = (path, options = {}) => {
  const headers = options.headers || {};
  return fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  });
};

const parsePath = (pathname) => {
  const parts = String(pathname || '/').split('/').filter(Boolean);
  if (parts.length === 0) return { page: 'editor' };
  if (parts[0] === 'new-map') return { page: 'editor', newMap: true };
  if (parts[0] === 'explore') return { page: 'explore' };
  if (parts[0] === 'users') return { page: 'users' };
  if (parts[0] === 'login') return { page: 'login' };
  if (parts.length >= 3 && parts[1] === 'map') {
    let version = 'alpha';
    if (parts[3] && /^v\d+$/i.test(parts[3])) version = parts[3].slice(1);
    if (parts[3] && String(parts[3]).toLowerCase() === 'alpha') version = 'alpha';
    return { page: 'editor', owner: parts[0], map: parts[2], version };
  }
  if (parts.length === 1) return { page: 'profile', username: parts[0] };
  return { page: 'editor' };
};

const isTerritoryPolygonPicker = (ctx) => /^territory-\d+$/.test(String(ctx || ''));
const isEditableTarget = (target) => (
  !!(target && typeof target.closest === 'function' && target.closest('input, textarea, [contenteditable="true"], [role="textbox"]'))
);

function App() {
  const [activeTab, setActiveTab] = useState('builder'); // 'builder' or 'code'
  const [activePreviewTab, setActivePreviewTab] = useState('main'); // 'main' | 'picker' | 'library'
  const [mapHtml, setMapHtml] = useState('');
  const [mapPayload, setMapPayload] = useState(null);
  const [pickerHtml, setPickerHtml] = useState('');
  const [territoryLibraryHtml, setTerritoryLibraryHtml] = useState('');
  const [territoryLibrarySource, setTerritoryLibrarySource] = useState('builtin'); // builtin | custom
  const [activeLibraryTab, setActiveLibraryTab] = useState('builtin');
  const [territoryLibraryNames, setTerritoryLibraryNames] = useState([]);
  const [selectedTerritoryNames, setSelectedTerritoryNames] = useState([]);
  const [territorySearchTerm, setTerritorySearchTerm] = useState('');
  const [copyIndexCopied, setCopyIndexCopied] = useState(false);
  const [loadingByView, setLoadingByView] = useState({ main: false, picker: false, library: false });
  const [mainRenderTask, setMainRenderTask] = useState(null); // 'code' | 'builder' | null
  const [error, setError] = useState(null);
  const [route, setRoute] = useState(() => parsePath(window.location.pathname));
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuFocusIndex, setMenuFocusIndex] = useState(0);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [statusNotice, setStatusNotice] = useState('');
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ username: '', password: '', full_name: '' });
  const [currentUser, setCurrentUser] = useState({ is_authenticated: false, user: { username: 'new_user', full_name: '', bio: '' } });
  const [authReady, setAuthReady] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [profileEdit, setProfileEdit] = useState({ full_name: '', bio: '' });
  const [passwordEdit, setPasswordEdit] = useState({ current_password: '', new_password: '' });
  const [profileSearch, setProfileSearch] = useState('');
  const [profilePage, setProfilePage] = useState(1);
  const [exploreData, setExploreData] = useState({ items: [], page: 1, per_page: 12, total: 0 });
  const [exploreQuery, setExploreQuery] = useState('');
  const [explorePage, setExplorePage] = useState(1);
  const [usersData, setUsersData] = useState({ items: [], page: 1, per_page: 20, total: 0 });
  const [usersQuery, setUsersQuery] = useState('');
  const [usersPage, setUsersPage] = useState(1);
  const [exploreLoading, setExploreLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Builder State
  const [builderElements, setBuilderElements] = useState([
    { type: 'flag', label: 'India', value: [], args: { note: 'Republic of India' } }
  ]);
  const [builderOptions, setBuilderOptions] = useState({
    basemaps: [{ url_or_provider: 'Esri.WorldTopoMap', default: true }],
    flag_color_sequences: [{ class_name: '', colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
    admin_color_sequences: [{ colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
    data_colormap: { type: 'LinearSegmented', colors: 'yellow,orange,red' },
  });
  const [isDarkMode, setIsDarkMode] = useState(() => {
    try {
      return localStorage.getItem('xatra-theme') === 'dark';
    } catch {
      return false;
    }
  });

  // Code State
  const [mapName, setMapName] = useState(() => {
    try {
      return localStorage.getItem('xatra-map-name') || 'new_map';
    } catch {
      return 'new_map';
    }
  });
  const [mapVersionLabel, setMapVersionLabel] = useState('alpha');
  const [libraryVersionLabel, setLibraryVersionLabel] = useState('alpha');
  const [themeVersionLabel, setThemeVersionLabel] = useState('alpha');
  const [selectedLibraryVersion, setSelectedLibraryVersion] = useState('alpha');
  const [selectedThemeVersion, setSelectedThemeVersion] = useState('alpha');
  const [mapOwner, setMapOwner] = useState('new_user');
  const [sourceMapRef, setSourceMapRef] = useState(null);
  const [mapDescription, setMapDescription] = useState('');
  const [mapDescriptionModalOpen, setMapDescriptionModalOpen] = useState(false);
  const [mapDescriptionDraft, setMapDescriptionDraft] = useState('');
  const [pendingMapPublish, setPendingMapPublish] = useState(null);
  const [mapVotes, setMapVotes] = useState(0);
  const [mapViews, setMapViews] = useState(0);
  const [importsCode, setImportsCode] = useState('indic = xatrahub("/srajma/lib/indic")\n');
  const [hubImports, setHubImports] = useState([]);
  const [themeCode, setThemeCode] = useState('');
  const [runtimeCode, setRuntimeCode] = useState('');
  const [hubQuery, setHubQuery] = useState('');
  const [hubSearchResults, setHubSearchResults] = useState([]);
  const [importLayerSelection, setImportLayerSelection] = useState(() => (
    IMPORTABLE_LAYER_TYPES.reduce((acc, key) => ({ ...acc, [key]: true }), {})
  ));
  const [artifactVersionOptions, setArtifactVersionOptions] = useState({});
  const [importVersionDraft, setImportVersionDraft] = useState({});
  const [code, setCode] = useState(`import xatra
from xatra.loaders import gadm, naturalearth

xatra.BaseOption("Esri.WorldTopoMap", default=True)
xatra.Flag(label="India", value=gadm("IND"), note="Republic of India")
xatra.TitleBox("<b>My Map</b>")
`);

  const [predefinedCode, setPredefinedCode] = useState(``);

  // Picker State
  const [pickerOptions, setPickerOptions] = useState({
    entries: [
      { country: 'IND', level: 2 },
      { country: 'PAK', level: 3 },
      { country: 'BGD', level: 2 },
      { country: 'NPL', level: 3 },
      { country: 'BTN', level: 1 },
      { country: 'LKA', level: 1 },
      { country: 'AFG', level: 2 },
    ],
    adminRivers: true
  });
  
  const [lastMapClick, setLastMapClick] = useState(null);
  const [activePicker, setActivePicker] = useState(null); // { id, type, context }
  const [draftPoints, setDraftPoints] = useState([]);
  const [freehandModifierPressed, setFreehandModifierPressed] = useState(false);
  const [isMouseDown, setIsMouseDown] = useState(false);
  const [pickedGadmSelection, setPickedGadmSelection] = useState([]);
  const [pickedTerritorySelection, setPickedTerritorySelection] = useState([]);
  const [referencePickTarget, setReferencePickTarget] = useState(null); // { kind: 'gadm'|'river'|'territory', flagIndex?, layerIndex?, partIndex? }
  const [countryLevelOptions, setCountryLevelOptions] = useState({});
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const [addLayerSignal, setAddLayerSignal] = useState(null);
  const hoverPickRef = useRef('');
  const didPrefetchReferenceRef = useRef(false);
  const didPrefetchTerritoryRef = useRef(false);

  const iframeRef = useRef(null);
  const pickerIframeRef = useRef(null);
  const territoryLibraryIframeRef = useRef(null);
  const menuRef = useRef(null);
  const importSearchRef = useRef(null);
  const menuOpenRef = useRef(false);
  const menuFocusIndexRef = useRef(0);

  const injectTerritoryLabelOverlayPatch = (html) => {
    if (!html || typeof html !== 'string') return html;
    const marker = '__xatraLabelOverlayPatchV1';
    if (html.includes(marker)) return html;
  const patchScript = `
<script>
(function() {
  if (window.__xatraLabelOverlayPatchV1) return;
  window.__xatraLabelOverlayPatchV1 = true;
  const styles = {
    union: { color: '#16a34a', fillColor: '#16a34a', fillOpacity: 0.2, weight: 3, opacity: 1.0 },
    difference: { color: '#e11d48', fillColor: '#e11d48', fillOpacity: 0.2, weight: 3, opacity: 1.0 },
    intersection: { color: '#4f46e5', fillColor: '#4f46e5', fillOpacity: 0.2, weight: 3, opacity: 1.0 },
    pending: { color: '#0ea5e9', fillColor: '#0ea5e9', fillOpacity: 0.2, weight: 3, opacity: 1.0 },
  };
  const highlighted = new Map();
  let sweepHandlersBound = false;

  function reset() {
    highlighted.forEach(function(original, layer) {
      if (!layer) return;
      if (layer.setStyle) {
        layer.setStyle(original.style);
      }
      if (typeof layer.setOpacity === 'function' && original.opacity != null) {
        layer.setOpacity(original.opacity);
      }
    });
    highlighted.clear();
  }

  function apply(groups) {
    reset();
    if (!Array.isArray(groups) || groups.length === 0) return;
    if (typeof layers === 'undefined' || !layers || !Array.isArray(layers.flags)) return;
    const labelToStyle = new Map();
    groups.forEach(function(group) {
      const op = (group && group.op) ? String(group.op) : 'pending';
      const style = styles[op] || styles.pending;
      const names = (group && Array.isArray(group.names)) ? group.names : [];
      names.forEach(function(name) {
        labelToStyle.set(String(name), style);
      });
    });
    if (labelToStyle.size === 0) return;

    layers.flags.forEach(function(groupLayer) {
      const label = groupLayer && groupLayer._flagData ? groupLayer._flagData.label : null;
      if (!label || !labelToStyle.has(String(label)) || !groupLayer.eachLayer) return;
      const style = labelToStyle.get(String(label));
      groupLayer.eachLayer(function(subLayer) {
        if (!subLayer || !subLayer.setStyle) return;
        if (!highlighted.has(subLayer)) {
          highlighted.set(subLayer, {
            style: {
              color: subLayer.options && subLayer.options.color,
              fillColor: subLayer.options && subLayer.options.fillColor,
              fillOpacity: subLayer.options && subLayer.options.fillOpacity,
              weight: subLayer.options && subLayer.options.weight,
              dashArray: subLayer.options && subLayer.options.dashArray,
            },
            opacity: (subLayer.options && subLayer.options.opacity) != null ? subLayer.options.opacity : null,
          });
        }
        subLayer.setStyle(style);
      });
    });
  }

  function bindSweepHandlers() {
    if (sweepHandlersBound) return;
    if (typeof layers === 'undefined' || !layers || !Array.isArray(layers.flags)) return;
    sweepHandlersBound = true;
    layers.flags.forEach(function(groupLayer) {
      const label = groupLayer && groupLayer._flagData ? String(groupLayer._flagData.label || '') : '';
      if (!label || !groupLayer || !groupLayer.eachLayer) return;
      groupLayer.eachLayer(function(subLayer) {
        if (!subLayer || !subLayer.on || subLayer.__xatraTerritorySweepBound) return;
        subLayer.__xatraTerritorySweepBound = true;
        subLayer.on('mousemove', function(e) {
          if (!window.parent) return;
          const originalEvent = (e && e.originalEvent) ? e.originalEvent : {};
          const isAddSweep = !!(originalEvent.ctrlKey || originalEvent.metaKey);
          const isRemoveSweep = !!originalEvent.altKey;
          if (!isAddSweep && !isRemoveSweep) return;
          window.parent.postMessage({
            type: 'mapFeaturePick',
            featureType: 'territory',
            name: label,
            hoverMode: isRemoveSweep ? 'remove' : 'add'
          }, '*');
        });
      });
    });
  }

  window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'setLabelSelectionOverlayFixed') {
      bindSweepHandlers();
      apply(event.data.groups || []);
    } else if (event.data && event.data.type === 'clearLabelSelectionOverlayFixed') {
      reset();
    }
  });

  window.setTimeout(bindSweepHandlers, 0);
  window.setTimeout(bindSweepHandlers, 400);
  window.setTimeout(bindSweepHandlers, 1200);
})();
</script>
`;
    if (html.includes('</body>')) return html.replace('</body>', `${patchScript}</body>`);
    return `${html}${patchScript}`;
  };

  const normalizedMapName = String(mapName || '').trim();
  const normalizedHubUsername = String(currentUser?.user?.username || 'new_user').trim().toLowerCase() || 'new_user';
  const viewedMapVersion = String(route?.version || 'alpha');
  const isMapAuthor = !!(currentUser.is_authenticated && normalizedHubUsername === mapOwner);
  const isReadOnlyMap = !!(route.owner && route.map) && (!isMapAuthor || viewedMapVersion !== 'alpha');

  useEffect(() => {
    try {
      localStorage.setItem('xatra-theme', isDarkMode ? 'dark' : 'light');
    } catch {
      // Ignore persistence errors (e.g., private mode restrictions)
    }
  }, [isDarkMode]);

  useEffect(() => {
    try {
      localStorage.setItem('xatra-map-name', mapName);
    } catch {
      // ignore
    }
  }, [mapName]);

  useEffect(() => {
    const handlePopState = () => setRoute(parsePath(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    const onDocMouseDown = (e) => {
      if (!menuOpen) return;
      const root = menuRef.current;
      if (root && !root.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, [menuOpen]);

  useEffect(() => {
    if (!importModalOpen) return;
    window.setTimeout(() => {
      importSearchRef.current?.focus();
      importSearchRef.current?.select?.();
    }, 0);
  }, [importModalOpen]);

  useEffect(() => {
    const v = String(route?.version || 'alpha');
    setMapVersionLabel(v);
    setSelectedLibraryVersion(v);
    setSelectedThemeVersion(v);
  }, [route?.owner, route?.map, route?.version]);

  const navigateTo = (path) => {
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
      setRoute(parsePath(path));
    }
  };

  const loadMe = async () => {
    try {
      const resp = await apiFetch('/auth/me');
      const data = await resp.json();
      if (resp.ok) {
        setCurrentUser(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthReady(true);
    }
  };

  useEffect(() => {
    loadMe();
  }, []);

  useEffect(() => {
    menuOpenRef.current = menuOpen;
  }, [menuOpen]);

  useEffect(() => {
    menuFocusIndexRef.current = menuFocusIndex;
  }, [menuFocusIndex]);

  useEffect(() => {
    const loadVersionLabels = async () => {
      const pairs = [
        ['map', setMapVersionLabel],
        ['lib', setLibraryVersionLabel],
        ['css', setThemeVersionLabel],
      ];
      for (const [kind, setter] of pairs) {
        try {
          const resp = await apiFetch(`/hub/${normalizedHubUsername}/${kind}/${normalizedMapName}`);
          if (!resp.ok) {
            setter('alpha');
            continue;
          }
          const data = await resp.json();
          setter(data.latest_published_version || 'alpha');
        } catch {
          setter('alpha');
        }
      }
    };
    if (normalizedHubUsername && HUB_NAME_RE.test(normalizedMapName)) {
      loadVersionLabels();
    }
  }, [normalizedHubUsername, normalizedMapName]);

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(String(text || ''));
    } catch {
      // ignore
    }
  };

  const executeMenuAction = (idx) => {
    const actions = [
      () => document.getElementById('xatra-load-input')?.click(),
      () => handleSaveProject(),
      () => handleExportHtml(),
      () => setIsDarkMode((prev) => !prev),
      () => window.open('/explore', '_blank'),
      () => window.open('/users', '_blank'),
      () => (currentUser.is_authenticated ? window.open(`/${normalizedHubUsername}`, '_blank') : navigateTo('/login')),
      () => window.open('/new-map', '_blank'),
      () => (currentUser.is_authenticated ? handleLogout() : navigateTo('/login')),
    ];
    if (actions[idx]) actions[idx]();
  };

  const computeFilterNot = () => (
    IMPORTABLE_LAYER_TYPES.filter((k) => !importLayerSelection[k])
  );

  const artifactKey = (username, kind, name) => `${username}:${kind}:${name}`;
  const buildImportPath = (entry, versionOverride = null) => {
    const v = String(versionOverride ?? entry.selected_version ?? 'alpha');
    return `/${entry.username}/${entry.kind}/${entry.name}/${v}`;
  };

  const serializeHubImports = (imports) => {
    const lines = [];
    (imports || []).forEach((imp) => {
      const filterNot = Array.isArray(imp.filter_not) ? imp.filter_not : [];
      const pathExpr = `"${buildImportPath(imp)}"`;
      if (imp.kind === 'lib') {
        const alias = (imp.alias || `${imp.name}_lib`).replace(/[^A-Za-z0-9_]/g, '_');
        lines.push(`${alias} = xatrahub(${pathExpr})`);
      } else if (filterNot.length) {
        lines.push(`xatrahub(${pathExpr}, filter_not=${JSON.stringify(filterNot)})`);
      } else {
        lines.push(`xatrahub(${pathExpr})`);
      }
    });
    return lines.join('\n') + (lines.length ? '\n' : '');
  };

  const parseImportsCodeToItems = (raw) => {
    const items = [];
    const lines = String(raw || '').split('\n');
    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.includes('xatrahub(')) return;
      const assignMatch = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*xatrahub\(\s*["']([^"']+)["']/);
      const callMatch = trimmed.match(/^xatrahub\(\s*["']([^"']+)["']/);
      const path = assignMatch?.[2] || callMatch?.[1];
      if (!path) return;
      const parts = path.split('/').filter(Boolean);
      if (parts.length < 3) return;
      const kind = parts[1];
      const selectedVersion = parts[3] || 'alpha';
      const filterNotMatch = trimmed.match(/filter_not\s*=\s*(\[[^\]]*\])/);
      let filterNot = [];
      if (filterNotMatch?.[1]) {
        try {
          const parsed = JSON.parse(filterNotMatch[1].replace(/'/g, '"'));
          if (Array.isArray(parsed)) filterNot = parsed.map((x) => String(x));
        } catch {
          filterNot = [];
        }
      }
      items.push({
        kind,
        username: parts[0],
        name: parts[2],
        path: `/${parts[0]}/${kind}/${parts[2]}/${selectedVersion}`,
        selected_version: selectedVersion,
        _draft_version: selectedVersion,
        alias: assignMatch?.[1] || '',
        filter_not: filterNot,
      });
    });
    return items;
  };

  const getImportVersionOptions = (imp) => (
    artifactVersionOptions[artifactKey(imp.username, imp.kind, imp.name)] || [{ value: 'alpha', label: 'alpha' }]
  );

  const buildHubMetadata = (kind) => ({
    kind,
    map_name: normalizedMapName,
    username: normalizedHubUsername,
    updated_from: activeTab,
  });

  const publishHubArtifact = async (kind, content, opts = {}) => {
    if (!HUB_NAME_RE.test(normalizedMapName)) {
      throw new Error('Map name must contain only lowercase letters, numerals, underscores, and dots.');
    }
    const owner = opts.owner || normalizedHubUsername;
    const targetName = opts.name || normalizedMapName;
    const response = await apiFetch(`/hub/${owner}/${kind}/${targetName}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        metadata: {
          ...buildHubMetadata(kind),
          forked_from: sourceMapRef,
          description: opts.description ?? mapDescription,
        },
      }),
    });
    const data = await response.json();
    if (!response.ok || data.detail || data.error) {
      throw new Error(data.detail || data.error || 'Failed to publish artifact');
    }
    const latest = data.latest_published_version;
    if (kind === 'map') setMapVersionLabel(latest || 'alpha');
    if (kind === 'lib') setLibraryVersionLabel(latest || 'alpha');
    if (kind === 'css') setThemeVersionLabel(latest || 'alpha');
    if (kind === 'map') {
      setMapOwner(owner);
      setMapName(targetName);
      setStatusNotice(data.no_changes ? 'No changes' : `Published v${latest}`);
      navigateTo(`/${owner}/map/${targetName}`);
      setTimeout(() => setStatusNotice(''), 1800);
    }
    return data;
  };

  const addHubImportLine = async (item) => {
    if (!item || !item.username || !item.name || !item.kind) return;
    const key = artifactKey(item.username, item.kind, item.name);
    const options = artifactVersionOptions[key] || [{ value: (item.latest_version ? String(item.latest_version) : 'alpha'), label: item.latest_version ? `v${item.latest_version}` : 'alpha' }];
    const selectedVersion = importVersionDraft[key] || (options[0]?.value || 'alpha');
    const path = `/${item.username}/${item.kind}/${item.name}/${selectedVersion}`;
    try {
      const verifyResp = await apiFetch(`/hub/${item.username}/${item.kind}/${item.name}`);
      if (!verifyResp.ok) {
        setError(`Cannot import ${item.kind}: /${item.username}/${item.kind}/${item.name} does not exist.`);
        return;
      }
    } catch (err) {
      setError(`Cannot import ${item.kind}: ${err.message}`);
      return;
    }
    const exists = (hubImports || []).some((imp) => imp.username === item.username && imp.kind === item.kind && imp.name === item.name);
    if (exists) return;
    const next = [
      ...(hubImports || []),
      {
        kind: item.kind,
        username: item.username,
        name: item.name,
        path,
        selected_version: selectedVersion,
        _draft_version: selectedVersion,
        alias: item.kind === 'lib' ? `${item.name}_lib`.replace(/[^a-zA-Z0-9_]/g, '_') : '',
        filter_not: item.kind === 'lib' ? [] : computeFilterNot(),
      },
    ];
    setHubImports(next);
    setImportsCode(serializeHubImports(next));
  };

  const searchHubRegistry = async () => {
    setImportLoading(true);
    setExploreQuery(hubQuery);
    try {
      await loadExplore(1, hubQuery);
    } finally {
      setImportLoading(false);
    }
  };

  const ensureArtifactVersions = async (username, name, kind) => {
    const key = artifactKey(username, kind, name);
    if (artifactVersionOptions[key]) return artifactVersionOptions[key];
    try {
      const resp = await apiFetch(`/hub/${username}/${kind}/${name}`);
      if (!resp.ok) {
        const fallback = [{ value: 'alpha', label: 'alpha' }];
        setArtifactVersionOptions((prev) => ({ ...prev, [key]: fallback }));
        return fallback;
      }
      const data = await resp.json();
      const published = Array.isArray(data.published_versions) ? data.published_versions.map((v) => String(v.version)) : [];
      published.sort((a, b) => Number(b) - Number(a));
      const options = [];
      if (published.length) {
        published.forEach((v) => options.push({ value: v, label: `v${v}` }));
      }
      options.push({ value: 'alpha', label: 'alpha' });
      setArtifactVersionOptions((prev) => ({ ...prev, [key]: options }));
      return options;
    } catch {
      const fallback = [{ value: 'alpha', label: 'alpha' }];
      setArtifactVersionOptions((prev) => ({ ...prev, [key]: fallback }));
      return fallback;
    }
  };

  useEffect(() => {
    (hubSearchResults || []).forEach((item) => {
      ensureArtifactVersions(item.username, item.name, 'map');
      ensureArtifactVersions(item.username, item.name, 'css');
      ensureArtifactVersions(item.username, item.name, 'lib');
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubSearchResults]);

  useEffect(() => {
    if (!mapOwner || !normalizedMapName || !HUB_NAME_RE.test(normalizedMapName)) return;
    ensureArtifactVersions(mapOwner, normalizedMapName, 'map');
    ensureArtifactVersions(mapOwner, normalizedMapName, 'css');
    ensureArtifactVersions(mapOwner, normalizedMapName, 'lib');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapOwner, normalizedMapName]);

  const loadMapFromHub = async (owner, name, version = 'alpha') => {
    try {
      const resp = await apiFetch(`/maps/${owner}/${name}?version=${encodeURIComponent(version || 'alpha')}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || 'Failed to load map');
      const content = typeof data.content === 'string' ? data.content : '';
      const parsed = (() => {
        try { return JSON.parse(content || '{}'); } catch { return null; }
      })();
      if (parsed && typeof parsed === 'object') {
        setImportsCode(parsed.imports_code || '');
        setHubImports(parseImportsCodeToItems(parsed.imports_code || ''));
        setThemeCode(parsed.theme_code || '');
        setPredefinedCode(parsed.predefined_code || predefinedCode);
        setCode(parsed.map_code || code);
        setRuntimeCode(parsed.runtime_code || '');
        if (parsed.project && parsed.project.elements && parsed.project.options) {
          setBuilderElements(parsed.project.elements);
          setBuilderOptions(parsed.project.options);
        }
      }
      setMapName(name);
      setMapOwner(owner);
      setSourceMapRef(`/${owner}/map/${name}`);
      const viewResp = await apiFetch(`/maps/${owner}/${name}/view`, { method: 'POST' });
      const viewData = await viewResp.json();
      if (viewResp.ok) setMapViews(Number(viewData.views || 0));
      const artifactResp = await apiFetch(`/hub/${owner}/map/${name}`);
      const artifactData = await artifactResp.json();
      if (artifactResp.ok) {
        setMapVotes(Number(artifactData.votes || 0));
        setMapViews(Number(artifactData.views || 0));
        setMapVersionLabel(version === 'alpha' ? 'alpha' : String(version));
        setMapDescription(String(artifactData?.alpha?.metadata?.description || ''));
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const loadDraft = async () => {
    try {
      const resp = await apiFetch('/draft/current');
      const data = await resp.json();
      if (!resp.ok || !data.exists || !data.draft) return;
      const draft = data.draft;
      if (draft.map_name && HUB_NAME_RE.test(draft.map_name)) setMapName(draft.map_name);
      if (draft.project?.elements && draft.project?.options) {
        setBuilderElements(draft.project.elements);
        setBuilderOptions(draft.project.options);
      }
      if (typeof draft.project?.code === 'string') setCode(draft.project.code);
      if (typeof draft.project?.predefinedCode === 'string') setPredefinedCode(draft.project.predefinedCode);
      if (typeof draft.project?.importsCode === 'string') {
        setImportsCode(draft.project.importsCode);
        setHubImports(parseImportsCodeToItems(draft.project.importsCode));
      }
      if (typeof draft.project?.themeCode === 'string') setThemeCode(draft.project.themeCode);
      if (typeof draft.project?.runtimeCode === 'string') setRuntimeCode(draft.project.runtimeCode);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      apiFetch('/draft/current', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          map_name: normalizedMapName || 'new_map',
          project: {
            elements: builderElements,
            options: builderOptions,
            code,
            predefinedCode,
            importsCode,
            themeCode,
            runtimeCode,
          },
        }),
      }).catch(() => {});
    }, 800);
    return () => clearTimeout(t);
  }, [normalizedMapName, builderElements, builderOptions, code, predefinedCode, importsCode, themeCode, runtimeCode]);

  const loadExplore = async (page = 1, query = exploreQuery) => {
    setExploreLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '12', q: query || '' });
      const resp = await apiFetch(`/explore?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load explore');
      setExploreData(data);
      setHubSearchResults(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      setError(err.message);
    } finally {
      setExploreLoading(false);
    }
  };

  const loadProfile = async (username, page = 1, query = profileSearch) => {
    if (!username) return;
    setProfileLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '10', q: query || '' });
      const resp = await apiFetch(`/users/${username}?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load profile');
      setProfileData(data);
      setProfileEdit({ full_name: data?.profile?.full_name || '', bio: data?.profile?.bio || '' });
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileLoading(false);
    }
  };

  const loadUsers = async (page = 1, query = usersQuery) => {
    setUsersLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '20', q: query || '' });
      const resp = await apiFetch(`/users?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load users');
      setUsersData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setUsersLoading(false);
    }
  };

  const switchHubImportVersion = (idx, version, applyNow = false) => {
    const next = [...(hubImports || [])];
    if (!next[idx]) return;
    if (!applyNow) {
      next[idx] = { ...next[idx], _draft_version: version };
      setHubImports(next);
      return;
    }
    const selected = version || next[idx]._draft_version || next[idx].selected_version || 'alpha';
    next[idx] = {
      ...next[idx],
      selected_version: selected,
      path: buildImportPath(next[idx], selected),
      _draft_version: selected,
    };
    setHubImports(next);
    setImportsCode(serializeHubImports(next));
  };

  useEffect(() => {
    if (route.page === 'explore') loadExplore(explorePage, exploreQuery);
    if (route.page === 'users') loadUsers(usersPage, usersQuery);
    if (route.page === 'profile') loadProfile(route.username, profilePage, profileSearch);
    if (route.page === 'editor' && route.owner && route.map) {
      setMapOwner(route.owner);
      loadMapFromHub(route.owner, route.map, route.version || 'alpha');
    }
    if (route.page === 'editor' && !route.owner) {
      if (route.newMap) {
        setMapName('new_map');
        setBuilderElements([{ type: 'flag', label: 'India', value: [], args: { note: 'Republic of India' } }]);
        setBuilderOptions({
          basemaps: [{ url_or_provider: 'Esri.WorldTopoMap', default: true }],
          flag_color_sequences: [{ class_name: '', colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
          admin_color_sequences: [{ colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
          data_colormap: { type: 'LinearSegmented', colors: 'yellow,orange,red' },
        });
        setCode('');
        setThemeCode('');
        setRuntimeCode('');
        setPredefinedCode('');
        setHubImports([]);
        setImportsCode('indic = xatrahub("/srajma/lib/indic")\n');
      } else {
        loadDraft();
      }
      apiFetch('/maps/default-name').then((r) => r.json()).then((d) => {
        if (d?.name && HUB_NAME_RE.test(d.name)) setMapName((prev) => (prev && prev !== 'new_map' ? prev : d.name));
      }).catch(() => {});
      setMapOwner(normalizedHubUsername);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.page, route.owner, route.map, route.version]);

  const handleLogin = async (mode = authMode) => {
    setAuthSubmitting(true);
    try {
      const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/login';
      const payload = mode === 'signup'
        ? { username: authForm.username, password: authForm.password, full_name: authForm.full_name }
        : { username: authForm.username, password: authForm.password };
      const resp = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || 'Authentication failed');
      await loadMe();
      navigateTo('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' });
      await loadMe();
      navigateTo('/');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleVoteMap = async () => {
    if (!route.owner || !route.map) return;
    try {
      const resp = await apiFetch(`/maps/${route.owner}/${route.map}/vote`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Vote failed');
      setMapVotes(Number(data.votes || 0));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSaveProfile = async () => {
    try {
      const resp = await apiFetch('/auth/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileEdit),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to save profile');
      await loadMe();
      if (route.page === 'profile' && route.username) loadProfile(route.username, profilePage, profileSearch);
      setStatusNotice('Profile saved');
      setTimeout(() => setStatusNotice(''), 1500);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleChangePassword = async () => {
    try {
      const resp = await apiFetch('/auth/me/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passwordEdit),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to update password');
      setPasswordEdit({ current_password: '', new_password: '' });
      setStatusNotice('Password updated');
      setTimeout(() => setStatusNotice(''), 1500);
    } catch (err) {
      setError(err.message);
    }
  };

  const updateDraft = (points, shapeType) => {
      const ref = activePreviewTab === 'picker'
        ? pickerIframeRef
        : (activePreviewTab === 'library' ? territoryLibraryIframeRef : iframeRef);
      if (ref.current && ref.current.contentWindow) {
          ref.current.contentWindow.postMessage({ type: 'setDraft', points, shapeType }, '*');
      }
  };

  useEffect(() => {
      const isDraftPicker = !!(activePicker && (activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context)));
      if (isDraftPicker) {
          updateDraft(draftPoints, activePicker.type);
      } else {
          updateDraft([], null);
      }
  }, [draftPoints, activePicker, activePreviewTab, pickerHtml, territoryLibraryHtml]);

  useEffect(() => {
    const handleKeyDown = (e) => {
        if (!activePicker) return;
        if (isEditableTarget(e.target)) return;
        const isDraftPicker = activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context);
        if (!isDraftPicker) return;
        if (e.key === 'Control' || e.key === 'Meta') {
            setFreehandModifierPressed(true);
            return;
        }
        if (e.key === 'Backspace') {
            e.preventDefault();
            setDraftPoints(prev => {
                const newPoints = prev.slice(0, -1);
                updateElementFromDraft(newPoints);
                return newPoints;
            });
        } else if (e.key === 'Escape') {
            setActivePicker(null);
            setDraftPoints([]);
            setFreehandModifierPressed(false);
        }
    };
    const handleKeyUp = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') setFreehandModifierPressed(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
        window.removeEventListener('keydown', handleKeyDown);
        window.removeEventListener('keyup', handleKeyUp);
    };
  }, [activePicker]);

  const updateElementFromDraft = (points) => {
      if (!activePicker) return;
      if (activePicker.context === 'layer') {
          const idx = activePicker.id;
          const newElements = [...builderElements];
          newElements[idx].value = JSON.stringify(points);
          setBuilderElements(newElements);
      } else if (isTerritoryPolygonPicker(activePicker.context)) {
          const parentId = parseInt(activePicker.context.replace('territory-', ''), 10);
          if (Number.isNaN(parentId)) return;
          const el = builderElements[parentId];
          if (!el || el.type !== 'flag' || !Array.isArray(el.value)) return;
          const path = Array.isArray(activePicker.target?.partPath)
            ? activePicker.target.partPath
            : (Number.isInteger(activePicker.id) ? [activePicker.id] : []);
          if (!path.length) return;
          const setPartAtPath = (parts, partPath, depth = 0) => {
            const idx = partPath[depth];
            if (!Array.isArray(parts) || idx == null || idx < 0 || idx >= parts.length) return parts;
            const next = [...parts];
            const part = next[idx];
            if (!part || typeof part !== 'object') return parts;
            if (depth === partPath.length - 1) {
              if (part.type !== 'polygon') return parts;
              next[idx] = { ...part, value: JSON.stringify(points) };
              return next;
            }
            if (part.type !== 'group' || !Array.isArray(part.value)) return parts;
            next[idx] = { ...part, value: setPartAtPath(part.value, partPath, depth + 1) };
            return next;
          };
          const newElements = [...builderElements];
          newElements[parentId] = { ...el, value: setPartAtPath(el.value, path) };
          setBuilderElements(newElements);
      }
  };

  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data && event.data.type === 'mapViewUpdate') {
        const targetSet = activePreviewTab === 'picker' ? null : setBuilderOptions;
        if (targetSet) {
            targetSet(prev => ({
                ...prev,
                focus: [
                    parseFloat(event.data.center[0].toFixed(4)), 
                    parseFloat(event.data.center[1].toFixed(4))
                ],
                zoom: event.data.zoom
            }));
        }
      } else if (event.data && event.data.type === 'mapClick') {
          setLastMapClick({ lat: event.data.lat, lng: event.data.lng, ts: Date.now() });
      } else if (event.data && event.data.type === 'mapMouseDown') {
          setIsMouseDown(true);
          if (event.data.ctrlKey || event.data.metaKey) setFreehandModifierPressed(true);
      } else if (event.data && event.data.type === 'mapMouseUp') {
          setIsMouseDown(false);
          if (!event.data.ctrlKey && !event.data.metaKey) setFreehandModifierPressed(false);
      } else if (event.data && event.data.type === 'mapMouseMove') {
          const modifierPressed = !!(event.data.ctrlKey || event.data.metaKey || freehandModifierPressed);
          if (modifierPressed !== freehandModifierPressed) setFreehandModifierPressed(modifierPressed);
          if (activePicker && modifierPressed && isMouseDown && (activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context))) {
              const point = [parseFloat(event.data.lat.toFixed(4)), parseFloat(event.data.lng.toFixed(4))];
              setDraftPoints(prev => {
                  const last = prev[prev.length - 1];
                  if (last && Math.abs(last[0] - point[0]) < 0.0001 && Math.abs(last[1] - point[1]) < 0.0001) return prev;
                  const newPoints = [...prev, point];
                  updateElementFromDraft(newPoints);
                  return newPoints;
              });
          }
      } else if (event.data && event.data.type === 'mapKeyDown') {
          // Keys forwarded from map iframe (when user clicked map, focus is in iframe)
          const key = event.data.key;
          if (!activePicker) return;
          const isDraftPicker = activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context);
          if (key === 'Backspace' && isDraftPicker) {
            setDraftPoints(prev => {
              const newPoints = prev.slice(0, -1);
              updateElementFromDraft(newPoints);
              return newPoints;
            });
          } else if (key === 'Escape') {
            setActivePicker(null);
            setDraftPoints([]);
            setFreehandModifierPressed(false);
          } else if (key === 'Control' || key === 'Meta') {
            setFreehandModifierPressed(true);
          }
      } else if (event.data && event.data.type === 'mapKeyUp') {
          if (event.data.key === 'Control' || event.data.key === 'Meta') setFreehandModifierPressed(false);
      } else if (event.data && event.data.type === 'mapShortcut') {
          if (event.data.shortcut === 'updatePickerMap') {
            if (activePreviewTab === 'picker') {
              renderPickerMap();
            } else if (activePreviewTab === 'library') {
              renderTerritoryLibrary(activeLibraryConfig?.source || territoryLibrarySource, { hubPath: activeLibraryConfig?.hub_path || null });
            }
          }
      } else if (event.data && event.data.type === 'mapFeaturePick') {
          const data = event.data || {};
          if (data.featureType === 'gadm' && data.gid && activePicker?.context === 'reference-gadm') {
              const gid = String(data.gid);
              if (data.hoverMode === 'add' || data.hoverMode === 'remove') {
                const sig = `${data.hoverMode}:${gid}`;
                if (hoverPickRef.current === sig) return;
                hoverPickRef.current = sig;
                setPickedGadmSelection((prev) => {
                  const exists = prev.some((x) => x.gid === gid);
                  let next;
                  if (data.hoverMode === 'add') {
                    next = exists ? prev : [...prev, { gid, name: data.name || '' }];
                  } else {
                    next = exists ? prev.filter((x) => x.gid !== gid) : prev;
                  }
                  setPickerTargetValues(referencePickTarget, next.map((x) => x.gid));
                  return next;
                });
              } else {
                hoverPickRef.current = '';
                setPickedGadmSelection((prev) => {
                  const exists = prev.some((x) => x.gid === gid);
                  const next = exists ? prev.filter((x) => x.gid !== gid) : [...prev, { gid, name: data.name || '' }];
                  setPickerTargetValues(referencePickTarget, next.map((x) => x.gid));
                  return next;
                });
              }
          } else if (data.featureType === 'river' && data.id && activePicker?.context === 'reference-river' && referencePickTarget?.kind === 'river') {
              const idx = referencePickTarget.layerIndex;
              if (idx != null) {
                setBuilderElements((prev) => {
                  const next = [...prev];
                  const el = next[idx];
                  if (!el || el.type !== 'river') return prev;
                  next[idx] = {
                    ...el,
                    value: String(data.id),
                    args: { ...(el.args || {}), source_type: data.source_type || 'naturalearth' }
                  };
                  return next;
                });
              }
              setActivePicker(null);
              setReferencePickTarget(null);
              setActivePreviewTab('main');
          } else if (data.featureType === 'territory' && data.name && activePicker?.context === 'territory-library' && referencePickTarget?.kind === 'territory') {
              const name = String(data.name);
              if (data.hoverMode === 'add' || data.hoverMode === 'remove') {
                const sig = `${data.hoverMode}:territory:${name}`;
                if (hoverPickRef.current === sig) return;
                hoverPickRef.current = sig;
                setPickedTerritorySelection((prev) => {
                  const exists = prev.includes(name);
                  let next;
                  if (data.hoverMode === 'add') {
                    next = exists ? prev : [...prev, name];
                  } else {
                    next = exists ? prev.filter((x) => x !== name) : prev;
                  }
                  setPickerTargetValues(referencePickTarget, next);
                  return next;
                });
              } else {
                hoverPickRef.current = '';
                setPickedTerritorySelection((prev) => {
                  const exists = prev.includes(name);
                  const next = exists ? prev.filter((x) => x !== name) : [...prev, name];
                  setPickerTargetValues(referencePickTarget, next);
                  return next;
                });
              }
          }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [activePreviewTab, activePicker, freehandModifierPressed, isMouseDown, referencePickTarget, builderElements]);

  useEffect(() => {
    const uniqueCountries = Array.from(
      new Set(
        (pickerOptions.entries || [])
          .map((entry) => String(entry.country || '').trim().toUpperCase().split('.')[0])
          .filter(Boolean)
      )
    );
    if (uniqueCountries.length === 0) {
      setCountryLevelOptions({});
      return;
    }
    Promise.all(
      uniqueCountries.map(async (country) => {
        try {
          const res = await fetch(`http://localhost:8088/gadm/levels?country=${encodeURIComponent(country)}`);
          const levels = await res.json();
          return [country, Array.isArray(levels) && levels.length ? levels : [0, 1, 2, 3, 4]];
        } catch {
          return [country, [0, 1, 2, 3, 4]];
        }
      })
    ).then((pairs) => {
      const next = {};
      pairs.forEach(([country, levels]) => {
        next[country] = levels;
      });
      setCountryLevelOptions(next);
    });
  }, [pickerOptions.entries]);

  useEffect(() => {
    const ref = pickerIframeRef.current;
    if (!ref || !ref.contentWindow) return;
    const groups = [
      ...(pickedGadmSelection.length ? [{ op: 'pending', gids: pickedGadmSelection.map((x) => x.gid) }] : []),
    ];
    ref.contentWindow.postMessage({ type: 'setSelectionOverlay', groups }, '*');
  }, [pickedGadmSelection, pickerHtml]);

  useEffect(() => {
    const ref = territoryLibraryIframeRef.current;
    if (!ref || !ref.contentWindow) return;
    const groups = [
      ...(pickedTerritorySelection.length ? [{ op: 'pending', names: pickedTerritorySelection }] : []),
    ];
    ref.contentWindow.postMessage({ type: 'setLabelSelectionOverlayFixed', groups }, '*');
  }, [pickedTerritorySelection, territoryLibraryHtml]);

  const handleStartReferencePick = (target) => {
    if (!target || !target.kind) return;
    setReferencePickTarget(target);
    setPickedGadmSelection([]);
    setPickedTerritorySelection([]);
    hoverPickRef.current = '';
    setDraftPoints([]);
    const isTerritoryPick = target.kind === 'territory';
    setActivePicker({
      id: target.layerIndex ?? target.flagIndex ?? 0,
      type: target.kind,
      context: isTerritoryPick ? 'territory-library' : (target.kind === 'river' ? 'reference-river' : 'reference-gadm'),
      target,
    });
    setActivePreviewTab(isTerritoryPick ? 'library' : 'picker');
    if (isTerritoryPick && !territoryLibraryHtml) {
      renderTerritoryLibrary(activeLibraryConfig?.source || territoryLibrarySource, { hubPath: activeLibraryConfig?.hub_path || null });
    }
    if (target.kind === 'gadm') {
      const initial = getCurrentPickerValues(target);
      setPickedGadmSelection(initial.map((gid) => ({ gid, name: '' })));
    } else if (target.kind === 'territory') {
      setPickedTerritorySelection(getCurrentPickerValues(target));
    }
  };

  const normalizePickerValues = (values) => (
    Array.from(new Set((values || []).map((v) => String(v || '').trim()).filter(Boolean)))
  );

  const normalizeFlagPartsForPicker = (rawValue) => {
    if (Array.isArray(rawValue)) return [...rawValue];
    if (!rawValue) return [];
    return [{ op: 'union', type: 'gadm', value: rawValue }];
  };

  const readPartAtPath = (parts, path, depth = 0) => {
    if (!Array.isArray(parts) || !Array.isArray(path) || path.length === 0) return null;
    const idx = path[depth];
    if (!Number.isInteger(idx) || idx < 0 || idx >= parts.length) return null;
    const part = parts[idx];
    if (!part || typeof part !== 'object') return null;
    if (depth === path.length - 1) return part;
    if (part.type !== 'group' || !Array.isArray(part.value)) return null;
    return readPartAtPath(part.value, path, depth + 1);
  };

  const setPartAtPath = (parts, path, updatePart, depth = 0) => {
    if (!Array.isArray(parts) || !Array.isArray(path) || path.length === 0) return null;
    const idx = path[depth];
    if (!Number.isInteger(idx) || idx < 0 || idx >= parts.length) return null;
    const nextParts = [...parts];
    const part = nextParts[idx];
    if (!part || typeof part !== 'object') return null;
    if (depth === path.length - 1) {
      const updated = updatePart(part);
      if (!updated) return null;
      nextParts[idx] = updated;
      return nextParts;
    }
    if (part.type !== 'group' || !Array.isArray(part.value)) return null;
    const nested = setPartAtPath(part.value, path, updatePart, depth + 1);
    if (!nested) return null;
    nextParts[idx] = { ...part, value: nested };
    return nextParts;
  };

  const getCurrentPickerValues = (target) => {
    if (!target || (target.kind !== 'gadm' && target.kind !== 'territory')) return [];
    const flagIndex = target.flagIndex;
    if (!Number.isInteger(flagIndex)) return [];
    const flag = builderElements[flagIndex];
    if (!flag || flag.type !== 'flag') return [];
    const parts = normalizeFlagPartsForPicker(flag.value);
    const path = Array.isArray(target.partPath)
      ? target.partPath
      : (Number.isInteger(target.partIndex) ? [target.partIndex] : []);
    const part = readPartAtPath(parts, path);
    if (!part) return [];
    const expectedType = target.kind === 'gadm' ? 'gadm' : 'predefined';
    if (part.type !== expectedType) return [];
    return normalizePickerValues(Array.isArray(part.value) ? part.value : [part.value]);
  };

  const setPickerTargetValues = (target, rawValues) => {
    if (!target || (target.kind !== 'gadm' && target.kind !== 'territory')) return;
    const targetType = target.kind === 'gadm' ? 'gadm' : 'predefined';
    const values = normalizePickerValues(rawValues);
    setBuilderElements((prev) => {
      const next = [...prev];
      const flagIndex = target.flagIndex;
      if (!Number.isInteger(flagIndex)) return prev;
      const flag = next[flagIndex];
      if (!flag || flag.type !== 'flag') return prev;
      const parts = normalizeFlagPartsForPicker(flag.value);
      const path = Array.isArray(target.partPath)
        ? target.partPath
        : (Number.isInteger(target.partIndex) ? [target.partIndex] : []);
      const nextValue = values.length <= 1 ? (values[0] || '') : values;
      const patched = setPartAtPath(parts, path, (part) => {
        if (part.type !== targetType) return null;
        return { ...part, value: nextValue };
      });
      if (patched) {
        next[flagIndex] = { ...flag, value: patched };
        return next;
      }
      return prev;
    });
  };

  const clearReferenceSelection = () => {
    setPickedGadmSelection([]);
    setPickedTerritorySelection([]);
    hoverPickRef.current = '';
  };

  const toggleTerritoryName = (name) => {
    setSelectedTerritoryNames((prev) => (
      prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]
    ));
  };

  const copySelectedTerritoryIndex = async () => {
    const payload = `__TERRITORY_INDEX__ = ${JSON.stringify(selectedTerritoryNames)}`;
    try {
      await navigator.clipboard.writeText(payload);
      setCopyIndexCopied(true);
      window.setTimeout(() => setCopyIndexCopied(false), 1400);
    } catch (err) {
      setError(`Failed to copy index list: ${err.message}`);
    }
  };

  useEffect(() => {
    if (!activePicker) {
      setReferencePickTarget(null);
      clearReferenceSelection();
      setFreehandModifierPressed(false);
    }
  }, [activePicker]);

  useEffect(() => {
    const onKeyDown = (e) => {
      const editableTarget = isEditableTarget(e.target);
      const lowerKey = String(e.key || '').toLowerCase();
      const isMeta = e.ctrlKey || e.metaKey;
      const allowInputShortcut = (
        (activeTab === 'builder' && isMeta && e.code === 'Space')
        || (isMeta && e.key === ';')
        || (isMeta && e.shiftKey && lowerKey === 'x')
      );
      if (editableTarget && !allowInputShortcut) return;
      if (menuOpenRef.current && ['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(e.key)) {
        e.preventDefault();
        const total = 9;
        if (e.key === 'ArrowDown') setMenuFocusIndex((i) => (i + 1) % total);
        if (e.key === 'ArrowUp') setMenuFocusIndex((i) => (i - 1 + total) % total);
        if (e.key === 'Enter') executeMenuAction(menuFocusIndexRef.current);
        if (e.key === 'Escape') {
          setMenuOpen(false);
          setMenuFocusIndex(0);
        }
        return;
      }
      if (mapDescriptionModalOpen) {
        if (e.key === 'Escape') {
          e.preventDefault();
          setMapDescriptionModalOpen(false);
          setPendingMapPublish(null);
          return;
        }
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          confirmMapPublish();
          return;
        }
      }
      if (e.key === 'Escape' && importModalOpen) {
        e.preventDefault();
        setImportModalOpen(false);
        return;
      }
      if (e.key === 'Escape' && activePicker?.context === 'reference-gadm' && referencePickTarget?.kind === 'gadm') {
        e.preventDefault();
        setActivePicker(null);
      } else if (e.key === 'Escape' && activePicker?.context === 'territory-library' && referencePickTarget?.kind === 'territory') {
        e.preventDefault();
        setActivePicker(null);
      } else if (e.key === '?') {
        e.preventDefault();
        setShowShortcutHelp((prev) => !prev);
      } else if (isMeta && e.key === '1') {
        e.preventDefault();
        handleTabChange('builder');
      } else if (isMeta && e.key === '2') {
        e.preventDefault();
        handleTabChange('code');
      } else if (isMeta && e.shiftKey && e.key === 'Enter') {
        e.preventDefault();
        handleStop(activePreviewTab);
      } else if (isMeta && e.key === 'Enter') {
        e.preventDefault();
        renderMap();
      } else if (isMeta && e.key === '3') {
        e.preventDefault();
        setActivePreviewTab('main');
      } else if (isMeta && e.key === '4') {
        e.preventDefault();
        setActivePreviewTab('picker');
      } else if (isMeta && e.key === '5') {
        e.preventDefault();
        setActivePreviewTab('library');
      } else if (isMeta && e.key === ';') {
        e.preventDefault();
        setMenuOpen((prev) => {
          const next = !prev;
          if (next) setMenuFocusIndex(0);
          return next;
        });
      } else if (isMeta && e.shiftKey && lowerKey === 'x') {
        e.preventDefault();
        setImportModalOpen((prev) => {
          const next = !prev;
          if (next) searchHubRegistry();
          return next;
        });
      } else if (isMeta && e.code === 'Space') {
        e.preventDefault();
        if (activePreviewTab === 'picker') {
          renderPickerMap();
        } else if (activePreviewTab === 'library') {
          renderTerritoryLibrary(activeLibraryConfig?.source || territoryLibrarySource, { hubPath: activeLibraryConfig?.hub_path || null });
        }
      } else if (activeTab === 'builder' && isMeta && e.shiftKey) {
        const layerByKey = {
          f: 'flag',
          r: 'river',
          p: 'point',
          t: 'text',
          h: 'path',
          a: 'admin',
          d: 'dataframe',
          b: 'titlebox',
          y: 'python',
        };
        const layerType = layerByKey[lowerKey];
        if (layerType) {
          e.preventDefault();
          setAddLayerSignal({ type: layerType, nonce: Date.now() });
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeTab, code, predefinedCode, builderElements, builderOptions, activePreviewTab, territoryLibrarySource, activePicker, referencePickTarget, mapDescriptionModalOpen, pendingMapPublish, mapDescriptionDraft]);

  const handleGetCurrentView = () => {
    const ref = activePreviewTab === 'picker' ? pickerIframeRef : activePreviewTab === 'library' ? territoryLibraryIframeRef : iframeRef;
    if (ref.current && ref.current.contentWindow) {
      ref.current.contentWindow.postMessage('getCurrentView', '*');
    }
  };

  const renderPickerMap = async ({ showLoading = true } = {}) => {
      if (showLoading) setLoadingByView((prev) => ({ ...prev, picker: true }));
      try {
          const payload = {
            ...pickerOptions,
            basemaps: builderOptions.basemaps || [],
          };
          const response = await fetch(`http://localhost:8088/render/picker`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
          });
          const data = await response.json();
          if (data.html) setPickerHtml(data.html);
      } catch (err) {
          setError(err.message);
      } finally {
          if (showLoading) setLoadingByView((prev) => ({ ...prev, picker: false }));
      }
  };

  const loadTerritoryLibraryCatalog = async (source = territoryLibrarySource, hubPath = null) => {
    try {
      const response = await apiFetch('/territory_library/catalog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source,
          predefined_code: predefinedCode || '',
          hub_path: hubPath || undefined,
        }),
      });
          const data = await response.json();
          if (!response.ok || data.error) {
              throw new Error(data.error || 'Failed to load territory catalog');
          }
          const names = Array.isArray(data.names) ? data.names : [];
          const indexNames = Array.isArray(data.index_names) ? data.index_names : [];
          setTerritoryLibraryNames(names);
          setSelectedTerritoryNames((prev) => {
            if (prev.length && prev.some((name) => names.includes(name))) {
              return prev.filter((name) => names.includes(name));
            }
            return indexNames.filter((name) => names.includes(name));
          });
      } catch (err) {
          setError(err.message);
      }
  };

  const renderTerritoryLibrary = async (
    source = territoryLibrarySource,
    { useDefaultSelection = false, showLoading = true, hubPath = null } = {}
  ) => {
      if (showLoading) setLoadingByView((prev) => ({ ...prev, library: true }));
      try {
          const body = {
            source,
            predefined_code: predefinedCode || '',
            basemaps: builderOptions.basemaps || [],
            hub_path: hubPath || undefined,
          };
          if (!useDefaultSelection) {
            body.selected_names = selectedTerritoryNames;
          }
          const response = await apiFetch('/render/territory-library', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
          });
          const data = await response.json();
          if (data.error) {
              setError(data.error);
          } else if (data.html) {
              setTerritoryLibraryHtml(injectTerritoryLabelOverlayPatch(data.html));
              const names = Array.isArray(data.available_names) ? data.available_names : [];
              if (names.length) setTerritoryLibraryNames(names);
          }
      } catch (err) {
          setError(err.message);
      } finally {
          if (showLoading) setLoadingByView((prev) => ({ ...prev, library: false }));
      }
  };

  const renderMap = async () => {
    const taskType = activeTab === 'code' ? 'code' : 'builder';
    setActivePreviewTab('main');
    setMainRenderTask(taskType);
    setLoadingByView((prev) => ({ ...prev, main: true }));
    setError(null);
    try {
      const endpoint = activeTab === 'code' ? '/render/code' : '/render/builder';
      const body = activeTab === 'code' 
        ? {
            code,
            predefined_code: predefinedCode || undefined,
            imports_code: importsCode || undefined,
            theme_code: themeCode || undefined,
            runtime_code: runtimeCode || undefined,
          }
        : {
            elements: builderElements,
            options: builderOptions,
            predefined_code: predefinedCode || undefined,
            imports_code: importsCode || undefined,
            theme_code: themeCode || undefined,
            runtime_code: runtimeCode || undefined,
          };

      const response = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        console.error(data.traceback);
      } else {
        setMapHtml(data.html);
        setMapPayload(data.payload);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingByView((prev) => ({ ...prev, main: false }));
      setMainRenderTask(null);
    }
  };

  const downloadFile = (content, filename, contentType) => {
    const a = document.createElement("a");
    const file = new Blob([content], {type: contentType});
    a.href = URL.createObjectURL(file);
    a.download = filename;
    a.click();
  };

  const handleExportHtml = () => {
    if (mapHtml) downloadFile(mapHtml, "map.html", "text/html");
  };

  const handleExportJson = () => {
    if (mapPayload) downloadFile(JSON.stringify(mapPayload, null, 2), "map.json", "application/json");
  };

  const handleSaveProject = async () => {
    if (activeTab === 'code') {
      try {
        const parsed = await parseCodeToBuilder();
        const project = {
          elements: Array.isArray(parsed.elements) ? parsed.elements : [],
          options: parsed.options && typeof parsed.options === 'object' ? parsed.options : { basemaps: [] },
          predefinedCode: typeof parsed.predefined_code === 'string' ? parsed.predefined_code : (predefinedCode || ''),
          importsCode,
          themeCode,
          runtimeCode,
        };
        downloadFile(JSON.stringify(project, null, 2), "project.json", "application/json");
      } catch (err) {
        setError(`Save Project failed: ${err.message}`);
      }
      return;
    }
    const project = { elements: builderElements, options: builderOptions, predefinedCode, importsCode, themeCode, runtimeCode };
    downloadFile(JSON.stringify(project, null, 2), "project.json", "application/json");
  };

  const buildMapArtifactContent = async () => {
    let mapCodeText = code;
    let projectPayload = { elements: builderElements, options: builderOptions, predefinedCode, importsCode, themeCode, runtimeCode };
    if (activeTab === 'builder') {
      mapCodeText = generatePythonCode() || '';
    } else {
      try {
        const parsed = await parseCodeToBuilder();
        projectPayload = {
          elements: Array.isArray(parsed.elements) ? parsed.elements : [],
          options: parsed.options && typeof parsed.options === 'object' ? parsed.options : { basemaps: [] },
          predefinedCode: typeof parsed.predefined_code === 'string' ? parsed.predefined_code : (predefinedCode || ''),
          importsCode,
          themeCode,
          runtimeCode,
        };
      } catch {
        // Keep current in-memory payload if parsing fails
      }
    }
    return JSON.stringify({
      imports_code: importsCode || '',
      theme_code: themeCode || '',
      predefined_code: predefinedCode || '',
      map_code: mapCodeText || '',
      runtime_code: runtimeCode || '',
      project: projectPayload,
    });
  };

  const handlePublishMap = async () => {
    try {
      if (!currentUser.is_authenticated) {
        setStatusNotice('Login required');
        setTimeout(() => setStatusNotice(''), 1800);
        return;
      }
      if (isReadOnlyMap) {
        setError('Read-only view. Fork this map to edit.');
        return;
      }
      let targetName = normalizedMapName;
      const check = await apiFetch(`/hub/${normalizedHubUsername}/map/${targetName}`);
      const exists = check.ok;
      const isSameCurrent = !!(route.owner === normalizedHubUsername && route.map === targetName);
      if (exists && !isSameCurrent) {
        setError(`Map name '${targetName}' already exists in your account. Choose a different name.`);
        return;
      }
      const content = await buildMapArtifactContent();
      setPendingMapPublish({ targetName, content });
      setMapDescriptionDraft(mapDescription || '');
      setMapDescriptionModalOpen(true);
    } catch (err) {
      setError(`Publish map failed: ${err.message}`);
    }
  };

  const confirmMapPublish = async () => {
    if (!pendingMapPublish) return;
    try {
      await publishHubArtifact('map', pendingMapPublish.content, {
        owner: normalizedHubUsername,
        name: pendingMapPublish.targetName,
        description: mapDescriptionDraft,
      });
      setMapDescription(mapDescriptionDraft);
      setMapDescriptionModalOpen(false);
      setPendingMapPublish(null);
    } catch (err) {
      setError(`Publish map failed: ${err.message}`);
    }
  };

  const handleForkMap = async () => {
    if (!currentUser.is_authenticated) {
      navigateTo('/login');
      return;
    }
    try {
      const base = normalizedMapName || 'new_map';
      const resp = await apiFetch(`/maps/resolve-name?base=${encodeURIComponent(base)}`);
      const data = await resp.json();
      if (!resp.ok || !data?.name) throw new Error(data?.detail || 'Failed to resolve fork name');
      const content = await buildMapArtifactContent();
      await publishHubArtifact('map', content, {
        owner: normalizedHubUsername,
        name: data.name,
        description: mapDescription,
      });
    } catch (err) {
      setError(`Fork failed: ${err.message}`);
    }
  };

  const handleMapVersionSelect = (version) => {
    if (!route.owner || !route.map) return;
    setMapVersionLabel(String(version || 'alpha'));
    const next = String(version || 'alpha');
    navigateTo(`/${route.owner}/map/${route.map}/${next === 'alpha' ? 'alpha' : `v${next}`}`);
  };

  const handleLibraryVersionSelect = async (version) => {
    const v = String(version || 'alpha');
    setSelectedLibraryVersion(v);
    if (!route.owner || !route.map || !mapOwner || !normalizedMapName) return;
    try {
      const resp = await apiFetch(`/hub/${mapOwner}/lib/${normalizedMapName}/${v}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load library version');
      let nextCode = '';
      try {
        const parsed = JSON.parse(data.content || '{}');
        nextCode = String(parsed.predefined_code || '');
      } catch {
        nextCode = String(data.content || '');
      }
      setPredefinedCode(nextCode);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleThemeVersionSelect = async (version) => {
    const v = String(version || 'alpha');
    setSelectedThemeVersion(v);
    if (!route.owner || !route.map || !mapOwner || !normalizedMapName) return;
    try {
      const resp = await apiFetch(`/hub/${mapOwner}/css/${normalizedMapName}/${v}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load theme version');
      let nextCode = '';
      try {
        const parsed = JSON.parse(data.content || '{}');
        nextCode = String(parsed.theme_code || '');
      } catch {
        nextCode = String(data.content || '');
      }
      setThemeCode(nextCode);
    } catch (err) {
      setError(err.message);
    }
  };

  const handlePublishLibrary = async () => {
    try {
      if (isReadOnlyMap || selectedLibraryVersion !== 'alpha') {
        setError('Library is read-only in this view.');
        return;
      }
      const content = JSON.stringify({
        predefined_code: predefinedCode || '',
        map_name: normalizedMapName,
      });
      await publishHubArtifact('lib', content, { owner: mapOwner, name: normalizedMapName });
    } catch (err) {
      setError(`Publish library failed: ${err.message}`);
    }
  };

  const handlePublishTheme = async () => {
    try {
      if (isReadOnlyMap || selectedThemeVersion !== 'alpha') {
        setError('Theme is read-only in this view.');
        return;
      }
      const content = JSON.stringify({
        theme_code: themeCode || '',
        map_name: normalizedMapName,
      });
      await publishHubArtifact('css', content, { owner: mapOwner, name: normalizedMapName });
    } catch (err) {
      setError(`Publish theme failed: ${err.message}`);
    }
  };

  const handleLoadProject = (e) => {
    if (isReadOnlyMap) {
      e.target.value = null;
      return;
    }
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const project = JSON.parse(e.target.result);
          if (project.elements && project.options) {
             setBuilderElements(project.elements);
             setBuilderOptions(project.options);
             if (project.predefinedCode) setPredefinedCode(project.predefinedCode);
             if (typeof project.importsCode === 'string') {
               setImportsCode(project.importsCode);
               setHubImports(parseImportsCodeToItems(project.importsCode));
             }
             if (typeof project.themeCode === 'string') setThemeCode(project.themeCode);
             if (typeof project.runtimeCode === 'string') setRuntimeCode(project.runtimeCode);
          }
        } catch (err) {
          setError("Failed to load project: " + err.message);
        }
      };
      reader.readAsText(file);
    }
    // Reset file input
    e.target.value = null;
  };

  const formatTerritory = (value) => {
      const ops = { union: '|', difference: '-', intersection: '&' };
      const normalizeValues = (raw) => {
        if (Array.isArray(raw)) return raw.map((x) => String(x || '').trim()).filter(Boolean);
        if (raw == null) return [];
        const s = String(raw).trim();
        return s ? [s] : [];
      };
      const formatLeaf = (part) => {
        if (!part || !part.type) return '';
        if (part.type === 'group') {
          const inner = formatParts(Array.isArray(part.value) ? part.value : []);
          return inner ? `(${inner})` : '';
        }
        if (part.type === 'polygon') {
          if (part.value == null || String(part.value).trim() === '') return '';
          return `polygon(${part.value})`;
        }
        if (part.type === 'gadm') {
          const values = normalizeValues(part.value);
          if (!values.length) return '';
          const exprs = values.map((gid) => `gadm("${gid}")`);
          return exprs.length === 1 ? exprs[0] : `(${exprs.join(' | ')})`;
        }
        if (part.type === 'predefined') {
          const values = normalizeValues(part.value);
          if (!values.length) return '';
          return values.length === 1 ? values[0] : `(${values.join(' | ')})`;
        }
        return '';
      };
      const formatParts = (parts) => {
        const emitted = [];
        (parts || []).forEach((part) => {
          const pStr = formatLeaf(part);
          if (!pStr) return;
          if (emitted.length === 0) emitted.push(pStr);
          else emitted.push(` ${ops[part.op] || '|'} ${pStr}`);
        });
        return emitted.join('');
      };
      if (value == null || (Array.isArray(value) && value.length === 0)) return 'None';
      if (Array.isArray(value)) {
          const rendered = formatParts(value);
          if (!rendered) return 'None';
          return rendered;
      }
      if (value === '') return 'None';
      return `gadm("${value}")`;
  };

  const handleSaveTerritoryToLibrary = (element) => {
      const name = (element.label || '').replace(/\s+/g, '_');
      const terrStr = formatTerritory(element.value);
      setPredefinedCode(prev => prev + `\n${name} = ${terrStr}\n`);
      handleTabChange('code');
  };

  const generatePythonCode = () => {
    const dataColormapOpt = (builderOptions.data_colormap && typeof builderOptions.data_colormap === 'object')
      ? builderOptions.data_colormap
      : (typeof builderOptions.data_colormap === 'string' && builderOptions.data_colormap
        ? { type: builderOptions.data_colormap, colors: 'yellow,orange,red' }
        : null);
    const pyString = (s) => {
        const str = String(s ?? '');
        if (str.includes('\n')) {
            const escapedTriple = str.replace(/"""/g, '\\"""');
            return `"""${escapedTriple}"""`;
        }
        return JSON.stringify(str);
    };
    const pyVal = (v) => {
        if (isPythonValue(v)) return getPythonExpr(v) || 'None';
        if (v == null || v === '') return 'None';
        if (typeof v === 'boolean') return v ? 'True' : 'False';
        if (typeof v === 'string') return pyString(v);
        if (Array.isArray(v)) return JSON.stringify(v);
        return JSON.stringify(v).replace(/"/g, "'").replace(/null/g, 'None').replace(/true/g, 'True').replace(/false/g, 'False');
    };
    const colorSequenceExpr = (raw) => {
        if (typeof raw !== 'string') return null;
        const val = raw.trim();
        if (!val) return null;
        const namedColors = new Set(['red', 'green', 'blue', 'yellow', 'purple', 'orange', 'brown', 'gray', 'black', 'white', 'pink', 'cyan', 'magenta', 'lime', 'teal', 'indigo', 'violet']);
        const parts = val
          .split(',')
          .map((p) => p.trim())
          .filter(Boolean)
          .map((p) => (
            p.startsWith('#')
              ? `Color.hex(${pyVal(p)})`
              : (namedColors.has(p.toLowerCase()) ? `Color.named(${pyVal(p.toLowerCase())})` : null)
          ));
        if (parts.length === 0 || parts.some((p) => p == null)) return null;
        return `[${parts.join(', ')}]`;
    };
    let lines = [];
    let themeLines = [];

    // Options
    if (builderOptions.basemaps) {
        builderOptions.basemaps.forEach(bm => {
            themeLines.push(`xatra.BaseOption("${bm.url_or_provider}", name="${bm.name || ''}", default=${bm.default ? 'True' : 'False'})`);
        });
    }

    if (builderOptions.zoom !== undefined && builderOptions.zoom !== null) {
        themeLines.push(`xatra.zoom(${builderOptions.zoom})`);
    }

    if (
      Array.isArray(builderOptions.focus) &&
      builderOptions.focus.length === 2 &&
      builderOptions.focus[0] != null &&
      builderOptions.focus[1] != null
    ) {
        themeLines.push(`xatra.focus(${builderOptions.focus[0]}, ${builderOptions.focus[1]})`);
    }

    if (builderOptions.css_rules) {
        let css = builderOptions.css_rules.map(r => `${r.selector} { ${r.style} }`).join('\n');
        if (css) themeLines.push(`xatra.CSS("""${css}""")`);
    }

    if (builderOptions.slider) {
        const { start, end, speed } = builderOptions.slider;
        themeLines.push(`xatra.slider(start=${start ?? 'None'}, end=${end ?? 'None'}, speed=${speed ?? 5.0})`);
    }

    if (Array.isArray(builderOptions.flag_color_sequences)) {
        builderOptions.flag_color_sequences.forEach((row) => {
            const className = (row?.class_name || '').trim();
            const stepH = Number.isFinite(Number(row?.step_h)) ? Number(row.step_h) : 1.6180339887;
            const stepS = Number.isFinite(Number(row?.step_s)) ? Number(row.step_s) : 0.0;
            const stepL = Number.isFinite(Number(row?.step_l)) ? Number(row.step_l) : 0.0;
            const colorsExpr = colorSequenceExpr(row?.colors || '') || 'None';
            const seqExpr = `LinearColorSequence(colors=${colorsExpr}, step=Color.hsl(${stepH}, ${stepS}, ${stepL}))`;
            if (className) themeLines.push(`xatra.FlagColorSequence(${seqExpr}, class_name=${pyVal(className)})`);
            else themeLines.push(`xatra.FlagColorSequence(${seqExpr})`);
        });
    } else if (builderOptions.flag_colors) {
        const colorsExpr = colorSequenceExpr(builderOptions.flag_colors) || 'None';
        themeLines.push(`xatra.FlagColorSequence(LinearColorSequence(colors=${colorsExpr}, step=Color.hsl(1.6180339887, 0.0, 0.0)))`);
    }

    if (Array.isArray(builderOptions.admin_color_sequences) && builderOptions.admin_color_sequences.length) {
        const row = builderOptions.admin_color_sequences[0];
        const stepH = Number.isFinite(Number(row?.step_h)) ? Number(row.step_h) : 1.6180339887;
        const stepS = Number.isFinite(Number(row?.step_s)) ? Number(row.step_s) : 0.0;
        const stepL = Number.isFinite(Number(row?.step_l)) ? Number(row.step_l) : 0.0;
        const colorsExpr = colorSequenceExpr(row?.colors || '') || 'None';
        const seqExpr = `LinearColorSequence(colors=${colorsExpr}, step=Color.hsl(${stepH}, ${stepS}, ${stepL}))`;
        themeLines.push(`xatra.AdminColorSequence(${seqExpr})`);
    } else if (builderOptions.admin_colors) {
        const colorsExpr = colorSequenceExpr(builderOptions.admin_colors) || 'None';
        themeLines.push(`xatra.AdminColorSequence(LinearColorSequence(colors=${colorsExpr}, step=Color.hsl(1.6180339887, 0.0, 0.0)))`);
    }

    if (dataColormapOpt && dataColormapOpt.type) {
        if (dataColormapOpt.type === 'LinearSegmented') {
            const colors = String(dataColormapOpt.colors || 'yellow,orange,red')
              .split(',')
              .map((x) => x.trim())
              .filter(Boolean)
              .map((c) => pyVal(c))
              .join(', ');
            themeLines.push(`xatra.DataColormap(LinearSegmentedColormap.from_list("custom_cmap", [${colors || '"yellow", "orange", "red"'}]))`);
        } else {
            themeLines.push(`xatra.DataColormap(plt.cm.${String(dataColormapOpt.type).replace(/[^A-Za-z0-9_]/g, '')})`);
        }
    }
    const argsEntries = (obj) => Object.entries(obj || {}).filter(([, v]) => {
        if (v == null || v === '') return false;
        if (Array.isArray(v) && v.length === 0) return false;
        return true;
    });
    const argsToStr = (args) => {
        const parts = argsEntries(args).map(([k, v]) => `${k}=${pyVal(v)}`);
        return parts.length ? ', ' + parts.join(', ') : '';
    };

    // Elements
    const labelCapableTypes = new Set(['flag', 'river', 'point', 'text', 'path']);
    builderElements.forEach(el => {
        const args = { ...el.args };
        if (el.type === 'flag') delete args.parent;
        if (labelCapableTypes.has(el.type) && el.label != null && el.label !== '') args.label = el.label;
        const argsStr = argsToStr(args);

        if (el.type === 'flag') {
            lines.push(`xatra.Flag(value=${formatTerritory(el.value)}${argsStr})`);
        } else if (el.type === 'river') {
            const func = el.args?.source_type === 'overpass' ? 'overpass' : 'naturalearth';
            const riverArgs = { ...args };
            delete riverArgs.source_type;
            const riverArgsStrFormatted = argsToStr(riverArgs);
            const riverVal = (el.value != null && el.value !== '')
              ? `${func}(${isPythonValue(el.value) ? (getPythonExpr(el.value) || 'None') : pyVal(el.value)})`
              : 'None';
            lines.push(`xatra.River(value=${riverVal}${riverArgsStrFormatted})`);
        } else if (el.type === 'point') {
            const pointArgs = { ...args };
            const iconVal = pointArgs.icon;
            delete pointArgs.icon;
            let pointArgsStr = argsToStr(pointArgs);
            let iconPy = '';
            if (iconVal != null && iconVal !== '') {
                if (isPythonValue(iconVal)) {
                    iconPy = `icon=${pyVal(iconVal)}`;
                } else if (typeof iconVal === 'string') {
                    iconPy = `icon=Icon.builtin("${iconVal}")`;
                } else if (iconVal.shape) {
                    iconPy = `icon=Icon.geometric(${pyVal(iconVal.shape || 'circle')}, color=${pyVal(iconVal.color || '#3388ff')}, size=${pyVal(iconVal.size ?? 24)})`;
                } else if (iconVal.icon_url || iconVal.iconUrl) {
                    iconPy = `icon=Icon(icon_url=${pyVal(iconVal.icon_url || iconVal.iconUrl)})`;
                }
            }
            if (iconPy) pointArgsStr = pointArgsStr ? `${pointArgsStr}, ${iconPy}` : `, ${iconPy}`;
            const pos = (el.value != null && el.value !== '')
              ? (isPythonValue(el.value) ? (getPythonExpr(el.value) || 'None') : (Array.isArray(el.value) ? JSON.stringify(el.value) : el.value))
              : 'None';
            lines.push(`xatra.Point(position=${pos}${pointArgsStr})`);
        } else if (el.type === 'text') {
            const pos = (el.value != null && el.value !== '')
              ? (isPythonValue(el.value) ? (getPythonExpr(el.value) || 'None') : (Array.isArray(el.value) ? JSON.stringify(el.value) : el.value))
              : 'None';
            lines.push(`xatra.Text(position=${pos}${argsStr})`);
        } else if (el.type === 'path') {
            const pathVal = (el.value != null && el.value !== '')
              ? (isPythonValue(el.value) ? (getPythonExpr(el.value) || 'None') : (typeof el.value === 'string' ? el.value : JSON.stringify(el.value)))
              : 'None';
            lines.push(`xatra.Path(value=${pathVal}${argsStr})`);
        } else if (el.type === 'admin') {
            const gadmVal = (el.value != null && el.value !== '') ? pyVal(el.value) : 'None';
            lines.push(`xatra.Admin(gadm=${gadmVal}${argsStr})`);
        } else if (el.type === 'admin_rivers') {
            const sourcesVal = (() => {
              if (el.value == null || el.value === '') return 'None';
              if (isPythonValue(el.value)) return getPythonExpr(el.value) || 'None';
              if (typeof el.value === 'string') {
                const trimmed = el.value.trim();
                if (trimmed.startsWith('[') || trimmed.startsWith('{') || trimmed.startsWith('(')) {
                  return trimmed || 'None';
                }
              }
              return pyVal(el.value);
            })();
            lines.push(`xatra.AdminRivers(sources=${sourcesVal}${argsStr})`);
        } else if (el.type === 'dataframe') {
            lines.push(`# DataFrame handling requires local CSV file or manual implementation in code mode`);
            lines.push(`import pandas as pd`);
            lines.push(`import io`);
            if (isPythonValue(el.value)) {
              lines.push(`df = pd.read_csv(${getPythonExpr(el.value) || 'None'})`);
            } else {
              const csvContent = (el.value != null && el.value !== '') ? String(el.value).replace(/"""/g, '\\"\\"\\"') : '';
              lines.push(`df = pd.read_csv(io.StringIO("""${csvContent}"""))`);
            }
            lines.push(`xatra.Dataframe(df${argsStr})`);
        } else if (el.type === 'titlebox') {
            const titleHtml = (el.value != null && el.value !== '') ? pyVal(el.value) : 'None';
            lines.push(`xatra.TitleBox(${titleHtml}${argsStr})`);
        } else if (el.type === 'python') {
            const raw = (el.value == null) ? '' : String(el.value);
            if (raw.trim()) lines.push(raw);
        }
    });

    const generated = lines.join('\n');
    setThemeCode(themeLines.join('\n'));
    setCode(generated);
    return generated;
  };

  const parseCodeToBuilder = async () => {
    const combinedCode = [importsCode || '', themeCode || '', code || '', runtimeCode || ''].filter((x) => String(x).trim()).join('\n\n');
    const response = await apiFetch('/sync/code_to_builder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: combinedCode, predefined_code: predefinedCode }),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Failed to parse code into Builder state');
    }
    return data;
  };

  const normalizePredefinedImports = () => {
    const lines = String(predefinedCode || '').split('\n');
    const keep = [];
    const moved = [];
    lines.forEach((ln) => {
      if (ln.includes('xatrahub(')) moved.push(ln);
      else keep.push(ln);
    });
    if (moved.length) {
      const mergedImports = `${String(importsCode || '').trim()}\n${moved.join('\n')}\n`.replace(/^\n+/, '');
      setImportsCode(mergedImports);
      setHubImports(parseImportsCodeToItems(mergedImports));
      setPredefinedCode(keep.join('\n'));
    }
  };

  const handleTabChange = async (nextTab) => {
    if (nextTab === activeTab) return;
    if (nextTab === 'code') {
      setImportsCode(serializeHubImports(hubImports));
      generatePythonCode();
      setActiveTab('code');
      return;
    }
    if (activeTab === 'code' && nextTab === 'builder') {
      normalizePredefinedImports();
      try {
        const parsed = await parseCodeToBuilder();
        if (Array.isArray(parsed.elements)) setBuilderElements(parsed.elements);
        if (parsed.options && typeof parsed.options === 'object') setBuilderOptions(parsed.options);
        if (typeof parsed.predefined_code === 'string') setPredefinedCode(parsed.predefined_code);
        setHubImports(parseImportsCodeToItems(importsCode));
      } catch (err) {
        setError(`Code → Builder sync failed: ${err.message}`);
        return;
      }
    }
    setActiveTab(nextTab);
  };

  const handleStop = async (view) => {
      const stopView = view || 'main';
      const mappedTaskTypes = (
        stopView === 'main'
          ? (mainRenderTask ? [mainRenderTask] : ['builder', 'code'])
          : (stopView === 'picker' ? ['picker'] : ['territory_library'])
      );
      setLoadingByView((prev) => ({ ...prev, [stopView]: false }));
      try {
          await fetch('http://localhost:8088/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_types: mappedTaskTypes }),
          });
      } catch (e) { console.error(e); }
      if (stopView === 'main') setMainRenderTask(null);
  };

  // Initial render
  useEffect(() => {
    renderMap();
  }, []);

  useEffect(() => {
    if (didPrefetchReferenceRef.current || !mapHtml) return;
    didPrefetchReferenceRef.current = true;
    renderPickerMap({ background: true, showLoading: true });
  }, [mapHtml]);

  useEffect(() => {
    if (didPrefetchTerritoryRef.current || !mapHtml) return;
    didPrefetchTerritoryRef.current = true;
    (async () => {
      await loadTerritoryLibraryCatalog('builtin');
      await renderTerritoryLibrary('builtin', { background: true, useDefaultSelection: true, showLoading: true });
    })();
  }, [mapHtml]);

  useEffect(() => {
    if (activePreviewTab !== 'library') return;
    const exists = libraryTabs.some((t) => t.id === activeLibraryTab);
    if (!exists) {
      setActiveLibraryTab('builtin');
      return;
    }
    const tab = libraryTabs.find((t) => t.id === activeLibraryTab) || libraryTabs[0];
    const src = tab?.source || 'builtin';
    setTerritoryLibrarySource(src);
    loadTerritoryLibraryCatalog(src, tab?.hub_path);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePreviewTab, activeLibraryTab, predefinedCode, hubImports]);

  const filteredTerritoryNames = territoryLibraryNames.filter((name) => (
    !territorySearchTerm.trim() || name.toLowerCase().includes(territorySearchTerm.trim().toLowerCase())
  ));
  const importedLibraryTabs = (hubImports || [])
    .filter((imp) => imp.kind === 'lib')
    .map((imp) => ({
      id: `hub:${imp.username}:${imp.name}:${imp.selected_version || 'alpha'}`,
      label: `${imp.name}`,
      source: 'hub',
      hub_path: buildImportPath(imp),
    }));
  const libraryTabs = [
    { id: 'builtin', label: 'xatra.territory_library', source: 'builtin' },
    { id: 'custom', label: 'Custom Library', source: 'custom' },
    ...importedLibraryTabs,
  ];
  const activeLibraryConfig = libraryTabs.find((t) => t.id === activeLibraryTab) || libraryTabs[0];
  const mapTabBarClass = isDarkMode
    ? 'bg-slate-900/90 border-slate-700'
    : 'bg-white/90 border-gray-200';
  const mapTabInactiveClass = isDarkMode
    ? 'text-slate-300 hover:bg-slate-800'
    : 'text-gray-600 hover:bg-gray-100';
  const sidePanelClass = isDarkMode
    ? 'bg-slate-900/95 border-slate-700 text-slate-100'
    : 'bg-white/95 border-gray-200';
  const shortcutsToggleClass = isDarkMode
    ? 'bg-slate-900/95 border-slate-700 text-slate-300 hover:text-blue-300 hover:border-blue-500'
    : 'bg-white/95 border-gray-200 text-gray-600 hover:text-blue-700 hover:border-blue-300';
  const shortcutsPanelClass = isDarkMode
    ? 'bg-slate-900/95 border-slate-700 text-slate-200'
    : 'bg-white/95 border-gray-200 text-gray-700';
  const currentMapVersionOptions = getImportVersionOptions({
    username: mapOwner,
    kind: 'map',
    name: normalizedMapName,
  });
  const currentLibraryVersionOptions = getImportVersionOptions({
    username: mapOwner,
    kind: 'lib',
    name: normalizedMapName,
  });
  const currentThemeVersionOptions = getImportVersionOptions({
    username: mapOwner,
    kind: 'css',
    name: normalizedMapName,
  });
  const importedBaseSet = new Set((hubImports || []).map((imp) => `${imp.kind}:${imp.username}:${imp.name}`));
  const renderExploreCatalogCard = (item) => {
    const mapKey = artifactKey(item.username, 'map', item.name);
    const mapOptions = artifactVersionOptions[mapKey] || [{ value: 'alpha', label: 'alpha' }];
    const mapVersion = importVersionDraft[mapKey] || mapOptions[0]?.value || 'alpha';
    return (
      <div
        key={`${item.username}-${item.name}`}
        className="border rounded bg-white overflow-hidden focus-within:ring-2 ring-blue-500 shadow-sm"
      >
        <img src={item.thumbnail || '/vite.svg'} alt="" className="w-full h-24 object-cover bg-gray-100" />
        <div className="p-2">
          <a href={`/${item.username}/map/${item.name}`} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-blue-700 hover:underline">{item.name}</a>
          <div className="text-[10px] text-gray-500 truncate">
            by <a href={`/${item.username}`} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{item.username}</a> · {item.votes || 0} votes · {item.views || 0} views
          </div>
          <div className="text-[10px] text-gray-600 line-clamp-2">{item.description || 'No description'}</div>
          <div className="mt-2 flex gap-1">
            <select
              value={mapVersion}
              onChange={(e) => setImportVersionDraft((prev) => ({ ...prev, [mapKey]: e.target.value }))}
              className="text-[11px] border rounded px-1 py-1"
            >
              {mapOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <button className="flex-1 text-xs px-2 py-1 border rounded hover:bg-blue-50" onClick={() => navigateTo(`/${item.username}/map/${item.name}/${mapVersion === 'alpha' ? 'alpha' : `v${mapVersion}`}`)}>Open</button>
          </div>
        </div>
      </div>
    );
  };

  const renderImportCatalogCard = (item) => {
    const mapKey = artifactKey(item.username, 'map', item.name);
    const cssKey = artifactKey(item.username, 'css', item.name);
    const libKey = artifactKey(item.username, 'lib', item.name);
    const mapOptions = artifactVersionOptions[mapKey] || [{ value: 'alpha', label: 'alpha' }];
    const cssOptions = artifactVersionOptions[cssKey] || [{ value: 'alpha', label: 'alpha' }];
    const libOptions = artifactVersionOptions[libKey] || [{ value: 'alpha', label: 'alpha' }];
    const mapVersion = importVersionDraft[mapKey] || mapOptions[0]?.value || 'alpha';
    const cssVersion = importVersionDraft[cssKey] || cssOptions[0]?.value || 'alpha';
    const libVersion = importVersionDraft[libKey] || libOptions[0]?.value || 'alpha';
    const mapImported = importedBaseSet.has(`map:${item.username}:${item.name}`);
    const cssImported = importedBaseSet.has(`css:${item.username}:${item.name}`);
    const libImported = importedBaseSet.has(`lib:${item.username}:${item.name}`);
    const isCurrentMap = (item.username === mapOwner && item.name === mapName);
    return (
      <div
        key={`${item.username}-${item.name}`}
        className={`border rounded bg-white focus-within:ring-2 ring-blue-500 shadow-sm min-h-[280px] ${isCurrentMap ? 'opacity-50 grayscale' : ''}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key.toLowerCase() === 'm') addHubImportLine({ ...item, kind: 'map', latest_version: mapVersion });
          if (e.key.toLowerCase() === 'c') addHubImportLine({ ...item, kind: 'css', latest_version: cssVersion });
          if (e.key.toLowerCase() === 't') addHubImportLine({ ...item, kind: 'lib', latest_version: libVersion });
        }}
      >
        <img src={item.thumbnail || '/vite.svg'} alt="" className="w-full h-20 object-cover bg-gray-100 rounded-t" />
        <div className="p-2">
          <a href={`/${item.username}/map/${item.name}`} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-blue-700 hover:underline">{item.name}</a>
          <div className="text-[10px] text-gray-500 truncate">
            by <a href={`/${item.username}`} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{item.username}</a> · {item.votes || 0} votes · {item.views || 0} views
          </div>
          <div className="mt-2 space-y-1 border rounded border-gray-200 bg-gray-50 p-1.5">
            <div className="text-[10px] font-semibold text-gray-700 px-0.5">Import actions</div>
            <div className="flex gap-1 items-center">
              <select value={mapVersion} onChange={(e) => setImportVersionDraft((prev) => ({ ...prev, [mapKey]: e.target.value }))} className="text-[11px] border rounded px-1 py-1 min-w-[72px]">
                {mapOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <button disabled={mapImported || isCurrentMap} className={`flex-1 text-[11px] px-2 py-1 border rounded transition-colors ${mapImported ? 'bg-blue-600 text-white border-blue-600 cursor-not-allowed' : 'hover:bg-blue-50'}`} onClick={() => addHubImportLine({ ...item, kind: 'map', latest_version: mapVersion })}>{mapImported ? '✓ Map Imported' : 'm Import Map'}</button>
            </div>
            <div className="flex gap-1 items-center">
              <select value={cssVersion} onChange={(e) => setImportVersionDraft((prev) => ({ ...prev, [cssKey]: e.target.value }))} className="text-[11px] border rounded px-1 py-1 min-w-[72px]">
                {cssOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <button disabled={cssImported || isCurrentMap} className={`flex-1 text-[11px] px-2 py-1 border rounded transition-colors ${cssImported ? 'bg-blue-600 text-white border-blue-600 cursor-not-allowed' : 'hover:bg-blue-50'}`} onClick={() => addHubImportLine({ ...item, kind: 'css', latest_version: cssVersion })}>{cssImported ? '✓ CSS Imported' : 'c Import CSS'}</button>
            </div>
            <div className="flex gap-1 items-center">
              <select value={libVersion} onChange={(e) => setImportVersionDraft((prev) => ({ ...prev, [libKey]: e.target.value }))} className="text-[11px] border rounded px-1 py-1 min-w-[72px]">
                {libOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <button disabled={libImported || isCurrentMap} className={`flex-1 text-[11px] px-2 py-1 border rounded transition-colors ${libImported ? 'bg-blue-600 text-white border-blue-600 cursor-not-allowed' : 'hover:bg-blue-50'}`} onClick={() => addHubImportLine({ ...item, kind: 'lib', latest_version: libVersion })}>{libImported ? '✓ Territories Imported' : 't Import Territories'}</button>
            </div>
          </div>
          {isCurrentMap && <div className="mt-1 text-[10px] text-gray-500">Current map cannot import itself.</div>}
          <div className="text-[10px] text-gray-600 mt-1 line-clamp-2">{item.description || 'No description'}</div>
        </div>
      </div>
    );
  };

  if (route.page === 'login') {
    return (
      <div className={`h-screen w-full flex items-center justify-center ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
        <div className="w-full max-w-3xl p-6 bg-white border rounded-lg shadow grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h1 className="text-xl font-bold mb-3">Login</h1>
            <div className="space-y-2">
              <input className="w-full border rounded p-2 text-sm font-mono" placeholder="username" value={authForm.username} onChange={(e) => setAuthForm((p) => ({ ...p, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))} />
              <input className="w-full border rounded p-2 text-sm" type="password" placeholder="password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} />
            </div>
            <button disabled={authSubmitting} className="mt-3 w-full px-3 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50" onClick={async () => { setAuthMode('login'); await handleLogin('login'); }}>{authSubmitting && authMode === 'login' ? 'Logging in ...' : 'Login'}</button>
          </div>
          <div>
            <h1 className="text-xl font-bold mb-3">Sign up</h1>
            <div className="space-y-2">
              <input className="w-full border rounded p-2 text-sm font-mono" placeholder="username" value={authForm.username} onChange={(e) => setAuthForm((p) => ({ ...p, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))} />
              <input className="w-full border rounded p-2 text-sm" placeholder="full name (optional)" value={authForm.full_name} onChange={(e) => setAuthForm((p) => ({ ...p, full_name: e.target.value }))} />
              <input className="w-full border rounded p-2 text-sm" type="password" placeholder="password (min 8)" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} />
            </div>
            <button disabled={authSubmitting} className="mt-3 w-full px-3 py-2 bg-slate-900 text-white rounded text-sm hover:bg-slate-800 disabled:opacity-50" onClick={async () => { setAuthMode('signup'); await handleLogin('signup'); }}>{authSubmitting && authMode === 'signup' ? 'Signing up ...' : 'Create account'}</button>
          </div>
          <div className="md:col-span-2">
            <button className="px-3 py-2 border rounded text-sm" onClick={() => navigateTo('/')}>Back to editor</button>
            {error && (
              <div className="mt-3 p-2 rounded border border-red-200 bg-red-50 text-red-700 text-xs">{error}</div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (route.page === 'explore') {
    const totalPages = Math.max(1, Math.ceil((exploreData.total || 0) / (exploreData.per_page || 12)));
    return (
      <div className={`h-screen w-full flex ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
        <div className="w-64 border-r p-4 bg-white space-y-2">
          <div className="text-lg font-bold lowercase px-2">xatra</div>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => setIsDarkMode((p) => !p)}>{isDarkMode ? <Sun size={14}/> : <Moon size={14}/>} Night mode</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800 bg-slate-800 text-slate-100' : 'hover:bg-gray-100 bg-blue-50 text-blue-700'}`}><Compass size={14}/> Explore</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/users')}><Users size={14}/> Users</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => (currentUser.is_authenticated ? navigateTo(`/${normalizedHubUsername}`) : navigateTo('/login'))}><User size={14}/> {currentUser.is_authenticated ? normalizedHubUsername : 'My Profile'}</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => window.open('/new-map', '_blank')}><FilePlus2 size={14}/> New map...</button>
          {currentUser.is_authenticated ? (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={handleLogout}><LogOut size={14}/> Logout</button>
          ) : (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/login')}><LogIn size={14}/> Login/Signup</button>
          )}
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          {exploreLoading && <div className="mb-3 text-xs px-2 py-1 border rounded bg-blue-50 text-blue-700 border-blue-200">Loading maps...</div>}
          <div className="flex gap-2 mb-3">
            <input value={exploreQuery} onChange={(e) => setExploreQuery(e.target.value)} placeholder='Search maps, e.g. "indica user:srajma"' className="flex-1 border rounded p-2 text-sm" />
            <button className="px-3 py-2 border rounded" onClick={() => { setExplorePage(1); loadExplore(1, exploreQuery); }}>Search</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {(exploreData.items || []).map((item) => renderExploreCatalogCard(item))}
          </div>
          <div className="flex gap-2 mt-4">
            <button disabled={explorePage <= 1} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.max(1, explorePage - 1); setExplorePage(p); loadExplore(p, exploreQuery); }}>Prev</button>
            <div className="text-xs self-center">Page {explorePage} / {totalPages}</div>
            <button disabled={explorePage >= totalPages} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.min(totalPages, explorePage + 1); setExplorePage(p); loadExplore(p, exploreQuery); }}>Next</button>
          </div>
        </div>
      </div>
    );
  }

  if (route.page === 'users') {
    const totalPages = Math.max(1, Math.ceil((usersData.total || 0) / (usersData.per_page || 20)));
    return (
      <div className={`h-screen w-full flex ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
        <div className="w-64 border-r p-4 bg-white space-y-2">
          <div className="text-lg font-bold lowercase px-2">xatra</div>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => setIsDarkMode((p) => !p)}>{isDarkMode ? <Sun size={14}/> : <Moon size={14}/>} Night mode</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/explore')}><Compass size={14}/> Explore</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800 bg-slate-800 text-slate-100' : 'hover:bg-gray-100 bg-blue-50 text-blue-700'}`}><Users size={14}/> Users</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => (currentUser.is_authenticated ? navigateTo(`/${normalizedHubUsername}`) : navigateTo('/login'))}><User size={14}/> {currentUser.is_authenticated ? normalizedHubUsername : 'My Profile'}</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => window.open('/new-map', '_blank')}><FilePlus2 size={14}/> New map...</button>
          {currentUser.is_authenticated ? (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={handleLogout}><LogOut size={14}/> Logout</button>
          ) : (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/login')}><LogIn size={14}/> Login/Signup</button>
          )}
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          {usersLoading && <div className="mb-3 text-xs px-2 py-1 border rounded bg-blue-50 text-blue-700 border-blue-200">Loading users...</div>}
          <div className="flex gap-2 mb-3">
            <input value={usersQuery} onChange={(e) => setUsersQuery(e.target.value)} placeholder='Search users...' className="flex-1 border rounded p-2 text-sm" />
            <button className="px-3 py-2 border rounded" onClick={() => { setUsersPage(1); loadUsers(1, usersQuery); }}>Search</button>
          </div>
          <div className="space-y-2">
            {(usersData.items || []).map((u) => (
              <a key={u.username} href={`/${u.username}`} className="block border rounded bg-white p-3 hover:bg-blue-50">
                <div className="font-mono text-sm text-blue-700">{u.username}</div>
                <div className="text-xs text-gray-600">{u.full_name || ''}</div>
                <div className="text-[11px] text-gray-500 mt-1">maps {u.maps_count || 0} · views {u.views_count || 0}</div>
              </a>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button disabled={usersPage <= 1} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.max(1, usersPage - 1); setUsersPage(p); loadUsers(p, usersQuery); }}>Prev</button>
            <div className="text-xs self-center">Page {usersPage} / {totalPages}</div>
            <button disabled={usersPage >= totalPages} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.min(totalPages, usersPage + 1); setUsersPage(p); loadUsers(p, usersQuery); }}>Next</button>
          </div>
        </div>
      </div>
    );
  }

  if (route.page === 'profile') {
    const profile = profileData?.profile;
    const maps = profileData?.maps || [];
    const totalPages = Math.max(1, Math.ceil((profileData?.total || 0) / (profileData?.per_page || 10)));
    const viewingOwnProfilePath = route.username && route.username === normalizedHubUsername;
    if (viewingOwnProfilePath && !authReady) {
      return (
        <div className={`h-screen w-full flex items-center justify-center ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
          <div className="text-sm text-gray-600">Loading profile…</div>
        </div>
      );
    }
    const isOwn = authReady && profile?.username && profile.username === normalizedHubUsername && currentUser.is_authenticated;
    return (
      <div className={`h-screen w-full flex ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
        <div className="w-64 border-r p-4 bg-white space-y-2">
          <div className="text-lg font-bold lowercase px-2">xatra</div>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => setIsDarkMode((p) => !p)}>{isDarkMode ? <Sun size={14}/> : <Moon size={14}/>} Night mode</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/explore')}><Compass size={14}/> Explore</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/users')}><Users size={14}/> Users</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800 bg-slate-800 text-slate-100' : 'hover:bg-gray-100 bg-blue-50 text-blue-700'}`}><User size={14}/> {profile?.username || normalizedHubUsername}</button>
          <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => window.open('/new-map', '_blank')}><FilePlus2 size={14}/> New map...</button>
          {currentUser.is_authenticated ? (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={handleLogout}><LogOut size={14}/> Logout</button>
          ) : (
            <button className={`w-full text-left px-2 py-2 rounded inline-flex items-center gap-2 ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-gray-100'}`} onClick={() => navigateTo('/login')}><LogIn size={14}/> Login/Signup</button>
          )}
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          {profileLoading && <div className="mb-3 text-xs px-2 py-1 border rounded bg-blue-50 text-blue-700 border-blue-200">Loading maps...</div>}
          <h1 className="text-xl font-bold">{profile?.username || route.username}</h1>
          <div className="text-sm text-gray-600">{profile?.full_name || ''}</div>
          <div className="text-sm mt-1">{profile?.bio || ''}</div>
          <div className="text-xs text-gray-500 mt-1">maps {profile?.maps_count || 0} · views {profile?.views_count || 0}</div>
          {isOwn && (
            <div className="mt-3 border rounded bg-white p-3 space-y-3">
              <div className="text-xs font-semibold">Account settings</div>
              <div className="space-y-2">
                <input className="w-full border rounded p-2 text-sm" placeholder="Full name" value={profileEdit.full_name} onChange={(e) => setProfileEdit((p) => ({ ...p, full_name: e.target.value }))} />
                <textarea className="w-full border rounded p-2 text-sm min-h-[72px]" placeholder="Profile description" value={profileEdit.bio} onChange={(e) => setProfileEdit((p) => ({ ...p, bio: e.target.value }))} />
                <button className="px-2 py-1 border rounded text-xs hover:bg-gray-50" onClick={handleSaveProfile}>Save profile</button>
              </div>
              <div className="pt-2 border-t space-y-2">
                <input type="password" className="w-full border rounded p-2 text-sm" placeholder="Current password" value={passwordEdit.current_password} onChange={(e) => setPasswordEdit((p) => ({ ...p, current_password: e.target.value }))} />
                <input type="password" className="w-full border rounded p-2 text-sm" placeholder="New password" value={passwordEdit.new_password} onChange={(e) => setPasswordEdit((p) => ({ ...p, new_password: e.target.value }))} />
                <button className="px-2 py-1 border rounded text-xs hover:bg-gray-50" onClick={handleChangePassword}>Update password</button>
              </div>
            </div>
          )}
          <div className="mt-4 flex gap-2">
            <input value={profileSearch} onChange={(e) => setProfileSearch(e.target.value)} className="border rounded p-2 text-sm flex-1" placeholder="Search maps..." />
            <button className="px-2 py-1 border rounded" onClick={() => { setProfilePage(1); loadProfile(route.username, 1, profileSearch); }}>Search</button>
          </div>
          <div className="space-y-2 mt-3">
            {maps.map((m) => (
              <div key={m.slug} className="border rounded bg-white p-2 flex items-center justify-between">
                <div>
                  <div className="font-mono text-xs">{m.name}</div>
                  <div className="text-[11px] text-gray-600">{m.description || 'No description'}</div>
                </div>
                <button className="text-xs px-2 py-1 border rounded hover:bg-blue-50" onClick={() => navigateTo(m.slug)}>Open</button>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button disabled={profilePage <= 1} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.max(1, profilePage - 1); setProfilePage(p); loadProfile(route.username, p, profileSearch); }}>Prev</button>
            <div className="text-xs self-center">Page {profilePage} / {totalPages}</div>
            <button disabled={profilePage >= totalPages} className="px-2 py-1 border rounded disabled:opacity-40" onClick={() => { const p = Math.min(totalPages, profilePage + 1); setProfilePage(p); loadProfile(route.username, p, profileSearch); }}>Next</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex h-screen font-sans ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
      {/* Sidebar */}
      <div className="w-1/3 min-w-[350px] max-w-[500px] flex flex-col bg-white border-r border-gray-200 shadow-md z-10">
        <div className="p-4 border-b border-gray-200 bg-gray-50 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-wrap">
              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((m) => {
                    const next = !m;
                    if (next) setMenuFocusIndex(0);
                    return next;
                  })}
                  className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
                  title="xatra menu"
                >
                  <Menu size={14} className="text-gray-700" />
                </button>
                {menuOpen && (
                  <div className="absolute left-0 top-9 w-52 bg-white border rounded shadow-lg z-50 text-xs">
                    <label onMouseEnter={() => setMenuFocusIndex(0)} className={`flex items-center gap-2 px-3 py-2 cursor-pointer ${menuFocusIndex === 0 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><Upload size={12}/> Load<input id="xatra-load-input" type="file" className="hidden" accept=".json" onChange={handleLoadProject} /></label>
                    <button onMouseEnter={() => setMenuFocusIndex(1)} onClick={handleSaveProject} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 1 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><Download size={12}/> Save</button>
                    <button onMouseEnter={() => setMenuFocusIndex(2)} onClick={handleExportHtml} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 2 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><Image size={12}/> Export</button>
                    <button onMouseEnter={() => setMenuFocusIndex(3)} onClick={() => setIsDarkMode((prev) => !prev)} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 3 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}>{isDarkMode ? <Sun size={12}/> : <Moon size={12}/>} Night mode</button>
                    <button onMouseEnter={() => setMenuFocusIndex(4)} onClick={() => window.open('/explore', '_blank')} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 4 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><Compass size={12}/> Explore</button>
                    <button onMouseEnter={() => setMenuFocusIndex(5)} onClick={() => window.open('/users', '_blank')} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 5 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><Users size={12}/> Users</button>
                    <button onMouseEnter={() => setMenuFocusIndex(6)} onClick={() => (currentUser.is_authenticated ? window.open(`/${normalizedHubUsername}`, '_blank') : navigateTo('/login'))} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 6 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><User size={12}/> {currentUser.is_authenticated ? normalizedHubUsername : 'My Profile'}</button>
                    <button onMouseEnter={() => setMenuFocusIndex(7)} onClick={() => window.open('/new-map', '_blank')} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 7 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><FilePlus2 size={12}/> New map...</button>
                    {currentUser.is_authenticated ? (
                      <button onMouseEnter={() => setMenuFocusIndex(8)} onClick={handleLogout} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 8 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><LogOut size={12}/> Logout</button>
                    ) : (
                      <button onMouseEnter={() => setMenuFocusIndex(8)} onClick={() => navigateTo('/login')} className={`w-full flex items-center gap-2 px-3 py-2 ${menuFocusIndex === 8 ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}><LogIn size={12}/> Login/Signup</button>
                    )}
                  </div>
                )}
              </div>
              <input
                type="text"
                value={mapName}
                onChange={(e) => setMapName(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''))}
                disabled={isReadOnlyMap}
                className={`w-40 text-sm p-1.5 border rounded bg-white font-mono disabled:bg-gray-100 disabled:text-gray-500 ${HUB_NAME_RE.test(normalizedMapName) ? 'border-gray-300' : 'border-red-400'}`}
                title="Map title"
                placeholder="map_name"
              />
              {statusNotice && <span className="text-[10px] text-amber-700">{statusNotice}</span>}
              {isReadOnlyMap ? (
                <button onClick={handleForkMap} className="px-2 py-1 bg-white border border-gray-300 rounded hover:bg-gray-50 inline-flex items-center gap-1" title="Fork map">
                  <GitFork size={12} className="text-gray-700"/> <span className="font-mono text-[11px]">Fork</span>
                </button>
              ) : (
                <button onClick={handlePublishMap} className="px-2 py-1 bg-white border border-gray-300 rounded hover:bg-gray-50 inline-flex items-center gap-1" title="Save alpha">
                  <Save size={12} className="text-gray-700"/> <span className="font-mono text-[11px]">Save</span>
                </button>
              )}
              <select
                value={viewedMapVersion}
                onChange={(e) => handleMapVersionSelect(e.target.value)}
                className="text-[11px] border rounded px-1.5 py-1 bg-white font-mono"
                title="Map version"
              >
                {currentMapVersionOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <button
                onClick={handleVoteMap}
                disabled={!(route.owner && route.map)}
                className={`p-1 rounded border ${route.owner && route.map ? 'hover:bg-gray-50' : 'opacity-40'}`}
                title="Like/unlike"
              >
                <Heart size={12} className={mapVotes > 0 ? 'text-rose-600 fill-rose-600' : 'text-gray-500'} />
              </button>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex bg-white rounded-lg border border-gray-300 p-0.5">
                <button 
                onClick={() => handleTabChange('builder')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${activeTab === 'builder' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                <span className="flex items-center gap-1"><Layers size={16}/> Builder</span>
                </button>
                <button 
                onClick={() => handleTabChange('code')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${activeTab === 'code' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                <span className="flex items-center gap-1"><Code size={16}/> Code</span>
                </button>
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-600 flex items-center gap-2">
            <span>by</span>
            <a href={`/${mapOwner}`} className="text-blue-700 hover:underline">{mapOwner}</a>
            <span>·</span>
            <span>{mapVotes} likes</span>
            <span>·</span>
            <span>{mapViews} views</span>
          </div>
        </div>

        <div className={`flex-1 overflow-y-auto p-4 ${isReadOnlyMap ? 'opacity-60' : ''}`}>
          {activeTab === 'builder' ? (
            <Builder 
              elements={builderElements} 
              setElements={setBuilderElements}
              options={builderOptions}
              setOptions={setBuilderOptions}
              onGetCurrentView={handleGetCurrentView}
              lastMapClick={lastMapClick}
              activePicker={activePicker}
              setActivePicker={setActivePicker}
              draftPoints={draftPoints}
              setDraftPoints={setDraftPoints}
              onSaveTerritory={handleSaveTerritoryToLibrary}
              predefinedCode={predefinedCode}
              onStartReferencePick={handleStartReferencePick}
              addLayerSignal={addLayerSignal}
              onConsumeAddLayerSignal={() => setAddLayerSignal(null)}
              hubImports={hubImports}
              onOpenImportModal={() => { setImportModalOpen(true); searchHubRegistry(); }}
              onRemoveHubImport={(idx) => {
                const next = [...hubImports];
                next.splice(idx, 1);
                setHubImports(next);
                setImportsCode(serializeHubImports(next));
              }}
              getImportVersionOptions={getImportVersionOptions}
              onSwitchHubImportVersion={switchHubImportVersion}
              readOnly={isReadOnlyMap}
            />
          ) : (
            <CodeEditor 
                pythonImports={FIXED_PY_IMPORTS}
                code={code} setCode={setCode} 
                predefinedCode={predefinedCode} setPredefinedCode={setPredefinedCode}
                importsCode={importsCode} setImportsCode={setImportsCode}
                themeCode={themeCode} setThemeCode={setThemeCode}
                runtimeCode={runtimeCode} setRuntimeCode={setRuntimeCode}
                libraryVersionLabel={String(selectedLibraryVersion)}
                themeVersionLabel={String(selectedThemeVersion)}
                librarySlugText={`${mapOwner}/lib/${normalizedMapName}/${selectedLibraryVersion}`}
                themeSlugText={`${mapOwner}/css/${normalizedMapName}/${selectedThemeVersion}`}
                onSaveLibrary={handlePublishLibrary}
                onSaveTheme={handlePublishTheme}
                onSelectLibraryVersion={handleLibraryVersionSelect}
                onSelectThemeVersion={handleThemeVersionSelect}
                libraryVersionOptions={currentLibraryVersionOptions}
                themeVersionOptions={currentThemeVersionOptions}
                readOnlyMap={isReadOnlyMap}
                readOnlyLibrary={isReadOnlyMap || selectedLibraryVersion !== 'alpha'}
                readOnlyTheme={isReadOnlyMap || selectedThemeVersion !== 'alpha'}
            />
          )}
        </div>

        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={renderMap}
            disabled={isReadOnlyMap}
            className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-5 h-5 fill-current" /> Render Map
          </button>
          {error && (
            <div className="mt-3 p-3 bg-red-50 text-red-700 text-xs rounded border border-red-200 overflow-auto max-h-32">
              <strong>Error:</strong> {error}
            </div>
          )}
        </div>
      </div>

      {/* Main Preview Area */}
      <div className={`flex-1 flex flex-col relative ${isDarkMode ? 'bg-slate-900' : 'bg-gray-200'}`}>
        <div className={`absolute top-4 left-1/2 transform -translate-x-1/2 z-20 flex backdrop-blur shadow-md rounded-full p-1 border ${mapTabBarClass}`}>
            <button 
                onClick={() => setActivePreviewTab('main')}
                className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${activePreviewTab === 'main' ? 'bg-blue-600 text-white shadow-sm' : mapTabInactiveClass}`}
            >
                Map Preview
            </button>
            <button 
                onClick={() => setActivePreviewTab('picker')}
                className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${activePreviewTab === 'picker' ? 'bg-blue-600 text-white shadow-sm' : mapTabInactiveClass}`}
            >
                Reference Map
            </button>
            <button 
                onClick={() => setActivePreviewTab('library')}
                className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${activePreviewTab === 'library' ? 'bg-blue-600 text-white shadow-sm' : mapTabInactiveClass}`}
            >
                Territory Library
            </button>
        </div>
        {activePreviewTab === 'library' && (
          <div className={`absolute top-16 left-1/2 transform -translate-x-1/2 z-20 flex backdrop-blur shadow-md rounded-full p-1 border ${mapTabBarClass}`}>
            {libraryTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveLibraryTab(tab.id);
                  setSelectedTerritoryNames([]);
                }}
                className={`px-3 py-1 rounded-full text-[11px] font-semibold transition-all ${activeLibraryTab === tab.id ? 'bg-blue-600 text-white shadow-sm' : mapTabInactiveClass}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}

        {activePreviewTab === 'picker' && (
            <div className={`absolute top-16 right-4 z-20 w-72 backdrop-blur p-4 rounded-lg shadow-xl border space-y-4 max-h-[calc(100vh-100px)] overflow-y-auto overflow-x-hidden ${sidePanelClass}`}>
                <h3 className="text-sm font-bold text-gray-800 flex items-center gap-2 border-b pb-2">
                    Reference Map Options
                </h3>
                <div className="space-y-3">
                    <div className="space-y-2">
                         <div className="grid grid-cols-[1fr_64px_24px] gap-1.5 items-center">
                            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Countries</label>
                            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider">Admin Level</label>
                            <div />
                         </div>
                         {pickerOptions.entries.map((entry, idx) => (
                             <div key={idx} className="flex gap-1.5 items-center">
                                 <AutocompleteInput 
                                     value={entry.country}
                                     endpoint="http://localhost:8088/search/gadm"
                                     onChange={(val) => {
                                         const newEntries = [...pickerOptions.entries];
                                         newEntries[idx].country = val;
                                         setPickerOptions({...pickerOptions, entries: newEntries});
                                     }}
                                     onSelectSuggestion={(item) => {
                                         const code = String(item.gid || item.country_code || item.country || '');
                                         const newEntries = [...pickerOptions.entries];
                                         newEntries[idx].country = code;
                                         setPickerOptions({...pickerOptions, entries: newEntries});
                                     }}
                                     className="w-32 text-xs p-1.5 border rounded bg-white shadow-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                                     placeholder="e.g. IND.20"
                                 />
                                 <select
                                     value={entry.level}
                                     onChange={(e) => {
                                         const newEntries = [...pickerOptions.entries];
                                         newEntries[idx].level = parseInt(e.target.value);
                                         setPickerOptions({...pickerOptions, entries: newEntries});
                                     }}
                                     className="w-16 text-xs p-1.5 border rounded bg-white shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                 >
                                     {(countryLevelOptions[String(entry.country || '').toUpperCase().split('.')[0]] || [0, 1, 2, 3, 4]).map((level) => (
                                       <option key={level} value={level}>{level}</option>
                                     ))}
                                 </select>
                                 <button 
                                     onClick={() => {
                                         const newEntries = [...pickerOptions.entries];
                                         newEntries.splice(idx, 1);
                                         setPickerOptions({...pickerOptions, entries: newEntries});
                                     }}
                                     className="p-1.5 text-red-500 hover:bg-red-50 rounded flex-shrink-0"
                                 >
                                     <Trash2 size={12}/>
                                 </button>
                             </div>
                         ))}
                         <button 
                             onClick={() => setPickerOptions({...pickerOptions, entries: [...pickerOptions.entries, {country: '', level: 1}]})}
                             className="text-xs text-blue-600 flex items-center gap-1 font-medium hover:text-blue-800"
                         >
                             <Plus size={12}/> Add Country
                         </button>
                    </div>

                    <div className="flex items-center pb-2 pt-2 border-t border-gray-100">
                        <label className="flex items-center gap-2 text-xs font-medium text-gray-700 cursor-pointer">
                            <input 
                                type="checkbox"
                                checked={pickerOptions.adminRivers}
                                onChange={(e) => setPickerOptions({ ...pickerOptions, adminRivers: e.target.checked })}
                                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                            Show Admin Rivers
                        </label>
                    </div>

                    <button 
                        onClick={renderPickerMap}
                        disabled={loadingByView.picker}
                        className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded shadow transition-colors disabled:opacity-50"
                    >
                        Update Reference Map
                    </button>
                </div>
            </div>
        )}
        {activePreviewTab === 'library' && (
            <div className={`absolute top-16 right-4 z-20 w-72 backdrop-blur p-4 rounded-lg shadow-xl border space-y-3 max-h-[calc(100vh-100px)] overflow-y-auto overflow-x-hidden ${sidePanelClass}`}>
                <h3 className="text-sm font-bold text-gray-800 border-b pb-2">Territory Library</h3>
                <div className="text-[11px] text-gray-600">Active library: <span className="font-mono">{activeLibraryConfig?.label}</span></div>
                <div className="space-y-2 border border-gray-200 rounded p-2 bg-gray-50">
                    <div className="flex items-center justify-between">
                        <div className="text-[11px] font-semibold text-gray-700">Territories to Render</div>
                        <button
                          onClick={copySelectedTerritoryIndex}
                          className={`p-1 border rounded bg-white transition-colors ${copyIndexCopied ? 'text-green-700 border-green-300 bg-green-50' : 'text-gray-600 hover:bg-gray-50'}`}
                          disabled={!selectedTerritoryNames.length}
                          title="Copy selected names as __TERRITORY_INDEX__"
                        >
                          {copyIndexCopied ? <Check size={12}/> : <Copy size={12}/>}
                        </button>
                    </div>
                    <div className="space-y-1">
                        <input
                          type="text"
                          value={territorySearchTerm}
                          onChange={(e) => setTerritorySearchTerm(e.target.value)}
                          className="w-full text-[11px] p-1.5 border rounded bg-white"
                          placeholder="Filter territories..."
                        />
                    </div>
                    <div className="max-h-40 overflow-y-auto space-y-1">
                        {territoryLibraryNames.length === 0 ? (
                          <div className="text-[10px] text-gray-400 italic">No territories found.</div>
                        ) : filteredTerritoryNames.length === 0 ? (
                          <div className="text-[10px] text-gray-400 italic">No matches for this search.</div>
                        ) : (
                          filteredTerritoryNames.map((name) => (
                            <label key={name} className="flex items-center gap-2 text-[11px] text-gray-700 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={selectedTerritoryNames.includes(name)}
                                onChange={() => toggleTerritoryName(name)}
                                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                              />
                              <span className="font-mono">{name}</span>
                            </label>
                          ))
                        )}
                    </div>
                </div>
                <button 
                    onClick={() => renderTerritoryLibrary(activeLibraryConfig?.source || territoryLibrarySource, { hubPath: activeLibraryConfig?.hub_path || null })}
                    disabled={loadingByView.library}
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded shadow transition-colors disabled:opacity-50"
                >
                    Update Territory Library Map
                </button>
            </div>
        )}

        <div className="flex-1 overflow-hidden relative">
            <button
                type="button"
                onClick={() => setShowShortcutHelp((prev) => !prev)}
                className={`absolute top-4 right-4 z-40 rounded-full shadow p-2 border ${shortcutsToggleClass}`}
                title="Toggle keyboard shortcuts"
            >
                <Keyboard size={16} />
            </button>
            {showShortcutHelp && (
                <div className={`absolute top-16 right-4 z-40 rounded-lg shadow-lg p-3 text-xs w-64 border ${shortcutsPanelClass}`}>
                    <div className="font-semibold text-gray-800 mb-2">Shortcuts</div>
                    <div>`?` toggle this panel</div>
                    <div>`Ctrl/Cmd+1` Builder tab</div>
                    <div>`Ctrl/Cmd+2` Code tab</div>
                    <div>`Ctrl/Cmd+3` Map Preview</div>
                    <div>`Ctrl/Cmd+4` Reference Map</div>
                    <div>`Ctrl/Cmd+5` Territory Library</div>
                    <div>`Ctrl/Cmd+;` Toggle xatra menu</div>
                    <div>`Ctrl/Cmd+Enter` Render map</div>
                    <div>`Ctrl/Cmd+Shift+Enter` Stop active preview generation</div>
                    <div>`Ctrl/Cmd+Space` Update active picker map tab</div>
                    <div>`Ctrl/Cmd+Shift+X` Import from existing map</div>
                    <div className="mt-2 pt-2 border-t border-gray-200">`Ctrl/Cmd+Shift+F` add Flag</div>
                    <div>`Ctrl/Cmd+Shift+R` add River</div>
                    <div>`Ctrl/Cmd+Shift+P` add Point</div>
                    <div>`Ctrl/Cmd+Shift+T` add Text</div>
                    <div>`Ctrl/Cmd+Shift+H` add Path</div>
                    <div>`Ctrl/Cmd+Shift+A` add Admin</div>
                    <div>`Ctrl/Cmd+Shift+D` add Data</div>
                    <div>`Ctrl/Cmd+Shift+B` add TitleBox</div>
                    <div>`Ctrl/Cmd+Shift+Y` add Python</div>
                </div>
            )}
            {activePicker && (activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context)) && (
                <div className="absolute inset-0 z-30 pointer-events-none flex items-center justify-center">
                    <div className="bg-amber-500 text-white px-6 py-4 rounded-lg shadow-2xl border-2 border-amber-600 font-semibold text-center max-w-md animate-pulse">
                        <div className="text-sm mb-1">Click map to add points</div>
                        <div className="text-xs font-normal opacity-95">
                            <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Backspace</kbd> undo last point
                            {' · '}
                            <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Ctrl/Cmd</kbd> hold + drag for freehand
                            {' · '}
                            <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Esc</kbd> finish
                        </div>
                    </div>
                </div>
            )}
            {activePicker && (activePicker.context === 'reference-gadm' || activePicker.context === 'territory-library') && (
                <div className="absolute inset-0 z-30 pointer-events-none flex items-start justify-center pt-8">
                    <div className="bg-amber-500 text-white px-6 py-4 rounded-lg shadow-2xl border-2 border-amber-600 font-semibold text-center max-w-2xl animate-pulse">
                        <div className="text-sm">
                          Click regions to toggle selection. Hold <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Ctrl/Cmd</kbd> and move to paint-select, hold <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Alt</kbd> and move to paint-unselect, press <kbd className="bg-amber-600 px-1.5 py-0.5 rounded">Esc</kbd> to stop picker mode.
                        </div>
                    </div>
                </div>
            )}
            {activePreviewTab === 'main' ? (
                <MapPreview html={mapHtml} loading={loadingByView.main} iframeRef={iframeRef} onStop={() => handleStop('main')} />
            ) : activePreviewTab === 'picker' ? (
                <MapPreview html={pickerHtml} loading={loadingByView.picker} iframeRef={pickerIframeRef} onStop={() => handleStop('picker')} />
            ) : (
                <MapPreview html={territoryLibraryHtml} loading={loadingByView.library} iframeRef={territoryLibraryIframeRef} onStop={() => handleStop('library')} />
            )}
        </div>
      </div>
      {importModalOpen && (
        <div className="fixed inset-0 bg-black/40 z-[100] flex items-center justify-center">
          <div className="w-[980px] max-w-[96vw] h-[84vh] bg-white rounded-lg border shadow-xl flex flex-col">
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <div className="font-semibold text-sm">Import from existing map</div>
              <button className="text-xs px-2 py-1 border rounded" onClick={() => setImportModalOpen(false)}>Close</button>
            </div>
            <div className="p-3 flex gap-2 border-b">
              <input
                ref={importSearchRef}
                value={hubQuery}
                onChange={(e) => setHubQuery(e.target.value)}
                placeholder='Search maps/themes/libs, e.g. "indica user:srajma"'
                className="flex-1 border rounded p-2 text-sm"
              />
              <button className="px-3 py-2 border rounded" onClick={searchHubRegistry}>Search</button>
            </div>
            {importLoading && <div className="mx-3 mt-2 text-xs px-2 py-1 border rounded bg-blue-50 text-blue-700 border-blue-200">Loading maps...</div>}
            <div className="px-3 py-2 border-b bg-gray-50">
              <div className="text-[11px] font-semibold mb-1 text-gray-700">Imported layers from maps/themes</div>
              <div className="flex flex-wrap gap-2">
                {IMPORTABLE_LAYER_TYPES.map((layer) => (
                  <label key={layer} className="text-[11px] inline-flex items-center gap-1 px-1.5 py-0.5 border rounded bg-white">
                    <input
                      type="checkbox"
                      checked={!!importLayerSelection[layer]}
                      onChange={(e) => setImportLayerSelection((prev) => ({ ...prev, [layer]: e.target.checked }))}
                    />
                    {layer}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex-1 overflow-auto p-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {(hubSearchResults || []).map((item) => renderImportCatalogCard(item))}
            </div>
          </div>
        </div>
      )}
      {mapDescriptionModalOpen && (
        <div className="fixed inset-0 bg-black/40 z-[110] flex items-center justify-center">
          <div className="w-[520px] max-w-[92vw] bg-white rounded-lg border shadow-xl">
            <div className="px-4 py-3 border-b">
              <div className="font-semibold text-sm">Map description</div>
            </div>
            <div className="p-4">
              <textarea
                autoFocus
                value={mapDescriptionDraft}
                onChange={(e) => setMapDescriptionDraft(e.target.value)}
                className="w-full min-h-[110px] border rounded p-2 text-sm"
                placeholder="Describe this map..."
              />
            </div>
            <div className="px-4 py-3 border-t flex justify-end gap-2">
              <button className="px-3 py-1.5 border rounded text-sm" onClick={() => { setMapDescriptionModalOpen(false); setPendingMapPublish(null); }}>Cancel</button>
              <button className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700" onClick={confirmMapPublish}>Save map</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
