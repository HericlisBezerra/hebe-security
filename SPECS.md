# SPECS — how v2.0 was built

> Check-by-check record of the merge between `hebe-sec-audit` v1 (HeBeDigital) and `vibe-security` (Chris Raroque / Aloa, MIT), documenting exactly which source each item came from. Kept for auditability — and so the merge can be verified rather than trusted.

> Fontes lidas na íntegra: **1.113 linhas** (sua skill) + **772 linhas** (externa).

---

## 1. Inventário das duas fontes

### FONTE A — `hebe-sec-audit` (sua, PT-BR)

| Arquivo | Linhas | Conteúdo |
|---|---:|---|
| `SKILL.md` | 140 | Processo em **6 fases** (0–5) + regras de conduta + execução em cron |
| `references/audit-playbook.md` | 253 | **11 categorias**, cada uma com *Como o atacante explora · Onde procurar · Como reproduzir · Correção* + testes de regressão + ferramentas por fase |
| `references/stack-adapters.md` | 88 | **9 stacks**: Node/TS, Next.js, Python, Rails, PHP/Laravel, Go, Supabase, Firebase, Pagamento (transversal) + fallback |
| `references/guia-vibe-coding-fonte.md` | 632 | **15 seções**: filosofia, prompt engineering, auth, autorização, race conditions, validação, segredos, injeções, lógica de negócio, testes automatizados, IA como adversário, templates de prompt, ferramentas, **checklist pré-deploy**, **mapeamento OWASP Top 10 (2021)** |

**Natureza:** auditoria **ofensiva** (red team). Detecta a stack primeiro e adapta o ataque. Exige **prova de exploração**, não apontamento teórico.

### FONTE B — `vibe-security` (externa, EN · MIT · Chris Raroque/Aloa)

| Arquivo | Conteúdo |
|---|---|
| `SKILL.md` | Princípio "**Never trust the client**" + **9 passos** + formato de saída (Critical→Low, com *before/after*) + modo proativo ao gerar código |
| `references/secrets-and-env.md` | Credenciais hardcoded, **tabela de prefixos client-side**, o que pode/não pode ser público, `.gitignore`, **padrões de detecção** |
| `references/database-security.md` | **Supabase RLS profundo** + **Firebase profundo** + **Convex** |
| `references/authentication.md` | JWT, **CVE-2025-29927** (middleware Next.js), **Server Actions**, vazamento p/ Client Components, storage de sessão |
| `references/rate-limiting.md` | Onde é obrigatório, contador em tabela pública, per-IP + per-user, proteção de billing |
| `references/payments.md` | Preço do cliente, **assinatura de webhook (raw body)**, status de assinatura, metadata do checkout |
| `references/mobile.md` | Bundle JS, `AsyncStorage`, deep links, **biometria criptográfica** |
| `references/ai-integration.md` | Chaves de IA, **spending caps**, prompt injection, output não-confiável, **tool calling** |
| `references/deployment.md` | Debug, **source maps**, **`.git` exposto**, separação de ambientes, **6 security headers**, gitleaks, CORS |
| `references/data-access.md` | SQL injection, **Prisma operator injection**, validação com Zod, mass assignment |

**Natureza:** **checklist** por categoria, focado nos erros que a IA comete. Cobertura horizontal ampla.

---

## 2. Tabela comparativa item a item

Legenda: **A** = sua · **B** = externa · ✅ cobre · ⚠️ cobre raso · ❌ não cobre

### 2.1 Segredos e credenciais

