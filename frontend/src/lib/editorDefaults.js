export const DEFAULT_INDIC_IMPORT = {
  kind: 'lib',
  username: null,
  name: 'indic_lib',
  path: '/lib/indic_lib/alpha',
  selected_version: 'alpha',
  _draft_version: 'alpha',
  alias: 'indic',
  filter_not: [],
};

export const DEFAULT_IMPORTS = [
  DEFAULT_INDIC_IMPORT,
  {
    kind: 'lib',
    username: null,
    name: 'iran_lib',
    path: '/lib/iran_lib/alpha',
    selected_version: 'alpha',
    _draft_version: 'alpha',
    alias: 'iran',
    filter_not: [],
  },
  {
    kind: 'lib',
    username: null,
    name: 'sb_lib',
    path: '/lib/sb_lib/alpha',
    selected_version: 'alpha',
    _draft_version: 'alpha',
    alias: 'sb',
    filter_not: [],
  },
];

export const DEFAULT_INDIC_IMPORT_CODE = 'indic = xatrahub("/lib/indic_lib")\niran = xatrahub("/lib/iran_lib")\nsb = xatrahub("/lib/sb_lib")\n';

export const createDefaultBuilderOptions = () => ({
  basemaps: [
    { url_or_provider: 'Esri.WorldTopoMap', default: true },
    { url_or_provider: 'OpenStreetMap' },
    { url_or_provider: 'Esri.WorldImagery' },
    { url_or_provider: 'OpenTopoMap' },
    { url_or_provider: 'Esri.WorldPhysical' },
  ],
  flag_color_sequences: [{ class_name: '', colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
  admin_color_sequences: [{ colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
  data_colormap: { type: 'LinearSegmented', colors: 'yellow,orange,red' },
});

export const createDefaultBuilderElements = () => ([
  { type: 'flag', label: 'India', value: [{ op: 'union', type: 'gadm', value: 'IND' }], args: { note: 'Republic of India' } },
]);
