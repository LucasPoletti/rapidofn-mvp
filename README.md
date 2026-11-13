# RápidoNF MVP — Emissor Inteligente de NFS-e (Padrão Nacional)

Aplicação web desenvolvida como projeto de extensão universitária (**Análise e Desenvolvimento de Sistemas — Universidade Cruzeiro do Sul Virtual**) em parceria com a clínica **Casa Psico Psicologia Clínica Ltda** e homologação contábil pela **LUYON Assessoria Contábil & Inteligência Empresarial**.

- **Aplicação em Produção:** [https://rapidonf-mvp.onrender.com](https://rapidonf-mvp.onrender.com)
- **Endpoint de Monitoramento (Health Check):** [https://rapidonf-mvp.onrender.com/health](https://rapidonf-mvp.onrender.com/health)
- **Prestador Piloto:** CASA PSICO PSICOLOGIA CLÍNICA LTDA (CNPJ `63.897.592/0001-06`)
- **Responsável Técnico & Contábil:** Lucas Felipe Apollo Poletti (`LUYON Assessoria Contábil`)

---

## Principais Funcionalidades Implementadas

1. **Emissão Simplificada de NFS-e com Validação Fiscal:**
   - Validação real de dígitos verificadores do CPF do tomador (front-end e back-end), bloqueando sequências inválidas.
   - Formatação monetária em Real Brasileiro (`R$`) com cálculo instantâneo do **DAS previsto** conforme a alíquota configurada pelo contador.
2. **Parametrização Fiscal do Contador (`configuracoes_fiscais`):**
   - Módulo dedicado ao contador com tabelas de domínio padronizadas conforme o **Guia do Emissor Público Nacional NFS-e (v1.3)** e **Notas Técnicas 004/007/009**:
     - Ambiente Nacional (`tpAmb`: Produção/Homologação) e Série da DPS.
     - Dados cadastrais do prestador, Município/UF com sincronização automática de **Código IBGE**, **CNAE Principal**, **Item de Serviço LC 116/03 (`cTribNac`)**, **Código NBS** e regra de transição **IBS/CBS (LC 214/2025)**.
     - Enquadramento no **Simples Nacional (`opSimpNac`, `regApTribSN`, Anexo III / Anexo V)** com sugestão automática de alíquota efetiva do PGDAS-D e regras de exigibilidade/retenção de ISSQN.
3. **DANFSe — Documento Auxiliar da NFS-e (Padrão Nacional):**
   - Geração fiel ao leiaute oficial do Portal Nacional NFS-e com **Chave de Acesso de 50 dígitos**, QR Code de consulta nacional, dados completos do emitente/tomador, discriminação clínica sob sigilo profissional e impressão/exportação direta em PDF.
4. **Base de Tomadores (Pacientes Cadastrados):**
   - Listagem consolidada de pacientes atendidos com histórico de sessões, faturamento acumulado e autopreenchimento em um clique no formulário de emissão.
5. **Compartilhamento Rápido & Fechamento Contábil:**
   - **Envio via WhatsApp:** Geração automática de mensagem institucional com os dados da nota e link direto para o PDF do DANFSe.
   - **Exportação Mensal Contábil (CSV/Excel):** Download de planilha estruturada por competência (`MM/AAAA` ou consolidada) em UTF-8 com BOM e separador `;`, pronta para conferência fiscal e importação contábil.
6. **Acessibilidade (WCAG AAA):**
   - Controles nativos de **Alto Contraste** e **Ampliação Tipográfica (`A+`)**, além de semântica ARIA para leitores de tela.

---

## Arquitetura e Stack Tecnológica

- **Back-end:** Python 3 + Flask + Gunicorn
- **Banco de Dados:** SQLite (`rapidofn.db`) com criação automática de esquema, migração segura de colunas e tabelas `configuracoes_fiscais` e `notas_fiscais`
- **Front-end:** HTML5, CSS3 responsivo (variáveis CSS para temas de acessibilidade) e JavaScript Vanilla
- **Infraestrutura Cloud:** Render Web Service com monitoramento contínuo via UptimeRobot

---

## Estrutura do Projeto

```text
rapidonf-mvp/
├── app_ui.py           # Aplicação principal Flask, regras fiscais, rotas, DANFSe e SQLite
├── requirements.txt    # Dependências Python (Flask, Gunicorn)
├── rapidofn.db         # Banco de dados SQLite (gerado automaticamente na inicialização)
└── README.md           # Documentação técnica e funcional do projeto