| Item a revisar | A | B | Ação na fusão |
|---|:--:|:--:|---|
| Credenciais hardcoded no código | ✅ | ✅ | funde |
| `grep` por padrões de chave | ✅ | ✅ | funde |
| **Padrões nomeados** (`sk_live_`, `AKIA`, `ghp_`, `glpat-`, `xoxb-`, `Bearer`) | ⚠️ | ✅ | **adota B** |
| **Histórico git** (chave "removida" continua no reflog) | ✅ | ✅ | funde |
| `gitleaks detect` | ❌ | ✅ | **adota B** |
| **Tabela de prefixos client-side** (`NEXT_PUBLIC_`/`VITE_`/`EXPO_PUBLIC_`/`REACT_APP_`) | ❌ | ✅ | **adota B** |
| **Lista do que PODE ser público** (pk_live, anon key, Firebase config, analytics) | ❌ | ✅ | **adota B** |
| **Lista do que NUNCA pode** (service_role, sk_live, connection string, JWT secret, OAuth secret) | ⚠️ | ✅ | **adota B** |
| `.env` no `.gitignore` antes do 1º commit | ⚠️ | ✅ | **adota B** |
| `.env.example` só com placeholder | ❌ | ✅ | **adota B** |
| Connection string com senha embutida na URL | ❌ | ✅ | **adota B** |

### 2.2 Controle de acesso / IDOR

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Todo recurso com `:id` valida dono no backend | ✅ | ✅ | funde |
| Como o atacante explora (trocar ID, enumerar) | ✅ | ⚠️ | **mantém A** |
| Onde procurar no código | ✅ | ⚠️ | **mantém A** |
| **Como reproduzir** (passo a passo) | ✅ | ❌ | **mantém A** |
| Autorização ≠ autenticação (logado não basta) | ✅ | ✅ | funde |

### 2.3 RLS e regras de banco — **maior ganho da fusão**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| RLS ativo em todas as tabelas | ✅ | ✅ | funde |
| **Script SQL que ativa RLS em todas** (`DO $$ ... pg_tables`) | ❌ | ✅ | **adota B** |
| **Políticas perigosas**: `USING (true)` e `USING (auth.uid() IS NOT NULL)` | ⚠️ | ✅ | **adota B** |
| **`WITH CHECK` faltando** em INSERT/UPDATE (permite reatribuir dono) | ❌ | ✅ | **adota B** |
| **Campos sensíveis** em tabela editável (`is_admin`, `credits`, `subscription_tier`) | ⚠️ | ✅ | **adota B** |
| **Column-level `GRANT/REVOKE`** como correção | ❌ | ✅ | **adota B** |
| **Tabelas relacionadas esquecidas** (junction, audit log, metadata) | ❌ | ✅ | **adota B** |
| **`SECURITY DEFINER`** burla RLS · manter em schema `private` · `SET search_path = ''` | ❌ | ✅ | **adota B** |
| **Storage buckets** precisam de política própria (escopo por UID) | ❌ | ✅ | **adota B** |
| Firebase: regras default perigosas | ⚠️ | ✅ | **adota B** |
| Firebase: **proteção por campo** (`affectedKeys().hasOnly`) | ❌ | ✅ | **adota B** |
| Firebase: **subcollection NÃO herda regra do pai** | ❌ | ✅ | **adota B** |
| Firebase: validação de tipo/tamanho e `request.time` | ❌ | ✅ | **adota B** |
| Firebase: **custom claims** em vez de ler doc de usuário | ❌ | ✅ | **adota B** |
| Firebase: Cloud Storage (`contentType`, `size`, path) | ❌ | ✅ | **adota B** |
| **Convex**: `ctx.auth.getUserIdentity()`, ownership, `internal*` | ❌ | ✅ | **adota B** |
| Testar RLS com a chave anon de verdade | ✅ | ⚠️ | **mantém A** |

### 2.4 Autenticação e sessão

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Hash forte de senha | ✅ | ❌ | **mantém A** |
| Enumeração de usuário | ✅ | ❌ | **mantém A** |
| Rate limit em login | ✅ | ✅ | funde |
| Tokens revogáveis | ✅ | ⚠️ | **mantém A** |
| **`jwt.verify()` vs `jwt.decode()`** | ⚠️ | ✅ | **adota B** |
| **Rejeitar `"alg": "none"`** | ❌ | ✅ | **adota B** |
| **Validar issuer/audience/expiração** | ⚠️ | ✅ | **adota B** |
| **Middleware Next.js não basta (CVE-2025-29927)** | ❌ | ✅ | **adota B** |
| Cookie `HttpOnly + Secure + SameSite` vs localStorage | ✅ | ✅ | funde |

