import React, { useState, useEffect, useRef } from 'react';
import { Layers, Code, Play, Upload, Download, Image, Plus, Trash2, Keyboard, Copy, Check, Moon, Sun, Menu, Search, Compass, User, Users, LogIn, LogOut, FilePlus2, Import, Save, Triangle, GitFork, CloudUpload, UserX, Settings } from 'lucide-react';

// Components (defined inline for simplicity first, can be split later)
import Builder from './components/Builder';
import CodeEditor from './components/CodeEditor';
import MapPreview from './components/MapPreview';
import AutocompleteInput from './components/AutocompleteInput';
import { isPythonValue, getPythonExpr } from './utils/pythonValue';
import {
  DEFAULT_INDIC_IMPORT,
  DEFAULT_INDIC_IMPORT_CODE,
  createDefaultBuilderOptions,
  createDefaultBuilderElements,
} from './lib/editorDefaults';
import { API_BASE } from './config';
const HUB_NAME_RE = /^[a-z0-9_.]+$/;
const RESERVED_MAP_NAMES = new Set([
  'guest', 'admin', 'explore', 'users', 'login', 'logout', 'new-map', 'new_map',
  'map', 'lib', 'css', 'user', 'hub', 'auth', 'registry', 'render', 'sync',
  'health', 'stop', 'search', 'docs', 'redoc', 'openapi.json', 'favicon.ico',
]);
const FIXED_PY_IMPORTS = `import xatra
from xatra.loaders import gadm, naturalearth, polygon, overpass
from xatra.icon import Icon
from xatra.colorseq import Color, ColorSequence, LinearColorSequence
from matplotlib.colors import LinearSegmentedColormap`;
const DEFAULT_MAP_CODE = `xatra.BaseOption("Esri.WorldTopoMap", default=True)
xatra.Flag(label="India", value=gadm("IND"), note="Republic of India")
xatra.TitleBox("<b>My Map</b>")
`;
const IMPORTABLE_LAYER_TYPES = [
  'Flag', 'River', 'Path', 'Point', 'Text', 'Admin', 'AdminRivers', 'Dataframe',
  'TitleBox', 'Music', 'CSS', 'BaseOption', 'FlagColorSequence', 'AdminColorSequence',
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

const getApiErrorMessage = (payload, fallback = 'Request failed') => {
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object') {
    const msg = detail.message || detail.error || detail.detail;
    const retry = detail.retry_after_seconds;
    if (typeof msg === 'string' && msg.trim()) {
      if (typeof retry === 'number' && retry > 0) return `${msg} Try again in ${retry}s.`;
      return msg;
    }
  }
  if (typeof payload?.error === 'string' && payload.error.trim()) return payload.error;
  if (typeof payload?.message === 'string' && payload.message.trim()) return payload.message;
  return fallback;
};

const parsePath = (pathname) => {
  const parts = String(pathname || '/').split('/').filter(Boolean);
  if (parts.length === 0) return { page: 'editor' };
  if (parts[0] === 'new-map') return { page: 'editor', newMap: true };
  if (parts[0] === 'explore' || parts[0] === 'users') return { page: 'explore' };
  if (parts[0] === 'login') return { page: 'login' };
  // New: /user/{username} → profile
  if (parts[0] === 'user' && parts.length >= 2) return { page: 'profile', username: parts[1] };
  // Old format (backwards compat): /{username}/map/{name}[/{version}]
  if (parts.length >= 3 && parts[1] === 'map') {
    let version = 'alpha';
    if (parts[3] && /^v\d+$/i.test(parts[3])) version = parts[3].slice(1);
    else if (parts[3] && /^\d+$/.test(parts[3])) version = parts[3];
    else if (parts[3] && String(parts[3]).toLowerCase() === 'alpha') version = 'alpha';
    return { page: 'editor', owner: parts[0], map: parts[2], version };
  }
  // New format: /{name} or /{name}/{version}
  if (parts.length === 1) return { page: 'editor', map: parts[0], version: 'alpha' };
  if (parts.length === 2) {
    const v = parts[1];
    if (/^v\d+$/i.test(v)) return { page: 'editor', map: parts[0], version: v.slice(1) };
    if (v.toLowerCase() === 'alpha') return { page: 'editor', map: parts[0], version: 'alpha' };
  }
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
  const [newMapDialogOpen, setNewMapDialogOpen] = useState(false);
  const [newMapDialogName, setNewMapDialogName] = useState('');
  const [newMapDialogChecking, setNewMapDialogChecking] = useState(false);
  const [newMapDialogError, setNewMapDialogError] = useState('');
  const [forkDialogOpen, setForkDialogOpen] = useState(false);
  const [forkDialogName, setForkDialogName] = useState('');
  const [forkDialogChecking, setForkDialogChecking] = useState(false);
  const [forkDialogError, setForkDialogError] = useState('');
  const [publishV1WarnOpen, setPublishV1WarnOpen] = useState(false);
  const [publishV1WarnKind, setPublishV1WarnKind] = useState('map'); // 'map' | 'lib' | 'css'
  const [profileSettingsOpen, setProfileSettingsOpen] = useState(false);
  const [statusNotice, setStatusNotice] = useState('');
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ username: '', password: '', full_name: '' });
  const [currentUser, setCurrentUser] = useState({ is_authenticated: false, user: { username: 'guest', full_name: '', bio: '' } });
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
  const [disassociateConfirm, setDisassociateConfirm] = useState({ open: false, kind: 'map', name: '', nameInput: '', loading: false, error: null });
  // Auto-save state: 'idle' | 'unsaved' | 'saving' | 'saved' | 'conflict'
  const [autoSaveStatus, setAutoSaveStatus] = useState('idle');
  const autoSaveTimerRef = useRef(null);
  const lastAutoSavedContentRef = useRef(null);
  const lastRenderedThumbnailRef = useRef('');
  const editorReadyRef = useRef(false); // true after initial load phase; guards against spurious auto-saves on first render
  const [guestHasChanges, setGuestHasChanges] = useState(false);
  const [userDraftMeta, setUserDraftMeta] = useState(null); // null | { exists: bool, mapName?: string }
  const [promoteDraftDialogOpen, setPromoteDraftDialogOpen] = useState(false);
  const [promoteDraftName, setPromoteDraftName] = useState('');
  const [promoteDraftLoading, setPromoteDraftLoading] = useState(false);
  const [promoteDraftError, setPromoteDraftError] = useState('');
  // Publish status for library and theme: null | 'publishing' | 'published:v{n}' | 'no_changes' | 'error'
  const [libraryPublishStatus, setLibraryPublishStatus] = useState(null);
  const [themePublishStatus, setThemePublishStatus] = useState(null);

  // Sidebar resize state
  const [sidebarWidth, setSidebarWidth] = useState(500);
  const [sidebarDragging, setSidebarDragging] = useState(false);
  const sidebarResizingRef = useRef(false);
  const sidebarStartXRef = useRef(0);
  const sidebarStartWidthRef = useRef(500);

  // Builder State
  const [builderElements, setBuilderElements] = useState([
    ...createDefaultBuilderElements()
  ]);
  const [builderOptions, setBuilderOptions] = useState(createDefaultBuilderOptions);
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
  const [mapOwner, setMapOwner] = useState('guest');
  const [sourceMapRef, setSourceMapRef] = useState(null);
  const [forkedFrom, setForkedFrom] = useState(null);
  const [mapVotes, setMapVotes] = useState(0);
  const [mapUserVoted, setMapUserVoted] = useState(false);
  const [mapViews, setMapViews] = useState(0);
  const [importsCode, setImportsCode] = useState(DEFAULT_INDIC_IMPORT_CODE);
  const [hubImports, setHubImports] = useState([{ ...DEFAULT_INDIC_IMPORT }]);
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

