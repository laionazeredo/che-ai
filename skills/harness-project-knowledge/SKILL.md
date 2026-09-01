---
name: "harness-project-knowledge"
description: "Registro humano compartilhado (Nível 1.5 registry) de contexto do PRODUTO + ARQUITETURA MANUAL + ROADMAP + PESSOAS. Complemento de harness-xray (automático): este skill é o lado HUMANO. O harness SEMPRE lê product_context.md + architecture.md ANTES de gerar QUALQUER SPEC via harness-spec. Gate obrigatório ANTES de /harness-spec em projetos que nunca passaram por aqui."
---

# Harness Project Knowledge — Registry Humano do Projeto

> **SHARED REFERENCES (CANONICAL):**
> - Auto-onboarding complementar: `/harness-xray` (este skill não substitui xray)
> - Paths: `source ~/.trae/contracts/harness_sessions_contract.sh`
> - Regras de complexidade acidental + deep modules: `engineering-contracts` §1 + Appendix D (Ousterhout)

## 0. POR QUE EXISTE (Lean Motivation)

harness-xray = automático, lê CÓDIGO.
harness-project-knowledge = humano, lê INTENÇÃO, CONTEXTO DE NEGÓCIO, PESSOAS.

Sem este skill: o harness gera specs tecnicamente corretos mas **desalinhados do produto**, errando personas, limites de escopo, integrações planejadas e riscos conhecidos do negócio. Economiza 3-5 interações de "não era isso" por feature.

---

## 1. QUANDO CHAMAR

| Momento | Ação |
|---|---|
| ✅ PRIMEIRA VEZ depois de `/harness-xray` (obrigação) | Preencher **product_context.md** + **roadmap.md** + architecture.md manual |
| ✅ MUDANÇA DE ESCOPO DO PRODUTO (ex: pivô, nova feature grande, novo segmento) | Atualizar product_context + roadmap |
| ✅ MUDANÇA ARQUITETURAL GRANDE (ex: monolito → microservices, troca DB) | Atualizar architecture.md manual |
| ✅ NOVO MEMBRO DO TIME entra | Usar `--show` para dar onboarding estruturado |
| ✅ ANTES DE `/harness-spec` se for a primeira feature do projeto | Ler tudo + absorver |

**Não use se:** é só refresh de código → `/harness-xray`.

---

## 2. 4 ARQUIVOS NO REGISTRY NÍVEL 1.5 (compartilhado worktrees)

Sempre ABAIXO de `$HARNESS_PROJECT_DIR/` (NUNCA dentro worktree user):

```
$HARNESS_SESSIONS_ROOT/.registry/projects/<PROJECT_SLUG>/
├── project_profile.md   ← AUTO (harness-xray)   · 12 seções técnicas
├── product_context.md   ← HUMANO (ESTE SKILL)    · 8 seções OBRIGATÓRIAS
├── architecture.md      ← HYBRID                  · auto do xray + manual aqui
├── roadmap.md           ← HUMANO (ESTE SKILL)    · épicos planejados
└── registry.jsonl       ← append-only audit
```

---

## 3. MODELO OBRIGATÓRIO `product_context.md` (8 SEÇÕES)

ESTE SKILL gera o esqueleto abaixo e INTERAGE com o usuário para preencher cada seção. Não inventa nada; se o usuário não souber → deixa `[PENDENTE — preencher depois]`.

