/**
 * Label + input/select + error, wired up consistently so every field gets
 * the same aria-invalid/aria-describedby behavior instead of re-deriving
 * it by hand eight times.
 */
export default function SignupField({
  label,
  name,
  type = "text",
  as = "input",
  value,
  onChange,
  onBlur,
  error,
  optional = false,
  suffix = null,
  children,
  ...rest
}) {
  const id = `field-${name}`;
  const errorId = `${id}-error`;

  const controlProps = {
    id,
    name,
    value,
    onChange,
    onBlur,
    "aria-invalid": error ? "true" : undefined,
    "aria-describedby": error ? errorId : undefined,
    className: `field__control ${error ? "field__control--error" : ""}`.trim(),
    ...rest,
  };

  return (
    <div className="field">
      <label htmlFor={id} className="field__label">
        {label}
        {optional && <span className="field__optional">Optional</span>}
      </label>

      <div className="field__control-wrap">
        {as === "select" ? (
          <select {...controlProps}>{children}</select>
        ) : (
          <input type={type} {...controlProps} />
        )}
        {suffix}
      </div>

      {error && (
        <p id={errorId} className="field__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
