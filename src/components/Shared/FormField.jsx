import PropTypes from "prop-types";

function FormField({
  label = null,
  error = null,
  required = false,
  children,
  helpText = null
}) {
  return (
    <div className="form-field">
      {label && (
        <label className={required ? "required" : ""}>
          {label}
        </label>
      )}

      {children}

      {error && (
        <span className="error-message">
          {error}</span>
      )}

      {helpText && !error && (
        <span className="help-text">{helpText}</span>
      )}
    </div>
  );
}

FormField.propTypes = {
  label: PropTypes.string,
  error: PropTypes.string,
  required: PropTypes.bool,
  children: PropTypes.node.isRequired,
  helpText: PropTypes.string
};

export default FormField;