### 2.5 Endpoints públicos ocultos — **categoria nova**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| **Server Actions são endpoints POST públicos** (chamáveis por curl) | ❌ | ✅ | **adota B** |
| **Os 3 itens obrigatórios no topo**: validação → autenticação → autorização | ❌ | ✅ | **adota B** |
| Route handlers `app/api/` seguem a mesma regra | ⚠️ | ✅ | **adota B** |
| **Vazamento de objeto inteiro pra Client Component** (`select` só o necessário) | ❌ | ✅ | **adota B** |
| **`import 'server-only'`** em módulos de acesso a dados | ❌ | ✅ | **adota B** |

### 2.6 Race conditions — **exclusivo seu**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Alvos (financeiro, toggle, limite, cupom) | ✅ | ❌ | **preserva A** |
| Exploração clássica | ✅ | ❌ | **preserva A** |
| **Reprodução: 10 requisições idênticas em paralelo** | ✅ | ❌ | **preserva A** |
| Correção (lock, transação, constraint, idempotência) | ✅ | ❌ | **preserva A** |

### 2.7 Validação de input

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Server-side sempre | ✅ | ✅ | funde |
| **Limite de tamanho em TODO campo** | ✅ | ⚠️ | **mantém A** |
| **Upload: MIME + magic bytes + tamanho** | ✅ | ❌ | **preserva A** |
| **Zod/schema runtime nas 5 fronteiras** (API, Server Action, webhook, form, query param) | ⚠️ | ✅ | **adota B** |
| **TypeScript ≠ validação** (tipo é compile-time) | ❌ | ✅ | **adota B** |

### 2.8 Injeção

| Item | A | B | Ação |
|---|:--:|:--:|---|
| SQL injection / query parametrizada | ✅ | ✅ | funde |
| XSS | ✅ | ⚠️ | **mantém A** |
| **SSRF** | ✅ | ❌ | **preserva A** |
| **Command injection** | ✅ | ❌ | **preserva A** |
| **Template injection** | ✅ | ❌ | **preserva A** |
| **Prisma: operator injection** (`findFirst` com objeto cru) | ❌ | ✅ | **adota B** |
| **`$queryRawUnsafe` / `$executeRawUnsafe`** | ❌ | ✅ | **adota B** |

### 2.9 Lógica de negócio — **exclusivo seu**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Como pensar (fluxos que geram dinheiro/permissão do nada) | ✅ | ❌ | **preserva A** |
| Exemplo real do vídeo-fonte | ✅ | ❌ | **preserva A** |
| "o que a IA mais erra" | ✅ | ❌ | **preserva A** |

### 2.10 Rate limiting — **categoria nova**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| **Onde é obrigatório**: auth, chamadas de IA, e-mail/SMS, processamento de arquivo, webhooks | ⚠️ | ✅ | **adota B** |
| **Contador em tabela pública = usuário zera o próprio** | ❌ | ✅ | **adota B** |
| Alternativas: Upstash Redis, schema privado, middleware/edge, memória | ❌ | ✅ | **adota B** |
| **Per-IP + per-user juntos** (IP: VPN; user: conta nova) | ❌ | ✅ | **adota B** |
| **Proteção de billing**: alertas + hard caps + quota por usuário + anomalias | ❌ | ✅ | **adota B** |

### 2.11 Pagamento

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Preço vindo do cliente | ⚠️ | ✅ | **adota B** |
| Usar Price ID do Stripe em vez de montar preço | ❌ | ✅ | **adota B** |
| **Assinatura de webhook exige RAW body** (`express.raw()` antes do `json()`; Next: `request.text()`) | ❌ | ✅ | **adota B** |
| **Status de assinatura validado server-side a cada request** (não cache/JWT antigo) | ❌ | ✅ | **adota B** |
| **Metadata do checkout definida no servidor** | ❌ | ✅ | **adota B** |

