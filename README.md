# Central de Certificados - Brobot

Aplicação desktop local baseada em Streamlit para conferência e geração de mensagens de cobrança para certificados digitais a partir de planilhas Excel.

---

## 🚀 Como Executar

Basta dar um duplo clique no arquivo:
```
iniciar.bat
```
O script verifica o ambiente Python, ativa o ambiente virtual (se existente) e inicia o Streamlit automaticamente na porta dedicada **8502** (`http://localhost:8502`), permitindo que a aplicação rode simultaneamente com a *Central de Erros* (porta 8501) sem conflito.

Caso queira iniciar manualmente via terminal:
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

---

## 📊 Colunas Obrigatórias da Planilha

A aplicação lê e valida obrigatoriamente estas 5 colunas:
1. `Nome da Conta`
2. `Empresa`
3. `CNPJ`
4. `Certificado Expira em`
5. `status do fluxo`

*Todas as demais colunas existentes na planilha são ignoradas.*

---

## ⚙️ Regras de Negócio

1. **CERTIFICADO OK**:
   - Registros com esse status são ignorados e não geram mensagens de cobrança.
2. **Agrupamento**:
   - Agrupador chave: `Nome da Conta` + `status do fluxo` + `Certificado Expira em`.
   - Se uma conta possui vários CNPJs com a mesma data e mesmo status, todos entram na mesma mensagem.
   - Se possuir datas ou status distintos, o sistema gera mensagens separadas.
3. **Templates Dinâmicos**:
   - Os textos das mensagens ficam armazenados em `data/templates.json` e podem ser editados diretamente na interface (aba *Gerenciador de Templates*).
   - Placeholders aceitos nos templates:
     - `{data_expiracao}`: Data no formato brasileiro `DD/MM/AAAA`.
     - `{clientes_cnpjs}`: Pares de Empresa e CNPJ formatados linha a linha.
4. **Alerta de Status Desconhecido**:
   - Se a planilha trouxer um status que não esteja configurado, o sistema alerta o usuário exibindo o valor encontrado.
5. **Robustez contra Células Vazias**:
   - Linhas que precisem de cobrança com dados faltantes (sem Empresa, CNPJ ou Data) são segregadas em um relatório de alerta na interface, evitando gerar mensagens incompletas.

---

## 🧪 Testes Automatizados

Para rodar a suite de testes:
```bash
python -m unittest discover tests
```
