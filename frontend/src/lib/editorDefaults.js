export const DEFAULT_INDIC_IMPORT = {
  kind: 'lib',
  username: null,
  name: 'dtl',
  path: '/lib/dtl/alpha',
  selected_version: 'alpha',
  _draft_version: 'alpha',
  alias: 'indic',
  filter_not: [],
};

export const DEFAULT_INDIC_IMPORT_CODE = 'indic = xatrahub("/lib/dtl/alpha")\n';

export const createDefaultBuilderOptions = () => ({
  basemaps: [{ url_or_provider: 'Esri.WorldTopoMap', default: true }],
  flag_color_sequences: [{ class_name: '', colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
  admin_color_sequences: [{ colors: '', step_h: 1.6180339887, step_s: 0.0, step_l: 0.0 }],
  data_colormap: { type: 'LinearSegmented', colors: 'yellow,orange,red' },
});

export const createDefaultBuilderElements = () => ([
  { type: 'flag', label: 'India', value: [{ op: 'union', type: 'gadm', value: 'IND' }], args: { note: 'Republic of India' } },
]);