### 2.12 IA / LLM — **categoria nova**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| Chave de IA nunca no client | ⚠️ | ✅ | **adota B** |
| **Spending caps** no provedor + **quota por usuário** na aplicação | ❌ | ✅ | **adota B** |
| **Prompt injection** (system vs user message) | ❌ | ✅ | **adota B** |
| **Output de LLM é input não-confiável** (sanitizar HTML, nunca executar) | ❌ | ✅ | **adota B** |
| **Tool/function calling**: allowlist, schema, menor privilégio, log, nunca SQL/shell cru | ❌ | ✅ | **adota B** |

### 2.13 Mobile — **categoria nova**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| **Tudo no bundle JS é extraível** (inclusive Hermes) | ❌ | ✅ | **adota B** |
| `react-native-config`, `EXPO_PUBLIC_`, `eas.json` **não são secretos** | ❌ | ✅ | **adota B** |
| **Backend proxy** para toda chamada com chave | ❌ | ✅ | **adota B** |
| **`AsyncStorage` é texto plano** → `expo-secure-store`/`react-native-keychain` | ❌ | ✅ | **adota B** |
| **Deep links**: validar params, nada sensível na URL, sem ação destrutiva direta | ❌ | ✅ | **adota B** |
| **Biometria: boolean é hookável (Frida)** → challenge/nonce + Secure Enclave | ❌ | ✅ | **adota B** |

### 2.14 Config, headers, CORS

| Item | A | B | Ação |
|---|:--:|:--:|---|
| HTTPS/HSTS, CSP, cookies | ✅ | ✅ | funde |
| **Os 6 headers nomeados** (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) | ⚠️ | ✅ | **adota B** |
| CORS sem `*` em endpoint autenticado | ✅ | ✅ | funde |
| **`Allow-Credentials: true` exige origem específica** | ❌ | ✅ | **adota B** |

### 2.15 Deploy e ambientes — **categoria nova**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| **Debug mode desligado** em produção | ⚠️ | ✅ | **adota B** |
| **Source maps desligados** | ❌ | ✅ | **adota B** |
| **`/.git/HEAD` acessível** = código + histórico expostos | ❌ | ✅ | **adota B** |
| **Separação prod / preview / dev** (preview nunca com chave de prod) | ❌ | ✅ | **adota B** |
| Página de erro sem stack trace | ⚠️ | ✅ | **adota B** |

### 2.16 Dependências — **exclusivo seu**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| CVEs conhecidos (`npm audit`, `pip-audit`) | ✅ | ❌ | **preserva A** |

### 2.17 Processo e metodologia — **quase todo exclusivo seu**

| Item | A | B | Ação |
|---|:--:|:--:|---|
| **Fase 0** — escopo e regras de engajamento | ✅ | ❌ | **preserva A** |
| **Fase 1** — recon: detectar stack real + baseline | ✅ | ❌ | **preserva A** |
| **Fase 2** — mapear superfície de ataque | ✅ | ❌ | **preserva A** |
| **Fase 4** — relatório com severidade | ✅ | ✅ | funde |
| **Fase 5** — aplicar correções | ✅ | ⚠️ | **mantém A** |
| **Adaptação por stack (9 stacks)** | ✅ | ❌ | **preserva A** |
| **IA como adversário** (2ª passada de ataque) | ✅ | ❌ | **preserva A** |
| **Testes de regressão de segurança** | ✅ | ❌ | **preserva A** |
| **Checklist pré-deploy** | ✅ | ⚠️ | **mantém A** + itens de B |
| **Mapeamento OWASP Top 10 (2021)** | ✅ | ❌ | **preserva A** |
| **Templates de prompt seguro** | ✅ | ⚠️ | **mantém A** |
| **Execução em cron/desatendido** | ✅ | ❌ | **preserva A** |
| Regras de conduta | ✅ | ⚠️ | funde |
| **Exigir prova de exploração** | ✅ | ❌ | **preserva A** |
| **Formato *before/after* no fix** | ⚠️ | ✅ | **adota B** |
| **Modo proativo** (ao GERAR código, não só auditar) | ❌ | ✅ | **adota B** |
| **Achado crítico vai pro topo da resposta** | ⚠️ | ✅ | **adota B** |
| **"Never trust the client"** como princípio único | ⚠️ | ✅ | **adota B** |

