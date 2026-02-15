export const PYTHON_EXPR_KEY = '__xatra_python__';

export const isPythonValue = (value) => (
  !!value &&
  typeof value === 'object' &&
  !Array.isArray(value) &&
  typeof value[PYTHON_EXPR_KEY] === 'string'
);

export const toPythonValue = (expr = '') => ({ [PYTHON_EXPR_KEY]: String(expr ?? '') });

export const getPythonExpr = (value) => (isPythonValue(value) ? value[PYTHON_EXPR_KEY] : '');

export const toTextValue = (value) => {
  if (isPythonValue(value)) return getPythonExpr(value);
  if (value == null) return '';
  return String(value);
};