```markdown
---
project_slug: <slug>
last_updated: <ISO8601 UTC>
updated_by: human (harness-project-knowledge interactive)
lang_code: en
lang_docs: en
# ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# LANGUAGE PER-PROJECT CONFIGURATION
# - lang_code: en (DEFAULT — quase nunca mude) → controls identifiers, variables,
#   classes, functions, file/folder names, type names. ALWAYS English por padrão.
#   SÓ MUDE SE usuário EXPLICITLY disser que quer código em outro idioma.
# - lang_docs: en (DEFAULT) → controls inline comments, JSDoc, PR titles/bodies,
#   commit messages, ADRs, README, SPEC docs.
#   CONFIGURAÇÃO MAIS COMUM DE OVERRIDE:
#     lang_docs: pt-BR   (código variáveis continua EN → comments/PR/commits = PT)
# HARD RULE (verbatim user): nunca misturar linguagens. Se lang_docs = pt-BR,
# TODO comment do arquivo TODO em PT-BR. Se lang_code = en, TODO nome variável
# TODO em EN. Não faça metade PT metade EN.
---

# Product Context — <Nome Amigável do Produto>

## 1. O que é este produto? (elevator pitch 2-3 frases)
> Ex: "Flockr é uma plataforma de ingressos para eventos no Reino Unido focada em criadores independentes. Público final: quem organiza eventos (criador) + quem comparece (comprador). Diferencial: QR de ingresso com anti-fraud offline scanner."
- Nome curto:
- Nome longo (se marca tiver):
- País / região primária: ex UK, BR, US, Global
- Moeda canônica: ex GBP pence integer, BRL cents, USD cents
- Timezone canônico display: ex Europe/London, America/Sao_Paulo

## 2. Segmento de mercado + personas PRINCIPAIS
> MÁXIMO 3 personas. Menos = menos ambiguidade no harness.
| ID | Persona | Exemplo de ação diária NESTE produto | Nível técnico (1-5) |
|---|---|---|---|
| P1 | Criador de eventos independente | Cria evento, define preços, vê vendas | 2 = não sabe CLI |
| P2 | Comprador de ingressos | Procura evento, compra, recebe email com QR | 1 = só mobile app/site |
| P3 | Staff segurança na porta | Escaneia QR na entrada, offline | 1 = só toca no botão scan |

## 3. Domínio / ramo de negócio (palavras-chave para o harness não errar termos)
> Ex: ingressos, eventos, QR code offline scanner, antifraude em QR, capacidade de venue, criador vs comprador personas, Stripe Connect split payout.
- Palavras-chave negócio (10-20):
- Termos do domínio que NÃO PODEM ser confundidos: ex "refund" ≠ "cancel event" (defina 5 exemplos)

## 4. Stack high-level + integrações EXTERNAS CONHECIDAS
> Foco em NEGÓCIO, não em detalhe técnico (detalhe vai no project_profile.md).
- Pagamento: Stripe (Connect para criadores), PayPal, Apple/Google Pay?
- Email: Resend, Sendgrid, SES, Postal?
- SMS/WhatsApp (se tiver): Twilio, Messagebird?
- Outbound analytics: GA4, Segment, PostHog?
- CRMs externos (se tiver): HubSpot, Pipedrive?
- Storage de arquivos/imagens: S3, Supabase storage, Cloudflare R2?
- Outros SaaS: Slack webhooks, Linear/Jira tickets, etc

## 5. Regras de negócio NÃO-NEGOCIÁVEIS (hard invariants)
> Lista curta 5-10 itens. NÃO TÉCNICAS. Negócio.
> Ex: "Ingresso NÃO pode ser escaneado 2 vezes (mesmo se 2 pessoas diferentes tiverem cópia do QR)". "Criador NÃO pode retirar fundos 7 dias antes do evento (política antifraude)".
1.
2.
3.
4.
5.

## 6. Riscos do negócio + compliance (se aplicável)
> Ex: UK GDPR (PII), PCI DSS (pagamentos), CCPA (California), LGPD (BR), Gambling Commission (se for apostas).
- Regulatórios:
- Reputacionais (ex: vazamento de dados de compradores = K.O.):
- Operacionais (ex: offline scanner funcionar SEM internet no dia evento = prioridade 1):

## 7. Papéis + permissões (auth model)
> Se tiver multi-tenant / múltiplos papéis, defina aqui.
| Papel | Pode | NÃO pode |
|---|---|---|
| Admin global | Acessa tudo, inclusive billing | (nenhuma restrição) |
| Criador | Gerencia SEUS eventos, ingressos, payouts | Vê eventos de OUTROS criadores |
| Staff porta | Só escaneia QR no evento atribuído | Vê dashboard vendas |
| Comprador logado | Vê SEUS pedidos, transfere ingresso | Vê pedidos de outros |
| Anônimo | Procura evento, compra sem login | Acessa /admin/* |

## 8. URLs de referência (produto real, docs, etc)
> NÃO colocar aqui segredos. Só URLs públicas ou staging conhecidas.
- Ambiente produção público: https://...
- Ambiente staging: https://...
- Docs do produto (Notion, Confluence, etc): https://...
- Figma (se tiver): https://...
- Linear / ClickUp / Jira board: https://...
```

---

## 4. MODELO OBRIGATÓRIO `roadmap.md` (simples, não overengineer)

