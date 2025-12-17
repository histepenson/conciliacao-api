function FormPage({ title, children }) {
  return (
    <div className="form-page">
      <h1 className="form-page-title">{title}</h1>
      <div className="form-page-card">
        {children}
      </div>
    </div>
  );
}

export default FormPage;
