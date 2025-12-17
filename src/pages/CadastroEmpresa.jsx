import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";

import FormPage from "../components/Shared/FormPage";
import FormField from "../components/Shared/FormField";
import PrimaryButton from "../components/Shared/PrimaryButton";

import "../styles/form/form-extras.css";
import "../styles/form/form-layout.css";

// ============================================================
// VALIDAÇÃO COM YUP
// ============================================================
const schema = yup.object().shape({
  nome: yup
    .string()
    .trim()
    .required("Nome é obrigatório")
    .min(3, "Nome deve ter pelo menos 3 caracteres"),
  cnpj: yup
    .string()
    .required("CNPJ é obrigatório")
    .test("valid-cnpj", "CNPJ inválido", (value) => {
      if (!value) return false;
      const digits = value.replace(/\D/g, "");
      if (digits.length !== 14) return false;
      if (/^(\d)\1{13}$/.test(digits)) return false;
      return true;
    }),
  status: yup.boolean().required(),
});

export default function CadastroEmpresa() {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: {
      nome: "",
      cnpj: "",
      status: true,
    },
  });

  const cnpjValue = watch("cnpj");

  // ============================================================
  // MÁSCARA DE CNPJ
  // ============================================================
  const formatCNPJ = (value) => {
    const digits = value.replace(/\D/g, "");
    return digits
      .replace(/(\d{2})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1/$2")
      .replace(/(\d{4})(\d)/, "$1-$2")
      .slice(0, 18);
  };

  const handleCNPJChange = (e) => {
    const formatted = formatCNPJ(e.target.value);
    setValue("cnpj", formatted);
  };

  // ============================================================
  // SUBMIT
  // ============================================================
  const onSubmit = async (data) => {
    try {
      const response = await fetch("http://localhost:8000/empresas/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: data.nome,
          cnpj: data.cnpj.replace(/\D/g, ""),
          status: data.status,
        }),
      });

      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || "Erro ao cadastrar empresa");
      }

      toast.success("✅ Empresa cadastrada com sucesso!");
      setTimeout(() => navigate("/cadastros/empresas"), 1200);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleVoltar = () => navigate("/cadastros/empresas");

  const handleClear = () => {
    if (window.confirm("Deseja realmente limpar o formulário?")) {
      reset();
    }
  };

  // ============================================================
  // RENDER
  // ============================================================
  return (
    <FormPage title="Cadastro de Empresa">
      <form className="form-grid" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField label="Nome da Empresa" error={errors.nome?.message} required>
          <input
            type="text"
            placeholder="Ex: Empresa ABC Ltda"
            disabled={isSubmitting}
            autoComplete="organization"
            {...register("nome")}
          />
        </FormField>

        <FormField label="CNPJ" error={errors.cnpj?.message} required>
          <input
            type="text"
            placeholder="00.000.000/0000-00"
            maxLength={18}
            disabled={isSubmitting}
            value={cnpjValue}
            onChange={handleCNPJChange}
          />
        </FormField>

        <FormField label="Status">
          <select {...register("status")} disabled={isSubmitting}>
            <option value={true}>✅ Ativo</option>
            <option value={false}>❌ Inativo</option>
          </select>
        </FormField>

        <div className="form-actions">
          <PrimaryButton type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <span className="spinner"></span> Salvando...
              </>
            ) : (
              "💾 Salvar Empresa"
            )}
          </PrimaryButton>

          <button
            type="button"
            className="secondary-button"
            onClick={handleClear}
            disabled={isSubmitting}
          >
            🔄 Limpar
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={handleVoltar}
            disabled={isSubmitting}
          >
            ← Voltar para Lista
          </button>
        </div>
      </form>
    </FormPage>
  );
}
