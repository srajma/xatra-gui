import React, { useRef, useEffect, useCallback } from 'react';
import { Map, Users, MapPin, Type, GitMerge, Table, Heading, Code2, Import, Trash2, Music } from 'lucide-react';
import LayerItem from './LayerItem';
import GlobalOptions from './GlobalOptions';

const Builder = ({ 
  elements, setElements, options, setOptions, onGetCurrentView, 
  lastMapClick, activePicker, setActivePicker, draftPoints, setDraftPoints,
  onSaveTerritory, predefinedCode, onStartReferencePick, addLayerSignal, onConsumeAddLayerSignal,
  hubImports, onOpenImportModal, onRemoveHubImport, getImportVersionOptions, onSwitchHubImportVersion,
  runtimeElements = [], runtimeSetElements = null, runtimeOptions = {}, runtimeSetOptions = null,
  runtimeHubImports = [], onOpenRuntimeImportModal = null, onRemoveRuntimeHubImport = null, onSwitchRuntimeHubImportVersion = null,
  trustedUser = false,
  readOnly = false,
  isDarkMode = false,
}) => {
  const layersContainerRef = useRef(null);
  const runtimeLayersContainerRef = useRef(null);
  const prevElementsLengthRef = useRef(elements.length);
  const pendingFocusNewLayerRef = useRef(false);
  const focusTimeoutsRef = useRef([]);

  const _newElementForType = (type) => {
    let newElement = {
      type, 
      label: 'New ' + type, 
      value: '',
      args: {} 
    };

    switch (type) {
      case 'flag':
        newElement.label = 'New Country';
        newElement.value = [];
        break;
      case 'river':
        newElement.value = '1159122643';
        newElement.args = { source_type: 'naturalearth' };
        break;
      case 'point':
        newElement.value = '[28.6, 77.2]';
        break;
      case 'text':
        newElement.value = '[28.6, 77.2]';
        break;
      case 'path':
        newElement.value = '[]';
        break;
      case 'admin':
        newElement.value = 'IND';
        newElement.args = { level: 1 };
        break;
      case 'dataframe':
        newElement.label = 'Data';
        newElement.value = 'GID,value\nIND,100\nPAK,50';
        newElement.args = { data_column: 'value' };
        break;
      case 'titlebox':
        newElement.label = 'TitleBox';
        newElement.value = '<b>My Map</b>';
        newElement.args = {};
        break;
      case 'music':
        newElement.label = 'Music';
        newElement.value = '';
        newElement.args = {};
        break;
      case 'python':
        newElement.label = 'Python';
        newElement.value = '# custom Python layer';
        newElement.args = {};
        break;
      default:
        break;
    }
    return newElement;
  };

  const addElement = (type, opts = { focusFirstField: true }) => {
    if (readOnly) return;
    const newElement = _newElementForType(type);

    if (opts.focusFirstField) pendingFocusNewLayerRef.current = true;
    setElements([newElement, ...elements]);
  };

  const addRuntimeElement = (type) => {
    if (readOnly || typeof runtimeSetElements !== 'function') return;
    const newElement = _newElementForType(type);
    runtimeSetElements([newElement, ...(runtimeElements || [])]);
  };

  useEffect(() => {
    if (elements.length > prevElementsLengthRef.current && layersContainerRef.current) {
      layersContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
      if (pendingFocusNewLayerRef.current) {
        // Clear any previous pending focus timeouts
        focusTimeoutsRef.current.forEach(clearTimeout);
        focusTimeoutsRef.current = [];
        [0, 40, 120, 240].forEach((delay) => {
          const id = window.setTimeout(() => {
            focusTimeoutsRef.current = focusTimeoutsRef.current.filter((t) => t !== id);
            const cards = document.querySelectorAll('#layers-container .xatra-layer-card');
            const firstCard = cards[0];
            if (!firstCard) return;
            const firstField = firstCard.querySelector('[data-focus-primary="true"], input, textarea, select');
            if (firstField && typeof firstField.focus === 'function') {
              firstField.focus();
              if (typeof firstField.select === 'function' && (firstField.tagName === 'INPUT' || firstField.tagName === 'TEXTAREA')) {
                firstField.select();
              }
            }
          }, delay);
          focusTimeoutsRef.current.push(id);
        });
        pendingFocusNewLayerRef.current = false;
      }
    }
    prevElementsLengthRef.current = elements.length;
    return () => {
      focusTimeoutsRef.current.forEach(clearTimeout);
      focusTimeoutsRef.current = [];
    };
  }, [elements.length]);

  useEffect(() => {
    if (!addLayerSignal || !addLayerSignal.type) return;
    addElement(addLayerSignal.type, { focusFirstField: true });
    if (typeof onConsumeAddLayerSignal === 'function') {
      onConsumeAddLayerSignal();
    }
  }, [addLayerSignal]);

  const removeElement = (index) => {
    if (readOnly) return;
    const newElements = [...elements];
    newElements.splice(index, 1);
    setElements(newElements);
  };

  const updateElement = (index, field, value) => {
    if (readOnly) return;
    const newElements = [...elements];
    newElements[index][field] = value;
    setElements(newElements);
  };

  const updateArg = (index, key, value) => {
    if (readOnly) return;
    const newElements = [...elements];
    newElements[index].args = { ...newElements[index].args, [key]: value };
    setElements(newElements);
  };

  const replaceElement = (index, newElement) => {
    if (readOnly) return;
    const newElements = [...elements];
    newElements[index] = newElement;
    setElements(newElements);
  };

  const removeRuntimeElement = (index) => {
    if (readOnly || typeof runtimeSetElements !== 'function') return;
    const newElements = [...(runtimeElements || [])];
    newElements.splice(index, 1);
    runtimeSetElements(newElements);
  };

  const updateRuntimeElement = (index, field, value) => {
    if (readOnly || typeof runtimeSetElements !== 'function') return;
    const newElements = [...(runtimeElements || [])];
    newElements[index][field] = value;
    runtimeSetElements(newElements);
  };

  const updateRuntimeArg = (index, key, value) => {
    if (readOnly || typeof runtimeSetElements !== 'function') return;
    const newElements = [...(runtimeElements || [])];
    newElements[index].args = { ...newElements[index].args, [key]: value };
    runtimeSetElements(newElements);
  };

  const replaceRuntimeElement = (index, newElement) => {
    if (readOnly || typeof runtimeSetElements !== 'function') return;
    const newElements = [...(runtimeElements || [])];
    newElements[index] = newElement;
    runtimeSetElements(newElements);
  };

  return (
    <div className={`space-y-6 ${readOnly ? 'opacity-70' : ''}`}>
      <section className={`bg-white p-4 rounded-lg border border-gray-200 shadow-sm ${readOnly ? 'pointer-events-none' : ''}`}>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-900">Imports</h3>
          <button
            type="button"
            onClick={onOpenImportModal}
            className="text-xs px-2 py-1 border border-gray-200 rounded bg-gray-50 hover:bg-gray-100 inline-flex items-center gap-1"
          >
            <Import size={12} /> Import from existing map
          </button>
        </div>
        {(hubImports || []).length === 0 ? (
          <div className="text-xs text-gray-500">No imports yet.</div>
        ) : (
          <div className="space-y-1">
            {(hubImports || []).map((imp, idx) => (
              <div key={`${imp.kind}-${imp.path}-${idx}`} className="flex items-center justify-between px-2 py-1 rounded border border-gray-100 bg-gray-50">
                <div className="text-[11px] font-mono text-gray-700 flex-1 min-w-0">
                  {imp.kind} /{imp.name}
                </div>
                <div className="flex items-center gap-1 mr-2">
                  <select
                    value={imp._draft_version || imp.selected_version || 'alpha'}
                    onChange={(e) => onSwitchHubImportVersion?.(idx, e.target.value, false)}
                    className="text-[11px] border rounded px-1 py-0.5"
                  >
                    {(getImportVersionOptions?.(imp) || [{ value: 'alpha', label: 'alpha' }]).map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => onSwitchHubImportVersion?.(idx, imp._draft_version || imp.selected_version || 'alpha', true)}
                    disabled={!imp._draft_version || imp._draft_version === (imp.selected_version || 'alpha')}
                    className="text-[11px] px-1.5 py-0.5 border rounded disabled:opacity-40 hover:bg-gray-100"
                  >
                    Switch version
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveHubImport?.(idx)}
                  className="p-1 rounded hover:bg-red-50 text-red-600"
                  title="Remove import"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Global Options */}
      <div className={readOnly ? 'pointer-events-none' : ''}>
        <GlobalOptions
          options={options}
          setOptions={setOptions}
          elements={elements}
          onGetCurrentView={onGetCurrentView}
        />
      </div>

      {/* Layers */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Layers</h3>
        </div>

        <div ref={layersContainerRef} className="space-y-3 overflow-auto max-h-[70vh]" id="layers-container">
          <div className={`grid grid-cols-3 gap-2 pt-1 sm:grid-cols-4 ${readOnly ? 'pointer-events-none' : ''}`}>
             <button data-kind="flag" onClick={() => addElement('flag', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 text-[10px] gap-1 border border-blue-100">
               <Map size={14}/> Flag
             </button>
             <button data-kind="river" onClick={() => addElement('river', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-cyan-50 text-cyan-700 rounded hover:bg-cyan-100 text-[10px] gap-1 border border-cyan-100">
               <span className="text-lg leading-3">~</span> River
             </button>
             <button data-kind="point" onClick={() => addElement('point', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-purple-50 text-purple-700 rounded hover:bg-purple-100 text-[10px] gap-1 border border-purple-100">
               <MapPin size={14}/> Point
             </button>
             <button data-kind="text" onClick={() => addElement('text', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 text-[10px] gap-1 border border-gray-100">
               <Type size={14}/> Text
             </button>
             <button data-kind="path" onClick={() => addElement('path', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-orange-50 text-orange-700 rounded hover:bg-orange-100 text-[10px] gap-1 border border-orange-100">
               <GitMerge size={14}/> Path
             </button>
             <button data-kind="admin" onClick={() => addElement('admin', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100 text-[10px] gap-1 border border-indigo-100">
               <Users size={14}/> Admin
             </button>
             <button data-kind="data" onClick={() => addElement('dataframe', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-green-50 text-green-700 rounded hover:bg-green-100 text-[10px] gap-1 border border-green-100">
               <Table size={14}/> Data
             </button>
             <button data-kind="titlebox" onClick={() => addElement('titlebox', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-fuchsia-50 text-fuchsia-700 rounded hover:bg-fuchsia-100 text-[10px] gap-1 border border-fuchsia-100">
               <Heading size={14}/> TitleBox
             </button>
             <button data-kind="music" onClick={() => addElement('music', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-pink-50 text-pink-700 rounded hover:bg-pink-100 text-[10px] gap-1 border border-pink-100">
               <Music size={14}/> Music
             </button>
             {trustedUser && (
               <button data-kind="python" onClick={() => addElement('python', { focusFirstField: true })} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-amber-50 text-amber-700 rounded hover:bg-amber-100 text-[10px] gap-1 border border-amber-100">
                 <Code2 size={14}/> Python
               </button>
             )}
          </div>

          {elements.map((el, index) => (
            <LayerItem
              key={index}
              element={el}
              index={index}
              elements={elements}
              updateElement={updateElement}
              updateArg={updateArg}
              replaceElement={replaceElement}
              removeElement={removeElement}
              lastMapClick={lastMapClick}
              activePicker={activePicker}
              setActivePicker={setActivePicker}
              draftPoints={draftPoints}
              setDraftPoints={setDraftPoints}
              onSaveTerritory={onSaveTerritory}
              predefinedCode={predefinedCode}
              onStartReferencePick={onStartReferencePick}
              hubImports={hubImports}
              trustedUser={trustedUser}
              isDarkMode={isDarkMode}
              readOnly={readOnly}
            />
          ))}
          
          {elements.length === 0 && (
            <div className="text-center py-8 border-2 border-dashed border-gray-200 rounded-lg text-gray-400 text-sm">
              No layers added yet. Add one above.
            </div>
          )}
        </div>
      </section>

      <details className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm" open={false}>
        <summary className="cursor-pointer text-sm font-semibold text-gray-900 select-none">Do not expose to importers</summary>
        <div className="mt-4 space-y-4">
          <div className={readOnly ? 'pointer-events-none' : ''}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-900">Imports</h3>
              <button
                type="button"
                onClick={onOpenRuntimeImportModal}
                className="text-xs px-2 py-1 border border-gray-200 rounded bg-gray-50 hover:bg-gray-100 inline-flex items-center gap-1"
              >
                <Import size={12} /> Import from existing map
              </button>
            </div>
            {(runtimeHubImports || []).length === 0 ? (
              <div className="text-xs text-gray-500">No imports yet.</div>
            ) : (
              <div className="space-y-1">
                {(runtimeHubImports || []).map((imp, idx) => (
                  <div key={`${imp.kind}-${imp.path}-${idx}`} className="flex items-center justify-between px-2 py-1 rounded border border-gray-100 bg-gray-50">
                    <div className="text-[11px] font-mono text-gray-700 flex-1 min-w-0">
                      {imp.kind} /{imp.name}
                    </div>
                    <div className="flex items-center gap-1 mr-2">
                      <select
                        value={imp._draft_version || imp.selected_version || 'alpha'}
                        onChange={(e) => onSwitchRuntimeHubImportVersion?.(idx, e.target.value, false)}
                        className="text-[11px] border rounded px-1 py-0.5"
                      >
                        {(getImportVersionOptions?.(imp) || [{ value: 'alpha', label: 'alpha' }]).map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => onSwitchRuntimeHubImportVersion?.(idx, imp._draft_version || imp.selected_version || 'alpha', true)}
                        disabled={!imp._draft_version || imp._draft_version === (imp.selected_version || 'alpha')}
                        className="text-[11px] px-1.5 py-0.5 border rounded disabled:opacity-40 hover:bg-gray-100"
                      >
                        Switch version
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemoveRuntimeHubImport?.(idx)}
                      className="p-1 rounded hover:bg-red-50 text-red-600"
                      title="Remove import"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className={readOnly ? 'pointer-events-none' : ''}>
            <GlobalOptions
              options={runtimeOptions || {}}
              setOptions={typeof runtimeSetOptions === 'function' ? runtimeSetOptions : (() => {})}
              elements={runtimeElements || []}
              onGetCurrentView={onGetCurrentView}
            />
          </div>
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">Runtime Layers</h3>
            </div>
            <div ref={runtimeLayersContainerRef} className="space-y-3 overflow-auto max-h-[60vh]" id="runtime-layers-container">
              <div className={`grid grid-cols-3 gap-2 pt-1 sm:grid-cols-4 ${readOnly ? 'pointer-events-none' : ''}`}>
                <button onClick={() => addRuntimeElement('flag')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 text-[10px] gap-1 border border-blue-100"><Map size={14}/> Flag</button>
                <button onClick={() => addRuntimeElement('river')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-cyan-50 text-cyan-700 rounded hover:bg-cyan-100 text-[10px] gap-1 border border-cyan-100"><span className="text-lg leading-3">~</span> River</button>
                <button onClick={() => addRuntimeElement('point')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-purple-50 text-purple-700 rounded hover:bg-purple-100 text-[10px] gap-1 border border-purple-100"><MapPin size={14}/> Point</button>
                <button onClick={() => addRuntimeElement('text')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 text-[10px] gap-1 border border-gray-100"><Type size={14}/> Text</button>
                <button onClick={() => addRuntimeElement('path')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-orange-50 text-orange-700 rounded hover:bg-orange-100 text-[10px] gap-1 border border-orange-100"><GitMerge size={14}/> Path</button>
                <button onClick={() => addRuntimeElement('admin')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100 text-[10px] gap-1 border border-indigo-100"><Users size={14}/> Admin</button>
                <button onClick={() => addRuntimeElement('dataframe')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-green-50 text-green-700 rounded hover:bg-green-100 text-[10px] gap-1 border border-green-100"><Table size={14}/> Data</button>
                <button onClick={() => addRuntimeElement('titlebox')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-fuchsia-50 text-fuchsia-700 rounded hover:bg-fuchsia-100 text-[10px] gap-1 border border-fuchsia-100"><Heading size={14}/> TitleBox</button>
                <button onClick={() => addRuntimeElement('music')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-pink-50 text-pink-700 rounded hover:bg-pink-100 text-[10px] gap-1 border border-pink-100"><Music size={14}/> Music</button>
                {trustedUser && (
                  <button onClick={() => addRuntimeElement('python')} className="xatra-add-layer-btn flex flex-col items-center justify-center p-2 bg-amber-50 text-amber-700 rounded hover:bg-amber-100 text-[10px] gap-1 border border-amber-100"><Code2 size={14}/> Python</button>
                )}
              </div>

              {(runtimeElements || []).map((el, index) => (
                <LayerItem
                  key={`runtime-${index}`}
                  element={el}
                  index={index}
                  elements={runtimeElements || []}
                  updateElement={updateRuntimeElement}
                  updateArg={updateRuntimeArg}
                  replaceElement={replaceRuntimeElement}
                  removeElement={removeRuntimeElement}
                  lastMapClick={lastMapClick}
                  activePicker={activePicker}
                  setActivePicker={setActivePicker}
                  draftPoints={draftPoints}
                  setDraftPoints={setDraftPoints}
                  onSaveTerritory={onSaveTerritory}
                  predefinedCode={predefinedCode}
                  onStartReferencePick={onStartReferencePick}
                  hubImports={hubImports}
                  trustedUser={trustedUser}
                  readOnly={readOnly}
                />
              ))}
              {(runtimeElements || []).length === 0 && (
                <div className="text-center py-8 border-2 border-dashed border-gray-200 rounded-lg text-gray-400 text-sm">
                  No runtime layers yet. Add one above.
                </div>
              )}
            </div>
          </section>
        </div>
      </details>
    </div>
  );
};

export default Builder;
