import React, { useEffect, useRef } from 'react';
import { Code2 } from 'lucide-react';
import { isPythonValue, toPythonValue, getPythonExpr, toTextValue } from '../utils/pythonValue';

const PythonTextField = ({
  value,
  onChange,
  multiline = false,
  className = '',
  inputClassName = '',
  rows,
  placeholder,
  type = 'text',
  title,
  autoGrow = false,
  ...rest
}) => {
  const inputRef = useRef(null);
  const pythonMode = isPythonValue(value);
  const shownValue = pythonMode ? getPythonExpr(value) : toTextValue(value);

  useEffect(() => {
    if (!autoGrow || !multiline) return;
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 34)}px`;
  }, [shownValue, autoGrow, multiline]);

  const handleToggle = () => {
    if (pythonMode) {
      onChange(getPythonExpr(value));
      return;
    }
    onChange(toPythonValue(shownValue));
  };

  const commonProps = {
    ...rest,
    ref: inputRef,
    value: shownValue,
    onChange: (e) => {
      const next = e.target.value;
      onChange(pythonMode ? toPythonValue(next) : next);
    },
    onInput: (e) => {
      if (!autoGrow || !multiline) return;
      e.currentTarget.style.height = 'auto';
      e.currentTarget.style.height = `${Math.max(e.currentTarget.scrollHeight, 34)}px`;
    },
    placeholder: pythonMode ? 'Python expression' : placeholder,
    className: `${inputClassName} pr-8 ${pythonMode ? 'border-amber-400 bg-amber-50 font-mono' : ''}`.trim(),
  };

  return (
    <div className={`relative ${className}`.trim()}>
      {multiline ? (
        <textarea rows={rows} {...commonProps} />
      ) : (
        <input type={type} {...commonProps} />
      )}
      <button
        type="button"
        onClick={handleToggle}
        className={`absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded transition-colors ${pythonMode ? 'text-amber-700 bg-amber-100 hover:bg-amber-200' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
        title={title || (pythonMode ? 'Python mode ON (click to switch to text)' : 'Use Python expression')}
      >
        <Code2 size={12} />
      </button>
    </div>
  );
};

export default PythonTextField;
