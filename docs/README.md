# 📚 Documentação do Repositório

Este repositório contém a configuração e automação para atualização automática do README do perfil do GitHub.

## 📁 Estrutura do Repositório

```
MarceloRodrigues1853/
├── .github/
│   └── workflows/
│       └── update-readme.yml    # Workflow do GitHub Actions
├── docs/
│   ├── TEMPLATE.md              # Template do README com variáveis
│   └── README.md                # Esta documentação
├── README.md                    # README gerado automaticamente (não editar manualmente)
└── .gitignore                   # Arquivos ignorados pelo Git
```

## 🔄 Como Funciona

### Workflow Automático

O workflow (`update-readme.yml`) é executado:

1. **Diariamente às 09:00 (horário de Brasília)** via cron schedule
2. **Manual** via `workflow_dispatch`

### Processo de Atualização

1. **Geração de Estatísticas**: Usa a action `teoxoy/profile-readme-stats@v3` para gerar estatísticas do perfil usando o template em `docs/TEMPLATE.md`

2. **Injeção de Repositórios Recentes**: 
   - Busca os 5 repositórios mais recentes via API do GitHub
   - Injeta no README entre os marcadores `{{ REPOSITORIES_TEMPLATE_START }}` e `{{ REPOSITORIES_TEMPLATE_END }}`

3. **Injeção de Tecnologias por Uso**:
   - Calcula o uso de linguagens em todos os repositórios
   - Injeta as top 6 linguagens com percentuais no README entre os marcadores `{{ LANGUAGE_TEMPLATE_START }}` e `{{ LANGUAGE_TEMPLATE_END }}`

4. **Commit Automático**: Se houver mudanças, faz commit e push automaticamente

## ✏️ Como Editar o Template

Para modificar o conteúdo do README:

1. Edite o arquivo `docs/TEMPLATE.md`
2. As variáveis disponíveis são substituídas automaticamente pela action `profile-readme-stats`:
   - `{{ ACCOUNT_AGE }}` - Idade da conta em anos
   - `{{ REPOSITORIES }}` - Número de repositórios
   - `{{ COMMITS }}` - Número de commits
   - `{{ STARS }}` - Stars recebidas
   - `{{ ISSUES }}` - Issues
   - `{{ PULL_REQUESTS }}` - Pull Requests
   - `{{ CODE_REVIEWS }}` - Code Reviews

3. **Não edite o `README.md` diretamente** - ele é gerado automaticamente e será sobrescrito

## ⚙️ Configuração

### Variáveis de Ambiente no Workflow

- `GH_USER`: Nome de usuário do GitHub (atualmente: `MarceloRodrigues1853`)
- `GH_TOKEN`: Token de autenticação (usado automaticamente: `secrets.GITHUB_TOKEN`)

### Permissões

O workflow requer permissão `contents: write` para fazer commits automáticos.

## 🔧 Troubleshooting

### O workflow não está atualizando

1. Verifique se o workflow está habilitado em `.github/workflows/update-readme.yml`
2. Verifique os logs do workflow na aba "Actions" do GitHub
3. Certifique-se de que a branch principal está configurada como `main`

### Erro ao buscar repositórios

- Verifique se o token tem permissões adequadas
- Confirme que o nome de usuário está correto na variável `GH_USER`

### Template não está sendo encontrado

- Certifique-se de que o caminho do template está correto: `./docs/TEMPLATE.md`

## 📝 Notas Importantes

- O `README.md` na raiz é gerado automaticamente - **não edite manualmente**
- Arquivos temporários (`.tmp`) são criados durante a execução e limpos automaticamente
- O workflow usa `concurrency` para evitar execuções simultâneas