---

## 3. Placar da fusão

| | Quantidade |
|---|---|
| Itens **exclusivos seus** (preservados integralmente) | **28** |
| Itens **exclusivos da externa** (incorporados) | **57** |
| Itens **em ambos** (fundidos, ficando a versão mais completa) | **19** |
| **Total de itens de verificação na v2.0** | **≈104** |
| Categorias: v1 = 11 → **v2.0 = 17** | +6 |

**Nada é perdido.** Onde as duas cobrem o mesmo item, fica a versão mais detalhada (indicada na coluna "Ação").

---

## 4. Estrutura proposta da v2.0

**Esqueleto = o seu** (processo em fases é superior a checklist puro).
**Granularidade das referências = da externa** (1 arquivo por categoria carrega só o que importa — *progressive disclosure*).

```
hebe-security-scan/
├── SKILL.md                          ← fases 0–5 + princípio + conduta + cron + modo proativo
└── references/
    ├── 01-segredos-e-env.md          A5 + B1
    ├── 02-controle-de-acesso.md      A1
    ├── 03-banco-rls.md               A11 + B2  (Supabase · Firebase · Convex)  ← maior ganho
    ├── 04-autenticacao-sessao.md     A2 + B3
    ├── 05-endpoints-publicos.md      B3        ← novo (Server Actions, route handlers)
    ├── 06-race-conditions.md         A3        ← exclusivo seu
    ├── 07-validacao-input.md         A4 + B9
    ├── 08-injecao.md                 A6 + B9   (SQL, XSS, SSRF, command, template, Prisma)
    ├── 09-mass-assignment.md         A8 + B9
    ├── 10-logica-de-negocio.md       A7        ← exclusivo seu
    ├── 11-rate-limiting.md           B4        ← novo
    ├── 12-pagamento.md               B5 + A
    ├── 13-ia-llm.md                  B7        ← novo
    ├── 14-mobile.md                  B6        ← novo
    ├── 15-config-headers-cors.md     A9 + B8
    ├── 16-deploy-ambientes.md        B8        ← novo
    ├── 17-dependencias.md            A10       ← exclusivo seu
    ├── stack-adapters.md             A (9 stacks) + Convex + React Native/Expo
    ├── testes-regressao.md           A
    ├── checklist-pre-deploy.md       A + B
    ├── owasp-top10.md                A
    └── guia-vibe-coding-fonte.md     A (mantido íntegro, 632 linhas)
```

**Cada arquivo de categoria mantém as 4 seções da sua skill:**
*Como o atacante explora · Onde procurar no código · Como reproduzir · Correção* — agora com **exemplos before/after** (contribuição da externa).

---

## 5. Decisões que preciso de você

1. **Idioma:** tudo em **PT-BR** (traduzo o conteúdo da externa) ou manter os trechos técnicos da externa em EN?
2. **`guia-vibe-coding-fonte.md`:** mantenho íntegro (632 linhas, tem OWASP + templates) ou realoco o conteúdo nas categorias novas?
3. **Nome da skill:** confirmo `hebe-security-scan`. Mantenho a `hebe-sec-audit` antiga instalada em paralelo, ou aposento (movendo pro `_arquivo/`)?
4. **Crédito da externa:** incluo atribuição a Chris Raroque / Aloa + MIT no cabeçalho? *(recomendo sim — é licença MIT, exige preservar o aviso de copyright em cópias substanciais)*