${DEFAULT_MAP_CODE}
`);

  const [predefinedCode, setPredefinedCode] = useState(``);
  // Saved local alpha snapshots so switching back from a published version restores local edits
  const localPredefinedAlphaRef = useRef(null);
  const localThemeAlphaRef = useRef(null);

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
  const topBarRef = useRef(null);
  const importSearchRef = useRef(null);
  const importGridRef = useRef(null);
  const menuOpenRef = useRef(false);
  const menuFocusIndexRef = useRef(0);
  const librarySubTabsRef = useRef(null);
  const editorInitKeyRef = useRef('');

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
  const normalizedHubUsername = String(currentUser?.user?.username || 'guest').trim().toLowerCase() || 'guest';
  const viewedMapVersion = String(route?.version || 'alpha');
  const isMapAuthor = !!(currentUser.is_authenticated && normalizedHubUsername === mapOwner);
  const hasLikedMap = isMapAuthor || mapUserVoted;
  const isReadOnlyMap = !!(route.map) && (!isMapAuthor || viewedMapVersion !== 'alpha');
  const showMapMetaLine = !!(route.map) || currentUser.is_authenticated;
  const editorContextReady = route.page !== 'editor' || !!route.map || authReady;

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
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const resp = await apiFetch('/auth/me');
        const data = await resp.json();
        if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load session state'));
        setCurrentUser(data);
        setAuthReady(true);
        return;
      } catch (err) {
        lastError = err;
        if (attempt < 2) {
          // Short retry for transient backend/reload blips in dev.
          await new Promise((resolve) => setTimeout(resolve, 250));
        }
      }
    }
    setError(lastError?.message || 'Failed to load session state');
    setAuthReady(true);
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
          const resp = await apiFetch(`/hub/${kind}/${normalizedMapName}`);
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
      () => (currentUser.is_authenticated ? window.open(`/user/${normalizedHubUsername}`, '_blank') : navigateTo('/login')),
      () => handleNewMapClick(),
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
    return `/${entry.kind}/${entry.name}/${v}`;
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
    const HUB_KINDS_SET = new Set(['lib', 'map', 'css']);
    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.includes('xatrahub(')) return;
      const assignMatch = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*xatrahub\(\s*["']([^"']+)["']/);
      const callMatch = trimmed.match(/^xatrahub\(\s*["']([^"']+)["']/);
      const path = assignMatch?.[2] || callMatch?.[1];
      if (!path) return;
      const parts = path.split('/').filter(Boolean);
      let kind, name, username, selectedVersion;
      if (parts.length >= 2 && HUB_KINDS_SET.has(parts[0])) {
        // New format: /kind/name[/version]
        kind = parts[0];
        name = parts[1];
        username = null;
        selectedVersion = parts[2] || 'alpha';
      } else if (parts.length >= 3) {
        // Old format: /username/kind/name[/version]
        username = parts[0];
        kind = parts[1];
        name = parts[2];
        selectedVersion = parts[3] || 'alpha';
      } else {
        return;
      }
      const canonicalPath = `/${kind}/${name}/${selectedVersion}`;
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
        username,
        name,
        path: canonicalPath,
        selected_version: selectedVersion,
        _draft_version: selectedVersion,
        alias: assignMatch?.[1] || '',
        filter_not: filterNot,
      });
    });
    return items;
  };

  const ensureDefaultIndicImport = (items) => {
    const list = Array.isArray(items) ? [...items] : [];
    const exists = list.some((imp) => imp.kind === 'lib' && imp.name === 'dtl');
    if (!exists) list.unshift({ ...DEFAULT_INDIC_IMPORT });
    return list;
  };

  const getImportVersionOptions = ({ username, kind, name }) => {
    const v = artifactVersionOptions[artifactKey(username, kind, name)];
    if (v === null) return [];
    return v || [{ value: 'alpha', label: 'alpha' }];
  };

  const buildHubMetadata = (kind) => ({
    kind,
    map_name: normalizedMapName,
    username: normalizedHubUsername,
    updated_from: activeTab,
    ...(kind === 'map' && lastRenderedThumbnailRef.current ? { thumbnail: lastRenderedThumbnailRef.current } : {}),
  });

  const publishHubArtifact = async (kind, content, opts = {}) => {
    const owner = opts.owner || normalizedHubUsername;
    const targetName = opts.name || normalizedMapName;
    if (!HUB_NAME_RE.test(targetName)) {
      throw new Error('Map name must contain only lowercase letters, numerals, underscores, and dots.');
    }
    const response = await apiFetch(`/hub/${owner}/${kind}/${targetName}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        metadata: {
          ...buildHubMetadata(kind),
          forked_from: sourceMapRef,
        },
      }),
    });
    const data = await response.json();
    if (!response.ok || data.detail || data.error) {
      throw new Error(getApiErrorMessage(data, 'Failed to publish artifact'));
    }
    const latest = data.latest_published_version;
    const publishedVersion = data?.published?.version ?? latest ?? null;
    if (kind === 'map') setMapVersionLabel(publishedVersion || 'alpha');
    if (kind === 'lib') {
      setLibraryVersionLabel(latest || 'alpha');
      setSelectedLibraryVersion('alpha');
      const status = data.no_changes ? 'no_changes' : `published:v${latest}`;
      setLibraryPublishStatus(status);
      setTimeout(() => setLibraryPublishStatus(null), 3000);
      // Force-refresh version options (bypass cache)
      ensureArtifactVersions(owner, targetName, 'lib', true);
    }
    if (kind === 'css') {
      setThemeVersionLabel(latest || 'alpha');
      setSelectedThemeVersion('alpha');
      const status = data.no_changes ? 'no_changes' : `published:v${latest}`;
      setThemePublishStatus(status);
      setTimeout(() => setThemePublishStatus(null), 3000);
      // Force-refresh version options (bypass cache)
      ensureArtifactVersions(owner, targetName, 'css', true);
    }
    if (kind === 'map') {
      setMapOwner(owner);
      setMapName(targetName);
      const publishedLabel = Number(publishedVersion ?? latest ?? 1) || 1;
      setStatusNotice(data.no_changes ? 'No changes' : `Published v${publishedLabel}`);
      // Force-refresh version options (bypass cache)
      ensureArtifactVersions(owner, targetName, 'map', true);
      ensureArtifactVersions(owner, targetName, 'lib', true);
      ensureArtifactVersions(owner, targetName, 'css', true);
      navigateTo(`/${targetName}`);
      setTimeout(() => setStatusNotice(''), 5000);
    }
    return data;
  };

  const addHubImportLine = async (item) => {
    if (!item || !item.name || !item.kind) return;
    const key = artifactKey(item.username || '', item.kind, item.name);
    const options = artifactVersionOptions[key] || [{ value: (item.latest_version ? String(item.latest_version) : 'alpha'), label: item.latest_version ? `v${item.latest_version}` : 'alpha' }];
    const selectedVersion = importVersionDraft[key] || (options[0]?.value || 'alpha');
    const path = `/${item.kind}/${item.name}/${selectedVersion}`;
    try {
      const verifyResp = await apiFetch(`/hub/${item.kind}/${item.name}`);
      if (!verifyResp.ok) {
        setError(`Cannot import ${item.kind}: /${item.kind}/${item.name} does not exist.`);
        return;
      }
    } catch (err) {
      setError(`Cannot import ${item.kind}: ${err.message}`);
      return;
    }
    const exists = (hubImports || []).some((imp) => imp.kind === item.kind && imp.name === item.name);
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

  const ensureArtifactVersions = async (username, name, kind, force = false) => {
    const key = artifactKey(username, kind, name);
    if (!force && artifactVersionOptions[key] !== undefined) return artifactVersionOptions[key];
    try {
      const resp = await apiFetch(`/hub/${kind}/${name}`);
      if (!resp.ok) {
        setArtifactVersionOptions((prev) => ({ ...prev, [key]: null }));
        return null;
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
    // Only eagerly load map versions; lib/css are loaded lazily when the import modal opens
    (hubSearchResults || []).forEach((item) => {
      ensureArtifactVersions(item.username, item.name, 'map');
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubSearchResults]);

  useEffect(() => {
    // When import modal opens, also load lib/css version info (deferred to avoid 404 noise on explore)
    if (!importModalOpen) return;
    (hubSearchResults || []).forEach((item) => {
      ensureArtifactVersions(item.username, item.name, 'css');
      ensureArtifactVersions(item.username, item.name, 'lib');
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importModalOpen, hubSearchResults]);

  useEffect(() => {
    if (!mapOwner || !route.map || !HUB_NAME_RE.test(route.map)) return;
    ensureArtifactVersions(mapOwner, route.map, 'map');
    ensureArtifactVersions(mapOwner, route.map, 'css');
    ensureArtifactVersions(mapOwner, route.map, 'lib');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapOwner, route.map]);

  const loadMapFromHub = async (owner, name, version = 'alpha') => {
    setAutoSaveStatus('idle');
    lastAutoSavedContentRef.current = null;
    setForkedFrom(null);
    try {
      const endpoint = owner
        ? `/maps/${owner}/${name}?version=${encodeURIComponent(version || 'alpha')}`
        : `/maps/${name}?version=${encodeURIComponent(version || 'alpha')}`;
      const resp = await apiFetch(endpoint);
      const data = await resp.json();
      if (!resp.ok) {
        // If the map doesn't exist yet and the user is creating their own new map, initialize with defaults
        const isOwner = currentUser.is_authenticated && (owner === null || owner === currentUser?.user?.username);
        if (resp.status === 404 && isOwner && version === 'alpha') {
          const defElements = createDefaultBuilderElements();
          const defOptions = createDefaultBuilderOptions();
          const defaultImports = [{ ...DEFAULT_INDIC_IMPORT }];
          const defaultImportsCode = serializeHubImports(defaultImports);
          setMapName(name);
          setMapOwner(currentUser?.user?.username || owner || 'guest');
          setBuilderElements(defElements);
          setBuilderOptions(defOptions);
          setCode(DEFAULT_MAP_CODE);
          setThemeCode('');
          setRuntimeCode('');
          setPredefinedCode('');
          setHubImports(defaultImports);
          setImportsCode(defaultImportsCode);
          renderMapWithData({
            elements: defElements,
            options: defOptions,
            mapCode: DEFAULT_MAP_CODE,
            predCode: '',
            importsCode: defaultImportsCode,
            themeCode: '',
            runtimeCode: '',
          });
          return;
        }
        if (resp.status === 404) {
          navigateTo('/explore');
          return;
        }
        throw new Error(getApiErrorMessage(data, 'Failed to load map'));
      }
      const content = typeof data.content === 'string' ? data.content : '';
      const parsed = (() => {
        try { return JSON.parse(content || '{}'); } catch { return null; }
      })();
      if (parsed && typeof parsed === 'object') {
        setImportsCode(parsed.imports_code || '');
        setHubImports(parseImportsCodeToItems(parsed.imports_code || ''));
        setThemeCode(parsed.theme_code || '');
        setPredefinedCode(parsed.predefined_code ?? '');
        setCode(parsed.map_code ?? '');
        setRuntimeCode(parsed.runtime_code ?? '');
        if (parsed.project && parsed.project.elements && parsed.project.options) {
          setBuilderElements(parsed.project.elements);
          setBuilderOptions(parsed.project.options);
        }
        if (parsed.picker_options && typeof parsed.picker_options === 'object') {
          setPickerOptions(parsed.picker_options);
        }
      }
      const actualOwner = data.username || owner || 'guest';
      setMapName(name);
      setMapOwner(actualOwner);
      setMapUserVoted(false);
      // Trigger initial render with fresh data (state updates are async, so pass data directly)
      if (parsed?.project?.elements && parsed?.project?.options) {
        renderMapWithData({
          elements: parsed.project.elements,
          options: parsed.project.options,
          mapCode: parsed.map_code || '',
          predCode: parsed.predefined_code || '',
          importsCode: parsed.imports_code || '',
          themeCode: parsed.theme_code || '',
          runtimeCode: parsed.runtime_code || '',
        });
      }
      setSourceMapRef(`/${name}`);
      // Update URL to canonical form if loaded via old-format URL
      if (owner) {
        const canonicalUrl = `/${name}${version !== 'alpha' ? `/v${version}` : ''}`;
        if (window.location.pathname !== canonicalUrl) {
          window.history.replaceState({}, '', canonicalUrl);
        }
      }
      const viewResp = await apiFetch(`/maps/${actualOwner}/${name}/view`, { method: 'POST' });
      const viewData = await viewResp.json();
      if (viewResp.ok) setMapViews(Number(viewData.views || 0));
      setMapVotes(Number(data.votes || 0));
      setMapUserVoted(!!data.viewer_voted);
      const artifactResp = await apiFetch(`/hub/map/${name}`);
      const artifactData = await artifactResp.json();
      if (artifactResp.ok) {
        setMapVotes(Number(artifactData.votes || 0));
        setMapViews(Number(artifactData.views || 0));
        setMapUserVoted(!!artifactData.viewer_voted);
        setMapVersionLabel(version === 'alpha' ? 'alpha' : String(version));
        const forkSrc = artifactData?.alpha?.metadata?.forked_from;
        setForkedFrom(forkSrc ? String(forkSrc) : null);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const loadDraft = async () => {
    try {
      const resp = await apiFetch('/draft/current');
      const data = await resp.json();
      if (!resp.ok || !data.exists || !data.draft) return false;
      const draft = data.draft;
      if (draft.map_name && HUB_NAME_RE.test(draft.map_name)) setMapName(draft.map_name);
      if (draft.project?.elements && draft.project?.options) {
        setBuilderElements(draft.project.elements);
        setBuilderOptions(draft.project.options);
      }
      if (typeof draft.project?.code === 'string') setCode(draft.project.code);
      if (typeof draft.project?.predefinedCode === 'string') setPredefinedCode(draft.project.predefinedCode);
      if (typeof draft.project?.importsCode === 'string') {
        const parsedImports = parseImportsCodeToItems(draft.project.importsCode);
        const safeImports = parsedImports.length ? parsedImports : ensureDefaultIndicImport(parsedImports);
        setHubImports(safeImports);
        setImportsCode(serializeHubImports(safeImports));
      }
      if (typeof draft.project?.themeCode === 'string') setThemeCode(draft.project.themeCode);
      if (typeof draft.project?.runtimeCode === 'string') setRuntimeCode(draft.project.runtimeCode);
      if (draft.project?.pickerOptions && typeof draft.project.pickerOptions === 'object') {
        setPickerOptions(draft.project.pickerOptions);
      }
      // Trigger initial render with the draft data (state updates are async, so pass data directly)
      if (draft.project?.elements && draft.project?.options) {
        renderMapWithData({
          elements: draft.project.elements,
          options: draft.project.options,
          mapCode: draft.project.code || '',
          predCode: draft.project.predefinedCode || '',
          importsCode: draft.project.importsCode || '',
          themeCode: draft.project.themeCode || '',
          runtimeCode: draft.project.runtimeCode || '',
        });
      }
      return true;
    } catch {
      return false;
    }
  };

  useEffect(() => {
    // Guest-only draft persistence. Logged-in users should not mutate their stored unsaved draft.
    if (!editorReadyRef.current || currentUser.is_authenticated) return;
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
            pickerOptions,
          },
        }),
      }).catch(() => {});
    }, 800);
    return () => clearTimeout(t);
  }, [normalizedMapName, builderElements, builderOptions, code, predefinedCode, importsCode, themeCode, runtimeCode, pickerOptions, currentUser.is_authenticated]);

  const loadExplore = async (page = 1, query = exploreQuery) => {
    setExploreLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '12', q: query || '' });
      const resp = await apiFetch(`/explore?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load explore'));
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
      const params = new URLSearchParams({ page: String(page), per_page: '12', q: query || '' });
      const resp = await apiFetch(`/users/${username}?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load profile'));
      setProfileData(data);
      setProfileEdit({ full_name: data?.profile?.full_name || '', bio: data?.profile?.bio || '' });
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileLoading(false);
    }
  };

  const loadUserDraftMeta = async () => {
    try {
      const resp = await apiFetch('/draft/current');
      const data = await resp.json();
      if (data.exists && data.draft) {
        setUserDraftMeta({ exists: true, mapName: data.draft.map_name || 'new_map' });
      } else {
        setUserDraftMeta({ exists: false });
      }
    } catch {
      setUserDraftMeta({ exists: false });
    }
  };

  const loadUsers = async (page = 1, query = usersQuery) => {
    setUsersLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '20', q: query || '' });
      const resp = await apiFetch(`/users?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load users'));
      setUsersData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setUsersLoading(false);
    }
  };

  const applyNewMapDefaults = (opts = {}) => {
    const nextName = opts.name && HUB_NAME_RE.test(opts.name) ? opts.name : 'new_map';
    const nextOwner = opts.owner || (currentUser.is_authenticated ? normalizedHubUsername : 'guest');
    const defElements = createDefaultBuilderElements();
    const defOptions = createDefaultBuilderOptions();
    const defaults = [{ ...DEFAULT_INDIC_IMPORT }];
    const defaultImportsCode = serializeHubImports(defaults);

    setMapOwner(nextOwner);
    setMapName(nextName);
    setBuilderElements(defElements);
    setBuilderOptions(defOptions);
    setCode(DEFAULT_MAP_CODE);
    setThemeCode('');
    setRuntimeCode('');
    setPredefinedCode('');
    setHubImports(defaults);
    setImportsCode(defaultImportsCode);
    setActiveTab('builder');
    setStatusNotice('');
    setAutoSaveStatus('idle');
    lastAutoSavedContentRef.current = null;
    setForkedFrom(null);

    renderMapWithData({
      elements: defElements,
      options: defOptions,
      mapCode: DEFAULT_MAP_CODE,
      predCode: '',
      importsCode: defaultImportsCode,
      themeCode: '',
      runtimeCode: '',
    });
  };

  const handleNewMapClick = () => {
    if (!currentUser.is_authenticated) {
      navigateTo('/login');
      return;
    }
    setNewMapDialogName('');
    setNewMapDialogError('');
    setNewMapDialogChecking(false);
    setNewMapDialogOpen(true);
  };

  const handleNewMapConfirm = async () => {
    const name = String(newMapDialogName || '').trim().toLowerCase();
    if (!name || !HUB_NAME_RE.test(name)) return;
    if (RESERVED_MAP_NAMES.has(name)) {
      setNewMapDialogError(`'${name}' is a reserved name and cannot be used for a map.`);
      return;
    }
    setNewMapDialogChecking(true);
    setNewMapDialogError('');
    try {
      const resp = await apiFetch(`/hub/map/${name}`);
      if (resp.ok) {
        setNewMapDialogError(`Map '${name}' already exists. Choose a different name.`);
        return;
      }
      if (resp.status !== 404) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(getApiErrorMessage(data, 'Failed to validate map name'));
      }
      setNewMapDialogOpen(false);
      applyNewMapDefaults({ name, owner: normalizedHubUsername });
      navigateTo(`/${name}`);
    } catch (err) {
      setNewMapDialogError(err.message || 'Failed to validate map name');
    } finally {
      setNewMapDialogChecking(false);
    }
  };

  const handlePromoteDraft = async () => {
    if (!HUB_NAME_RE.test(promoteDraftName)) return;
    setPromoteDraftLoading(true);
    setPromoteDraftError('');
    try {
      const resp = await apiFetch('/draft/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: promoteDraftName }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to save map'));
      setPromoteDraftDialogOpen(false);
      setUserDraftMeta({ exists: false });
      navigateTo(`/${promoteDraftName}`);
    } catch (err) {
      setPromoteDraftError(err.message);
    } finally {
      setPromoteDraftLoading(false);
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
    if (route.page === 'explore') { loadExplore(explorePage, exploreQuery); loadUsers(usersPage, usersQuery); }
    if (route.page === 'profile') loadProfile(route.username, profilePage, profileSearch);
    // Reset editor init key when leaving editor so re-entry always reloads draft
    if (route.page !== 'editor') { editorInitKeyRef.current = ''; return; }
    if (route.page === 'editor' && route.map) {
      editorInitKeyRef.current = '';
      if (route.owner) setMapOwner(route.owner);
      loadMapFromHub(route.owner || null, route.map, route.version || 'alpha');
      return;
    }
    if (route.page === 'editor' && !route.map) {
      if (!authReady) return;
      // Logged-in users never edit a draft — redirect to explore
      if (currentUser.is_authenticated) {
        navigateTo('/explore');
        return;
      }
      // Guest-only draft editor flow
      const initKey = `draft:guest`;
      if (editorInitKeyRef.current === initKey) return;
      editorInitKeyRef.current = initKey;
      setMapOwner('guest');
      // Load draft; don't call /maps/default-name afterwards (it would overwrite the draft's map name)
      (async () => {
        const hasDraft = await loadDraft();
        if (!hasDraft) {
          // Guest with no draft: set a default map name and render default
          apiFetch('/maps/default-name').then((r) => r.json()).then((d) => {
            if (d?.name && HUB_NAME_RE.test(d.name)) setMapName(d.name);
          }).catch(() => {});
          renderMap();
        }
      })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.page, route.owner, route.map, route.version, route.newMap, authReady, currentUser.is_authenticated, normalizedHubUsername]);

  useEffect(() => {
    if (route.page === 'explore' && currentUser.is_authenticated && authReady) {
      loadProfile(normalizedHubUsername, 1, '');
      loadUserDraftMeta();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.page, currentUser.is_authenticated, authReady, normalizedHubUsername]);

  useEffect(() => {
    if (route.page === 'profile' && currentUser.is_authenticated && authReady && route.username === normalizedHubUsername) {
      loadUserDraftMeta();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.page, route.username, currentUser.is_authenticated, authReady, normalizedHubUsername]);

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
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Authentication failed'));
      await loadMe();
      navigateTo('/explore');
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
    if (!mapOwner || !route.map) return;
    try {
      const resp = await apiFetch(`/maps/${mapOwner}/${route.map}/vote`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Vote failed'));
      setMapVotes(Number(data.votes || 0));
      setMapUserVoted(!!data.voted);
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
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to save profile'));
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
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to update password'));
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
          setBuilderElements((prev) => {
            const next = [...prev];
            const el = next[idx];
            if (!el) return prev;
            if (el.type === 'point' || el.type === 'text') {
              const pt = points.length ? points[points.length - 1] : null;
              next[idx] = { ...el, value: pt ? JSON.stringify(pt) : '' };
            } else {
              next[idx] = { ...el, value: JSON.stringify(points) };
            }
            return next;
          });
      } else if (isTerritoryPolygonPicker(activePicker.context)) {
          const parentId = parseInt(activePicker.context.replace('territory-', ''), 10);
          if (Number.isNaN(parentId)) return;
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
          setBuilderElements((prev) => {
            const next = [...prev];
            const el = next[parentId];
            if (!el || el.type !== 'flag' || !Array.isArray(el.value)) return prev;
            next[parentId] = { ...el, value: setPartAtPath(el.value, path) };
            return next;
          });
      }
  };

  useEffect(() => {
    const handleMessage = (event) => {
      // Only accept messages from our srcdoc iframes (null origin) or same origin
      if (event.origin !== 'null' && event.origin !== window.location.origin) return;
      const allowedSources = [
        iframeRef.current?.contentWindow,
        pickerIframeRef.current?.contentWindow,
        territoryLibraryIframeRef.current?.contentWindow,
      ].filter(Boolean);
      if (allowedSources.length > 0 && !allowedSources.includes(event.source)) return;
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
          const isFreehandEligible = !!(
            activePicker &&
            (activePicker.type === 'path' || activePicker.type === 'polygon') &&
            (activePicker.context === 'layer' || isTerritoryPolygonPicker(activePicker.context))
          );
          if (isFreehandEligible && modifierPressed && isMouseDown) {
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
          // Forward modifier+key combos to the global shortcut handler via synthetic event
          if ((event.data.ctrlKey || event.data.metaKey) && key !== 'Control' && key !== 'Meta') {
            window.dispatchEvent(new KeyboardEvent('keydown', {
              key: key,
              ctrlKey: !!event.data.ctrlKey,
              metaKey: !!event.data.metaKey,
              shiftKey: !!event.data.shiftKey,
              altKey: !!event.data.altKey,
              bubbles: true,
            }));
            return;
          }
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
              const rawName = String(data.name);
              // Prefix with the library alias when picking from a hub library tab
              const libConfig = activeLibraryConfigRef.current;
              const libAlias = libConfig?.source === 'hub' ? (libConfig?.alias || '') : '';
              const name = libAlias ? `${libAlias}.${rawName}` : rawName;
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
  }, [activePreviewTab, activePicker, freehandModifierPressed, isMouseDown, referencePickTarget]);

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
          const res = await fetch(`${API_BASE}/gadm/levels?country=${encodeURIComponent(country)}`);
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
    // Strip any library prefix (e.g. "indic.KURU" → "KURU") so the map can match by raw name
    const rawNames = pickedTerritorySelection.map((n) => {
      const dotIdx = n.indexOf('.');
      return dotIdx >= 0 ? n.slice(dotIdx + 1) : n;
    });
    const groups = [
      ...(rawNames.length ? [{ op: 'pending', names: rawNames }] : []),
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
      setIsMouseDown(false);
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
      if (e.key === 'Escape' && publishV1WarnOpen) {
        e.preventDefault();
        setPublishV1WarnOpen(false);
        return;
      }
      if (e.key === 'Escape' && newMapDialogOpen) {
        e.preventDefault();
        setNewMapDialogOpen(false);
        return;
      }
      if (e.key === 'Escape' && forkDialogOpen) {
        e.preventDefault();
        setForkDialogOpen(false);
        return;
      }
      if (e.key === 'Escape' && promoteDraftDialogOpen) {
        e.preventDefault();
        setPromoteDraftDialogOpen(false);
        return;
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
      } else if (isMeta && e.key === '0') {
        e.preventDefault();
        setActivePreviewTab('library');
        setTimeout(() => {
          const firstBtn = librarySubTabsRef.current?.querySelector('button');
          if (firstBtn) firstBtn.focus();
        }, 50);
      } else if (isMeta && e.key === ';') {
        e.preventDefault();
        // Focus the top bar so the user can tab through it
        const firstFocusable = topBarRef.current?.querySelector('button, a, [tabindex]');
        if (firstFocusable) firstFocusable.focus();
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
          m: 'music',
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
  }, [activeTab, code, predefinedCode, builderElements, builderOptions, activePreviewTab, territoryLibrarySource, activePicker, referencePickTarget, publishV1WarnOpen, newMapDialogOpen, forkDialogOpen, promoteDraftDialogOpen, importModalOpen]);

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
          const response = await fetch(`${API_BASE}/render/picker`, {
              method: 'POST',
              credentials: 'include',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
          });
          const data = await response.json();
          if (!response.ok || data.error) {
              throw new Error(getApiErrorMessage(data, 'Failed to render picker preview'));
          }
          if (data.html) setPickerHtml(data.html);
      } catch (err) {
          setError(err.message);
      } finally {
          if (showLoading) setLoadingByView((prev) => ({ ...prev, picker: false }));
      }
  };

  const dedupeNames = (values) => (
    Array.from(new Set((values || []).map((v) => String(v || '').trim()).filter(Boolean)))
  );

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
              throw new Error(getApiErrorMessage(data, 'Failed to load territory catalog'));
          }
          const names = dedupeNames(Array.isArray(data.names) ? data.names : []);
          const indexNames = dedupeNames(Array.isArray(data.index_names) ? data.index_names : []);
          setTerritoryLibraryNames(names);
          setSelectedTerritoryNames((prev) => {
            const prevDeduped = dedupeNames(prev);
            if (prevDeduped.length && prevDeduped.some((name) => names.includes(name))) {
              return prevDeduped.filter((name) => names.includes(name));
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
          if (!response.ok || data.error) {
              setError(getApiErrorMessage(data, 'Failed to render territory library'));
          } else if (data.html) {
              setTerritoryLibraryHtml(injectTerritoryLabelOverlayPatch(data.html));
              const names = dedupeNames(Array.isArray(data.available_names) ? data.available_names : []);
              if (names.length) setTerritoryLibraryNames(names);
          }
      } catch (err) {
          setError(err.message);
      } finally {
          if (showLoading) setLoadingByView((prev) => ({ ...prev, library: false }));
      }
  };

  const renderMapWithData = async ({ elements, options, mapCode, predCode, importsCode: iCode, themeCode: tCode, runtimeCode: rCode }) => {
    setActivePreviewTab('main');
    setLoadingByView((prev) => ({ ...prev, main: true }));
    setError(null);
    try {
      const endpoint = '/render/builder';
      const body = { elements, options, predefined_code: predCode || undefined, imports_code: iCode || undefined, theme_code: tCode || undefined, runtime_code: rCode || undefined };
      const response = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        setError(getApiErrorMessage(data, 'Failed to render map'));
        console.error(data.traceback);
      } else if (typeof data.html === 'string' && data.html) {
        setMapHtml(injectThumbnailCapture(data.html));
        setMapPayload(data.payload);
      } else {
        setError('Render completed but returned no HTML.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingByView((prev) => ({ ...prev, main: false }));
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
      if (!response.ok || data.error) {
        setError(getApiErrorMessage(data, 'Failed to render map'));
        console.error(data.traceback);
      } else if (typeof data.html === 'string' && data.html) {
        setMapHtml(injectThumbnailCapture(data.html));
        setMapPayload(data.payload);
      } else {
        setError('Render completed but returned no HTML.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingByView((prev) => ({ ...prev, main: false }));
      setMainRenderTask(null);
    }
  };

  // Inject a postMessage listener into rendered HTML so the sandboxed iframe can
  // respond to thumbnail capture requests (contentDocument is inaccessible without allow-same-origin).
  const injectThumbnailCapture = (html) => {
    const script = `<script>
window.addEventListener('message', function(e) {
  if (e.source !== parent) return;
  if (!e.data || e.data.type !== 'xatra_request_thumbnail') return;
  var targetOrigin = (e.origin && e.origin !== 'null') ? e.origin : '*';
  try {
    var mapEl = document.querySelector('.leaflet-container');
    var svgEl = mapEl ? mapEl.querySelector('svg') : null;
    if (!svgEl) { parent.postMessage({ type: 'xatra_thumbnail_response', svg: null }, targetOrigin); return; }
    var w = mapEl.clientWidth || 1;
    var h = mapEl.clientHeight || 1;

    // Leaflet positions the SVG via CSS translate3d, and the map pane also has a pan offset.
    // We must account for both to produce the correct viewBox for the visible area.
    function getTranslate(el) {
      var t = el ? (el.style.transform || '') : '';
      var m = t.match(/translate3d\\((-?[\\d.]+)px,\\s*(-?[\\d.]+)px/);
      return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0];
    }
    var paneEl = mapEl.querySelector('.leaflet-map-pane');
    var pane = getTranslate(paneEl);  // pan offset [A, B]
    var svgT = getTranslate(svgEl);   // pixel-origin offset [C, D]
    // Screen (0,0) = path coordinate (-A-C, -B-D)
    var vbX = -(pane[0] + svgT[0]);
    var vbY = -(pane[1] + svgT[1]);

    var clone = svgEl.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(w));
    clone.setAttribute('height', String(h));
    clone.setAttribute('viewBox', vbX + ' ' + vbY + ' ' + w + ' ' + h);
    clone.style.transform = '';  // strip the CSS transform — viewBox handles positioning now
    var svg = new XMLSerializer().serializeToString(clone);
    parent.postMessage({ type: 'xatra_thumbnail_response', svg: svg, width: w, height: h }, targetOrigin);
  } catch(err) {
    parent.postMessage({ type: 'xatra_thumbnail_response', svg: null }, targetOrigin);
  }
});<\/script>`;
    return html.includes('</body>') ? html.replace('</body>', script + '</body>') : html + script;
  };

  const captureMapThumbnail = async () => {
    try {
      const iframe = iframeRef.current;
      if (!iframe?.contentWindow) return '';
      // The iframe is sandboxed without allow-same-origin, so contentDocument is inaccessible.
      // Use postMessage to ask the iframe to serialize its own SVG and send it back.
      const svgData = await new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(null), 3000);
        const handler = (event) => {
          if (event.source !== iframe.contentWindow) return;
          if (event.origin !== 'null' && event.origin !== window.location.origin) return;
          if (event.data?.type === 'xatra_thumbnail_response') {
            clearTimeout(timeout);
            window.removeEventListener('message', handler);
            resolve(event.data);
          }
        };
        window.addEventListener('message', handler);
        iframe.contentWindow.postMessage({ type: 'xatra_request_thumbnail' }, '*');
      });
      if (!svgData?.svg) return '';
      const { svg, width: srcW, height: srcH } = svgData;
      const targetW = 480;
      const targetH = 270;
      const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      try {
        const img = await new Promise((resolve, reject) => {
          const nextImg = new window.Image();
          nextImg.onload = () => resolve(nextImg);
          nextImg.onerror = reject;
          nextImg.src = url;
        });
        const canvas = document.createElement('canvas');
        canvas.width = targetW;
        canvas.height = targetH;
        const ctx = canvas.getContext('2d');
        if (!ctx) return '';
        ctx.fillStyle = isDarkMode ? '#0f172a' : '#f8fafc';
        ctx.fillRect(0, 0, targetW, targetH);
        ctx.drawImage(img, 0, 0, srcW, srcH, 0, 0, targetW, targetH);
        return canvas.toDataURL('image/jpeg', 0.78);
      } finally {
        URL.revokeObjectURL(url);
      }
    } catch {
      return '';
    }
  };

  const ensureLatestThumbnail = async () => {
    if (!mapHtml) return;
    const dataUrl = await captureMapThumbnail();
    if (dataUrl) {
      lastRenderedThumbnailRef.current = dataUrl;
    }
  };

  useEffect(() => {
    if (!mapHtml) {
      lastRenderedThumbnailRef.current = '';
      return;
    }
    const timer = window.setTimeout(async () => {
      const dataUrl = await captureMapThumbnail();
      if (dataUrl) lastRenderedThumbnailRef.current = dataUrl;
    }, 200);
    return () => window.clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapHtml, isDarkMode]);

  const downloadFile = (content, filename, contentType) => {
    const a = document.createElement("a");
    const file = new Blob([content], {type: contentType});
    a.href = URL.createObjectURL(file);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 0);
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
      picker_options: pickerOptions,
      project: projectPayload,
    });
  };

  const performAutoSave = async (content) => {
    if (!currentUser.is_authenticated || isReadOnlyMap || !normalizedMapName) return;
    if (!HUB_NAME_RE.test(normalizedMapName)) return;
    setAutoSaveStatus('saving');
    try {
      await ensureLatestThumbnail();
      // Only flag conflict when the user has renamed the map to something that already exists
      // (i.e. route.map is set — an existing map was loaded — but mapName was changed to something different)
      const isRename = !!(route.map && route.map !== normalizedMapName);
      if (isRename) {
        const check = await apiFetch(`/hub/map/${normalizedMapName}`);
        if (check.ok) {
          setAutoSaveStatus('conflict');
          return;
        }
        // If the old map has no published versions, rename it in-place instead of creating a new one
        const oldVersionOpts = await ensureArtifactVersions(normalizedHubUsername, route.map, 'map');
        const oldHasPublished = Array.isArray(oldVersionOpts) && oldVersionOpts.some((o) => o.value !== 'alpha');
        if (!oldHasPublished) {
          const renameResp = await apiFetch(`/hub/${normalizedHubUsername}/map/${route.map}/rename`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: normalizedMapName }),
          });
          if (!renameResp.ok) {
            const d = await renameResp.json().catch(() => ({}));
            const detailMsg = getApiErrorMessage(d, '');
            if (detailMsg.includes('already exists') || detailMsg.includes('conflict')) {
              setAutoSaveStatus('conflict');
            } else {
              setAutoSaveStatus('unsaved');
            }
            return;
          }
          // Also rename lib/css if they exist (alpha-only, same name as old map)
          await apiFetch(`/hub/${normalizedHubUsername}/lib/${route.map}/rename`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: normalizedMapName }),
          }).catch(() => {}); // ignore if lib doesn't exist
          await apiFetch(`/hub/${normalizedHubUsername}/css/${route.map}/rename`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: normalizedMapName }),
          }).catch(() => {}); // ignore if css doesn't exist
          // Fall through to save content under the new name
        }
      }
      const resp = await apiFetch(`/hub/${normalizedHubUsername}/map/${normalizedMapName}/alpha`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          metadata: {
            owner: normalizedHubUsername,
            updated_at: new Date().toISOString(),
            thumbnail: lastRenderedThumbnailRef.current || undefined,
          },
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const detailMsg = getApiErrorMessage(data, '');
        if (detailMsg.includes('already exists') || detailMsg.includes('conflict')) {
          setAutoSaveStatus('conflict');
        } else {
          setAutoSaveStatus('unsaved');
        }
        return;
      }
      lastAutoSavedContentRef.current = content;
      setAutoSaveStatus('saved');
      setTimeout(() => setAutoSaveStatus((s) => s === 'saved' ? 'idle' : s), 3000);
      // After a successful rename, update the URL to reflect the new map name
      if (isRename) {
        navigateTo(`/${normalizedMapName}`);
      }
    } catch {
      setAutoSaveStatus('unsaved');
    }
  };

  const handlePublishMap = async (skipV1Warn = false) => {
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
      // Warn before publishing v1 (which locks the map name permanently)
      if (!skipV1Warn && !currentMapVersionOptions.some((o) => o.value !== 'alpha')) {
        setPublishV1WarnKind('map');
        setPublishV1WarnOpen(true);
        return;
      }
      await ensureLatestThumbnail();
      const check = await apiFetch(`/hub/map/${targetName}`);
      const exists = check.ok;
      const isSameCurrent = !!(mapOwner === normalizedHubUsername && route.map === targetName);
      if (exists && !isSameCurrent) {
        setError(`Map name '${targetName}' already exists. Choose a different name.`);
        return;
      }
      const content = await buildMapArtifactContent();
      await publishHubArtifact('map', content, { owner: normalizedHubUsername, name: targetName });
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
      const suggested = (resp.ok && data?.name) ? data.name : base;
      setForkDialogName(suggested);
      setForkDialogError('');
      setForkDialogChecking(false);
      setForkDialogOpen(true);
    } catch (err) {
      setError(`Fork failed: ${err.message}`);
    }
  };

  const handleForkConfirm = async () => {
    const name = String(forkDialogName || '').trim().toLowerCase();
    if (!name || !HUB_NAME_RE.test(name)) return;
    if (RESERVED_MAP_NAMES.has(name)) {
      setForkDialogError(`'${name}' is a reserved name and cannot be used for a map.`);
      return;
    }
    setForkDialogChecking(true);
    setForkDialogError('');
    const forkSourceOwner = mapOwner;
    const forkSourceMap = route.map;
    try {
      const checkResp = await apiFetch(`/hub/map/${name}`);
      if (checkResp.ok) {
        setForkDialogError(`Map '${name}' already exists. Choose a different name.`);
        return;
      }
      if (checkResp.status !== 404) {
        const d = await checkResp.json().catch(() => ({}));
        throw new Error(getApiErrorMessage(d, 'Failed to validate map name'));
      }
      setForkDialogOpen(false);
      await ensureLatestThumbnail();
      const content = await buildMapArtifactContent();
      await publishHubArtifact('map', content, { owner: normalizedHubUsername, name });
      if (forkSourceOwner && forkSourceMap) {
        apiFetch(`/maps/${forkSourceOwner}/${forkSourceMap}/vote`, { method: 'POST' }).catch(() => {});
      }
    } catch (err) {
      setForkDialogError(err.message || 'Fork failed');
    } finally {
      setForkDialogChecking(false);
    }
  };

  const handleDisassociateMap = async () => {
    const { kind, name, nameInput } = disassociateConfirm;
    if (nameInput !== name) return;
    setDisassociateConfirm((p) => ({ ...p, loading: true, error: null }));
    try {
      const resp = await apiFetch(`/hub/${kind}/${name}/disassociate`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Disassociation failed'));
      setDisassociateConfirm({ open: false, kind: 'map', name: '', nameInput: '', loading: false, error: null });
      // Navigate to profile and reload map list (navigateTo is a no-op if already on profile page,
      // so always call loadProfile explicitly to ensure the map disappears from the grid)
      navigateTo(`/user/${normalizedHubUsername}`);
      loadProfile(normalizedHubUsername, profilePage, profileSearch);
    } catch (err) {
      setDisassociateConfirm((p) => ({ ...p, loading: false, error: err.message }));
    }
  };

  const handleMapVersionSelect = (version) => {
    if (!route.map) return;
    setMapVersionLabel(String(version || 'alpha'));
    const next = String(version || 'alpha');
    navigateTo(`/${route.map}/${next === 'alpha' ? 'alpha' : `v${next}`}`);
  };

  const handleLibraryVersionSelect = async (version) => {
    const v = String(version || 'alpha');
    // Switching back to alpha — restore locally-edited code without fetching from server
    if (v === 'alpha') {
      setSelectedLibraryVersion('alpha');
      if (localPredefinedAlphaRef.current !== null) {
        setPredefinedCode(localPredefinedAlphaRef.current);
        localPredefinedAlphaRef.current = null;
      }
      return;
    }
    // Switching away from alpha to a published version — save current local alpha first
    if (selectedLibraryVersion === 'alpha') {
      localPredefinedAlphaRef.current = predefinedCode;
    }
    setSelectedLibraryVersion(v);
    if (!route.map || !mapOwner || !normalizedMapName) return;
    try {
      const resp = await apiFetch(`/hub/${mapOwner}/lib/${normalizedMapName}/${v}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load library version'));
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
    // Switching back to alpha — restore locally-edited code without fetching from server
    if (v === 'alpha') {
      setSelectedThemeVersion('alpha');
      if (localThemeAlphaRef.current !== null) {
        setThemeCode(localThemeAlphaRef.current);
        localThemeAlphaRef.current = null;
      }
      return;
    }
    // Switching away from alpha to a published version — save current local alpha first
    if (selectedThemeVersion === 'alpha') {
      localThemeAlphaRef.current = themeCode;
    }
    setSelectedThemeVersion(v);
    if (!route.map || !mapOwner || !normalizedMapName) return;
    try {
      const resp = await apiFetch(`/hub/${mapOwner}/css/${normalizedMapName}/${v}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(getApiErrorMessage(data, 'Failed to load theme version'));
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

  const handlePublishLibrary = async (skipV1Warn = false) => {
    try {
      if (isReadOnlyMap || selectedLibraryVersion !== 'alpha') {
        setError('Library is read-only in this view.');
        return;
      }
      if (!skipV1Warn && !currentLibraryVersionOptions.some((o) => o.value !== 'alpha')) {
        setPublishV1WarnKind('lib');
        setPublishV1WarnOpen(true);
        return;
      }
      setLibraryPublishStatus('publishing');
      const content = JSON.stringify({
        predefined_code: predefinedCode || '',
        map_name: normalizedMapName,
      });
      await publishHubArtifact('lib', content, { owner: mapOwner, name: normalizedMapName });
    } catch (err) {
      setLibraryPublishStatus(null);
      setError(`Publish library failed: ${err.message}`);
    }
  };

  const handlePublishTheme = async (skipV1Warn = false) => {
    try {
      if (isReadOnlyMap || selectedThemeVersion !== 'alpha') {
        setError('Theme is read-only in this view.');
        return;
      }
      if (!skipV1Warn && !currentThemeVersionOptions.some((o) => o.value !== 'alpha')) {
        setPublishV1WarnKind('css');
        setPublishV1WarnOpen(true);
        return;
      }
      setThemePublishStatus('publishing');
      const content = JSON.stringify({
        theme_code: themeCode || '',
        map_name: normalizedMapName,
      });
      await publishHubArtifact('css', content, { owner: mapOwner, name: normalizedMapName });
    } catch (err) {
      setThemePublishStatus(null);
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
             if (project.pickerOptions && typeof project.pickerOptions === 'object') setPickerOptions(project.pickerOptions);
          }
          // Also check for picker_options at top-level (from buildMapArtifactContent format)
          if (project.picker_options && typeof project.picker_options === 'object') setPickerOptions(project.picker_options);
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
          try {
            const parsed = JSON.parse(part.value);
            if (!Array.isArray(parsed)) return '';
            const sanitized = parsed
              .map((coord) => Array.isArray(coord) && coord.length === 2 ? [Number(coord[0]), Number(coord[1])] : null)
              .filter((c) => c !== null && !c.some(isNaN));
            if (!sanitized.length) return '';
            return `polygon(${JSON.stringify(sanitized)})`;
          } catch {
            return '';
          }
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
      // Sanitize to a valid Python identifier (letters, digits, underscores only; no leading digit)
      const safeName = ((element.label || 'territory')
          .replace(/\s+/g, '_')
          .replace(/[^a-zA-Z0-9_]/g, '')
          .replace(/^[0-9]+/, '')) || 'territory';
      const terrStr = formatTerritory(element.value);
      setPredefinedCode(prev => prev + `\n${safeName} = ${terrStr}\n`);
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
    // Recursively converts a JS value to a Python literal, without string-level replacement
    // that would corrupt string values containing "null", "true", or "false".
    const jsonToPy = (val) => {
        if (val === null || val === undefined) return 'None';
        if (typeof val === 'boolean') return val ? 'True' : 'False';
        if (typeof val === 'number') return String(val);
        if (typeof val === 'string') return pyString(val);
        if (Array.isArray(val)) return `[${val.map(jsonToPy).join(', ')}]`;
        if (typeof val === 'object') {
            const pairs = Object.entries(val).map(([k, v]) => `${JSON.stringify(k)}: ${jsonToPy(v)}`);
            return `{${pairs.join(', ')}}`;
        }
        return JSON.stringify(val);
    };
    const pyVal = (v) => {
        if (isPythonValue(v)) return getPythonExpr(v) || 'None';
        if (v == null || v === '') return 'None';
        if (typeof v === 'boolean') return v ? 'True' : 'False';
        if (typeof v === 'string') return pyString(v);
        return jsonToPy(v);
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
        } else if (el.type === 'music') {
            const musicArgs = { ...args };
            delete musicArgs.filename;
            const musicArgsStr = argsToStr(musicArgs);
            const musicVal = (el.value != null && el.value !== '') ? pyVal(el.value) : 'None';
            lines.push(`xatra.Music(path=${musicVal}${musicArgsStr})`);
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
          await fetch(`${API_BASE}/stop`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_types: mappedTaskTypes }),
          });
      } catch (e) { console.error(e); }
      if (stopView === 'main') setMainRenderTask(null);
  };

  // Sidebar resize handlers
  useEffect(() => {
    const onMove = (e) => {
      if (!sidebarResizingRef.current) return;
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const delta = clientX - sidebarStartXRef.current;
      setSidebarWidth(Math.max(0, Math.min(900, sidebarStartWidthRef.current + delta)));
    };
    const onUp = () => { sidebarResizingRef.current = false; setSidebarDragging(false); document.body.style.cursor = ''; document.body.style.userSelect = ''; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  // Mark editor as past its initial load phase after editorContextReady fires.
  // This prevents the auto-save from treating the draft/default load as "user changes".
  useEffect(() => {
    if (!editorContextReady) { editorReadyRef.current = false; return; }
    const t = setTimeout(() => { editorReadyRef.current = true; }, 300);
    return () => clearTimeout(t);
  }, [editorContextReady]);

  // Auto-save: trigger 'unsaved' status and schedule save whenever content changes
  useEffect(() => {
    if (!editorContextReady) return;
    // For new maps, skip during initial load phase (before user makes any change)
    if (!route.map && !editorReadyRef.current) return;
    if (!currentUser.is_authenticated) {
      setGuestHasChanges(true);
      return;
    }
    if (isReadOnlyMap) return;
    setAutoSaveStatus('unsaved');
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(async () => {
      const content = await buildMapArtifactContent().catch(() => null);
      if (content !== null && content !== lastAutoSavedContentRef.current) {
        await performAutoSave(content);
      }
    }, 3000);
    return () => { if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedMapName, currentUser.is_authenticated, builderElements, builderOptions, code, predefinedCode, importsCode, themeCode, runtimeCode]);

  // Initial render — for hub maps, loadMapFromHub triggers the render directly;
  // for root/new-map, the route effect handles rendering after draft load or defaults.
  useEffect(() => {
    if (!editorContextReady) return;
    if (!route.map) return; // root/new-map: handled by route effect
    // Hub map without explicit map name (shouldn't happen per parsePath, but guard anyway)
    if (!route.map) renderMap();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editorContextReady]);

  useEffect(() => {
    if (!editorContextReady) return;
    if (didPrefetchReferenceRef.current || !mapHtml) return;
    didPrefetchReferenceRef.current = true;
    renderPickerMap({ background: true, showLoading: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapHtml, editorContextReady]);

  useEffect(() => {
    if (!editorContextReady) return;
    if (didPrefetchTerritoryRef.current || !mapHtml) return;
    didPrefetchTerritoryRef.current = true;
    (async () => {
      await loadTerritoryLibraryCatalog('builtin');
      await renderTerritoryLibrary('builtin', { background: true, useDefaultSelection: true, showLoading: true });
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapHtml, editorContextReady]);

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
      alias: imp.alias || imp.name,
    }));
  const libraryTabs = [
    { id: 'builtin', label: 'xatra.territory_library', source: 'builtin' },
    { id: 'custom', label: 'Custom Library', source: 'custom' },
    ...importedLibraryTabs,
  ];
  const activeLibraryConfig = libraryTabs.find((t) => t.id === activeLibraryTab) || libraryTabs[0];
  // Keep a ref so the message handler closure always has the latest value
  const activeLibraryConfigRef = useRef(activeLibraryConfig);
  activeLibraryConfigRef.current = activeLibraryConfig;
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
    name: route.map || '',
  });
  const currentLibraryVersionOptions = getImportVersionOptions({
    username: mapOwner,
    kind: 'lib',
    name: route.map || '',
  });
  const currentThemeVersionOptions = getImportVersionOptions({
    username: mapOwner,
    kind: 'css',
    name: route.map || '',
  });
  // True when the current map (or its lib/css) has at least one published (non-alpha) version.
  // Publishing any of these locks the map name permanently.
  const hasPublishedVersions = !!route.map && (
    currentMapVersionOptions.some((o) => o.value !== 'alpha') ||
    currentLibraryVersionOptions.some((o) => o.value !== 'alpha') ||
    currentThemeVersionOptions.some((o) => o.value !== 'alpha')
  );
  const importedBaseSet = new Set((hubImports || []).map((imp) => `${imp.kind}:${imp.name}`));
  const renderExploreCatalogCard = (item) => (
    <button
      key={`${item.username}-${item.name}`}
      type="button"
      onClick={() => navigateTo(item.slug || `/${item.name}`)}
      className={`block text-left w-full rounded-xl border overflow-hidden shadow-sm hover:shadow-md transition-shadow group ${isDarkMode ? 'bg-slate-800 border-slate-700 hover:border-slate-600' : 'bg-white border-gray-200 hover:border-gray-300'}`}
    >
      <img src={item.thumbnail || '/vite.svg'} alt="" className={`w-full h-28 object-cover ${isDarkMode ? 'bg-slate-700' : 'bg-gray-100'}`} />
      <div className="p-3">
        <div className={`font-mono text-xs font-medium group-hover:text-blue-500 transition-colors ${isDarkMode ? 'text-slate-200' : 'text-slate-800'}`}>{item.name}</div>
        <div className={`text-[10px] mt-0.5 truncate ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>by {item.username}</div>
        <div className={`flex items-center gap-2 mt-1.5 text-[10px] ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>
          <span className="inline-flex items-center gap-0.5"><Triangle size={9}/> {item.votes || 0}</span>
          <span>{item.views || 0} views</span>
        </div>
      </div>
    </button>
  );

  const renderImportCatalogCard = (item) => {
    const mapKey = artifactKey(item.username, 'map', item.name);
    const cssKey = artifactKey(item.username, 'css', item.name);
    const libKey = artifactKey(item.username, 'lib', item.name);
    const mapOptions = artifactVersionOptions[mapKey] || [{ value: 'alpha', label: 'alpha' }];
    const cssOptions = artifactVersionOptions[cssKey] || [{ value: 'alpha', label: 'alpha' }];
    const libOptions = artifactVersionOptions[libKey] || [{ value: 'alpha', label: 'alpha' }];
    const cssNotFound = artifactVersionOptions[cssKey] === null;
    const libNotFound = artifactVersionOptions[libKey] === null;
    const mapVersion = importVersionDraft[mapKey] || mapOptions[0]?.value || 'alpha';
    const cssVersion = importVersionDraft[cssKey] || cssOptions[0]?.value || 'alpha';
    const libVersion = importVersionDraft[libKey] || libOptions[0]?.value || 'alpha';
    const mapImported = importedBaseSet.has(`map:${item.name}`);
    const cssImported = importedBaseSet.has(`css:${item.name}`);
    const libImported = importedBaseSet.has(`lib:${item.name}`);
    const isCurrentMap = (item.username === mapOwner && item.name === mapName);
    return (
      <div
        key={`${item.username}-${item.name}`}
        data-import-card="true"
        className={`border rounded bg-white focus-within:ring-2 ring-blue-500 shadow-sm min-h-[280px] ${isCurrentMap ? 'opacity-50 grayscale' : ''}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key.toLowerCase() === 'm') addHubImportLine({ ...item, kind: 'map', latest_version: mapVersion });
          if (e.key.toLowerCase() === 'c') addHubImportLine({ ...item, kind: 'css', latest_version: cssVersion });
          if (e.key.toLowerCase() === 't') addHubImportLine({ ...item, kind: 'lib', latest_version: libVersion });
          if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) {
            e.preventDefault();
            const cards = Array.from(importGridRef.current?.querySelectorAll('[data-import-card]') || []);
            const idx = cards.indexOf(e.currentTarget);
            if (idx === -1) return;
            if (e.key === 'ArrowRight') { cards[idx + 1]?.focus(); }
            else if (e.key === 'ArrowLeft') {
              if (idx === 0) importSearchRef.current?.focus();
              else cards[idx - 1]?.focus();
            } else {
              const myTop = e.currentTarget.getBoundingClientRect().top;
              const colCount = Math.max(1, cards.filter(c => Math.abs(c.getBoundingClientRect().top - myTop) < 10).length);
              if (e.key === 'ArrowDown') { cards[idx + colCount]?.focus(); }
              else { // ArrowUp
                const prevIdx = idx - colCount;
                if (prevIdx < 0) importSearchRef.current?.focus();
                else cards[prevIdx]?.focus();
              }
            }
          }
        }}
      >
        <img src={item.thumbnail || '/vite.svg'} alt="" className="w-full h-20 object-cover bg-gray-100 rounded-t" />
        <div className="p-2">
          <a href={item.slug || `/${item.name}`} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-blue-700 hover:underline">{item.name}</a>
          <div className="text-[10px] text-gray-500 truncate">
            by <a href={`/user/${item.username}`} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{item.username}</a> · {item.votes || 0} votes · {item.views || 0} views
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
              <button disabled={cssImported || isCurrentMap || cssNotFound} className={`flex-1 text-[11px] px-2 py-1 border rounded transition-colors ${cssImported ? 'bg-blue-600 text-white border-blue-600 cursor-not-allowed' : cssNotFound ? 'opacity-40 cursor-not-allowed' : 'hover:bg-blue-50'}`} onClick={() => !cssNotFound && addHubImportLine({ ...item, kind: 'css', latest_version: cssVersion })} title={cssNotFound ? 'This map has no theme' : 'Import CSS'}>{cssImported ? '✓ CSS Imported' : cssNotFound ? 'No theme' : 'c Import CSS'}</button>
            </div>
            <div className="flex gap-1 items-center">
              <select value={libVersion} onChange={(e) => setImportVersionDraft((prev) => ({ ...prev, [libKey]: e.target.value }))} className="text-[11px] border rounded px-1 py-1 min-w-[72px]">
                {libOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <button disabled={libImported || isCurrentMap || libNotFound} className={`flex-1 text-[11px] px-2 py-1 border rounded transition-colors ${libImported ? 'bg-blue-600 text-white border-blue-600 cursor-not-allowed' : libNotFound ? 'opacity-40 cursor-not-allowed' : 'hover:bg-blue-50'}`} onClick={() => !libNotFound && addHubImportLine({ ...item, kind: 'lib', latest_version: libVersion })} title={libNotFound ? 'This map has no territory library' : 'Import Territories'}>{libImported ? '✓ Territories Imported' : libNotFound ? 'No territories' : 't Import Territories'}</button>
            </div>
          </div>
          {isCurrentMap && <div className="mt-1 text-[10px] text-gray-500">Current map cannot import itself.</div>}
        </div>
      </div>
    );
  };

  const renderTopBar = () => (
    <div
      ref={topBarRef}
      className={`flex items-center h-10 px-2 gap-0.5 border-b flex-shrink-0 ${isDarkMode ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-200'}`}
      onKeyDown={(e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        const focusables = Array.from(topBarRef.current?.querySelectorAll('button:not([disabled]), a[href]') || []);
        const idx = focusables.indexOf(document.activeElement);
        if (idx === -1) return;
        e.preventDefault();
        const next = e.key === 'ArrowRight'
          ? focusables[(idx + 1) % focusables.length]
          : focusables[(idx - 1 + focusables.length) % focusables.length];
        next?.focus();
      }}
    >
      {/* Hidden file input for Load JSON */}
      <input id="xatra-load-input" type="file" className="hidden" accept=".json" onChange={handleLoadProject} />
      {/* Left: title + file actions (file buttons only on editor pages) */}
      <button
        onClick={() => navigateTo(currentUser.is_authenticated ? '/explore' : '/')}
        className={`font-bold text-sm lowercase tracking-tight px-2 py-1 rounded mr-1 ${isDarkMode ? 'text-white hover:bg-slate-800' : 'text-slate-900 hover:bg-gray-100'}`}
        title="Home"
      >xatra</button>
      {route.page === 'editor' && !isReadOnlyMap && (
        <button
          onClick={() => document.getElementById('xatra-load-input')?.click()}
          title="Load JSON"
          className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
        ><Upload size={14}/></button>
      )}
      {route.page === 'editor' && (
        <>
          <button
            onClick={handleSaveProject}
            title="Save JSON"
            className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
          ><Download size={14}/></button>
          <button
            onClick={handleExportHtml}
            title="Export HTML (Download Map)"
            className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
          ><Image size={14}/></button>
          {route.map && isMapAuthor && (
            <button
              onClick={() => setDisassociateConfirm({ open: true, kind: 'map', name: route.map, nameInput: '', loading: false, error: null })}
              title="Disassociate map from your account"
              className={`p-1.5 rounded ${isDarkMode ? 'text-red-400 hover:bg-red-950/40' : 'text-red-600 hover:bg-red-50'}`}
            ><Trash2 size={14}/></button>
          )}
        </>
      )}
      {/* Spacer */}
      <div className="flex-1" />
      {/* Right: nav actions */}
      <button
        onClick={() => setIsDarkMode((p) => !p)}
        title={isDarkMode ? 'Switch to light mode' : 'Switch to night mode'}
        className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
      >{isDarkMode ? <Sun size={14}/> : <Moon size={14}/>}</button>
      <div className="relative">
        <button
          onClick={() => setShowShortcutHelp((prev) => !prev)}
          title="Keyboard shortcuts"
          className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
        ><Keyboard size={14}/></button>
        {showShortcutHelp && (
          <div className={`absolute top-full right-0 mt-1 z-50 rounded-lg shadow-lg p-3 text-xs w-64 border ${shortcutsPanelClass}`}>
            <div className="font-semibold mb-2">Shortcuts</div>
            <div>`?` toggle this panel</div>
            <div>`Ctrl/Cmd+1` Builder tab</div>
            <div>`Ctrl/Cmd+2` Code tab</div>
            <div>`Ctrl/Cmd+3` Map Preview</div>
            <div>`Ctrl/Cmd+4` Reference Map</div>
            <div>`Ctrl/Cmd+5` Territory Library</div>
            <div>`Ctrl/Cmd+0` Focus Territory library sub-tabs</div>
            <div>`Ctrl/Cmd+;` Focus top bar (←→ to navigate)</div>
            <div>`Ctrl/Cmd+Enter` Render map</div>
            <div>`Ctrl/Cmd+Shift+Enter` Stop active preview generation</div>
            <div>`Ctrl/Cmd+Space` Update active picker map tab</div>
            <div>`Ctrl/Cmd+Shift+X` Import from existing map</div>
            <div className="mt-2 pt-2 border-t border-gray-200">`Ctrl/Cmd+Shift+F` add Flag</div>
            <div>`Ctrl/Cmd+Shift+R` add River</div>
            <div>`Ctrl/Cmd+Shift+P` add Point</div>
            <div>`Ctrl/Cmd+Shift+T` add Text</div>
            <div>`Ctrl/Cmd+Shift+H` add Path</div>
            <div>`Ctrl/Cmd+Shift+M` add Music</div>
            <div>`Ctrl/Cmd+Shift+A` add Admin</div>
            <div>`Ctrl/Cmd+Shift+D` add Data</div>
            <div>`Ctrl/Cmd+Shift+B` add TitleBox</div>
            <div>`Ctrl/Cmd+Shift+Y` add Python</div>
          </div>
        )}
      </div>
      <button
        onClick={handleNewMapClick}
        className="px-3 py-1 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 ml-1 mr-1"
        title="Create a new map"
      >New map</button>
      <button
        onClick={() => navigateTo('/explore')}
        title="Explore"
        className={`px-2.5 py-1.5 text-xs rounded inline-flex items-center gap-1.5 ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
      ><Compass size={14}/> Explore</button>
      {currentUser.is_authenticated ? (
        <>
          <a
            href={`/user/${normalizedHubUsername}`}
            className={`px-2 py-1 text-xs rounded font-mono ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-700 hover:bg-gray-100'}`}
            title="My profile"
          >{normalizedHubUsername}</a>
          <button
            onClick={handleLogout}
            title="Logout"
            className={`p-1.5 rounded ${isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-gray-600 hover:bg-gray-100'}`}
          ><LogOut size={14}/></button>
        </>
      ) : (
        <button
          onClick={() => navigateTo('/login')}
          className={`px-3 py-1 text-xs border rounded-lg ml-1 ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
        >Login/Signup</button>
      )}
    </div>
  );

  const renderNavSidebar = (activePage) => (
    <div className={`w-56 flex-shrink-0 flex flex-col border-r ${isDarkMode ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-200'}`}>
      <div className={`px-5 py-5 border-b ${isDarkMode ? 'border-slate-700' : 'border-gray-100'}`}>
        <div className={`text-xl font-bold lowercase tracking-tight ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>xatra</div>
        <div className={`text-[10px] mt-0.5 ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>studio</div>
      </div>
      <nav className="px-2 py-3 flex-1 space-y-0.5">
        <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${activePage === 'explore' ? (isDarkMode ? 'bg-slate-800 text-white font-medium' : 'bg-blue-50 text-blue-700 font-medium') : (isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100')}`} onClick={() => navigateTo('/explore')}><Search size={14}/> Explore</button>
        <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${activePage === 'users' ? (isDarkMode ? 'bg-slate-800 text-white font-medium' : 'bg-blue-50 text-blue-700 font-medium') : (isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100')}`} onClick={() => navigateTo('/explore')}><Users size={14}/> Users</button>
        <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${activePage === 'profile' ? (isDarkMode ? 'bg-slate-800 text-white font-medium' : 'bg-blue-50 text-blue-700 font-medium') : (isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100')}`} onClick={() => (currentUser.is_authenticated ? navigateTo(`/user/${normalizedHubUsername}`) : navigateTo('/login'))}><User size={14}/> {currentUser.is_authenticated ? normalizedHubUsername : 'My Profile'}</button>
        <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100'}`} onClick={handleNewMapClick}><FilePlus2 size={14}/> New map…</button>
      </nav>
      <div className={`px-2 pb-3 pt-2 border-t space-y-0.5 ${isDarkMode ? 'border-slate-700' : 'border-gray-100'}`}>
        <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100'}`} onClick={() => setIsDarkMode((p) => !p)}>{isDarkMode ? <Sun size={14}/> : <Moon size={14}/>} {isDarkMode ? 'Light mode' : 'Night mode'}</button>
        {currentUser.is_authenticated ? (
          <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100'}`} onClick={handleLogout}><LogOut size={14}/> Logout</button>
        ) : (
          <button className={`w-full text-left px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2.5 transition-colors ${isDarkMode ? 'text-slate-300 hover:bg-slate-800 hover:text-white' : 'text-gray-600 hover:bg-gray-100'}`} onClick={() => navigateTo('/login')}><LogIn size={14}/> Login</button>
        )}
      </div>
    </div>
  );

  if (route.page === 'login') {
    const inputCls = `w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 placeholder-gray-400 focus:border-blue-400'}`;
    return (
      <div className={`h-screen w-full flex flex-col ${isDarkMode ? 'theme-dark bg-slate-950' : 'bg-gradient-to-br from-slate-50 to-gray-100'}`}>
        {renderTopBar()}
        <div className="flex-1 flex items-center justify-center">
        <div className={`w-full max-w-2xl mx-4 rounded-2xl shadow-xl overflow-hidden ${isDarkMode ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-gray-200'}`}>
          <div className={`px-8 py-5 border-b ${isDarkMode ? 'border-slate-700 bg-slate-800/40' : 'border-gray-100 bg-gray-50'}`}>
            <div className={`text-2xl font-bold lowercase tracking-tight ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>xatra</div>
            <div className={`text-sm mt-0.5 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Create interactive historical and administrative maps</div>
          </div>
          <div className={`grid grid-cols-1 md:grid-cols-2 ${isDarkMode ? 'divide-slate-700' : 'divide-gray-100'} divide-x`}>
            <div className="px-8 py-6">
              <h2 className={`text-base font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>Login</h2>
              <div className="space-y-3">
                <div>
                  <label className={`block text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-600'}`}>Username</label>
                  <input className={`${inputCls} font-mono`} placeholder="username" value={authForm.username} onChange={(e) => setAuthForm((p) => ({ ...p, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))} onKeyDown={(e) => { if (e.key === 'Enter') { setAuthMode('login'); handleLogin('login'); } }} />
                </div>
                <div>
                  <label className={`block text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-600'}`}>Password</label>
                  <input className={inputCls} type="password" placeholder="password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} onKeyDown={(e) => { if (e.key === 'Enter') { setAuthMode('login'); handleLogin('login'); } }} />
                </div>
              </div>
              <button disabled={authSubmitting} className="mt-4 w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors" onClick={async () => { setAuthMode('login'); await handleLogin('login'); }}>{authSubmitting && authMode === 'login' ? 'Logging in…' : 'Login'}</button>
            </div>
            <div className="px-8 py-6">
              <h2 className={`text-base font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>Create account</h2>
              <div className="space-y-3">
                <div>
                  <label className={`block text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-600'}`}>Username</label>
                  <input className={`${inputCls} font-mono`} placeholder="username" value={authForm.username} onChange={(e) => setAuthForm((p) => ({ ...p, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))} onKeyDown={(e) => { if (e.key === 'Enter') { setAuthMode('signup'); handleLogin('signup'); } }} />
                </div>
                <div>
                  <label className={`block text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-600'}`}>Full name <span className="font-normal opacity-60">(optional)</span></label>
                  <input className={inputCls} placeholder="Full name" value={authForm.full_name} onChange={(e) => setAuthForm((p) => ({ ...p, full_name: e.target.value }))} onKeyDown={(e) => { if (e.key === 'Enter') { setAuthMode('signup'); handleLogin('signup'); } }} />
                </div>
                <div>
                  <label className={`block text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-600'}`}>Password <span className="font-normal opacity-60">(min 8)</span></label>
                  <input className={inputCls} type="password" placeholder="password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} onKeyDown={(e) => { if (e.key === 'Enter') { setAuthMode('signup'); handleLogin('signup'); } }} />
                </div>
              </div>
              <button disabled={authSubmitting} className="mt-4 w-full px-4 py-2.5 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50 transition-colors" onClick={async () => { setAuthMode('signup'); await handleLogin('signup'); }}>{authSubmitting && authMode === 'signup' ? 'Creating account…' : 'Create account'}</button>
            </div>
          </div>
          <div className={`px-8 py-4 border-t ${isDarkMode ? 'border-slate-700 bg-slate-800/30' : 'border-gray-100 bg-gray-50'} flex items-center gap-3`}>
            <button className={`px-3 py-1.5 border rounded-lg text-sm transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-600 hover:bg-gray-100'}`} onClick={() => navigateTo('/')}>← Back to editor</button>
            {error && <div className={`flex-1 px-3 py-1.5 rounded-lg border text-xs ${isDarkMode ? 'border-red-700 bg-red-900/20 text-red-400' : 'border-red-200 bg-red-50 text-red-700'}`}>{error}</div>}
          </div>
        </div>
        </div>
      </div>
    );
  }

  const renderGlobalModals = () => (
    <>
      {publishV1WarnOpen && (
        <div className="fixed inset-0 bg-black/40 z-[100] flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) setPublishV1WarnOpen(false); }}>
          <div className={`rounded-lg border shadow-xl p-6 w-96 ${isDarkMode ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-gray-200 text-slate-800'}`}>
            <div className="font-semibold text-sm mb-2">Publish version 1?</div>
            <div className={`text-xs mb-4 leading-relaxed ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>
              Once you publish a version of this {publishV1WarnKind === 'map' ? 'map' : publishV1WarnKind === 'lib' ? 'territory library' : 'theme'}, the map name <span className="font-mono font-semibold">{normalizedMapName}</span> is permanently locked and cannot be changed.
              {' '}Make sure the name is correct before continuing.
            </div>
            <div className="flex gap-2 justify-end">
              <button
                className={`px-3 py-1.5 text-sm border rounded transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                onClick={() => setPublishV1WarnOpen(false)}
              >Cancel</button>
              <button
                autoFocus
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                onClick={() => {
                  setPublishV1WarnOpen(false);
                  if (publishV1WarnKind === 'map') handlePublishMap(true);
                  else if (publishV1WarnKind === 'lib') handlePublishLibrary(true);
                  else if (publishV1WarnKind === 'css') handlePublishTheme(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setPublishV1WarnOpen(false);
                    if (publishV1WarnKind === 'map') handlePublishMap(true);
                    else if (publishV1WarnKind === 'lib') handlePublishLibrary(true);
                    else if (publishV1WarnKind === 'css') handlePublishTheme(true);
                  } else if (e.key === 'Escape') setPublishV1WarnOpen(false);
                }}
              >Publish v1</button>
            </div>
          </div>
        </div>
      )}
      {newMapDialogOpen && (
        <div className="fixed inset-0 bg-black/40 z-[100] flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) setNewMapDialogOpen(false); }}>
          <div className={`rounded-lg border shadow-xl p-6 w-80 ${isDarkMode ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-gray-200 text-slate-800'}`}>
            <div className="font-semibold text-sm mb-3">Create new map</div>
            <label className={`block text-xs mb-1 ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>Map name <span className={`${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>(lowercase letters, digits, _ or .)</span></label>
            <input
              autoFocus
              type="text"
              value={newMapDialogName}
              onChange={(e) => {
                setNewMapDialogName(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''));
                if (newMapDialogError) setNewMapDialogError('');
              }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleNewMapConfirm(); else if (e.key === 'Escape') setNewMapDialogOpen(false); }}
              placeholder="my_map"
              className={`w-full border rounded px-3 py-2 text-sm mb-1 focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`}
            />
            {newMapDialogName && !HUB_NAME_RE.test(newMapDialogName) && (
              <div className="text-xs text-red-600 mb-2">Invalid name. Use only a–z, 0–9, _ or .</div>
            )}
            {newMapDialogError && (
              <div className="text-xs text-red-600 mb-2">{newMapDialogError}</div>
            )}
            <div className="flex gap-2 mt-3 justify-end">
              <button className={`px-3 py-1.5 text-sm border rounded transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`} onClick={() => setNewMapDialogOpen(false)}>Cancel</button>
              <button
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={!newMapDialogName || !HUB_NAME_RE.test(newMapDialogName) || newMapDialogChecking}
                onClick={handleNewMapConfirm}
              >{newMapDialogChecking ? 'Checking…' : 'Create'}</button>
            </div>
          </div>
        </div>
      )}
      {forkDialogOpen && (
        <div className="fixed inset-0 bg-black/40 z-[100] flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) setForkDialogOpen(false); }}>
          <div className={`rounded-lg border shadow-xl p-6 w-80 ${isDarkMode ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-gray-200 text-slate-800'}`}>
            <div className="font-semibold text-sm mb-1">Fork map</div>
            <div className={`text-xs mb-3 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Choose a name for your forked copy.</div>
            <label className={`block text-xs mb-1 ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>Map name <span className={`${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>(a–z, 0–9, _ or .)</span></label>
            <input
              autoFocus
              type="text"
              value={forkDialogName}
              onChange={(e) => {
                setForkDialogName(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''));
                if (forkDialogError) setForkDialogError('');
              }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleForkConfirm(); else if (e.key === 'Escape') setForkDialogOpen(false); }}
              placeholder="my_map"
              className={`w-full border rounded px-3 py-2 text-sm mb-1 focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`}
            />
            {forkDialogName && !HUB_NAME_RE.test(forkDialogName) && (
              <div className="text-xs text-red-600 mb-2">Invalid name. Use only a–z, 0–9, _ or .</div>
            )}
            {forkDialogError && (
              <div className="text-xs text-red-600 mb-2">{forkDialogError}</div>
            )}
            <div className="flex gap-2 mt-3 justify-end">
              <button className={`px-3 py-1.5 text-sm border rounded transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`} onClick={() => setForkDialogOpen(false)}>Cancel</button>
              <button
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={!forkDialogName || !HUB_NAME_RE.test(forkDialogName) || forkDialogChecking}
                onClick={handleForkConfirm}
              >{forkDialogChecking ? 'Forking…' : 'Fork'}</button>
            </div>
          </div>
        </div>
      )}
      {disassociateConfirm.open && (
        <div className="fixed inset-0 bg-black/50 z-[200] flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) setDisassociateConfirm((p) => ({ ...p, open: false })); }}>
          <div className={`w-[420px] max-w-[95vw] rounded-xl border shadow-2xl p-6 flex flex-col gap-4 ${isDarkMode ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-gray-200 text-slate-800'}`}>
            <div className="flex items-center gap-3">
              <UserX size={20} className="text-red-500 flex-shrink-0"/>
              <div className="font-semibold text-base">Disassociate map</div>
            </div>
            <div className={`text-sm leading-relaxed ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>
              This will remove <span className="font-mono font-semibold">{disassociateConfirm.name}</span> from your account and transfer it to an anonymous user.
              <br/><br/>
              You will <strong>permanently lose all ownership and editing rights</strong> to this map (though you can fork it). Published versions will remain accessible.
            </div>
            <div className={`rounded-lg border px-3 py-2 text-xs ${isDarkMode ? 'bg-red-900/20 border-red-700/40 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
              This action cannot be undone.
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={`text-xs font-medium ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                Type <span className="font-mono font-semibold">{disassociateConfirm.name}</span> to confirm
              </label>
              <input
                autoFocus
                value={disassociateConfirm.nameInput}
                onChange={(e) => setDisassociateConfirm((p) => ({ ...p, nameInput: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && disassociateConfirm.nameInput === disassociateConfirm.name) handleDisassociateMap();
                  else if (e.key === 'Escape') setDisassociateConfirm((p) => ({ ...p, open: false }));
                }}
                className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-red-400 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                placeholder={disassociateConfirm.name}
              />
            </div>
            {disassociateConfirm.error && (
              <div className="text-xs text-red-500">{disassociateConfirm.error}</div>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDisassociateConfirm((p) => ({ ...p, open: false }))}
                className={`px-4 py-2 rounded-lg border text-sm transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
              >
                Cancel
              </button>
              <button
                onClick={handleDisassociateMap}
                disabled={disassociateConfirm.nameInput !== disassociateConfirm.name || disassociateConfirm.loading}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {disassociateConfirm.loading ? 'Disassociating…' : 'Disassociate'}
              </button>
            </div>
          </div>
        </div>
      )}
      {promoteDraftDialogOpen && (
        <div className="fixed inset-0 bg-black/40 z-[100] flex items-center justify-center"
             onClick={(e) => { if (e.target === e.currentTarget) setPromoteDraftDialogOpen(false); }}>
          <div className={`rounded-lg border shadow-xl p-6 w-80 ${isDarkMode ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-gray-200 text-slate-800'}`}>
            <div className="font-semibold text-sm mb-1">Save map</div>
            <div className={`text-xs mb-3 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Give this unsaved draft a name to save it to your account.</div>
            <label className={`block text-xs mb-1 ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>Map name <span className={`${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>(a–z, 0–9, _ or .)</span></label>
            <input autoFocus type="text" value={promoteDraftName}
              onChange={(e) => setPromoteDraftName(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''))}
              onKeyDown={(e) => { if (e.key === 'Enter') handlePromoteDraft(); else if (e.key === 'Escape') setPromoteDraftDialogOpen(false); }}
              placeholder="my_map" className={`w-full border rounded px-3 py-2 text-sm mb-1 focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`} />
            {promoteDraftName && !HUB_NAME_RE.test(promoteDraftName) && (
              <div className="text-xs text-red-600 mb-2">Invalid name.</div>
            )}
            {promoteDraftError && <div className="text-xs text-red-600 mb-2">{promoteDraftError}</div>}
            <div className="flex gap-2 mt-3 justify-end">
              <button className={`px-3 py-1.5 text-sm border rounded transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                onClick={() => setPromoteDraftDialogOpen(false)}>Cancel</button>
              <button className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={!promoteDraftName || !HUB_NAME_RE.test(promoteDraftName) || promoteDraftLoading}
                onClick={handlePromoteDraft}>
                {promoteDraftLoading ? 'Saving…' : 'Save map'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  if (route.page === 'explore') {
    const totalPages = Math.max(1, Math.ceil((exploreData.total || 0) / (exploreData.per_page || 12)));
    const usersTotalPages = Math.max(1, Math.ceil((usersData.total || 0) / (usersData.per_page || 20)));
    return (
      <>
      <div className={`h-screen w-full flex flex-col ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-50'}`}>
        {renderTopBar()}
        <div className="flex-1 flex min-w-0 overflow-hidden">
          {/* Maps column */}
          <div className="flex-1 overflow-y-auto px-6 py-5 min-w-0">
            {/* My Maps section — logged-in users only */}
            {currentUser.is_authenticated && (
              <div className="mb-6">
                <div className={`text-xs font-semibold mb-2 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>My Maps</div>
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {/* New Map card */}
                  <button
                    onClick={handleNewMapClick}
                    className={`flex-shrink-0 min-w-[130px] h-28 rounded-xl border flex flex-col items-center justify-center gap-1.5 text-xs font-medium transition-colors ${isDarkMode ? 'bg-slate-800 border-slate-700 text-slate-300 hover:border-blue-500 hover:text-blue-400' : 'bg-white border-gray-200 text-gray-500 hover:border-blue-400 hover:text-blue-600'}`}
                  >
                    <Plus size={18}/>
                    New map
                  </button>
                  {/* Unsaved Draft card */}
                  {userDraftMeta?.exists && (
                    <button
                      onClick={() => { setPromoteDraftName(''); setPromoteDraftError(''); setPromoteDraftDialogOpen(true); }}
                      className={`flex-shrink-0 min-w-[130px] h-28 rounded-xl border flex flex-col items-center justify-center gap-1 text-xs transition-colors ${isDarkMode ? 'bg-slate-800 border-red-700/50 hover:border-red-500' : 'bg-white border-red-200 hover:border-red-400'}`}
                    >
                      <div className={`font-semibold ${isDarkMode ? 'text-red-400' : 'text-red-500'}`}>Unsaved Draft</div>
                      <div className={`text-[10px] ${isDarkMode ? 'text-slate-400' : 'text-gray-400'}`}>{userDraftMeta.mapName}</div>
                    </button>
                  )}
                  {/* Recent maps */}
                  {(profileData?.maps || []).slice(0, 5).map((item) => (
                    <a
                      key={item.name}
                      href={item.slug || `/${item.name}`}
                      className={`flex-shrink-0 min-w-[130px] h-28 rounded-xl border overflow-hidden shadow-sm hover:shadow-md transition-shadow group ${isDarkMode ? 'bg-slate-800 border-slate-700 hover:border-slate-600' : 'bg-white border-gray-200 hover:border-gray-300'}`}
                    >
                      <img src={item.thumbnail || '/vite.svg'} alt="" className={`w-full h-16 object-cover ${isDarkMode ? 'bg-slate-700' : 'bg-gray-100'}`} />
                      <div className="px-2 py-1">
                        <div className={`font-mono text-[11px] font-medium truncate group-hover:text-blue-500 transition-colors ${isDarkMode ? 'text-slate-200' : 'text-slate-800'}`}>{item.name}</div>
                      </div>
                    </a>
                  ))}
                  {/* More → link */}
                  {(profileData?.total || 0) > 5 && (
                    <a
                      href={`/user/${normalizedHubUsername}`}
                      className={`flex-shrink-0 min-w-[80px] h-28 rounded-xl border flex items-center justify-center text-xs font-medium transition-colors ${isDarkMode ? 'bg-slate-800 border-slate-700 text-slate-400 hover:text-blue-400 hover:border-blue-500' : 'bg-white border-gray-200 text-gray-400 hover:text-blue-600 hover:border-blue-400'}`}
                    >
                      More →
                    </a>
                  )}
                </div>
              </div>
            )}
            {exploreLoading && <div className={`mb-4 text-xs px-3 py-2 border rounded-lg ${isDarkMode ? 'bg-blue-900/20 text-blue-300 border-blue-700' : 'bg-blue-50 text-blue-700 border-blue-200'}`}>Loading maps…</div>}
            <div className="flex gap-2 mb-5">
              <input value={exploreQuery} onChange={(e) => setExploreQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { setExplorePage(1); loadExplore(1, exploreQuery); } }} placeholder='Search maps, e.g. "indica user:srajma"' className={`flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`} />
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors" onClick={() => { setExplorePage(1); loadExplore(1, exploreQuery); }}>Search</button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {(exploreData.items || []).map((item) => renderExploreCatalogCard(item))}
            </div>
            <div className={`flex items-center gap-3 mt-5 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>
              <button disabled={explorePage <= 1} className={`px-3 py-1.5 rounded-lg border text-xs disabled:opacity-40 transition-colors ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.max(1, explorePage - 1); setExplorePage(p); loadExplore(p, exploreQuery); }}>← Prev</button>
              <span className="text-xs">Page {explorePage} / {totalPages}</span>
              <button disabled={explorePage >= totalPages} className={`px-3 py-1.5 rounded-lg border text-xs disabled:opacity-40 transition-colors ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.min(totalPages, explorePage + 1); setExplorePage(p); loadExplore(p, exploreQuery); }}>Next →</button>
            </div>
          </div>
          {/* Users sidebar */}
          <div className={`w-64 flex-shrink-0 border-l overflow-y-auto px-4 py-5 ${isDarkMode ? 'border-slate-800 bg-slate-900/30' : 'border-gray-200 bg-white'}`}>
            <div className={`text-xs font-semibold mb-3 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Users</div>
            {usersLoading && <div className={`mb-3 text-xs px-2 py-1 border rounded ${isDarkMode ? 'bg-blue-900/20 text-blue-300 border-blue-700' : 'bg-blue-50 text-blue-700 border-blue-200'}`}>Loading…</div>}
            <div className={`flex gap-1.5 mb-3`}>
              <input value={usersQuery} onChange={(e) => setUsersQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { setUsersPage(1); loadUsers(1, usersQuery); } }} placeholder="Search users…" className={`flex-1 rounded-lg border px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`} />
              <button className="px-2 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors" onClick={() => { setUsersPage(1); loadUsers(1, usersQuery); }}>Go</button>
            </div>
            <div className="space-y-1.5">
              {(usersData.items || []).map((u) => (
                <a key={u.username} href={`/user/${u.username}`} className={`block rounded-lg border px-3 py-2 hover:shadow-sm transition-shadow ${isDarkMode ? 'bg-slate-800 border-slate-700 hover:border-slate-600' : 'bg-gray-50 border-gray-200 hover:border-gray-300 hover:bg-white'}`}>
                  <div className={`font-mono text-xs font-medium ${isDarkMode ? 'text-blue-400' : 'text-blue-700'}`}>{u.username}</div>
                  {u.full_name && <div className={`text-[11px] mt-0.5 truncate ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>{u.full_name}</div>}
                  <div className={`text-[10px] mt-1 ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>{u.maps_count || 0} maps</div>
                </a>
              ))}
            </div>
            {usersTotalPages > 1 && (
              <div className={`flex items-center gap-2 mt-4 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                <button disabled={usersPage <= 1} className={`px-2 py-1 rounded border text-[11px] disabled:opacity-40 ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.max(1, usersPage - 1); setUsersPage(p); loadUsers(p, usersQuery); }}>←</button>
                <span className="text-[11px]">{usersPage}/{usersTotalPages}</span>
                <button disabled={usersPage >= usersTotalPages} className={`px-2 py-1 rounded border text-[11px] disabled:opacity-40 ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.min(usersTotalPages, usersPage + 1); setUsersPage(p); loadUsers(p, usersQuery); }}>→</button>
              </div>
            )}
          </div>
        </div>
      </div>
      {renderGlobalModals()}
      </>
    );
  }

  if (route.page === 'profile') {
    const profile = profileData?.profile;
    const maps = profileData?.maps || [];
    const totalPages = Math.max(1, Math.ceil((profileData?.total || 0) / (profileData?.per_page || 12)));
    const viewingOwnProfilePath = route.username && route.username === normalizedHubUsername;
    if (viewingOwnProfilePath && !authReady) {
      return (
        <div className={`h-screen w-full flex flex-col ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-50'}`}>
          {renderTopBar()}
          <div className="flex-1 flex items-center justify-center">
            <div className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Loading profile…</div>
          </div>
        </div>
      );
    }
    const isOwn = authReady && profile?.username && profile.username === normalizedHubUsername && currentUser.is_authenticated;
    const profInputCls = `w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`;
    return (
      <>
      <div className={`h-screen w-full flex flex-col ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-50'}`}>
        {renderTopBar()}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Profile header */}
          <div className={`border-b px-6 py-5 flex-shrink-0 ${isDarkMode ? 'border-slate-800 bg-slate-900/50' : 'border-gray-200 bg-white'}`}>
            <div className="flex items-start gap-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center text-2xl font-bold flex-shrink-0 ${isDarkMode ? 'bg-slate-700 text-slate-300' : 'bg-gray-200 text-gray-600'}`}>{((profile?.username || route.username || '?')[0] || '?').toUpperCase()}</div>
              <div className="flex-1 min-w-0">
                <div className={`font-mono text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>{profile?.username || route.username}</div>
                {profile?.full_name && <div className={`text-sm ${isDarkMode ? 'text-slate-300' : 'text-gray-700'}`}>{profile.full_name}</div>}
                {profile?.bio && <div className={`text-sm mt-1 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>{profile.bio}</div>}
                <div className={`text-xs mt-1.5 ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>{profile?.maps_count || 0} maps · {profile?.views_count || 0} views</div>
              </div>
              {isOwn && (
                <button
                  onClick={() => setProfileSettingsOpen((p) => !p)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors flex-shrink-0 ${profileSettingsOpen ? (isDarkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-gray-100 border-gray-300 text-gray-800') : (isDarkMode ? 'border-slate-700 text-slate-400 hover:bg-slate-800' : 'border-gray-200 text-gray-500 hover:bg-gray-50')}`}
                  title="Account settings"
                >
                  <Settings size={12}/> Settings
                </button>
              )}
            </div>
            {/* Collapsible account settings */}
            {isOwn && profileSettingsOpen && (
              <div className={`mt-4 pt-4 border-t ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`}>
                <div className={`text-xs font-semibold uppercase tracking-wide mb-3 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>Account settings</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className={`text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-300' : 'text-gray-700'}`}>Profile</div>
                    <input className={profInputCls} placeholder="Full name" value={profileEdit.full_name} onChange={(e) => setProfileEdit((p) => ({ ...p, full_name: e.target.value }))} />
                    <textarea className={`${profInputCls} min-h-[64px] resize-none`} placeholder="Profile description" value={profileEdit.bio} onChange={(e) => setProfileEdit((p) => ({ ...p, bio: e.target.value }))} />
                    <button className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-700' : 'border-gray-300 text-gray-700 hover:bg-gray-100'}`} onClick={handleSaveProfile}>Save profile</button>
                  </div>
                  <div className="space-y-2">
                    <div className={`text-xs font-medium mb-1 ${isDarkMode ? 'text-slate-300' : 'text-gray-700'}`}>Change password</div>
                    <input type="password" className={profInputCls} placeholder="Current password" value={passwordEdit.current_password} onChange={(e) => setPasswordEdit((p) => ({ ...p, current_password: e.target.value }))} />
                    <input type="password" className={profInputCls} placeholder="New password" value={passwordEdit.new_password} onChange={(e) => setPasswordEdit((p) => ({ ...p, new_password: e.target.value }))} />
                    <button className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${isDarkMode ? 'border-slate-600 text-slate-300 hover:bg-slate-700' : 'border-gray-300 text-gray-700 hover:bg-gray-100'}`} onClick={handleChangePassword}>Update password</button>
                  </div>
                </div>
              </div>
            )}
          </div>
          {/* Maps grid */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {profileLoading && <div className={`mb-4 text-xs px-3 py-2 border rounded-lg ${isDarkMode ? 'bg-blue-900/20 text-blue-300 border-blue-700' : 'bg-blue-50 text-blue-700 border-blue-200'}`}>Loading maps…</div>}
            <div className="flex gap-2 mb-5">
              <input value={profileSearch} onChange={(e) => setProfileSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { setProfilePage(1); loadProfile(route.username, 1, profileSearch); } }} className={`flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 ${isDarkMode ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-400' : 'bg-white border-gray-300 focus:border-blue-400'}`} placeholder="Search maps…" />
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors" onClick={() => { setProfilePage(1); loadProfile(route.username, 1, profileSearch); }}>Search</button>
            </div>
            {maps.length === 0 && !profileLoading && !isOwn && (
              <div className={`text-sm text-center py-12 ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>No maps yet.</div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {isOwn && (
                <button
                  onClick={handleNewMapClick}
                  className={`rounded-xl border h-full min-h-[168px] flex flex-col items-center justify-center gap-1.5 text-xs font-medium transition-colors ${isDarkMode ? 'bg-slate-800 border-slate-700 text-slate-300 hover:border-blue-500 hover:text-blue-400' : 'bg-white border-gray-200 text-gray-500 hover:border-blue-400 hover:text-blue-600'}`}
                >
                  <Plus size={18}/>
                  New map
                </button>
              )}
              {isOwn && userDraftMeta?.exists && (
                <button
                  onClick={() => { setPromoteDraftName(''); setPromoteDraftError(''); setPromoteDraftDialogOpen(true); }}
                  className={`rounded-xl border h-full min-h-[168px] flex flex-col items-center justify-center gap-1 text-xs transition-colors ${isDarkMode ? 'bg-slate-800 border-red-700/50 hover:border-red-500' : 'bg-white border-red-200 hover:border-red-400'}`}
                >
                  <div className={`font-semibold ${isDarkMode ? 'text-red-400' : 'text-red-500'}`}>Unsaved Draft</div>
                  <div className={`text-[10px] ${isDarkMode ? 'text-slate-400' : 'text-gray-400'}`}>{userDraftMeta.mapName}</div>
                </button>
              )}
              {maps.map((m) => (
                <div key={m.slug} className={`relative group rounded-xl border overflow-hidden shadow-sm hover:shadow-md transition-shadow ${isDarkMode ? 'bg-slate-800 border-slate-700 hover:border-slate-600' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                  <a href={m.slug} className="block">
                    <img src={m.thumbnail || '/vite.svg'} alt="" className={`w-full h-28 object-cover ${isDarkMode ? 'bg-slate-700' : 'bg-gray-100'}`} />
                    <div className="p-3">
                      <div className={`font-mono text-xs font-medium truncate group-hover:text-blue-500 transition-colors ${isDarkMode ? 'text-slate-200' : 'text-slate-800'}`}>{m.name}</div>
                      <div className={`flex items-center gap-2 mt-1 text-[10px] ${isDarkMode ? 'text-slate-500' : 'text-gray-400'}`}>
                        <span className="inline-flex items-center gap-0.5"><Triangle size={9}/> {m.votes || 0}</span>
                        <span>{m.views || 0} views</span>
                      </div>
                    </div>
                  </a>
                  {isOwn && (
                    <button
                      onClick={() => setDisassociateConfirm({ open: true, kind: m.kind || 'map', name: m.name, nameInput: '', loading: false, error: null })}
                      className={`absolute top-2 right-2 p-1 rounded border opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50 hover:border-red-300 ${isDarkMode ? 'bg-slate-800/80 border-slate-600' : 'bg-white/80 border-gray-200'}`}
                      title="Disassociate from your account"
                    >
                      <UserX size={11} className={`${isDarkMode ? 'text-slate-400' : 'text-gray-400'} hover:text-red-500`}/>
                    </button>
                  )}
                </div>
              ))}
            </div>
            {totalPages > 1 && (
              <div className={`flex items-center gap-3 mt-6 ${isDarkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                <button disabled={profilePage <= 1} className={`px-3 py-1.5 rounded-lg border text-xs disabled:opacity-40 transition-colors ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.max(1, profilePage - 1); setProfilePage(p); loadProfile(route.username, p, profileSearch); }}>← Prev</button>
                <span className="text-xs">Page {profilePage} / {totalPages}</span>
                <button disabled={profilePage >= totalPages} className={`px-3 py-1.5 rounded-lg border text-xs disabled:opacity-40 transition-colors ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`} onClick={() => { const p = Math.min(totalPages, profilePage + 1); setProfilePage(p); loadProfile(route.username, p, profileSearch); }}>Next →</button>
              </div>
            )}
          </div>
        </div>
      </div>
      {renderGlobalModals()}
      </>
    );
  }

  if (route.page === 'editor' && !editorContextReady) {
    return (
      <div className={`h-screen w-full flex flex-col ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
        {renderTopBar()}
        <div className="flex-1 flex items-center justify-center">
          <div className={`text-sm ${isDarkMode ? 'text-slate-300' : 'text-gray-600'}`}>Loading editor context...</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-screen font-sans ${isDarkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-gray-100'}`}>
      {renderTopBar()}
      <div className="flex flex-1 overflow-hidden">
      {/* Full-screen overlay during sidebar drag to prevent iframe capturing mouse events */}
      {sidebarDragging && <div className="fixed inset-0 z-50 cursor-col-resize" style={{ userSelect: 'none' }} />}
      {/* Sidebar */}
      <div className="flex flex-col bg-white border-gray-200 shadow-md z-10 flex-shrink-0 overflow-hidden" style={{ width: sidebarWidth }}>
        <div className="p-4 border-b border-gray-200 bg-gray-50 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-wrap">
              <input
                type="text"
                value={mapName}
                onChange={(e) => setMapName(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''))}
                disabled={isReadOnlyMap || hasPublishedVersions}
                className={`w-30 text-sm p-1.5 border rounded bg-white font-mono disabled:bg-gray-100 disabled:text-gray-500 ${HUB_NAME_RE.test(normalizedMapName) ? 'border-gray-300' : 'border-red-400'}`}
                title={hasPublishedVersions ? 'Map name cannot be changed after publishing a version' : 'Map title'}
                placeholder="map_name"
              />
              {statusNotice && <span className="text-[10px] text-amber-700">{statusNotice}</span>}
              {isReadOnlyMap ? (
                <button onClick={handleForkMap} className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50 inline-flex items-center justify-center" title="Fork map">
                  <GitFork size={13} className="text-gray-700"/>
                </button>
              ) : (
                <button onClick={() => handlePublishMap()} className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50 inline-flex items-center justify-center" title="Publish new version">
                  <CloudUpload size={13} className="text-gray-700"/>
                </button>
              )}
              {currentMapVersionOptions.length > 0 && (
                <select
                  value={viewedMapVersion}
                  onChange={(e) => handleMapVersionSelect(e.target.value)}
                  className="text-[11px] border rounded px-1.5 py-1 bg-white font-mono"
                  title="Map version"
                >
                  {currentMapVersionOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              )}
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
          {showMapMetaLine && (
            <>
              <div className="text-xs text-gray-600 flex items-center gap-2">
                <span>by</span>
                <a href={`/user/${mapOwner}`} className="text-blue-700 hover:underline">{mapOwner}</a>
                <span>·</span>
                <button
                  onClick={isMapAuthor ? undefined : handleVoteMap}
                  disabled={!route.map || isMapAuthor}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border transition-colors ${
                    isMapAuthor
                      ? 'cursor-default border-blue-600 bg-blue-600 text-white'
                      : !route.map
                        ? 'opacity-40'
                        : hasLikedMap
                          ? 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700'
                          : 'border-gray-300 text-gray-700 hover:bg-blue-50 hover:border-blue-300'
                  }`}
                  title={isMapAuthor ? 'You always like your own map' : 'Like/unlike'}
                >
                  <Triangle size={12} className={hasLikedMap ? 'text-white fill-white' : 'text-gray-500'} />
                  <span>{mapVotes} likes</span>
                </button>
                <span>·</span>
                <span>{mapViews} views</span>
                {forkedFrom && (
                  <>
                    <span>·</span>
                    <span>fork of <a href={forkedFrom} className="text-blue-700 hover:underline">{forkedFrom}</a></span>
                  </>
                )}
                {!isReadOnlyMap && autoSaveStatus !== 'idle' && (
                  <>
                    <span>·</span>
                    {autoSaveStatus === 'unsaved' && (
                      <>
                        <span className="text-xs text-red-500 font-medium">Unsaved changes</span>
                        <span>·</span>
                        <button
                          onClick={async () => { const c = await buildMapArtifactContent().catch(() => null); if (c) performAutoSave(c); }}
                          className="text-xs text-blue-600 hover:underline"
                          title="Save now"
                        >Save now</button>
                      </>
                    )}
                    {autoSaveStatus === 'saving' && <span className="text-xs text-gray-500">Saving…</span>}
                    {autoSaveStatus === 'saved' && <span className="text-xs text-green-600">All changes saved</span>}
                    {autoSaveStatus === 'conflict' && <span className="text-xs text-red-600"><button onClick={async () => { const c = await buildMapArtifactContent().catch(() => null); if (c) performAutoSave(c); }} className="underline hover:no-underline" title="Retry save">Save</button> failed: name conflict</span>}
                  </>
                )}
              </div>
            </>
          )}
          {route.page === 'editor' && !currentUser.is_authenticated && (
            <div className="text-xs flex items-center gap-2 mt-0.5">
              {guestHasChanges && <span className="text-red-500 font-medium">Unsaved changes</span>}
              {guestHasChanges && <span className="text-gray-400">·</span>}
              <a href="/login" className="text-blue-600 hover:underline">Login to save/publish</a>
            </div>
          )}
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
                libraryPublishStatus={libraryPublishStatus}
                themePublishStatus={themePublishStatus}
                readOnlyMap={isReadOnlyMap}
                readOnlyLibrary={isReadOnlyMap || selectedLibraryVersion !== 'alpha'}
                readOnlyTheme={isReadOnlyMap || selectedThemeVersion !== 'alpha'}
            />
          )}
        </div>

        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={renderMap}
            className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-sm flex items-center justify-center gap-2 transition-all"
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
      {/* Sidebar resize handle — sibling so it stays visible even at width 0 */}
      <div
        className="w-1.5 flex-shrink-0 cursor-col-resize z-20 hover:bg-blue-400 hover:opacity-50 transition-colors border-r border-gray-200 bg-transparent"
        onMouseDown={(e) => {
          sidebarResizingRef.current = true;
          setSidebarDragging(true);
          sidebarStartXRef.current = e.clientX;
          sidebarStartWidthRef.current = sidebarWidth;
          document.body.style.cursor = 'col-resize';
          document.body.style.userSelect = 'none';
          e.preventDefault();
        }}
      />

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
          <div
            ref={librarySubTabsRef}
            className={`absolute top-16 left-1/2 transform -translate-x-1/2 z-20 flex backdrop-blur shadow-md rounded-full p-1 border ${mapTabBarClass}`}
            onKeyDown={(e) => {
              const btns = Array.from(librarySubTabsRef.current?.querySelectorAll('button') || []);
              const idx = btns.indexOf(document.activeElement);
              if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); btns[(idx + 1) % btns.length]?.focus(); }
              else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); btns[(idx - 1 + btns.length) % btns.length]?.focus(); }
              else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); btns[idx]?.click(); }
            }}
          >
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
                                     endpoint={`${API_BASE}/search/gadm`}
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
                <div className="absolute inset-0 z-30 pointer-events-none flex items-end justify-center pb-4">
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
      {renderGlobalModals()}
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
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); searchHubRegistry(); }
                  else if (e.key === 'Escape') { e.preventDefault(); setImportModalOpen(false); }
                  else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    importGridRef.current?.querySelector('[data-import-card]')?.focus();
                  }
                }}
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
            <div ref={importGridRef} className="flex-1 overflow-auto p-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {(hubSearchResults || []).map((item) => renderImportCatalogCard(item))}
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

export default App;
