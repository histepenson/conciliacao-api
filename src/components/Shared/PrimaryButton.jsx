function PrimaryButton({ children, disabled }) {
  return (
    <button className="btn-primary" disabled={disabled}>
      {children}
    </button>
  );
}

export default PrimaryButton;
