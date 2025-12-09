class PlanoDeContas:
    def __init__(
        self, 
        conta_contabil: str, 
        descricao: str, 
        tipo: str,                # "Analítica" ou "Sintética"
        conciliavel: str          # "Sim" ou "Não"
    ):
        # validações
        if tipo not in ["Analítica", "Sintética"]:
            raise ValueError("Tipo deve ser 'Analítica' ou 'Sintética'.")

        if conciliavel not in ["Sim", "Não"]:
            raise ValueError("Conciliável deve ser 'Sim' ou 'Não'.")

        self.conta_contabil = conta_contabil
        self.descricao = descricao
        self.tipo = tipo
        self.conciliavel = conciliavel

    def __repr__(self):
        return (
            f"<PlanoDeContas {self.conta_contabil} - {self.descricao} | "
            f"Tipo: {self.tipo} | Conciliável: {self.conciliavel}>"
        )