```markdown
# Roadmap — <slug>
> Atualizado em: <ISO8601>

## Épicos Confirmados (próximos 3 meses)
> Cada épico = 1 linha. Nível épico (não nível task — tasks ficam no project tracker).
- E1: Refund automation (FLO-513 em diante) — comprador pode pedir reembolso, criador aprova/rejeita, executa via Stripe
- E2: Transferência de ingresso entre usuários (P2P)
- E3: Analytics para criadores (vendidos por dia, taxa comparecimento, taxa scan)

## Épicos Planejados (3-6 meses)
- E4: Waitlist para eventos esgotados
- E5: Multi-tenant organizações (vários criadores na mesma conta empresa)

## Backlog Ideias (>6 meses, hipóteses não validadas)
- B1: App mobile nativo (hoje é PWA scanner)
- B2: White-label para promotoras grandes
- B3: Integração Facebook Eventbrite import

## FUNCIONALIDADES EXPLICITAMENTE FORA DO ESCOPO (não é de graça, é decisão)
> IMPORTANTE para o harness não propor features "óbvias" mas que produto já decidiu não fazer.
- ❌ Não vamos fazer marketplace agregador de múltiplas plataformas (somente nosso ingressos)
- ❌ Não vamos fazer vendas presenciais via PDV (foco 100% online checkin QR)
- ❌ Não vamos oferecer serviço de impressão de ingressos físicos (cliente imprime ou usa QR)
```

---

## 5. MODOS DE EXECUÇÃO DO SKILL

### Modo A — `--show` (leitura + resumo)
Quando usuário só quer revisar, não editar.
Devolve em PT-BR (ou idioma user_rules) resumo estruturado:
```
[harness-project-knowledge] 📄 Registry atual — <slug>
  ├─ Produto: <nome> · <pitch 1 frase>
  ├─ 3 Personas: P1 (Criador) · P2 (Comprador) · P3 (Staff)
  ├─ Hard invariants: 5 regras (listar 1ª palavra cada: antifraude-QR, split-payout, 7-day-payout, offline-scan, max-1-scan)
  ├─ Integrações externas: Stripe Connect · Resend · Supabase Storage
  ├─ Roadmap: 3 épicos confirmados (E1 refund, E2 transfer, E3 analytics)
  ├─ Decisões arquiteturais manual: (não preenchido — 0 ADRs registrados)
  └─ Fora de escopo: 3 items (não marketplace, não PDV físico, não impressão física)
```

### Modo B — default (interativo preencher / atualizar)
1. Carrega contracts helpers, confirma PROJECT_DIR existe.
2. **LÊ product_context.md, architecture.md, roadmap.md existentes** (se existirem — não sobrescreve sem perguntar).
3. Pergunta ao usuário **8 perguntas estruturadas** (uma por seção do product_context template).
4. Pede confirmação de cada item (Não é "tudo certo?" — é "§3 Palavras-chave domínio: estão corretas ou quer editar?").
5. **Sobrescreve apenas as seções que o usuário confirmou.**
6. Faz o mesmo para roadmap.md (épicos confirmados, planejados, backlog, fora escopo).
7. Atualiza a parte MANUAL de architecture.md (pergunta se quer adicionar ADRs, diagramas C4 em texto).
8. **Append 1 linha audit em registry.jsonl:**
   ```json
   {"ts":"ISO8601","event":"PROJECT_KNOWLEDGE_UPDATE","project_slug":"...","data":{"updated_sections":["product_context.1","roadmap.E1"]}}
   ```

### Modo C — `--bootstrap` (1ª vez, modo mais rápido)
Não faz perguntas. Cria os 3 arquivos (product_context, architecture manual, roadmap) **VAZIOS com o template padrão** `[PENDENTE]` em todas as seções. Devolve a lista de sections para o usuário preencher via chat ou manualmente.

---

## 6. CONTRATO DE LEITURA: COMO OUTROS SKILLS USAM ISSO

**OBRIGAÇÃO DOS DEMAIS SKILLS (engineering-contracts §X):**
Antes de QUALQUER `harness-spec` gerar SPEC de feature, o harness DEVE:
1. Rodar `source contracts/harness_sessions_contract.sh` + resolver `$HARNESS_PROJECT_DIR`
2. Se `product_context.md` existir → **ler as seções §2 (personas) + §5 (hard invariants) + §8 (fora escopo)**.
3. Injetar no começo da SPEC:
   ```
   > Project Context absorbed from registry Nível 1.5:
   > - Personas: P1 Criador, P2 Comprador, P3 Staff (ver product_context §2)
   > - Hard invariants do negócio: 5 regras (§5)
   > - Fora de escopo: não marketplace, não PDV, não impressão (§roadmap último)
   ```

Se `product_context.md` NÃO existir num projeto que já tem worktrees e commits → WARN no começo da SPEC:
```
> ⚠️ [project knowledge não preenchido] — rode /harness-project-knowledge para reduzir ambiguidade do produto.
```
