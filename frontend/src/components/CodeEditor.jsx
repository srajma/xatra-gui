import React, { useRef, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { CloudUpload } from 'lucide-react';

const XATRA_COMPLETIONS = {
  globals: [
    { label: 'xatra', kind: 'module', insertText: 'xatra', detail: 'Main map library' },
    { label: 'xatrahub', kind: 'function', insertText: 'xatrahub("${1:/username/map/name}")', insertTextRules: 4, detail: 'Import from XatraHub database' },
    { label: 'gadm', kind: 'function', insertText: 'gadm("${1:IND}")', insertTextRules: 4, detail: 'GADM territory by code' },
    { label: 'naturalearth', kind: 'function', insertText: 'naturalearth("${1:id}")', insertTextRules: 4, detail: 'Natural Earth river/feature' },
    { label: 'overpass', kind: 'function', insertText: 'overpass("${1:id}")', insertTextRules: 4, detail: 'Overpass/OSM feature' },
    { label: 'polygon', kind: 'function', insertText: 'polygon(${1:[[lat,lon],...]})', insertTextRules: 4, detail: 'Polygon from coordinates' },
    { label: 'Icon', kind: 'class', insertText: 'Icon', detail: 'from xatra.icon import Icon' },
  ],
  xatraMethods: [
    { label: 'Flag', insertText: 'Flag(label="${1:}", value=${2:gadm("IND")})', insertTextRules: 4 },
    { label: 'River', insertText: 'River(value=${1:naturalearth("id")})', insertTextRules: 4 },
    { label: 'Path', insertText: 'Path(label="${1:}", value=${2:[[28,77],[19,73]]})', insertTextRules: 4 },
    { label: 'Point', insertText: 'Point(label="${1:}", position=${2:[28.6, 77.2]})', insertTextRules: 4 },
    { label: 'Text', insertText: 'Text(label="${1:}", position=${2:[28.6, 77.2]})', insertTextRules: 4 },
    { label: 'Admin', insertText: 'Admin(gadm="${1:IND}", level=${2:1})', insertTextRules: 4 },
    { label: 'AdminRivers', insertText: 'AdminRivers(sources=${1:["naturalearth"]})', insertTextRules: 4 },
    { label: 'Dataframe', insertText: 'Dataframe(${1:df})', insertTextRules: 4 },
    { label: 'BaseOption', insertText: 'BaseOption("${1:Esri.WorldTopoMap}", default=${2:True})', insertTextRules: 4 },
    { label: 'TitleBox', insertText: 'TitleBox("${1:<b>Title</b>}")', insertTextRules: 4 },
    { label: 'CSS', insertText: 'CSS("""${1:.flag { } }""")', insertTextRules: 4 },
    { label: 'zoom', insertText: 'zoom(${1:4})', insertTextRules: 4 },
    { label: 'focus', insertText: 'focus(${1:20}, ${2:78})', insertTextRules: 4 },
    { label: 'slider', insertText: 'slider(${1:-500}, ${2:500})', insertTextRules: 4 },
    { label: 'FlagColorSequence', insertText: 'FlagColorSequence(${1:})', insertTextRules: 4 },
    { label: 'AdminColorSequence', insertText: 'AdminColorSequence(${1:})', insertTextRules: 4 },
    { label: 'DataColormap', insertText: 'DataColormap(${1:})', insertTextRules: 4 },
    { label: 'show', insertText: 'show()', insertTextRules: 4 },
  ],
};

const headingClass = 'px-3 py-2 bg-slate-900 text-slate-100 text-xs font-semibold rounded-t border border-slate-700 flex items-center justify-between';

const CodeEditor = ({
  pythonImports,
  code,
  setCode,
  predefinedCode,
  setPredefinedCode,
  importsCode,
  setImportsCode,
  themeCode,
  setThemeCode,
  runtimeImportsCode,
  setRuntimeImportsCode,
  runtimeCode,
  setRuntimeCode,
  libraryVersionLabel,
  themeVersionLabel,
  librarySlugText,
  themeSlugText,
  onSaveLibrary,
  onSaveTheme,
  onSelectLibraryVersion,
  onSelectThemeVersion,
  libraryVersionOptions = [{ value: 'alpha', label: 'alpha' }],
  themeVersionOptions = [{ value: 'alpha', label: 'alpha' }],
  libraryPublishStatus = null,
  themePublishStatus = null,
  readOnlyMap = false,
  readOnlyLibrary = false,
  readOnlyTheme = false,
}) => {
  const editorRef = useRef(null);
  const predefinedEditorRef = useRef(null);
  const completionDisposableRef = useRef(null);
  const mapChangeDisposableRef = useRef(null);
  const predefinedChangeDisposableRef = useRef(null);

  const handleEditorDidMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    if (mapChangeDisposableRef.current) {
      mapChangeDisposableRef.current.dispose();
      mapChangeDisposableRef.current = null;
    }
    mapChangeDisposableRef.current = editor.onDidChangeModelContent(() => {
      setCode(editor.getValue());
    });
    monaco.editor.defineTheme('xatra-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: { 'editor.background': '#0f172a' },
    });
    monaco.editor.setTheme('xatra-dark');

    if (completionDisposableRef.current) {
      completionDisposableRef.current.dispose();
      completionDisposableRef.current = null;
    }

    completionDisposableRef.current = monaco.languages.registerCompletionItemProvider('python', {
      triggerCharacters: ['.', '('],
      provideCompletionItems: (model, position) => {
        const textUntilPosition = model.getValueInRange({ startLineNumber: 1, startColumn: 1, endLineNumber: position.lineNumber, endColumn: position.column });
        const word = model.getWordUntilPosition(position);
        const linePrefix = textUntilPosition.slice(-80);
        const items = [];
        if (linePrefix.endsWith('xatra.')) {
          XATRA_COMPLETIONS.xatraMethods.forEach((m) => {
            items.push({
              label: m.label,
              kind: monaco.languages.CompletionItemKind.Method,
              insertText: m.insertText,
              insertTextRules: m.insertTextRules ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet : undefined,
            });
          });
        } else {
          XATRA_COMPLETIONS.globals.forEach((g) => {
            if (!word.word || g.label.toLowerCase().startsWith(word.word.toLowerCase())) {
              items.push({
                label: g.label,
                kind: g.kind === 'module' ? monaco.languages.CompletionItemKind.Module : monaco.languages.CompletionItemKind.Function,
                insertText: g.insertText,
                insertTextRules: g.insertTextRules ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet : undefined,
                detail: g.detail,
              });
            }
          });
        }
        return { suggestions: items };
      },
    });
  }, [setCode]);

  const handlePredefinedMount = useCallback((editor) => {
    predefinedEditorRef.current = editor;
    if (predefinedChangeDisposableRef.current) {
      predefinedChangeDisposableRef.current.dispose();
      predefinedChangeDisposableRef.current = null;
    }
    predefinedChangeDisposableRef.current = editor.onDidChangeModelContent(() => {
      setPredefinedCode(editor.getValue());
    });
  }, [setPredefinedCode]);

  useEffect(() => {
    return () => {
      if (completionDisposableRef.current) completionDisposableRef.current.dispose();
      if (mapChangeDisposableRef.current) mapChangeDisposableRef.current.dispose();
      if (predefinedChangeDisposableRef.current) predefinedChangeDisposableRef.current.dispose();
    };
  }, []);

  return (
    <div className="h-full flex flex-col space-y-3 min-h-0">
      <div className="bg-red-600 text-white border border-red-700 rounded-md px-3 py-2 text-xs font-semibold">
        If you are using <b>Vimium</b>, please DISABLE it on this website.
      </div>

      <div className="flex flex-col min-h-0 space-y-3 overflow-y-auto pr-1">
        <div>
          <div className={headingClass}>
            <span>Python Imports</span>
          </div>
          <textarea
            className="w-full min-h-[108px] p-2 border border-slate-700 border-t-0 rounded-b bg-slate-950 text-slate-300 font-mono text-xs"
            value={pythonImports || ''}
            readOnly
            spellCheck={false}
          />
        </div>

        <div>
          <div className={headingClass}>
            <span>xatrahub Imports</span>
            {/* <span className="text-[10px] text-slate-300">`xatrahub("/user/map/name")`</span> */}
          </div>
          <textarea
            className="w-full min-h-[92px] p-2 border border-slate-700 border-t-0 rounded-b bg-slate-950 text-slate-100 font-mono text-xs focus:outline-none"
            value={importsCode}
            onChange={(e) => setImportsCode(e.target.value)}
            readOnly={readOnlyMap}
            spellCheck={false}
          />
        </div>

        <div>
          <div className={headingClass}>
            <span>Custom Territory Library <span className="font-mono text-[10px] text-slate-300 ml-1">{librarySlugText}</span></span>
            <div className="flex items-center gap-1">
              {libraryPublishStatus && (
                <span className={`text-[10px] font-mono ${libraryPublishStatus === 'no_changes' ? 'text-slate-400' : libraryPublishStatus === 'publishing' ? 'text-slate-300' : 'text-green-400'}`}>
                  {libraryPublishStatus === 'no_changes' ? 'No changes' : libraryPublishStatus === 'publishing' ? 'Publishing…' : libraryPublishStatus.replace('published:', '')}
                </span>
              )}
              <button type="button" onClick={() => onSaveLibrary()} disabled={readOnlyLibrary} className="px-1.5 py-1 rounded border border-slate-600 hover:bg-slate-800 inline-flex items-center gap-1 disabled:opacity-40" title="Publish new library version">
                <CloudUpload size={12} />
              </button>
              <select value={libraryVersionLabel} onChange={(e) => onSelectLibraryVersion?.(e.target.value)} className="px-1 py-1 rounded border border-slate-600 bg-slate-900 text-slate-100 text-[10px] font-mono">
                {libraryVersionOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
          </div>
          <div className="border border-slate-700 border-t-0 rounded-b overflow-hidden">
            <Editor
              height={160}
              defaultLanguage="python"
              path="xatra_territory_library.py"
              value={predefinedCode || ''}
              onMount={handlePredefinedMount}
              theme="xatra-dark"
              options={{ minimap: { enabled: false }, fontSize: 13, lineNumbers: 'on', scrollBeyondLastLine: false, wordWrap: 'on', readOnly: readOnlyLibrary }}
            />
          </div>
        </div>

        <div>
          <div className={headingClass}>
            <span>Custom Theme <span className="font-mono text-[10px] text-slate-300 ml-1">{themeSlugText}</span></span>
            <div className="flex items-center gap-1">
              {themePublishStatus && (
                <span className={`text-[10px] font-mono ${themePublishStatus === 'no_changes' ? 'text-slate-400' : themePublishStatus === 'publishing' ? 'text-slate-300' : 'text-green-400'}`}>
                  {themePublishStatus === 'no_changes' ? 'No changes' : themePublishStatus === 'publishing' ? 'Publishing…' : themePublishStatus.replace('published:', '')}
                </span>
              )}
              <button type="button" onClick={() => onSaveTheme()} disabled={readOnlyTheme} className="px-1.5 py-1 rounded border border-slate-600 hover:bg-slate-800 inline-flex items-center gap-1 disabled:opacity-40" title="Publish new theme version">
                <CloudUpload size={12} />
              </button>
              <select value={themeVersionLabel} onChange={(e) => onSelectThemeVersion?.(e.target.value)} className="px-1 py-1 rounded border border-slate-600 bg-slate-900 text-slate-100 text-[10px] font-mono">
                {themeVersionOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
          </div>
          <textarea
            className="w-full min-h-[140px] p-2 border border-slate-700 border-t-0 rounded-b bg-slate-950 text-slate-100 font-mono text-xs focus:outline-none"
            value={themeCode}
            onChange={(e) => setThemeCode(e.target.value)}
            readOnly={readOnlyTheme}
            spellCheck={false}
          />
        </div>

        <div>
          <div className={headingClass}>
            <span>Map Code</span>
          </div>
          <div className="border border-slate-700 border-t-0 rounded-b overflow-hidden">
            <Editor
              height={320}
              defaultLanguage="python"
              path="xatra_map.py"
              value={code || ''}
              onMount={handleEditorDidMount}
              theme="xatra-dark"
              options={{ minimap: { enabled: false }, fontSize: 13, lineNumbers: 'on', scrollBeyondLastLine: false, wordWrap: 'on', readOnly: readOnlyMap }}
            />
          </div>
        </div>

        <div>
          <div className={headingClass}>
            <span>Do not expose to importers</span>
          </div>
          <div className="px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300 border border-slate-700 border-t-0 bg-slate-900">Imports</div>
          <textarea
            className="w-full min-h-[92px] p-2 border border-slate-700 border-t-0 bg-slate-950 text-slate-100 font-mono text-xs focus:outline-none"
            value={runtimeImportsCode}
            onChange={(e) => setRuntimeImportsCode(e.target.value)}
            readOnly={readOnlyMap}
            spellCheck={false}
            placeholder='xatrahub("/lib/some_lib/alpha")'
          />
          <div className="px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300 border border-slate-700 border-t-0 bg-slate-900">Code</div>
          <textarea
            className="w-full min-h-[120px] p-2 border border-slate-700 border-t-0 rounded-b bg-slate-950 text-slate-100 font-mono text-xs focus:outline-none"
            value={runtimeCode}
            onChange={(e) => setRuntimeCode(e.target.value)}
            readOnly={readOnlyMap}
            spellCheck={false}
          />
        </div>
      </div>
    </div>
  );
};

export default CodeEditor;
